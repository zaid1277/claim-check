from fastapi import APIRouter

from app.core.settings import get_settings
from app.schemas.inputs import TextInput, URLInput
from app.services.article_extraction import extract_article
from app.services.claim_extraction import SentenceClaimExtractor

router = APIRouter(tags=["inputs"])


@router.post("/inputs/text")
def text_input(body: TextInput):
    return {
        "text": body.text,
        "claims": SentenceClaimExtractor(get_settings()).extract(body.text),
    }


@router.post("/inputs/url")
def url_input(body: URLInput):
    article = extract_article(body.url)
    text = article.text[:30000]
    return {
        "text": text,
        "claims": SentenceClaimExtractor(get_settings()).extract(text),
        "source_url": article.url,
        "title": article.title,
    }
