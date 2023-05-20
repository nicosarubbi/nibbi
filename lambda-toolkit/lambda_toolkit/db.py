import os
import boto3
from pydantic import BaseModel, PrivateAttr
from typing import Any


class IndexDescriptor:
    def __init__(self, partition_key: str, sort_key: str = None):
        self.partition_key = partition_key
        self.sort_key = sort_key



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
            if not hasattr(model, '_Meta'):
                model._Meta = TableDescriptor()
            model._Meta.describe_table(table_name, model, partition_key, sort_key)
            return model
        return decorator
    
    @classmethod
    def secondary_index(cls, index_name, partition_key, sort_key=None):
        def decorator(model: type[BaseModel]) -> type[BaseModel]:
            if not hasattr(model, '_Meta'):
                model._META = TableDescriptor()
            model._META.add_index(index_name, partition_key, sort_key)
            return model
        return decorator

    @staticmethod
    def _validate_model(model):
        if not isinstance(model, type):
            model = type(model)
        assert issubclass(model, BaseModel), f'Invalid Type: {model}'
        assert hasattr(model, '_Meta'), 'Missing Table Description'
        assert model._Meta.name is not None, 'Incomplete Table Description'

    def put_item(self, item: BaseModel, **kwargs):
        self._validate_model(item)
        item._Meta.table.put_item(Item=item.dict(), **kwargs)
    
    def get_item(self, model: type[BaseModel], **key) -> BaseModel:
        self._validate_model(model)
        raw = model._Meta.table.get_item(Key=key)
        return model(**raw['Item']) if 'Item' in raw else None
