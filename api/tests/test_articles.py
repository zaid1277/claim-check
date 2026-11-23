import gzip

import pytest

from app.core.errors import ProviderError
from app.services.article_extraction import make_passages, parse_article
from app.services.url_fetch import public_address


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://127.0.0.1",
        "http://[::1]",
        "http://169.254.169.254",
        "http://user:pass@example.org",
        "http://example.org:22",
    ],
)
def test_private_urls_rejected(url):
    with pytest.raises(ProviderError):
        public_address(url)


def test_plain_passages_and_sanitization():
    article = parse_article(
        "<html><title>Schedule</title><body><article><p>"
        + "The library opens on Sunday. " * 30
        + "</p></article><script>secretScript()</script></body></html>",
        "https://example.org",
    )
    assert "secretScript" not in article.text
    assert all(len(p.split()) <= 20 for p in make_passages(article.text, 20))


def test_compressed_pages_are_decoded_with_output_limit():
    from app.services.url_fetch import decode_body

    assert (
        decode_body(gzip.compress(b"Readable article"), "gzip", "utf-8", 100)
        == "Readable article"
    )
    with pytest.raises(ProviderError):
        decode_body(gzip.compress(b"x" * 1000), "gzip", "utf-8", 100)


def test_corrupt_compressed_pages_raise_safe_error():
    from app.services.url_fetch import decode_body

    with pytest.raises(ProviderError):
        decode_body(b"broken gzip", "gzip", "utf-8", 100)


@pytest.mark.parametrize(
    "attributes",
    ['class="mw-references references"', 'class="reflist"', 'role="doc-bibliography"'],
)
def test_bibliography_is_not_evidence(attributes):
    passage = (
        "The Eiffel Tower is a wrought-iron lattice tower "
        "on the Champ de Mars in Paris, France."
    )
    html = (
        f"<html><body><article><p>{passage}</p>"
        f"<div {attributes}><ol>"
        + "<li>Bibliography-only title. Archived and retrieved April 2016.</li>" * 30
        + "</ol></div></article></body></html>"
    )
    article = parse_article(html, "https://example.org/article")
    assert passage in article.text
    assert "Bibliography-only" not in article.text
    assert all("Bibliography-only" not in text for text in make_passages(article.text))


def test_prose_about_references_is_preserved():
    text = (
        "The article references earlier research and explains its scientific findings."
    )
    article = parse_article(
        f"<html><body><article><p>{text}</p></article></body></html>",
        "https://example.org/article",
    )
    assert text in article.text


def test_heading_marked_bibliography_list_is_not_evidence():
    text = "The Eiffel Tower is a wrought-iron lattice tower in Paris, France."
    article = parse_article(
        f"<article><p>{text}</p>"
        '<div class="mw-heading"><h3 id="Bibliography">Bibliography</h3></div>'
        "<ul><li>A bibliography title. ISBN 123. Archived 2016.</li></ul>"
        "<p>The monument is open to visitors throughout the year.</p></article>",
        "https://example.org/article",
    )
    assert text in article.text
    assert "ISBN" not in article.text
    assert "open to visitors" in article.text
