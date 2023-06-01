from cdk_toolkit.mock_db import ModelTestCase
from lambda_toolkit.db import DDB
from shared import models
from src.api_v1 import app
from fastapi.testclient import TestClient


class TestPostItems(ModelTestCase):
    client = TestClient(app)
    models = {
        models.Item: [],
    }

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


class TestGetItems(ModelTestCase):
    client = TestClient(app)

    models = {
        models.Item: [models.Item(name='sword', description='melee weapon', price=50)]
    }

    def test_api(self):
        sword = list(DDB().scan(models.Item))[-1]
        response = self.client.get(f'/v1/items/{sword.id}')
        assert response.status_code == 200

        data = response.json()
        assert data == {
            'id': sword.id,
            'name': 'sword',
            'description': 'melee weapon',
            'price': 50,
            'weight': 1,
        }

    def test_api_2(self):
        response = self.client.get(f'/v1/items/111')
        assert response.status_code == 404
