import os
import unittest
from unittest.mock import Mock, patch

from app.kite_service import KiteService


class KiteAuthenticationServiceTests(unittest.TestCase):
    @patch("app.kite_service.KiteConnect")
    @patch.dict(os.environ, {"KITE_API_KEY": "test-api-key", "KITE_API_SECRET": "test-api-secret", "KITE_ACCESS_TOKEN": ""})
    def test_create_session_stores_token_but_does_not_return_it(self, kite_connect):
        client = kite_connect.return_value
        client.generate_session.return_value = {
            "access_token": "sensitive-access-token",
            "user_id": "AB1234",
            "user_name": "Test User",
        }

        service = KiteService()
        result = service.create_session("single-use-request-token")

        client.generate_session.assert_called_once_with(
            "single-use-request-token", api_secret="test-api-secret"
        )
        client.set_access_token.assert_called_once_with("sensitive-access-token")
        self.assertTrue(service.authenticated)
        self.assertEqual(result, {"user_id": "AB1234", "user_name": "Test User"})
        self.assertNotIn("access_token", result)

    @patch("app.kite_service.KiteConnect")
    @patch.dict(os.environ, {"KITE_API_KEY": "test-api-key", "KITE_API_SECRET": "", "KITE_ACCESS_TOKEN": ""})
    def test_create_session_rejects_missing_api_secret(self, kite_connect):
        service = KiteService()
        with self.assertRaisesRegex(RuntimeError, "KITE_API_SECRET"):
            service.create_session("request-token")
        kite_connect.return_value.generate_session.assert_not_called()

    @patch("app.kite_service.KiteConnect")
    @patch.dict(os.environ, {"KITE_API_KEY": "test-api-key", "KITE_API_SECRET": "test-api-secret", "KITE_ACCESS_TOKEN": ""})
    def test_clear_session_invalidates_in_memory_session(self, kite_connect):
        service = KiteService()
        service._access_token = "existing-token"
        service._client.set_access_token.reset_mock()

        service.clear_session()

        self.assertFalse(service.authenticated)
        service._client.set_access_token.assert_called_once_with("")


if __name__ == "__main__":
    unittest.main()
