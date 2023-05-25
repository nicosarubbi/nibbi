from unittest import TestCase
from fastapi.testclient import TestClient
from cdk_toolkit import mock_db
from lambda_toolkit.db import DDB

from shared import models
from src.api_v1 import app


class TestPostItems(TestCase):
    client = TestClient(app)

    @classmethod
    def setUpClass(cls):
        cls.items = mock_db.mock_table(models.Item)

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


class TestPostItems(TestCase):
    client = TestClient(app)

    @classmethod
    def setUpClass(cls):
        cls.items = mock_db.mock_table(models.Item)
        cls.sword = models.Item.create(name='sword', description='melee weapon', price=50)

    def test_api(self):
        response = self.client.get(f'/v1/items/{self.sword.id}')
        assert response.status_code == 200

        data = response.json()
        assert data == {
            'id': self.sword.id,
            'name': 'sword',
            'description': 'melee weapon',
            'price': 50,
        }
