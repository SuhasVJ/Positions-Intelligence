import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from starlette.testclient import TestClient

from app import main


class AuthenticationRegressionTests(unittest.TestCase):
    def test_root_oauth_success_exchanges_token_and_redirects_to_dashboard(self):
        with patch.object(main.kite, "create_session") as create_session:
            response = TestClient(main.app).get(
                "/?action=login&type=login&status=success&request_token=regression-token",
                follow_redirects=False,
            )
        create_session.assert_called_once_with("regression-token")
        self.assertIsInstance(response, RedirectResponse)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/api/positions/intelligence")
        self.assertNotIn("request_token", response.headers["location"])

    def test_root_oauth_cancel_does_not_exchange_token(self):
        with patch.object(main.kite, "create_session") as create_session:
            response = TestClient(main.app).get(
                "/?action=login&type=login&status=cancel",
                follow_redirects=False,
            )
        create_session.assert_not_called()
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/?login=cancelled")

    def test_root_oauth_failure_does_not_expose_exception_or_token(self):
        with patch.object(main.kite, "create_session", side_effect=RuntimeError("bad credentials")) as create_session:
            response = TestClient(main.app).get(
                "/?action=login&type=login&status=success&request_token=bad-token",
                follow_redirects=False,
            )
        create_session.assert_called_once_with("bad-token")
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/?login=failed")
        self.assertNotIn("bad-token", response.text)

    def test_root_oauth_success_without_token_is_rejected(self):
        with patch.object(main.kite, "create_session") as create_session:
            response = TestClient(main.app).get(
                "/?action=login&type=login&status=success",
                follow_redirects=False,
            )
        create_session.assert_not_called()
        self.assertEqual(response.headers["location"], "/?login=failed")

    def test_auth_callback_alias_uses_same_oauth_flow(self):
        with patch.object(main.kite, "create_session") as create_session:
            response = TestClient(main.app).get(
                "/auth/callback?status=success&request_token=callback-token",
                follow_redirects=False,
            )
        create_session.assert_called_once_with("callback-token")
        self.assertEqual(response.headers["location"], "/api/positions/intelligence")

    def test_positions_page_requires_authenticated_session(self):
        with patch.object(type(main.kite), "authenticated", new_callable=property, create=True):
            with patch.object(main.kite, "authenticated", new_callable=unittest.mock.PropertyMock, create=True) as authenticated:
                authenticated.return_value = False
                response = TestClient(main.app).get(
                    "/api/positions/intelligence", follow_redirects=False
                )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/")

    def test_positions_api_returns_401_without_session(self):
        with patch.object(main.kite, "authenticated", new_callable=unittest.mock.PropertyMock, create=True) as authenticated:
            authenticated.return_value = False
            with self.assertRaises(HTTPException) as raised:
                import asyncio
                asyncio.run(main.today_positions())
        self.assertEqual(raised.exception.status_code, 401)

    def test_login_page_contains_button_and_login_script(self):
        from pathlib import Path
        html = Path("app/static/index.html").read_text(encoding="utf-8")
        script = Path("app/static/app.js").read_text(encoding="utf-8")
        self.assertIn('id="loginButton"', html)
        self.assertIn("initializeLoginPage", script)
        self.assertIn("if (!initializeLoginPage()) initializePositionsPage();", script)


if __name__ == "__main__":
    unittest.main()
