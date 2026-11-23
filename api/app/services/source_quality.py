from app.core.settings import Settings


def source_quality(domain: str, settings: Settings) -> tuple[str, float]:
    """Apply documented domain heuristics, never a learned credibility score."""
    domain = domain.lower().rstrip(".")
    kind = "general"
    for suffix, category in settings.source_domains.items():
        if domain == suffix or domain.endswith("." + suffix):
            kind = category
            break
    if kind == "general" and domain.endswith((".gov", ".gov.uk")):
        kind = "official"
    elif kind == "general" and domain.endswith(".edu"):
        kind = "institution"
    return kind, settings.source_weights[kind]
