from pydantic import BaseModel, Field
from uuid import uuid4
from lambda_toolkit.db import DDB


ID = Field(default_factory=lambda: uuid4().hex)


@DDB.table('items', partition_key='id')
@DDB.secondary_index('name-index', partition_key='name')
class Item(BaseModel):
    id: str = ID
    name: str
    description: str = ''
    price: int = 0
    weight: int = 1


class AbilitySet(BaseModel):
    strenght: int = 0
    dexterity: int = 0
    constitution: int = 0
    intellect: int = 0
    wisdom: int = 0
    charisma: int = 0


@DDB.table('characters', partition_key='id')
@DDB.secondary_index('party-index', partition_key='party_name', sort_key='name')
class Character(BaseModel):
    id: str = ID
    name: str
    party_name: str
    attributes: AbilitySet
    inventory: list[Item]
    inventory_capacity: int = 10
