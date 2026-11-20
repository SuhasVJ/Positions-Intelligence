import unittest
from unittest.mock import PropertyMock, patch

from fastapi import HTTPException

from app import main


class PositionIntelligenceApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_only_open_net_positions_and_classification_counts(self):
        snapshot = {
            "as_of": "2026-11-20T10:00:00+05:30",
            "net": [
                {"tradingsymbol": "NIFTYCE", "quantity": 50,
                 "asset_type": "INDEX_OPTION", "classification_status": "CLASSIFIED"},
                {"tradingsymbol": "RELIANCE", "quantity": 0,
                 "asset_type": "EQUITY", "classification_status": "CLASSIFIED"},
                {"tradingsymbol": "UNKNOWN", "quantity": -1,
                 "asset_type": "UNKNOWN", "classification_status": "UNKNOWN"},
            ],
        }
        with patch.object(type(main.kite), "authenticated",
                          new_callable=PropertyMock, return_value=True):
            with patch.object(main, "read_snapshot", return_value=snapshot):
                result = await main.intelligence_positions()

        self.assertEqual(result["position_count"], 2)
        self.assertEqual(result["classified_count"], 1)
        self.assertEqual(result["unknown_count"], 1)
        self.assertEqual(result["scoring_status"], "NOT_EVALUATED")
        self.assertEqual([p["tradingsymbol"] for p in result["positions"]],
                         ["NIFTYCE", "UNKNOWN"])

    async def test_requires_kite_authentication(self):
        with patch.object(type(main.kite), "authenticated",
                          new_callable=PropertyMock, return_value=False):
            with self.assertRaises(HTTPException) as raised:
                await main.intelligence_positions()
        self.assertEqual(raised.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
