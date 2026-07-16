from dataclasses import dataclass, field
from datetime import datetime
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
    description: str | None = None
    category: str | None = None
    category_id: str | None = None
    store_name: str | None = None
    commission_rate: Decimal | None = None
    shipping_info: dict | None = None
    platform_product_type: str | None = None
    last_synced_at: datetime | None = None
