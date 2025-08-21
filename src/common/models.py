from os import getenv
from pydantic import BaseModel, Field
from uuid import uuid4

from common.db import DynamoClient

# dynamodb client
TABLE_PREFIX = getenv('TABLE_PREFIX', 'app-local-')
ddb = DynamoClient(
    table_prefix=TABLE_PREFIX,
)

# fields
AUTO_ID = Field(default_factory=lambda: uuid4().hex)


@ddb.table('products', partition_key='id')
@ddb.secondary_index('gsi_name', partition_key='name')
class Product(BaseModel):
    id: str = AUTO_ID
    name: str
    description: str | None = None
    price: float
