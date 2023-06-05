from fastapi import APIRouter, status, HTTPException
from pydantic import BaseModel, constr, conint

from shared.api import serialize
from shared.models import Item, DDB


class ItemPayload(BaseModel):
    name: constr(min_length=1, max_length=50)
    description: constr(min_length=0, max_length=255)
    price: conint(ge=0, le=1_000_000)


router = APIRouter()


@router.post('/items', status_code=status.HTTP_201_CREATED)
def post_items(request: ItemPayload) -> Item:
    item = Item(**request.dict())
    DDB().put_item(item)
    return serialize(Item, item)


@router.get('/items/{item_id}', status_code=status.HTTP_200_OK)
def retrieve_item(item_id: str) -> Item:
    item = DDB().get_item(Item, id=item_id)
    if item is None:
        raise HTTPException(404, 'not found')
    return serialize(Item, item)
