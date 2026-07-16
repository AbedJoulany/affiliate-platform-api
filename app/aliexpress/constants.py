DEFAULT_PRODUCT_FIELDS = (
    "commission_rate,discount,evaluate_rate,lastest_volume,product_title,"
    "product_main_image_url,product_small_image_urls,promotion_link,"
    "product_detail_url,target_sale_price,target_original_price,"
    "target_sale_price_currency,sale_price,original_price,"
    "first_level_category_id,first_level_category_name,"
    "second_level_category_id,second_level_category_name,"
    "shop_id,shop_url,platform_product_type,ship_to_days,"
    "hot_product_commission_rate,relevant_market_commission_rate"
)

FAVORITE_PRODUCT_FIELDS = (
    "product_main_image_url,target_sale_price,product_title,target_sale_price_currency"
)

METHOD_PRODUCT_DETAIL = "aliexpress.affiliate.productdetail.get"
METHOD_PRODUCT_QUERY = "aliexpress.affiliate.product.query"
METHOD_HOT_PRODUCT_QUERY = "aliexpress.affiliate.hotproduct.query"
METHOD_SMART_MATCH = "aliexpress.affiliate.product.smartmatch"
METHOD_FEATURED_PROMO = "aliexpress.affiliate.featuredpromo.get"
METHOD_FEATURED_PROMO_PRODUCTS = "aliexpress.affiliate.featuredpromo.products.get"
METHOD_CATEGORY_GET = "aliexpress.affiliate.category.get"
METHOD_DS_IMAGE_SEARCH = "aliexpress.ds.image.search"
METHOD_LINK_GENERATE = "aliexpress.affiliate.link.generate"

RESPONSE_KEY_BY_METHOD = {
    METHOD_PRODUCT_DETAIL: "aliexpress_affiliate_productdetail_get_response",
    METHOD_PRODUCT_QUERY: "aliexpress_affiliate_product_query_response",
    METHOD_HOT_PRODUCT_QUERY: "aliexpress_affiliate_hotproduct_query_response",
    METHOD_SMART_MATCH: "aliexpress_affiliate_product_smartmatch_response",
    METHOD_FEATURED_PROMO: "aliexpress_affiliate_featuredpromo_get_response",
    METHOD_FEATURED_PROMO_PRODUCTS: "aliexpress_affiliate_featuredpromo_products_get_response",
    METHOD_CATEGORY_GET: "aliexpress_affiliate_category_get_response",
    METHOD_DS_IMAGE_SEARCH: "aliexpress_ds_image_search_response",
    METHOD_LINK_GENERATE: "aliexpress_affiliate_link_generate_response",
}
