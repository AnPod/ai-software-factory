"""Cart totals with percentage discounts and VAT."""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

VAT_RATE = Decimal("0.22")


@dataclass
class LineItem:
    sku: str
    unit_price: Decimal
    quantity: int = 1

    def total(self) -> Decimal:
        return self.unit_price * self.quantity


@dataclass
class Cart:
    items: list[LineItem] = field(default_factory=list)
    discount_percent: Decimal = Decimal("0")

    def add(self, item: LineItem) -> None:
        self.items.append(item)

    def subtotal(self) -> Decimal:
        return sum((i.total() for i in self.items), Decimal("0"))

    def total(self) -> Decimal:
        discounted = self.subtotal() * (1 - self.discount_percent / 100)
        with_vat = discounted * (1 + VAT_RATE)
        return with_vat.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
