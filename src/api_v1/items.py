from fastapi import APIRouter, status, HTTPException

from lambda_toolkit import api
from shared import models

from .serializers import ItemRequest, ItemSerializer


router = APIRouter()


@router.post('/items', status_code=status.HTTP_201_CREATED)
def post_items(request: ItemRequest) -> ItemSerializer:
    item = models.Item.create(
        request.name,
        request.description,
        request.price,
    )
    return api.serialize(ItemSerializer, item)


@router.get('/items/{item_id}', status_code=status.HTTP_200_OK)
def retrieve_item(item_id: str) -> ItemSerializer:
    item = models.Item.get_by_id(item_id)
    if item is None:
        raise HTTPException(404, 'not found')
    return api.serialize(ItemSerializer, item)
