from pydantic import BaseModel
from lambda_toolkit.db import DDB


@DDB.table('items', partition_key='id')
@DDB.secondary_index('name-index', partition_key='name')
class Item(BaseModel):
    id: str
    name: str
    description: str
    price: int
