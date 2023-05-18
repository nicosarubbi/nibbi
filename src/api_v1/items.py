from fastapi import APIRouter, Header, status
from uuid import uuid4

from lambda_toolkit import api
from lambda_toolkit.db import DDB

from shared import models

from .serializers import ItemRequest, ItemSerializer


router = APIRouter()


@router.post('/items', status_code=status.HTTP_200_OK)
def handler(request: ItemRequest) -> ItemSerializer:
    ddb = models.DDB()

    item = models.Item(
        id=str(uuid4()),
        name=request.name,
        description=request.description,
        price=request.price,
    )
    DDB.put_item(item)
    
    return api.serialize(ItemSerializer, item)
