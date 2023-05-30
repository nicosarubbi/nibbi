import os
import boto3
from pydantic import BaseModel, PrivateAttr
from typing import Any, Iterable, Callable, TypeVar
from boto3.dynamodb.conditions import Key, Attr
from typing import TypeVar


Model = TypeVar("Model", bound="BaseModel")


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

    @staticmethod
    def meta(model: type[BaseModel]) -> TableDescriptor:
        if not isinstance(model, type):
            model = type(model)
        assert issubclass(model, BaseModel), f'Invalid Type: {model}'
        assert hasattr(model, '_META'), 'Missing Table Description'
        assert model._META.name is not None, 'Incomplete Table Description'
        return model._META

    @classmethod
    def table(cls, table_name, partition_key, sort_key=None) -> Callable:
        def decorator(model: type[Model]) -> type[Model]:
            if not hasattr(model, '_META'):
                model._META = TableDescriptor()
            model._META.describe_table(table_name, model, partition_key, sort_key)
            return model
        return decorator
    
    @classmethod
    def secondary_index(cls, index_name, partition_key, sort_key=None) -> Callable:
        def decorator(model: type[Model]) -> type[Model]:
            if not hasattr(model, '_META'):
                model._META = TableDescriptor()
            model._META.add_index(index_name, partition_key, sort_key)
            return model
        return decorator

    def put_item(self, item: Model, **kwargs):
        self.meta(item).table.put_item(Item=item.dict(), **kwargs)
    
    def get_item(self, model: type[Model], **key) -> Model:
        raw = self.meta(model).table.get_item(Key=key)
        return model(**raw['Item']) if 'Item' in raw else None
    
    def delete_item(self, item: Model):
        index = self.meta(item).indexes[None]
        key = index.get_key(item)
        self.meta(item).table.delete_item(Key=key)

    def batch_get_item(self, model: type[Model], keys: list[dict]) -> list[Model]:
        table_name = self.meta(model).table_name

        while keys:
            response = self.client.batch_get_item(
                RequestItems={table_name: {'Keys': keys}}
            )
            raw_items = response.get('Response', {}).get(table_name, [])
            for item in raw_items:
                yield model(**item)
            keys = response.get('UnprocessedKeys', {}).get('Keys', [])

    def update_item(self, item: Model, values: dict, **kwargs) -> Model:
        index = self.meta(item).indexes[None]
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
        response = self.meta(item).table.update_item(
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

    def simple_query(self, model: type[Model], index_name=None, **conditions) -> Iterable[Model]:
        """ DDB().simple_query(Product, 'category-index', category='fruit')
        """
        args = None
        for key, value in conditions.items():
            if args:
                args = args & Key(key).eq(value)
            else:
                args = Key(key).eq(value)
        return self.query(model, args, index_name=index_name)

    def query(self, model: type[Model], key_expression, *,
              index_name=None,  # IndexName
              filter_expression=None,  # FilterConditionExpression
              after=None,  # ExclusiveStartKey
              backward=False,  # not ScanIndexForward
              **kwargs) -> Iterable[Model]:
        """
        DDB().query(
            Product,
            Key('category').eq('fruit') & Key('price').lt(50),
            index='category-index',
        )
        """
        assert index_name in self.meta(model).indexes
        args = {'KeyConditionExpression': key_expression}
        if index_name:
            args['IndexName'] = index_name
        if filter_expression:
            args['FilterExpression'] = index_name
        if after:
            args['ExclusiveStartKey'] = after
        if backward:
            args['ScanIndexForward'] = False
        args.update(kwargs)

        return self.paginate(model, self.meta(model).table.query, **args)

    def scan(self, model: type[Model], filter_expression, *,
             after=None,  # ExclusiveStartKey
             backward=False,  # not ScanIndexForward
             **kwargs) -> Iterable[Model]:
        self.validate_model(model)

        args = {"FilterExpression": filter_expression}
        if after:
            args['ExclusiveStartKey'] = after
        if backward:
            args['ScanIndexForward'] = False
        args.update(kwargs)
        return self.paginate(model, self.meta(model).table.scan, **args)

    @staticmethod
    def paginate(model: type[Model], function: Callable, **arguments) -> Iterable[Model]:
        while True:
            result = function(**arguments)
            raw_items = result.get('Items', [])
            last_key = result.get('LastEvaluatedKey', None)
            for raw in raw_items:
                yield model(**raw)
            if not last_key:
                break
            arguments['ExclusiveStartKey'] = last_key
