from enum import StrEnum


class DiscoveryMode(StrEnum):
    GENERAL = "general"
    HOT = "hot"
    DEALS = "deals"
    BIG_DISCOUNT = "big_discount"
    CHOICE = "choice"
    CATEGORY = "category"
    KEYWORD = "keyword"
    COMMISSION = "commission"
    TRENDING = "trending"


class ProductSortOption(StrEnum):
    ORDERS_DESC = "orders_desc"
    RATING_DESC = "rating_desc"
    DISCOUNT_DESC = "discount_desc"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    NEWEST = "newest"
    COMMISSION_DESC = "commission_desc"


class AliExpressAPISort(StrEnum):
    SALE_PRICE_ASC = "SALE_PRICE_ASC"
    SALE_PRICE_DESC = "SALE_PRICE_DESC"
    LAST_VOLUME_ASC = "LAST_VOLUME_ASC"
    LAST_VOLUME_DESC = "LAST_VOLUME_DESC"


class AliExpressPromoSort(StrEnum):
    COMMISSION_ASC = "commissionAsc"
    COMMISSION_DESC = "commissionDesc"
    PRICE_ASC = "priceAsc"
    PRICE_DESC = "priceDesc"
    VOLUME_ASC = "volumeAsc"
    VOLUME_DESC = "volumeDesc"
    DISCOUNT_ASC = "discountAsc"
    DISCOUNT_DESC = "discountDesc"
    RATING_ASC = "ratingAsc"
    RATING_DESC = "ratingDesc"


class PlatformProductType(StrEnum):
    ALL = "ALL"
    TMALL = "TMALL"
    PLAZA = "PLAZA"
