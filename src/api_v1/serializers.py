from pydantic import BaseModel, constr, conint


# constr

NAME_CONSTR = constr(min_length=1, max_length=50)
DESCRIPTION_CONSTR = constr(min_length=0, max_length=100)
PRICE_CONINT = conint(ge=0, le=1_000_000)


# requests

class ItemRequest(BaseModel):
    name: NAME_CONSTR
    description: DESCRIPTION_CONSTR
    price: PRICE_CONINT


# responses

class ItemSerializer(ItemRequest):
    id: str
    name: str
    description: str
    price: int
