import unittest

from app.pnl_progress import add_pnl_progress


class PositionPnlProgressTests(unittest.TestCase):
    def test_profit_multiple_and_progress_are_calculated_from_position_value(self):
        position = {"quantity": 10, "average_price": 100, "pnl": 1000}
        result = add_pnl_progress(position)
        self.assertEqual(result["position_value_basis"], 1000)
        self.assertEqual(result["pnl_multiple"], 1.0)
        self.assertEqual(result["pnl_progress_percent"], 50.0)
        self.assertEqual(result["pnl_progress_direction"], "PROFIT")

    def test_loss_uses_red_direction_and_absolute_progress(self):
        position = {"quantity": -5, "average_price": 200, "pnl": -500}
        result = add_pnl_progress(position)
        self.assertEqual(result["position_value_basis"], 1000)
        self.assertEqual(result["pnl_multiple"], -0.5)
        self.assertEqual(result["pnl_progress_percent"], 50.0)
        self.assertEqual(result["pnl_progress_direction"], "LOSS")

    def test_full_position_value_loss_fills_the_red_bar(self):
        position = {"quantity": 5, "average_price": 200, "pnl": -1000}
        result = add_pnl_progress(position)
        self.assertEqual(result["pnl_multiple"], -1.0)
        self.assertEqual(result["pnl_progress_percent"], 100.0)

    def test_progress_caps_at_two_times(self):
        position = {"quantity": 2, "average_price": 50, "pnl": 500}
        result = add_pnl_progress(position)
        self.assertEqual(result["pnl_multiple"], 5.0)
        self.assertEqual(result["pnl_progress_percent"], 100.0)

    def test_flat_position_has_no_investment_multiple(self):
        position = {"quantity": 0, "average_price": 50, "pnl": 125}
        result = add_pnl_progress(position)
        self.assertEqual(result["position_value_basis"], 0)
        self.assertIsNone(result["pnl_multiple"])
        self.assertEqual(result["pnl_progress_percent"], 0.0)
        self.assertEqual(result["pnl_progress_direction"], "UNAVAILABLE")

    def test_zero_average_price_does_not_divide_by_zero(self):
        position = {"quantity": 10, "average_price": 0, "pnl": -25}
        result = add_pnl_progress(position)
        self.assertIsNone(result["pnl_multiple"])
        self.assertEqual(result["pnl_progress_percent"], 0.0)


if __name__ == "__main__":
    unittest.main()
