from unittest import TestCase
from fastapi.testclient import TestClient
from src.api import app


class TestApi(TestCase):
    client = TestClient(app)

    def test_api(self):
        response = self.client.get('/api/healthcheck')
        assert response.status_code == 200
