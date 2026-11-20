import unittest
from unittest.mock import Mock

from app.kite_service import KiteService


class KiteServiceTests(unittest.TestCase):
    def test_normalize_position_converts_numeric_values(self):
        position = KiteService._normalize_position({
            "tradingsymbol": "NIFTY26NOV25000CE", "exchange": "NFO",
            "quantity": -50, "average_price": "120.5", "last_price": "135",
            "realised": "0", "unrealised": "725", "pnl": "725",
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


    def test_day_margins_pnl_uses_booked_m2m_from_both_segments(self):
        service = KiteService()
        service._access_token = "test-token"
        service._client = Mock()
        service._client.margins.return_value = {
            "equity": {"utilised": {"m2m_realised": 1250.5, "m2m_unrealised": -100.0}},
            "commodity": {"utilised": {"m2m_realised": -250.0, "m2m_unrealised": 50.0}},
        }

        result = service.get_day_margins_pnl()

        self.assertEqual(result["realised"], 1000.5)
        self.assertEqual(result["unrealised"], -50.0)
        self.assertEqual(result["source"], "kite_margins")
        service._client.margins.assert_called_once_with()

    def test_day_margins_pnl_handles_missing_segments(self):
        service = KiteService()
        service._access_token = "test-token"
        service._client = Mock()
        service._client.margins.return_value = {
            "equity": {"utilised": {"m2m_realised": 75.25}},
        }

        result = service.get_day_margins_pnl()

        self.assertEqual(result["realised"], 75.25)
        self.assertEqual(result["unrealised"], 0.0)

    def test_daily_charges_aggregate_fills_by_order_and_sum_breakdown(self):
        service = KiteService()
        service._access_token = "test-token"
        service._client = Mock()
        service._client.trades.return_value = [
            {"order_id": "o1", "quantity": 2, "average_price": 100},
            {"order_id": "o1", "quantity": 3, "average_price": 110},
        ]
        service._client.orders.return_value = [{
            "order_id": "o1", "exchange": "NFO", "tradingsymbol": "NIFTY26NOV25000CE",
            "transaction_type": "BUY", "variety": "regular", "product": "MIS",
            "order_type": "LIMIT",
        }]
        service._client.get_virtual_contract_note.return_value = [{
            "charges": {
                "brokerage": 20, "transaction_tax": 1.5,
                "exchange_turnover_charge": 0.5, "sebi_turnover_charge": 0.01,
                "stamp_duty": 0.2, "gst": {"total": 3.6}, "total": 25.81,
            }
        }]

        result = service.get_day_charges()

        self.assertEqual(result["trade_count"], 2)
        self.assertEqual(result["order_count"], 1)
        self.assertEqual(result["total"], 25.81)
        request = service._client.get_virtual_contract_note.call_args.args[0]
        self.assertEqual(request[0]["quantity"], 5)
        self.assertEqual(request[0]["average_price"], 106.0)

    def test_daily_charges_returns_zero_when_no_trades(self):
        service = KiteService()
        service._access_token = "test-token"
        service._client = Mock()
        service._client.trades.return_value = []
        result = service.get_day_charges()
        self.assertEqual(result["total"], 0.0)
        self.assertEqual(result["trade_count"], 0)
        service._client.orders.assert_not_called()


if __name__ == "__main__":
    unittest.main()
