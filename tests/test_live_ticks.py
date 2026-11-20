import unittest
from unittest.mock import patch

from app import main


class LiveTickRepricingTests(unittest.TestCase):
    def setUp(self):
        self.original_snapshot = main.latest_snapshot
        self.original_loop = main.event_loop
        main.event_loop = None
        main.latest_snapshot = {
            "as_of": "2026-11-20T10:00:00+05:30",
            "day": [{
                "instrument_token": 123, "quantity": 10, "average_price": 99.0,
                "last_price": 100.0, "realised": 5.0, "unrealised": 20.0, "pnl": 25.0,
            }],
            "net": [{
                "instrument_token": 123, "quantity": 10, "average_price": 99.0,
                "last_price": 100.0, "realised": 5.0, "unrealised": 20.0, "pnl": 25.0,
            }, {
                "instrument_token": 456, "quantity": -5, "average_price": 210.0,
                "last_price": 200.0, "realised": -2.0, "unrealised": 30.0, "pnl": 28.0,
            }],
        }

    def tearDown(self):
        main.latest_snapshot = self.original_snapshot
        main.event_loop = self.original_loop

    def test_tick_updates_ltp_and_unrealised_pnl_using_quantity(self):
        main.on_ticker_ticks(None, [{"instrument_token": 123, "last_price": 102.0}])
        position = main.latest_snapshot["net"][0]
        self.assertEqual(position["last_price"], 102.0)
        self.assertEqual(position["unrealised"], 40.0)
        self.assertEqual(position["pnl"], 45.0)
        self.assertEqual(position["position_value_basis"], 990.0)
        self.assertAlmostEqual(position["pnl_multiple"], 45.0 / 990.0, places=4)
        self.assertAlmostEqual(position["pnl_progress_percent"], (45.0 / 990.0) / 2 * 100, places=2)
        self.assertEqual(position["pnl_progress_direction"], "PROFIT")
        self.assertEqual(main.latest_snapshot["net_summary"]["pnl"], 73.0)

    def test_short_position_pnl_moves_opposite_to_ltp(self):
        main.on_ticker_ticks(None, [{"instrument_token": 456, "last_price": 202.0}])
        position = main.latest_snapshot["net"][1]
        self.assertEqual(position["last_price"], 202.0)
        self.assertEqual(position["unrealised"], 20.0)
        self.assertEqual(position["pnl"], 18.0)

    def test_unrelated_instrument_tick_does_not_mutate_positions(self):
        before = main.latest_snapshot["net"][0]["pnl"]
        main.on_ticker_ticks(None, [{"instrument_token": 999, "last_price": 55.0}])
        self.assertEqual(main.latest_snapshot["net"][0]["pnl"], before)

    def test_zero_quantity_position_keeps_realised_pnl_on_tick(self):
        main.latest_snapshot["net"].append({
            "instrument_token": 789, "quantity": 0, "average_price": 10.0,
            "last_price": 11.0, "realised": 100.0, "unrealised": 0.0, "pnl": 100.0,
        })
        main.on_ticker_ticks(None, [{"instrument_token": 789, "last_price": 12.0}])
        position = main.latest_snapshot["net"][-1]
        self.assertEqual(position["unrealised"], 0.0)
        self.assertEqual(position["pnl"], 100.0)


if __name__ == "__main__":
    unittest.main()
