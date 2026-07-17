from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.aliexpress.exceptions import AliExpressAPIError, AliExpressImageSearchNotSupportedError
from app.aliexpress.types import DiscoveryMode, ProductSortOption
from app.api.deps import require_roles
from app.api.deps_aliexpress import (
    get_aliexpress_import_service,
    get_product_discovery_service,
)
from app.core.enums import UserRole
from app.models.user import User
from app.schemas.discovery import (
    ProductDiscoveryQuery,
    ProductDiscoveryResponse,
    ProductImageSearchRequest,
    ProductImportBatchRequest,
    ProductImportBatchResponse,
    ProductImportRequest,
    ProductImportResponse,
    ProductImportUrlRequest,
    ProductSearchQuery,
)
from app.services.aliexpress_import import AliExpressImportService
from app.services.exceptions import ServiceError
from app.services.product_discovery import ProductDiscoveryService

router = APIRouter()


def _discovery_filters(
    category_id: str | None = Query(default=None),
    min_rating: Decimal | None = Query(default=None, ge=0, le=5),
    min_orders: int | None = Query(default=None, ge=0),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    min_discount: Decimal | None = Query(default=None, ge=0, le=100),
    shipping_country: str | None = Query(default=None, min_length=2, max_length=2),
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    choice_only: bool = Query(default=False),
    free_shipping: bool = Query(default=False),
    keywords: str | None = Query(default=None, max_length=255),
    sort: ProductSortOption = Query(default=ProductSortOption.ORDERS_DESC),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    persist: bool = Query(default=False),
    promotion_name: str | None = Query(default=None, max_length=255),
) -> ProductDiscoveryQuery:
    return ProductDiscoveryQuery(
        category_id=category_id,
        min_rating=min_rating,
        min_orders=min_orders,
        min_price=min_price,
        max_price=max_price,
        min_discount=min_discount,
        shipping_country=shipping_country,
        currency=currency,
        choice_only=choice_only,
        free_shipping=free_shipping,
        keywords=keywords,
        sort=sort,
        page=page,
        page_size=page_size,
        persist=persist,
        promotion_name=promotion_name,
    )


def _discovery_filters_without_category(
    min_rating: Decimal | None = Query(default=None, ge=0, le=5),
    min_orders: int | None = Query(default=None, ge=0),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    min_discount: Decimal | None = Query(default=None, ge=0, le=100),
    shipping_country: str | None = Query(default=None, min_length=2, max_length=2),
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    choice_only: bool = Query(default=False),
    free_shipping: bool = Query(default=False),
    keywords: str | None = Query(default=None, max_length=255),
    sort: ProductSortOption = Query(default=ProductSortOption.ORDERS_DESC),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    persist: bool = Query(default=False),
    promotion_name: str | None = Query(default=None, max_length=255),
) -> ProductDiscoveryQuery:
    return ProductDiscoveryQuery(
        min_rating=min_rating,
        min_orders=min_orders,
        min_price=min_price,
        max_price=max_price,
        min_discount=min_discount,
        shipping_country=shipping_country,
        currency=currency,
        choice_only=choice_only,
        free_shipping=free_shipping,
        keywords=keywords,
        sort=sort,
        page=page,
        page_size=page_size,
        persist=persist,
        promotion_name=promotion_name,
    )


def _raise_service_error(exc: Exception) -> None:
    if isinstance(exc, ServiceError):
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    if isinstance(exc, AliExpressImageSearchNotSupportedError):
        raise HTTPException(status_code=501, detail=exc.message) from exc
    if isinstance(exc, AliExpressAPIError):
        raise HTTPException(
            status_code=502,
            detail=exc.message,
        ) from exc
    raise exc


async def _handle_discovery(
    handler,
    discovery_service: ProductDiscoveryService,
) -> ProductDiscoveryResponse:
    try:
        result = await handler(discovery_service)
        return result.response
    except Exception as exc:
        _raise_service_error(exc)
        raise


@router.get("/discover", response_model=ProductDiscoveryResponse)
async def discover_products(
    query: Annotated[ProductDiscoveryQuery, Depends(_discovery_filters)],
    discovery_service: Annotated[ProductDiscoveryService, Depends(get_product_discovery_service)],
) -> ProductDiscoveryResponse:
    return await _handle_discovery(lambda service: service.discover(query), discovery_service)


@router.get("/discover/hot", response_model=ProductDiscoveryResponse)
async def discover_hot_products(
    query: Annotated[ProductDiscoveryQuery, Depends(_discovery_filters)],
    discovery_service: Annotated[ProductDiscoveryService, Depends(get_product_discovery_service)],
) -> ProductDiscoveryResponse:
    return await _handle_discovery(lambda service: service.discover_hot(query), discovery_service)


