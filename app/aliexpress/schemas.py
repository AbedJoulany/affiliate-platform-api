from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class AliExpressProductData:
    aliexpress_product_id: str
    title: str
    image_url: str
    images: list[str] = field(default_factory=list)
    price: Decimal = Decimal("0.00")
    original_price: Decimal | None = None
    discount: Decimal = Decimal("0.00")
    rating: Decimal = Decimal("0.00")
    sales: int = 0
    reviews: int = 0
    product_url: str = ""
    promotion_url: str | None = None
    currency: str = "USD"
