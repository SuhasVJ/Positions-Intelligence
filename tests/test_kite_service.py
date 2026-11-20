import unittest
from unittest.mock import Mock

from app.kite_service import KiteService


class KiteServiceTests(unittest.TestCase):
    def test_normalize_position_converts_numeric_values(self):
        position = KiteService._normalize_position({
            "tradingsymbol": "NIFTY26NOV25000CE",
            "exchange": "NFO",
            "quantity": -50,
            "average_price": "120.5",
            "last_price": "135",
            "realised": "0",
            "unrealised": "725",
            "pnl": "725",
        })
        self.assertEqual(position["tradingsymbol"], "NIFTY26NOV25000CE")
        self.assertEqual(position["quantity"], -50)
        self.assertEqual(position["average_price"], 120.5)
        self.assertEqual(position["last_price"], 135.0)
        self.assertEqual(position["pnl"], 725.0)

    def test_summary_aggregates_pnl_and_open_positions(self):
        positions = [
            {"quantity": 10, "realised": 100.0, "unrealised": 25.0, "pnl": 125.0},
            {"quantity": 0, "realised": -20.0, "unrealised": 0.0, "pnl": -20.0},
            {"quantity": -5, "realised": 0.0, "unrealised": -15.0, "pnl": -15.0},
        ]
        summary = KiteService.summarize(positions)
        self.assertEqual(summary["position_count"], 3)
        self.assertEqual(summary["open_positions"], 2)
        self.assertEqual(summary["realised"], 80.0)
        self.assertEqual(summary["unrealised"], 10.0)
        self.assertEqual(summary["pnl"], 90.0)

    def test_get_positions_returns_day_and_net_collections(self):
        service = KiteService()
        service._access_token = "test-token"
        service._client = Mock()
        service._client.positions.return_value = {
            "day": [{"tradingsymbol": "TODAY", "quantity": 1, "pnl": 10}],
            "net": [{"tradingsymbol": "CARRY", "quantity": 2, "pnl": 20}],
        }

        positions = service.get_positions()

        self.assertEqual([p["tradingsymbol"] for p in positions["day"]], ["TODAY"])
        self.assertEqual([p["tradingsymbol"] for p in positions["net"]], ["CARRY"])
        service._client.positions.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
