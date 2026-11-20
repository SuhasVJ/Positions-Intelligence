import unittest

from app.portfolio_intelligence.classifier.position_classifier import classify_position


class PositionClassifierTests(unittest.TestCase):
    def classify(self, exchange, instrument_type, name, quantity=1, **extra):
        position = {"exchange": exchange, "quantity": quantity}
        instrument = {
            "exchange": exchange,
            "instrument_type": instrument_type,
            "name": name,
            **extra,
        }
        return classify_position(position, instrument)

    def test_classifies_equity(self):
        result = self.classify("NSE", "EQ", "RELIANCE")
        self.assertEqual(result["asset_type"], "EQUITY")
        self.assertEqual(result["direction"], "LONG")

    def test_classifies_index_option_and_preserves_option_metadata(self):
        result = self.classify("NFO", "CE", "NIFTY", -50,
                               expiry="2026-11-26", strike=25750, lot_size=50)
        self.assertEqual(result["asset_type"], "INDEX_OPTION")
        self.assertEqual(result["direction"], "SHORT")
        self.assertEqual(result["option_type"], "CE")
        self.assertEqual(result["strike"], 25750.0)
        self.assertEqual(result["lot_size"], 50)

    def test_classifies_stock_option(self):
        result = self.classify("NFO", "PE", "RELIANCE")
        self.assertEqual(result["asset_type"], "STOCK_OPTION")
        self.assertEqual(result["option_type"], "PE")

    def test_classifies_index_future(self):
        result = self.classify("NFO", "FUT", "BANKNIFTY")
        self.assertEqual(result["asset_type"], "INDEX_FUTURE")

    def test_classifies_stock_future(self):
        result = self.classify("NFO", "FUT", "RELIANCE")
        self.assertEqual(result["asset_type"], "STOCK_FUTURE")

    def test_classifies_commodity_future_and_option(self):
        future = self.classify("MCX", "FUT", "NATURALGAS", segment="MCX-FUT")
        option = self.classify("MCX", "CE", "GOLD", segment="MCX-OPT")
        self.assertEqual(future["asset_type"], "COMMODITY_FUTURE")
        self.assertEqual(option["asset_type"], "COMMODITY_OPTION")

    def test_zero_quantity_is_flat(self):
        result = self.classify("NSE", "EQ", "INFY", quantity=0)
        self.assertEqual(result["direction"], "FLAT")

    def test_unknown_without_instrument_master_metadata_is_not_guessed(self):
        result = classify_position({"exchange": "NFO", "quantity": 25})
        self.assertEqual(result["asset_type"], "UNKNOWN")
        self.assertEqual(result["classification_status"], "UNKNOWN")
        self.assertEqual(result["classification_confidence"], 0.0)

    def test_unknown_instrument_type_is_not_guessed_from_symbol(self):
        result = self.classify("NFO", "", "NIFTY")
        self.assertEqual(result["asset_type"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
