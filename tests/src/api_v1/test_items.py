from fastapi.testclient import TestClient
from shared import models
from shared.db import DDB
from src.api import app
from tests.test_utils import ModelTestCase, Like, Any
from parameterized import parameterized


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
        response = self.client.post('/api/v1/items', json=body)
        assert response.status_code == 201

        data = response.json()
        assert data == Like({
            'id': data['id'],
            'name': 'sword',
            'description': 'melee weapon',
            'price': 50,
            'weight': 1,
        })

        item = DDB().get_item(models.Item, id=data['id'])
        assert item.name == "sword"
        assert item.description == "melee weapon"
        assert item.price == 50

    @parameterized.expand([
            ("long name", {"name": "x" * 51, "description": "melee weapon", "price": 50}),
            ("long description", {"name": "sword", "description": "x" * 256, "price": 50}),
            ("negative price", {"name": "sword", "description": "melee weapon", "price": -1}),
            ("price too high", {"name": "sword", "description": "melee weapon", "price": 1_000_001}),
            ("price not numeric", {"name": "sword", "description": "melee weapon", "price": 'fifty'}),
    ])
    def test_error(self, _, body):
        response = self.client.post('/api/v1/items', json=body)
        assert response.status_code == 422
        assert response.json() == {"detail": [Like(msg=Any(str))]}


class TestGetItems(ModelTestCase):
    client = TestClient(app)

    models = {
        models.Item: [models.Item(name='sword', description='melee weapon', price=50)]
    }

    def test_api(self):
        sword = list(DDB().scan(models.Item))[-1]
        response = self.client.get(f'/api/v1/items/{sword.id}')
        assert response.status_code == 200

        data = response.json()
        assert data == Like({
            'id': sword.id,
            'name': 'sword',
            'description': 'melee weapon',
            'price': 50,
            'weight': 1,
        })

    def test_api_2(self):
        response = self.client.get(f'/api/v1/items/111')
        assert response.status_code == 404
        assert response.json() == {"detail": Any(str)}
