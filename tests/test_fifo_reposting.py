"""Tests for the FIFO reposting example. Run with: python -m unittest discover -s tests"""

import unittest

from fifo_reposting import (
    Delivery,
    Receipt,
    StockLedger,
    example_transactions,
    find_row,
    number,
)


class FifoRepostingTests(unittest.TestCase):
    def replay(self, receipt_rate):
        ledger = StockLedger(example_transactions(number(receipt_rate)))
        return ledger.replay()

    def test_changed_receipt_does_not_change_earlier_fifo_delivery_cost(self):
        rows = self.replay(80)
        delivery = find_row(rows, "15 Jan Delivery Note")

        self.assertEqual(delivery.value_change, number(-4000))
        # Its remaining 50 L receipt layer is now worth 50 * ₹80, plus 20 * ₹50.
        self.assertEqual(delivery.balance_value, number(5000))

    def test_jan_20_receipt_uses_its_own_rate_but_new_balance(self):
        rows = self.replay(80)
        receipt = find_row(rows, "20 Jan Purchase Receipt")

        self.assertEqual(receipt.value_change, number(3000))
        self.assertEqual(receipt.balance_quantity, number(120))
        self.assertEqual(receipt.balance_value, number(8000))

    def test_manufacture_cost_flows_to_powder_and_delivery(self):
        rows = self.replay(80)
        consumed = find_row(rows, "21 Jan Manufacture (consume)")
        produced = find_row(rows, "21 Jan Manufacture (produce)")
        powder_delivery = find_row(rows, "25 Jan Powder Delivery Note")

        self.assertEqual(consumed.value_change, number(-6800))
        self.assertEqual(produced.value_change, number(6800))
        self.assertEqual(powder_delivery.value_change, number(-6800))

    def test_rate_change_increases_manufacturing_cost_by_one_thousand(self):
        old_rows = self.replay(60)
        new_rows = self.replay(80)
        old_cost = -find_row(old_rows, "21 Jan Manufacture (consume)").value_change
        new_cost = -find_row(new_rows, "21 Jan Manufacture (consume)").value_change

        self.assertEqual(new_cost - old_cost, number(1000))

    def test_delivery_rejects_insufficient_stock(self):
        ledger = StockLedger([Delivery(1, "too much", "Milk", number(1))])

        with self.assertRaisesRegex(ValueError, "Not enough Milk stock"):
            ledger.replay()


if __name__ == "__main__":
    unittest.main()
