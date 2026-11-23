import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlsplit

import trafilatura

from app.core.errors import ProviderError
from app.services.url_fetch import fetch_html

_BIBLIOGRAPHY_XPATH = (
    "//*[contains(concat(' ', normalize-space(@class), ' '), ' references ')"
    " or contains(concat(' ', normalize-space(@class), ' '), ' reflist ')"
    " or @role='doc-bibliography']"
    " | //*[@id='Bibliography']/parent::div"
    "/following-sibling::*[1][self::ul or self::ol]"
)
_MIN_TEXT_LENGTH = 50


class _VisibleTextParser(HTMLParser):
    """Remediation pass 5, part 11, layer 5: a last-resort, fully generic
    (no site-specific rules) visible-text extractor. Used only when
    trafilatura -- in both its default and favor_recall modes -- and the
    structured-metadata fallback all found nothing, e.g. markup trafilatura's
    heuristics reject as "not an article" despite genuine body prose (a real
    behavior measured on some nav-heavy government/corporate pages)."""

    _SKIP_TAGS = {"script", "style", "nav", "footer", "header", "noscript", "svg"}

    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self.chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth:
            text = data.strip()
            if text:
                self.chunks.append(text)


def _visible_text_fallback(html: str) -> str | None:
    parser = _VisibleTextParser()
    try:
        parser.feed(html)
    except Exception:
        return None
    text = " ".join(parser.chunks)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


_JSON_LD = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
_OG_DESCRIPTION = re.compile(
    r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)


def _structured_metadata_fallback(html: str) -> str | None:
    """Remediation pass 5, part 11, layer 3: JSON-LD `articleBody`/
    `description`, else an Open Graph description meta tag. General-purpose
    (every site that follows these widely-used standards benefits, none
    specifically targeted); much shorter than full article text, so it is
    only ever used when nothing richer was extractable."""
    for match in _JSON_LD.finditer(html):
        try:
            data = json.loads(match.group(1).strip())
        except (json.JSONDecodeError, ValueError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            for key in ("articleBody", "description"):
                value = item.get(key)
                if isinstance(value, str) and len(value.strip()) >= _MIN_TEXT_LENGTH:
                    return value.strip()
    match = _OG_DESCRIPTION.search(html)
    if match and len(match.group(1).strip()) >= _MIN_TEXT_LENGTH:
        return match.group(1).strip()
    return None


@dataclass
class Article:
    url: str
    title: str
    domain: str
    text: str
    published_at: str | None = None


def parse_article(html: str, url: str) -> Article:
    """Return plain article text; scripts and markup never reach the UI.

    Remediation pass 5, part 11: layered extraction. Each layer is a
    general-purpose method (no per-site rules), tried in order of
    decreasing precision, and only consulted when the previous layer
    genuinely found nothing usable:
      1. trafilatura, strict (unchanged from before this pass).
      2. trafilatura, favor_recall=True -- same library, a documented,
         less conservative extraction mode; recovers real body text on
         nav-heavy pages the strict pass rejects as boilerplate.
      3. JSON-LD / Open Graph structured metadata.
      4. a generic visible-text tag-stripping fallback.
    A browser-rendered fallback for JS-heavy pages (part 11, layer 4) was
    deliberately not implemented this pass: it would require adding a
    headless-browser dependency to the API service itself -- a real
    architecture change explicitly out of scope for a targeted remediation
    pass -- and diagnostic testing against the previous run's actual
    failures found none of them were JS-rendering issues (every fetched
    page was already fully server-rendered HTML); see
    docs/remediation-final-report.md part 9 for the measured failure
    taxonomy this was prioritized against.
    """
    # Bibliography entries identify sources; they are not evidence assertions.
    text = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        prune_xpath=_BIBLIOGRAPHY_XPATH,
    )
    if not text or len(text.strip()) < _MIN_TEXT_LENGTH:
        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            prune_xpath=_BIBLIOGRAPHY_XPATH,
            favor_recall=True,
        )
    if not text or len(text.strip()) < _MIN_TEXT_LENGTH:
        text = _structured_metadata_fallback(html)
    if not text or len(text.strip()) < _MIN_TEXT_LENGTH:
        text = _visible_text_fallback(html)
    if not text or len(text.strip()) < _MIN_TEXT_LENGTH:
        raise ProviderError(
            "No readable article was found. Paste the text instead.",
            category="no-readable-text",
        )
    metadata = trafilatura.extract_metadata(html, default_url=url)
    return Article(
        url=url,
        title=(metadata.title if metadata else None)
        or urlsplit(url).hostname
        or "Source",
        domain=urlsplit(url).hostname or "",
        text=text,
        published_at=metadata.date if metadata else None,
    )


def extract_article(url: str) -> Article:
    html, final_url = fetch_html(url)
    return parse_article(html, final_url)


def make_passages(text: str, words_per_passage: int = 100) -> list[str]:
    from app.services.propositions import sentence_texts

    passages, current = [], []
    for sentence in sentence_texts(text):
        words = sentence.split()
        if len(words) > words_per_passage:
            if current:
                passages.append(" ".join(current))
                current = []
            passages.extend(
                " ".join(words[i : i + words_per_passage])
                for i in range(0, len(words), words_per_passage)
            )
        elif len(current) + len(words) > words_per_passage:
            passages.append(" ".join(current))
            current = words
        else:
            current.extend(words)
    if current:
        passages.append(" ".join(current))
    return passages
