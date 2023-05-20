from decimal import Decimal

import boto3
from pydantic import BaseModel

from lambda_toolkit.db import TableDescriptor, IndexDescriptor
from src.api_v1 import app


def _index_schema(index: IndexDescriptor) -> list[dict]:
    result = [
        {
            'AttributeName': index.partition_key,
            'KeyType': 'HASH',
        }
    ]
    if index.sort_key:
        result.append({
            'AttributeName': index.sort_key,
            'KeyType': 'RANGE',
        })
    return result


def _field_type(model: type[BaseModel], field_name):
    field = model.__fields__[field_name]
    if isinstance(field.type_, type) and issubclass(field.type_, str):
        return 'S'
    if isinstance(field.type_, type) and any(issubclass(field.type_, type_) for type_ in [int, float, Decimal]):
        return 'N'
    raise TypeError(f'DynamoDB Index field `{field_name}` should be either string or numeric')


def table_schema(model: type[BaseModel]):
    meta: TableDescriptor = model._Meta
    schema = dict(
        TableName=meta.name,
    )
    attributes = set([])
    for name, index in meta.indexes.items():
        attributes.add(index.partition_key)
        if index.sort_key:
            attributes.add(index.sort_key)
        if name is None:
            schema['KeySchema'] = _index_schema(index)
        else:
            schema.setdefault('GlobalSecondaryIndexes', [])
            schema['GlobalSecondaryIndexes'].append(dict(
                IndexName=name,
                KeySchema=_index_schema(index),
                Projection= {'ProjectionType': 'ALL'},
                ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1},
            ))
    schema['AttributeDefinitions'] = [
        {'AttributeName': name, 'AttributeType': _field_type(model, name)}
        for name in attributes
    ]
    return schema


def mock_table(model):
    model._Meta._table = None
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    schema = table_schema(model)
    return dynamodb.create_table(**schema)

