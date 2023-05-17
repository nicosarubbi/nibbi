from shared import models
from uuid import uuid4


def handler(event, context):
    print("event: ", event)
    print("context: ", context)
    item = models.Item(
        id=uuid4(),
        name='Apple',
        description='Lorem Ipsum',
        price=1,
    )
    response = models.items_table.put_item(item.dict())
    return response
