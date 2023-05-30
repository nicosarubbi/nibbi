from pydantic import BaseModel, constr, conint


# requests

class ItemPayload(BaseModel):
    name: constr(min_length=1, max_length=50)
    description: constr(min_length=0, max_length=255)
    price: conint(ge=0, le=1_000_000)


# responses

class ItemResponse(BaseModel):
    id: str
    name: str
    description: str
    price: int
