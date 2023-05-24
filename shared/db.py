import os
import boto3
from pydantic import BaseModel, PrivateAttr
from typing import Any
from boto3.dynamodb.conditions import Key


class IndexDescriptor:
    def __init__(self, partition_key: str, sort_key: str = None):
        self.partition_key = partition_key
        self.sort_key = sort_key

    def get_key(self, item: BaseModel):
        return { key: getattr(item, key) for key in [self.partition_key, self.sort_key] if key is not None }



class TableDescriptor(BaseModel):
    name: str = None
    model: type[BaseModel] = None
    indexes: dict = None
    _table: Any = PrivateAttr(None)

    def describe_table(self, name: str, model: BaseModel, partition_key: str, sort_key: str=None):
        self.name = name
        self.model = model
        if self.indexes is None:
            self.indexes = {}
        self.indexes[None] = IndexDescriptor(partition_key, sort_key)

    def add_index(self, index_name: str, partition_key: str, sort_key: str=None):
        if self.indexes is None:
            self.indexes = {}
        self.indexes[index_name] = IndexDescriptor(partition_key, sort_key)

    @property
    def table(self):
        if self._table is None:
            self._table = DDB().client.Table(os.environ.get(f'TABLE_{self.name}', self.name))
        return self._table


class DDB:
    _client = None

    def __init__(self):
        if DDB._client is None:
            DDB._client = boto3.resource("dynamodb")
        self.client = DDB._client

    @classmethod
    def table(cls, table_name, partition_key, sort_key=None):
        def decorator(model: type[BaseModel]) -> type[BaseModel]:
            if not hasattr(model, '_META'):
                model._META = TableDescriptor()
            model._META.describe_table(table_name, model, partition_key, sort_key)
            return model
        return decorator
    
    @classmethod
    def secondary_index(cls, index_name, partition_key, sort_key=None):
        def decorator(model: type[BaseModel]) -> type[BaseModel]:
            if not hasattr(model, '_META'):
                model._META = TableDescriptor()
            model._META.add_index(index_name, partition_key, sort_key)
            return model
        return decorator

    @staticmethod
    def validate_model(model):
        if not isinstance(model, type):
            model = type(model)
        assert issubclass(model, BaseModel), f'Invalid Type: {model}'
        assert hasattr(model, '_META'), 'Missing Table Description'
        assert model._META.name is not None, 'Incomplete Table Description'

    def put_item(self, item: BaseModel, **kwargs):
        self.validate_model(item)
        item._META.table.put_item(Item=item.dict(), **kwargs)
    
    def get_item(self, model: type[BaseModel], **key) -> BaseModel:
        self.validate_model(model)
        raw = model._META.table.get_item(Key=key)
        return model(**raw['Item']) if 'Item' in raw else None

    def batch_get_item(self, model: type[BaseModel], keys: list[dict]) -> list[BaseModel]:
        self.validate_model(model)
        table_name = model._META.table_name

        while keys:
            response = self.client.batch_get_item(
                RequestItems={table_name: {'Keys': keys}}
            )
            raw_items = response.get('Response', {}).get(table_name, [])
            for item in raw_items:
                yield model(**item)
            keys = response.get('UnprocessedKeys', {}).get('Keys', [])

    def update_item(self, item: BaseModel, values: dict, **kwargs) -> BaseModel:
        self.validate_model(item)
        index = item._META.indexes[None]
        key = index.get_key(item)
        query_expressions = []
        query_values = {}
        query_names = {}
        for field, value in values.items():
            if field.endswith("+"):
                field = field.strip("+")
                query_expressions.append(f'#{field} = #{field} + :{field}')
            else:
                query_expressions.append(f'#{field} = :{field}')
            query_values[f':{field}'] = value
            query_names[f'#{field}'] = field
        expresion = 'SET ' + ', '.join(query_expressions)
        response = item._META.table.update_item(
            Key=key,
            UpdateExpression=expresion,
            ExpressionAttributeValues=query_values,
            ExpressionAttributeNames=query_names,
            ReturnValues='ALL_NEW',
            **kwargs,
        )
        for attr, value in response['Attributes'].items():
            setattr(item, attr, value)
        return item

    def simple_query(self, model: type[BaseModel], index=None, **conditions) -> list[BaseModel]:
        """
        DDB().simple_query(
            Product,
            category='fruit',
            index='category-index',
        )
        """
        self.validate_model(model)
        args = None
        for key, value in conditions.items():
            if args:
                args = args & Key(key).eq(value)
            else:
                args = Key(key).eq(value)
        return self.query(model, args, index=index)

    def query(self, model: type[BaseModel], condition=None,
              index=None, start=None, limit=None, pagination=100, **kwargs) -> list[BaseModel]:
        """
        DDB().query(
            Product,
            Key('category').eq('fruit') & Key('price').lt(50),
            index='category-index',
        )
        """
        self.validate_model(model)
        assert index in model._META.indexes
        args = dict(
            KeyConditionExpression=condition,
            Limit=min(limit, pagination) if limit else pagination,
        )
        if index:
            args['IndexName'] = index
        if start:
            args['ExclusiveStartKey'] = start
        args.update(kwargs)

        result = model._META.table.query(**args)
        raw_items = result.get('Items') or result.get('Item') or []
        count = 0
        while True:
            for raw in raw_items:
                yield model(**raw)
                count += 1
                if limit and count >= limit:
                    break

            if limit and count >= limit:
                break
            last_key = result.get('LastEvaluatedKey', None)
            if not last_key:
                break
            args['ExclusiveStartKey'] = last_key
            result = model._META.table.query(**args)
            raw_items = result.get('Items') or result.get('Item') or []

    def scan(self, model: type[BaseModel], condition=None, limit=None, start=None, **kwargs) -> list[BaseModel]:
        self.validate_model(model)
        args = {}
        if condition:
            args['FilterExpression'] = condition
        if start:
            args['ExclusiveStartKey'] = start
        
        result = model._META.table.scan(**args)
        raw_items = result.get('Items') or result.get('Item') or []
        count = 0
        while True:
            for raw in raw_items:
                yield model(**raw)
                count += 1
                if limit and count >= limit:
                    break

            if limit and count >= limit:
                break
            last_key = result.get('LastEvaluatedKey', None)
            if not last_key:
                break
            args['ExclusiveStartKey'] = last_key
            result = model._META.table.query(**args)
            raw_items = result.get('Items') or result.get('Item') or []
