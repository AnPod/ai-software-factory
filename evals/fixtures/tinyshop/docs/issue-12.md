# GH-12: Apply a per-SKU discount cap

Requester: @bob
Labels: enhancement, pricing
Link: https://github.com/example/tinyshop/issues/12

## Request

Right now `Cart.discount_percent` applies the same percentage discount to every line item in the cart. Some SKUs (clearance items and low-margin products) should not be discounted past a per-SKU cap.

Add an optional `max_discount_percent` field (`Decimal | None`, default `None`) to `LineItem`:

- When `max_discount_percent` is `None`, the item receives the full cart `discount_percent`.
- When `max_discount_percent` is set, the effective discount for that line item is `min(cart.discount_percent, item.max_discount_percent)`.
- A cap of `Decimal("0")` means the SKU receives no discount even if the cart has a discount.
- Raise `ValueError` if `max_discount_percent` is less than `0` or greater than `100`.
- Keep all monetary calculations in `Decimal`, apply the 22% VAT after discounts, and round half up to cents at the end (per ADR 0001).
