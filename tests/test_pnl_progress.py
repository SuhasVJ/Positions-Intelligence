import unittest

from app.pnl_progress import add_pnl_progress


class PositionPnlProgressTests(unittest.TestCase):
    def test_profit_progress_uses_unrealised_pnl(self):
        position = {"quantity": 10, "average_price": 100, "pnl": 1500, "realised": 500, "unrealised": 1000}
        result = add_pnl_progress(position)
        self.assertEqual(result["position_value_basis"], 1000)
        self.assertEqual(result["pnl_progress_amount"], 1000)
        self.assertEqual(result["pnl_multiple"], 1.0)
        self.assertEqual(result["pnl_progress_percent"], 50.0)
        self.assertEqual(result["pnl_progress_direction"], "PROFIT")
        self.assertEqual(result["pnl_progress_basis"], "OPEN_UNREALISED_PNL")
        self.assertEqual(result["pnl"], 1500)

    def test_large_realised_loss_does_not_distort_remaining_open_position(self):
        position = {
            "quantity": 7, "average_price": 1.0,
            "pnl": -4375.70, "realised": -4375.28, "unrealised": -0.42,
        }
        result = add_pnl_progress(position)
        self.assertEqual(result["pnl_multiple"], -0.06)
        self.assertEqual(result["pnl_progress_percent"], 6.0)
        self.assertEqual(result["pnl_progress_direction"], "LOSS")
        self.assertEqual(result["pnl"], -4375.70)

    def test_loss_uses_absolute_progress_and_caps_at_negative_one_x(self):
        position = {"quantity": 5, "average_price": 200, "pnl": -500, "unrealised": -500}
        result = add_pnl_progress(position)
        self.assertEqual(result["pnl_multiple"], -0.5)
        self.assertEqual(result["pnl_progress_percent"], 50.0)

        position["unrealised"] = -1000
        result = add_pnl_progress(position)
        self.assertEqual(result["pnl_multiple"], -1.0)
        self.assertEqual(result["pnl_progress_percent"], 100.0)

    def test_profit_progress_caps_at_two_times(self):
        position = {"quantity": 2, "average_price": 50, "pnl": 500, "unrealised": 500}
        result = add_pnl_progress(position)
        self.assertEqual(result["pnl_multiple"], 5.0)
        self.assertEqual(result["pnl_progress_percent"], 100.0)

    def test_flat_position_has_no_open_position_multiple(self):
        position = {"quantity": 0, "average_price": 50, "pnl": 125, "unrealised": 125}
        result = add_pnl_progress(position)
        self.assertEqual(result["position_value_basis"], 0)
        self.assertIsNone(result["pnl_multiple"])
        self.assertEqual(result["pnl_progress_percent"], 0.0)
        self.assertEqual(result["pnl_progress_direction"], "UNAVAILABLE")

    def test_missing_unrealised_pnl_does_not_fall_back_to_total_pnl(self):
        position = {"quantity": 10, "average_price": 100, "pnl": -500}
        result = add_pnl_progress(position)
        self.assertIsNone(result["pnl_multiple"])
        self.assertEqual(result["pnl_progress_percent"], 0.0)
        self.assertEqual(result["pnl_progress_direction"], "UNAVAILABLE")

    def test_zero_average_price_does_not_divide_by_zero(self):
        position = {"quantity": 10, "average_price": 0, "pnl": -25, "unrealised": -25}
        result = add_pnl_progress(position)
        self.assertIsNone(result["pnl_multiple"])
        self.assertEqual(result["pnl_progress_percent"], 0.0)


if __name__ == "__main__":
    unittest.main()
