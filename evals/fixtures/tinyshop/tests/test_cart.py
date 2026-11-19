from decimal import Decimal

from tinyshop import Cart, LineItem


def test_total_with_vat():
    cart = Cart()
    cart.add(LineItem("A1", Decimal("10.00"), 2))
    assert cart.total() == Decimal("24.40")


def test_discount():
    cart = Cart(discount_percent=Decimal("10"))
    cart.add(LineItem("A1", Decimal("100.00")))
    assert cart.total() == Decimal("109.80")
