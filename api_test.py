import unittest
import requests
import os


class TestAvailabilityEndpoint(unittest.TestCase):
    def setUp(self):
        self.base_url = os.getenv('API_BASE_URL', 'http://localhost:8000')

        self.availability_endpoint = f"{self.base_url}/availability"
        self.booking_endpoint = f"{self.base_url}/book"

    def test_availability_endpoint_returns_success(self):
        params = {
            'slug': 'luis-pacheco',
            'timezone': 'America/Mexico_City',
        }
        response = requests.get(self.availability_endpoint, params=params)

        self.assertEqual(response.status_code, 200)
        availability = response.json()
        self.assertIsNotNone(availability)

    def test_booking_endpoint_returns_success(self):
        data = {
            "slug": "luis-pacheco",
            "slot": "Wednesday 2025-05-27 11:30",
            "duration": "30min",
            "timezone": "America/Mexico_City",
            "firstName": "Robert",
            "lastName": "Todea",
            "country": "Mexico",
            "company": "Mobile Insight",
            "email": "rtodea@mobileinsight.com"
        }
        response = requests.post(self.booking_endpoint, json=data)

        self.assertEqual(response.status_code, 200)
        booking = response.json()
        self.assertIsNotNone(booking)


if __name__ == '__main__':
    unittest.main()