@router.get("/discover/deals", response_model=ProductDiscoveryResponse)
async def discover_deals(
    query: Annotated[ProductDiscoveryQuery, Depends(_discovery_filters)],
    discovery_service: Annotated[ProductDiscoveryService, Depends(get_product_discovery_service)],
) -> ProductDiscoveryResponse:
    return await _handle_discovery(lambda service: service.discover_deals(query), discovery_service)


@router.get("/discover/trending", response_model=ProductDiscoveryResponse)
async def discover_trending_products(
    query: Annotated[ProductDiscoveryQuery, Depends(_discovery_filters)],
    discovery_service: Annotated[ProductDiscoveryService, Depends(get_product_discovery_service)],
) -> ProductDiscoveryResponse:
    return await _handle_discovery(
        lambda service: service.discover_trending(query),
        discovery_service,
    )


@router.get("/discover/category/{category_id}", response_model=ProductDiscoveryResponse)
async def discover_products_by_category(
    category_id: str,
    query: Annotated[ProductDiscoveryQuery, Depends(_discovery_filters_without_category)],
    discovery_service: Annotated[ProductDiscoveryService, Depends(get_product_discovery_service)],
) -> ProductDiscoveryResponse:
    return await _handle_discovery(
        lambda service: service.discover_by_category(category_id, query),
        discovery_service,
    )


@router.get("/search", response_model=ProductDiscoveryResponse)
async def search_products(
    q: str = Query(min_length=1, max_length=255),
    category_id: str | None = Query(default=None),
    min_rating: Decimal | None = Query(default=None, ge=0, le=5),
    min_orders: int | None = Query(default=None, ge=0),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    min_discount: Decimal | None = Query(default=None, ge=0, le=100),
    shipping_country: str | None = Query(default=None, min_length=2, max_length=2),
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    choice_only: bool = Query(default=False),
    free_shipping: bool = Query(default=False),
    sort: ProductSortOption = Query(default=ProductSortOption.ORDERS_DESC),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    persist: bool = Query(default=False),
    discovery_service: Annotated[
        ProductDiscoveryService, Depends(get_product_discovery_service)
    ] = None,
) -> ProductDiscoveryResponse:
    search_query = ProductSearchQuery(
        q=q,
        category_id=category_id,
        min_rating=min_rating,
        min_orders=min_orders,
        min_price=min_price,
        max_price=max_price,
        min_discount=min_discount,
        shipping_country=shipping_country,
        currency=currency,
        choice_only=choice_only,
        free_shipping=free_shipping,
        sort=sort,
        page=page,
        page_size=page_size,
        persist=persist,
    )
    return await _handle_discovery(lambda service: service.search(search_query), discovery_service)


@router.post("/search/image", response_model=ProductDiscoveryResponse)
async def search_products_by_image(
    payload: ProductImageSearchRequest,
    discovery_service: Annotated[ProductDiscoveryService, Depends(get_product_discovery_service)],
) -> ProductDiscoveryResponse:
    try:
        products, meta = await discovery_service.client.search_products_by_image(
            image_url=str(payload.image_url) if payload.image_url else None,
            image_base64=payload.image_base64,
        )
    except Exception as exc:
        _raise_service_error(exc)
        raise

    products = discovery_service._dedupe_products(products)
    persisted_count = 0
    if payload.persist and discovery_service.importer and products:
        imported, updated = await discovery_service.importer.upsert_many(products)
        persisted_count = imported + updated

    items = [discovery_service._to_discovered_read(product) for product in products]
    return ProductDiscoveryResponse(
        items=items,
        total=meta.total_count,
        skip=(payload.page - 1) * payload.page_size,
        limit=payload.page_size,
        page=meta.current_page,
        total_pages=meta.total_pages,
        mode=DiscoveryMode.GENERAL,
        sort=ProductSortOption.ORDERS_DESC,
        persisted_count=persisted_count,
    )


@router.post("/import-url", response_model=ProductImportResponse)
async def import_product_by_url(
    payload: ProductImportUrlRequest,
    response: Response,
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    import_service: Annotated[AliExpressImportService, Depends(get_aliexpress_import_service)],
) -> ProductImportResponse:
    try:
        result = await import_service.import_from_url(payload)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    response.status_code = status.HTTP_201_CREATED if result.imported else status.HTTP_200_OK
    return result


@router.post("/import", response_model=ProductImportResponse)
async def import_product(
    payload: ProductImportRequest,
    response: Response,
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    import_service: Annotated[AliExpressImportService, Depends(get_aliexpress_import_service)],
) -> ProductImportResponse:
    try:
        result = await import_service.import_from_request(payload)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    response.status_code = status.HTTP_201_CREATED if result.imported else status.HTTP_200_OK
    return result


@router.post("/import/batch", response_model=ProductImportBatchResponse)
async def import_products_batch(
    payload: ProductImportBatchRequest,
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    import_service: Annotated[AliExpressImportService, Depends(get_aliexpress_import_service)],
) -> ProductImportBatchResponse:
    try:
        return await import_service.import_batch(payload)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
