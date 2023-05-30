from pydantic import BaseModel, Self
from lambda_toolkit.db import DDB
from uuid import uuid4


@DDB.table('items', partition_key='id')
@DDB.secondary_index('name-index', partition_key='name')
class Item(BaseModel):
    id: str
    name: str
    description: str
    price: int

    @classmethod
    def create(cls, name: str, description: str, price: int) -> Self:
        item = cls(
            id=uuid4().hex,
            name=name,
            description=description,
            price=price,
        )
        DDB().put_item(item)
        return item

    @classmethod
    def get_by_id(cls, item_id: str) -> Self:
        return DDB().get_item(cls, id=item_id)
