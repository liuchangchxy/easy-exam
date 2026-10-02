import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app


class LocalizedErrorContractTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.client = TestClient(create_app(str(Path(self.temp_dir.name) / 'test.db')))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_legacy_detail_and_localized_auth_code(self):
        payload = {'username': 'missing', 'password': 'password-123456'}
        legacy = self.client.post('/api/v1/auth/login', json=payload)
        self.assertEqual(legacy.status_code, 401)
        self.assertEqual(legacy.json()['detail'], 'invalid username or password')

        localized = self.client.post('/api/v1/auth/login', json=payload, headers={'Accept-Language': 'en-US'})
        self.assertEqual(localized.status_code, 401)
        self.assertEqual(localized.json()['error_code'], 'AUTH_INVALID_CREDENTIALS')
        self.assertEqual(localized.json()['params'], {})

    def test_validation_error_has_safe_structured_code(self):
        localized = self.client.post('/api/v1/auth/login', json={'username': ''}, headers={'Accept-Language': 'en-US'})
        self.assertEqual(localized.status_code, 422)
        self.assertEqual(localized.json()['error_code'], 'HTTP_422')
        self.assertEqual(localized.json()['params'], {})


if __name__ == '__main__':
    unittest.main()
