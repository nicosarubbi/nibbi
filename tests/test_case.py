from decimal import Decimal
from pydantic import BaseModel
from unittest import TestCase

import boto3
from moto import mock_dynamodb2

from shared.db import DDB


@mock_dynamodb2
class ModelTestCase(TestCase):
    models: dict[type[BaseModel], list[BaseModel]] = {}

    def setUp(self):
        [self.mock_table(model, *data) for model, data in self.models.items()]

    def tearDown(self) -> None:
        for model in self.models:
            DDB.meta(model).table.delete()

    @classmethod
    def mock_table(cls, model, *items):
        DDB._client = boto3.resource('dynamodb', region_name='us-east-1')
        schema = cls._mock_schema(model)
        DDB.meta(model)._table = DDB._client.create_table(**schema)
        DDB().batch_write_item(items)

    @classmethod
    def _mock_schema(cls, model: type[BaseModel]):
        meta = DDB.meta(model)
        schema = dict(
            TableName=f'mock_{meta.name}',
            BillingMode="PAY_PER_REQUEST",
        )
        attributes = set([])
        for name, index in meta.indexes.items():
            attributes.add(index.partition_key)
            if index.sort_key:
                attributes.add(index.sort_key)
            index_schema = [{'AttributeName': index.partition_key, 'KeyType': 'HASH'}]
            if index.sort_key:
                index_schema.append({'AttributeName': index.sort_key, 'KeyType': 'RANGE'})
            if name is None:
                schema['KeySchema'] = index_schema
            else:
                schema.setdefault('GlobalSecondaryIndexes', [])
                schema['GlobalSecondaryIndexes'].append(dict(
                    IndexName=name,
                    KeySchema=index_schema,
                    Projection={'ProjectionType': 'KEYS_ONLY'},
                ))
        schema['AttributeDefinitions'] = [
            {'AttributeName': name, 'AttributeType': cls._field_type(model, name)}
            for name in attributes
        ]
        return schema

    @staticmethod
    def _field_type(model: type[BaseModel], field_name):
        t = model.__fields__[field_name].type_
        if isinstance(t, type) and issubclass(t, str):
            return 'S'
        if isinstance(t, type) and any(issubclass(t, type_) for type_ in [int, float, Decimal]):
            return 'N'
        raise TypeError(f'DynamoDB Index field `{field_name}` should be either string or numeric')
