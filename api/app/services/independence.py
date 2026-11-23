"""Conservative provenance grouping; shared ownership cannot be inferred from DNS."""

import re
from functools import lru_cache
from urllib.parse import urlsplit


@lru_cache(maxsize=512)
def source_group(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    # tldextract ships a Public Suffix List snapshot; disable network refreshes.
    import tldextract

    extractor = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)
    domain = extractor(host).top_domain_under_public_suffix
    return domain or host


def content_words(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


def same_content(left: str, right: str, threshold: float = 0.9) -> bool:
    a, b = content_words(left), content_words(right)
    return bool(a and b) and len(a & b) / len(a | b) >= threshold
