from decimal import Decimal
from pydantic import BaseModel

import boto3

from lambda_toolkit.db import IndexDescriptor, DDB


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


def mock_schema(model: type[BaseModel]):
    meta = DDB.meta(model)
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


def table_schema(model: type[BaseModel]):
    CDK_FIELD_TYPE = {
        'S': 'STRING',
        'N': 'NUMBER',
    }
    meta = DDB.meta(model)
    schema = dict(
        name=meta.name,
    )
    secondary_indexes = []
    for name, index in meta.indexes.items():
        index_schema = {}
        index_schema['partition_key'] = index.partition_key
        index_schema['partition_key_type'] = CDK_FIELD_TYPE[_field_type(model, index.partition_key)]
        if index.sort_key:
            index_schema['sort_key'] = index.sort_key
            index_schema['sort_key_type'] = CDK_FIELD_TYPE[_field_type(model, index.sort_key)]
        if name is None:
            schema.update(index_schema)
        else:
            index_schema['name'] = name
            secondary_indexes.append(index_schema)
    return schema, secondary_indexes


def mock_table(model):
    DDB.meta(model)._table = None
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    schema = mock_schema(model)
    return dynamodb.create_table(**schema)

