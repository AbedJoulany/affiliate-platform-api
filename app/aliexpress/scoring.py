from decimal import Decimal


def calculate_initial_product_score(
    *,
    rating: Decimal,
    sales: int,
    discount: Decimal,
    reviews: int = 0,
) -> Decimal:
    rating_component = min(rating / Decimal("5"), Decimal("1")) * Decimal("35")
    sales_component = min(Decimal(sales) / Decimal("10000"), Decimal("1")) * Decimal("35")
    discount_component = min(discount / Decimal("100"), Decimal("1")) * Decimal("20")
    reviews_component = min(Decimal(reviews) / Decimal("1000"), Decimal("1")) * Decimal("10")
    return (rating_component + sales_component + discount_component + reviews_component).quantize(
        Decimal("0.0001")
    )
