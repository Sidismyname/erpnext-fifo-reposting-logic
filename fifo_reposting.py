"""A small, readable FIFO stock-ledger replay demonstration.

This is an educational model, not ERPNext production code.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Iterable, List, Tuple

Money = Decimal
Quantity = Decimal


def number(value: str | int) -> Decimal:
    """Convert a literal to Decimal so money calculations avoid float errors."""
    return Decimal(str(value))


@dataclass(frozen=True)
class Transaction:
    """Base transaction fields. `day` determines the order of replay."""

    day: int
    name: str


@dataclass(frozen=True)
class Receipt(Transaction):
    item: str
    quantity: Quantity
    rate: Money


@dataclass(frozen=True)
class Delivery(Transaction):
    item: str
    quantity: Quantity


@dataclass(frozen=True)
class Manufacture(Transaction):
    """Consume one item and receive another at the consumed material cost."""

    input_item: str
    input_quantity: Quantity
    output_item: str
    output_quantity: Quantity


@dataclass
class Layer:
    """One remaining FIFO batch: quantity still on hand and its unit cost."""

    quantity: Quantity
    rate: Money


@dataclass(frozen=True)
class LedgerRow:
    """Calculated result for one transaction during a replay."""

    name: str
    item: str
    quantity_change: Quantity
    value_change: Money
    valuation_rate: Money
    balance_quantity: Quantity
    balance_value: Money


class StockLedger:
    """Rebuild stock values by replaying submitted transactions in date order.

    A full replay is deliberately used here because it makes the key idea clear:
    balances and FIFO queues are derived from all earlier transactions. A real
    ERP system can optimize this by starting from a trusted checkpoint and by
    scheduling dependent item/warehouse ledgers when manufacture costs change.
    """

    def __init__(self, transactions: Iterable[Transaction]):
        self.transactions = sorted(transactions, key=lambda transaction: transaction.day)
        self.rows: List[LedgerRow] = []

    def replay(self) -> List[LedgerRow]:
        """Recalculate all FIFO layers, stock balances, and transaction values."""
        queues: Dict[str, List[Layer]] = {}
        self.rows = []

        for transaction in self.transactions:
            if isinstance(transaction, Receipt):
                self._receive(queues, transaction)
            elif isinstance(transaction, Delivery):
                self._deliver(queues, transaction)
            elif isinstance(transaction, Manufacture):
                self._manufacture(queues, transaction)
            else:
                raise TypeError(f"Unsupported transaction: {transaction!r}")

        return self.rows

    def _receive(self, queues: dict, receipt: Receipt) -> None:
        queues.setdefault(receipt.item, []).append(Layer(receipt.quantity, receipt.rate))
        self._record(queues, receipt.name, receipt.item, receipt.quantity,
                     receipt.quantity * receipt.rate)

    def _deliver(self, queues: dict, delivery: Delivery) -> None:
        cost = self._consume(queues, delivery.item, delivery.quantity)
        self._record(queues, delivery.name, delivery.item, -delivery.quantity, -cost)

    def _manufacture(self, queues: dict, entry: Manufacture) -> None:
        # The output's FIFO layer carries the recalculated consumed-material cost.
        input_cost = self._consume(queues, entry.input_item, entry.input_quantity)
        self._record(queues, entry.name + " (consume)", entry.input_item,
                     -entry.input_quantity, -input_cost)
        output_rate = input_cost / entry.output_quantity
        queues.setdefault(entry.output_item, []).append(
            Layer(entry.output_quantity, output_rate)
        )
        self._record(queues, entry.name + " (produce)", entry.output_item,
                     entry.output_quantity, input_cost)

    @staticmethod
    def _consume(queues: dict, item: str, quantity: Quantity) -> Money:
        """Remove oldest layers first and return their total cost."""
        remaining = quantity
        total_cost = number(0)
        layers = queues.setdefault(item, [])

        while remaining > 0:
            if not layers:
                raise ValueError(f"Not enough {item} stock to issue {quantity}")
            layer = layers[0]
            taken = min(remaining, layer.quantity)
            total_cost += taken * layer.rate
            layer.quantity -= taken
            remaining -= taken
            if layer.quantity == 0:
                layers.pop(0)

        return total_cost

    def _record(self, queues: dict, name: str, item: str,
                quantity_change: Quantity, value_change: Money) -> None:
        balance_quantity = sum((layer.quantity for layer in queues[item]), number(0))
        balance_value = sum(
            (layer.quantity * layer.rate for layer in queues[item]), number(0)
        )
        rate = balance_value / balance_quantity if balance_quantity else number(0)
        self.rows.append(LedgerRow(name, item, quantity_change, value_change,
                                   rate, balance_quantity, balance_value))


def example_transactions(changed_receipt_rate: Money) -> List[Transaction]:
    """Create the example transactions, with a configurable 10 January rate."""
    return [
        Receipt(1, "Opening stock", "Milk", number(100), number(50)),
        Receipt(10, "10 Jan Purchase Receipt", "Milk", number(50), changed_receipt_rate),
        Delivery(15, "15 Jan Delivery Note", "Milk", number(80)),
        Receipt(20, "20 Jan Purchase Receipt", "Milk", number(50), number(60)),
        Manufacture(21, "21 Jan Manufacture", "Milk", number(100),
                   "Milk Powder", number(10)),
        Delivery(25, "25 Jan Powder Delivery Note", "Milk Powder", number(10)),
    ]


def find_row(rows: List[LedgerRow], name: str) -> LedgerRow:
    """Return a calculated ledger row by its transaction label."""
    return next(row for row in rows if row.name == name)


if __name__ == "__main__":
    ledger = StockLedger(example_transactions(number(80)))
    for row in ledger.replay():
        print(f"{row.name:28} {row.item:12} qty={row.quantity_change:>6} "
              f"value={row.value_change:>8} balance={row.balance_quantity:>6} "
              f"stock_value={row.balance_value:>8}")
