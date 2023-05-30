from unittest import TestCase
from fastapi.testclient import TestClient
from src.api_v1 import app


class TestApi(TestCase):
    client = TestClient(app)

    def test_api(self):
        response = self.client.get('/v1/healthcheck')
        assert response.status_code == 200
