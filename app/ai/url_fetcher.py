import html
import re
from dataclasses import dataclass

import httpx

from app.services.exceptions import ValidationError

META_TAG_PATTERN = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?P<key>[^"\']+)["\'][^>]+content=["\'](?P<content>[^"\']+)["\']',
    re.IGNORECASE,
)
META_TAG_PATTERN_REVERSED = re.compile(
    r'<meta[^>]+content=["\'](?P<content>[^"\']+)["\'][^>]+(?:property|name)=["\'](?P<key>[^"\']+)["\']',
    re.IGNORECASE,
)
TITLE_PATTERN = re.compile(r"<title[^>]*>(?P<title>.*?)</title>", re.IGNORECASE | re.DOTALL)


@dataclass
class URLProductMetadata:
    url: str
    title: str
    description: str | None = None
    image_url: str | None = None


class ProductURLFetcher:
    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout

    async def fetch(self, url: str) -> URLProductMetadata:
        normalized_url = url.strip()
        if not normalized_url.startswith(("http://", "https://")):
            raise ValidationError("URL must start with http:// or https://")

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; AffiliatePlatformBot/1.0; +https://example.com/bot)"
            ),
            "Accept": "text/html,application/xhtml+xml",
        }

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers=headers,
        ) as client:
            try:
                response = await client.get(normalized_url)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise ValidationError(
                    f"Failed to fetch product URL: HTTP {exc.response.status_code}"
                ) from exc
            except httpx.HTTPError as exc:
                raise ValidationError(f"Failed to fetch product URL: {exc}") from exc

        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            raise ValidationError("URL did not return an HTML page")

        return self._parse_html(normalized_url, response.text)

    def _parse_html(self, url: str, page_html: str) -> URLProductMetadata:
        meta = self._extract_meta_tags(page_html)

        title = (
            meta.get("og:title")
            or meta.get("twitter:title")
            or self._extract_title_tag(page_html)
            or url
        )
        description = meta.get("og:description") or meta.get("description") or meta.get(
            "twitter:description"
        )
        image_url = meta.get("og:image") or meta.get("twitter:image")

        return URLProductMetadata(
            url=url,
            title=html.unescape(title.strip()),
            description=html.unescape(description.strip()) if description else None,
            image_url=image_url,
        )

    def _extract_meta_tags(self, page_html: str) -> dict[str, str]:
        tags: dict[str, str] = {}
        for pattern in (META_TAG_PATTERN, META_TAG_PATTERN_REVERSED):
            for match in pattern.finditer(page_html):
                tags[match.group("key").lower()] = html.unescape(match.group("content"))
        return tags

    def _extract_title_tag(self, page_html: str) -> str | None:
        match = TITLE_PATTERN.search(page_html)
        if not match:
            return None
        return html.unescape(re.sub(r"\s+", " ", match.group("title")))
