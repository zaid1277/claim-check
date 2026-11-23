from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, Field, model_validator

from app.schemas.investigation import ClaimInput


class TextInput(BaseModel):
    text: str = Field(min_length=20, max_length=30000)


class URLInput(BaseModel):
    url: str = Field(min_length=8, max_length=2048)


class InvestigationInput(BaseModel):
    input_type: Literal["claim", "url", "text", "image"] = "claim"
    source_url: AnyHttpUrl | None = None
    raw_text: str = Field(default="", max_length=30000)
    claim: str | None = None
    claims: list[str] | None = Field(default=None, min_length=1, max_length=5)

    @model_validator(mode="after")
    def validate_claims(self):
        if (self.claim is None) == (self.claims is None):
            raise ValueError("Supply one claim or a list of selected claims.")
        values = [self.claim] if self.claim is not None else self.claims
        self.claims = [ClaimInput(claim=value).claim for value in values]
        return self
