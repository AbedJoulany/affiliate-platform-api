from dataclasses import dataclass

from app.aliexpress.exceptions import AliExpressAPIError


@dataclass(frozen=True)
class AliExpressPageMeta:
    current_page: int
    total_pages: int
    current_count: int
    total_count: int
    is_finished: bool

def extract_response_root(payload: dict, method: str | None = None) -> dict:
    """Dynamically extracts the core data block by stripping any endpoint-specific outer keys."""
    if "error_response" in payload:
        error = payload["error_response"]
        raise AliExpressAPIError(
            str(error.get("msg") or error.get("sub_msg") or "AliExpress API error"),
            code=error.get("code") or error.get("sub_code"),
        )

    # DYNAMIC SEARCH: Automatically finds any top-level key ending with '_response'
    root = payload
    for key, value in payload.items():
        if key.endswith("_response") and isinstance(value, dict):
            root = value
            break

    if isinstance(root, dict) and root.get("error_code"):
        raise AliExpressAPIError(
            str(root.get("error_msg") or "AliExpress API error"),
            code=root.get("error_code"),
        )
    return root if isinstance(root, dict) else {}

def extract_result_container(root: dict) -> dict:
    result_container = root.get("resp_result") or root.get("result") or root
    if not isinstance(result_container, dict):
        return {}

    resp_code = result_container.get("resp_code")
    if resp_code not in (None, 200, "200"):
        raise AliExpressAPIError(
            str(result_container.get("resp_msg") or "AliExpress API call failed"),
            code=resp_code,
        )
    return result_container

def extract_result_payload(root: dict) -> dict:
    result_container = extract_result_container(root)
    result = result_container.get("result")
    if isinstance(result, dict):
        return result
    return result_container if isinstance(result_container, dict) else {}

def normalize_product_list(raw_products: object) -> list[dict]:
    if raw_products is None:
        return []

    if isinstance(raw_products, dict):
        nested = raw_products.get("product") or raw_products.get("products")
        raw_products = nested if nested is not None else raw_products

    if isinstance(raw_products, dict):
        return [raw_products]

    if isinstance(raw_products, list):
        return [item for item in raw_products if isinstance(item, dict)]

    return []

def extract_products_and_meta(
    payload: dict,
    method: str | None = None,
) -> tuple[list[dict], AliExpressPageMeta]:
    root = extract_response_root(payload, method)
    result = extract_result_payload(root)

    products = normalize_product_list(result.get("products") or result.get("product"))

    current_page = int(result.get("current_page_no") or result.get("page_no") or 1)
    total_pages = int(result.get("total_page_no") or result.get("total_pages") or 1)
    current_count = int(result.get("current_record_count") or len(products))
    total_count = int(result.get("total_record_count") or current_count)
    is_finished = bool(result.get("is_finished", current_page >= total_pages))

    return products, AliExpressPageMeta(
        current_page=current_page,
        total_pages=total_pages,
        current_count=current_count,
        total_count=total_count,
        is_finished=is_finished,
    )

def extract_categories(payload: dict, method: str | None = None) -> list[dict]:
    root = extract_response_root(payload, method)
    result = extract_result_payload(root)
    categories = result.get("categories")
    if isinstance(categories, dict):
        categories = categories.get("category") or categories.get("categories")
    if isinstance(categories, dict):
        return [categories]
    if isinstance(categories, list):
        return [item for item in categories if isinstance(item, dict)]
    return []

def extract_promotions(payload: dict, method: str | None = None) -> list[dict]:
    root = extract_response_root(payload, method)
    result = extract_result_payload(root)
    promos = result.get("promos") or result.get("promo")
    if isinstance(promos, dict):
        promos = promos.get("promo") or promos.get("promos")
    if isinstance(promos, dict):
        return [promos]
    if isinstance(promos, list):
        return [item for item in promos if isinstance(item, dict)]
    return []