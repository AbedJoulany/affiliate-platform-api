import hashlib


def sign_request(params: dict[str, str], app_secret: str) -> str:
    sorted_items = sorted(params.items(), key=lambda item: item[0])
    concatenated = "".join(f"{key}{value}" for key, value in sorted_items)
    digest_input = f"{app_secret}{concatenated}{app_secret}"
    return hashlib.md5(digest_input.encode("utf-8")).hexdigest().upper()
