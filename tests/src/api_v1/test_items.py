from unittest import TestCase

from fastapi.testclient import TestClient
from moto import mock_dynamodb2

from toolkit import mock_db
from shared import models
from src.api_v1 import app


@mock_dynamodb2
class TestPostItems(TestCase):
    client = TestClient(app)

    def setUp(self):
        self.items = mock_db.mock_table(models.Item)

    def test_api(self):
        body = {
            "name": "sword",
            "description": "melee weapon",
            "price": 50,
        }
        response = self.client.post('/v1/items', json=body)
        assert response.status_code == 201

        data = response.json()

        item = models.DDB().get_item(models.Item, id=data['id'])
        assert item.name == "sword"
        assert item.description == "melee weapon"
        assert item.price == 50
