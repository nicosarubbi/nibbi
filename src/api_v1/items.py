from fastapi import APIRouter, status, HTTPException

from lambda_toolkit import api
from shared import models

from .serializers import ItemRequest, ItemPayload


router = APIRouter()


@router.post('/items', status_code=status.HTTP_201_CREATED)
def post_items(request: ItemRequest) -> ItemPayload:
    item = models.Item.create(
        request.name,
        request.description,
        request.price,
    )
    return api.serialize(ItemPayload, item)


@router.get('/items/{item_id}', status_code=status.HTTP_200_OK)
def retrieve_item(item_id: str) -> ItemPayload:
    item = models.Item.get_by_id(item_id)
    if item is None:
        raise HTTPException(404, 'not found')
    return api.serialize(ItemPayload, item)
