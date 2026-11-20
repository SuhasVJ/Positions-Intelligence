import unittest
from pathlib import Path
from unittest.mock import PropertyMock, patch

from fastapi import HTTPException
from fastapi.responses import RedirectResponse

from app import main


class AuthenticationRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_root_oauth_success_exchanges_token_and_redirects_to_dashboard(self):
        with patch.object(main.kite, "create_session") as create_session:
            with patch.object(main, "make_snapshot", return_value={"day": [], "net": []}):
                with patch.object(main, "start_ticker"):
                    response = await main.login_page(
                        request_token="regression-token", status="success", action="login"
                    )
        create_session.assert_called_once_with("regression-token")
        self.assertIsInstance(response, RedirectResponse)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/api/positions/intelligence")
        self.assertNotIn("request_token", response.headers["location"])

    async def test_root_oauth_cancel_does_not_exchange_token(self):
        with patch.object(main.kite, "create_session") as create_session:
            response = await main.login_page(
                request_token=None, status="cancel", action="login"
            )
        create_session.assert_not_called()
        self.assertEqual(response.headers["location"], "/?login=cancelled")

    async def test_root_oauth_failure_does_not_expose_exception_or_token(self):
        with patch.object(main.kite, "create_session", side_effect=RuntimeError("bad credentials")) as create_session:
            response = await main.login_page(
                request_token="bad-token", status="success", action="login"
            )
        create_session.assert_called_once_with("bad-token")
        self.assertEqual(response.headers["location"], "/?login=failed")
        self.assertNotIn("bad-token", response.headers["location"])

    async def test_root_oauth_success_without_token_is_rejected(self):
        with patch.object(main.kite, "create_session") as create_session:
            response = await main.login_page(
                request_token=None, status="success", action="login"
            )
        create_session.assert_not_called()
        self.assertEqual(response.headers["location"], "/?login=failed")

    async def test_auth_callback_alias_uses_same_oauth_flow(self):
        with patch.object(main.kite, "create_session") as create_session:
            with patch.object(main, "make_snapshot", return_value={"day": [], "net": []}):
                with patch.object(main, "start_ticker"):
                    response = await main.auth_callback(
                        request_token="callback-token", status="success"
                    )
        create_session.assert_called_once_with("callback-token")
        self.assertEqual(response.headers["location"], "/api/positions/intelligence")

    async def test_positions_page_requires_authenticated_session(self):
        with patch.object(type(main.kite), "authenticated", new_callable=PropertyMock, return_value=False):
            response = await main.positions_intelligence()
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/")

    async def test_positions_api_returns_401_without_session(self):
        with patch.object(type(main.kite), "authenticated", new_callable=PropertyMock, return_value=False):
            with self.assertRaises(HTTPException) as raised:
                await main.today_positions()
        self.assertEqual(raised.exception.status_code, 401)

    def test_login_page_contains_button_and_page_specific_script_initialization(self):
        html = Path("app/static/index.html").read_text(encoding="utf-8")
        script = Path("app/static/app.js").read_text(encoding="utf-8")
        self.assertIn('id="loginButton"', html)
        self.assertIn("initializeLoginPage", script)
        self.assertIn("if (!initializeLoginPage()) initializePositionsPage();", script)


if __name__ == "__main__":
    unittest.main()
