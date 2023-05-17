import os
from pydantic import BaseModel
import boto3


class DDB():
    _client = None

    def __init__(self):
        items_table_name = os.environ.get('TABLE_items', 'test-items')
        self.client = self._client or boto3.resource("dynamodb")
        self.items = self.client.Table(items_table_name)


class Item(BaseModel):
    id: str
    name: str
    description: str
    price: int
