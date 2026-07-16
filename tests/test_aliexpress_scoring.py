from decimal import Decimal

from app.aliexpress.scoring import calculate_initial_product_score


def test_calculate_initial_product_score_weights():
    score = calculate_initial_product_score(
        rating=Decimal("5.00"),
        sales=10000,
        discount=Decimal("100.00"),
        reviews=1000,
    )
    assert score == Decimal("100.0000")


def test_calculate_initial_product_score_partial_values():
    score = calculate_initial_product_score(
        rating=Decimal("2.50"),
        sales=5000,
        discount=Decimal("50.00"),
        reviews=500,
    )
    assert score == Decimal("50.0000")
