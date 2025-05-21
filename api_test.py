import unittest
import requests
import os


class TestAvailabilityEndpoint(unittest.TestCase):
    def setUp(self):
        self.base_url = os.getenv('API_BASE_URL', 'http://localhost:8000')
        self.availability_endpoint = f"{self.base_url}/availability"

    def test_availability_endpoint_returns_success(self):
        params = {
            'slug': 'luis-pacheco',
            'timezone': 'America/Mexico_City',
        }
        response = requests.get(self.availability_endpoint, params=params)

        self.assertEqual(response.status_code, 200)
        availability = response.json()
        self.assertIsNotNone(availability)


if __name__ == '__main__':
    unittest.main()
