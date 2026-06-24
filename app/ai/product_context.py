from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.models.product import Product


@dataclass
class ProductContext:
    title: str
    product_url: str
    price: Decimal | None = None
    discount: Decimal | None = None
    rating: Decimal | None = None
    sales: int | None = None
    reviews: int | None = None
    description: str | None = None
    image_url: str | None = None
    product_id: UUID | None = None

    @classmethod
    def from_product(cls, product: Product) -> "ProductContext":
        return cls(
            product_id=product.id,
            title=product.title,
            product_url=product.product_url,
            price=product.price,
            discount=product.discount,
            rating=product.rating,
            sales=product.sales,
            reviews=product.reviews,
            image_url=product.image_url,
        )

    @classmethod
    def from_url_metadata(
        cls,
        *,
        url: str,
        title: str,
        description: str | None = None,
        image_url: str | None = None,
    ) -> "ProductContext":
        return cls(
            title=title,
            product_url=url,
            description=description,
            image_url=image_url,
        )
