from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Province = Literal['QC', 'ON']
Profile = Literal['H01','H02','H03','H04','H05','H06','H07','H08','H09','H10']


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class AccountInput(Input):
    name: str = Field(min_length=1, max_length=200)
    province: Province
    profile: Profile
    is_demo: bool = False
    website: str | None = None
    registration_id: str | None = None
    roles: list[str] = Field(default_factory=list, max_length=10)


class EvidenceInput(Input):
    source_url: str = Field(pattern=r'^https://', max_length=2000)
    observed_at: datetime
    expires_at: datetime
    confidence: float = Field(ge=0, le=1)
    fact_type: str = Field(max_length=60)
    value: Any = None
    raw_excerpt: str = Field(min_length=1, max_length=20000)
    provenance_license: str = Field(min_length=1, max_length=200)
    permitted_purposes: list[Literal['score','outreach','export','reply']]
    source_provider: str = Field(max_length=80)
    independent: bool = False
    signal_type: str | None = None
    event_date: datetime | None = None

    @model_validator(mode='after')
    def capability_values(self):
        from .domain import CAPABILITY_VALUES
        choices=CAPABILITY_VALUES.get(self.fact_type)
        if choices and self.value is not None:
            if not isinstance(self.value,list) or len(self.value)>20 or any(not isinstance(x,str) or x not in choices for x in self.value):
                raise ValueError('Profile capability facts require a list of recognized tags, or null for Unknown')
            self.value=sorted(set(self.value))
        return self


class Review(Input):
    approved: bool
    reason: str = Field(min_length=10, max_length=1000)


class EvidenceReview(Review):
    confidence: float | None = Field(default=None,ge=0,le=1)


class CredentialInput(Input):
    province: Province
    status: Literal['unknown','verified','invalid','not_required']
    work_class: str | None = None
    authority: Literal['RBQ','STO','TSSA','DEMO_AUTHORITY'] | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=10, max_length=1000)


class ContactInput(Input):
    email: str = Field(pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$', max_length=320)
    evidence_id: str
    name: str | None = None


class ConsentInput(Input):
    contact_id: str
    basis: Literal['express_consent','existing_relationship','conspicuous_business_publication']
    evidence_id: str
    basis_evidence_id: str | None = None
    business_relevance: str = Field(min_length=10, max_length=1000)
    expires_at: datetime


class DraftInput(Input):
    contact_id: str
    language: Literal['fr','en'] | None = None
    use_ai: bool = False


class DraftEdit(Input):
    revision: int = Field(ge=1)
    language: Literal['fr','en']


class DraftApprove(Review):
    revision: int = Field(ge=1)


class ReplyInput(Input):
    external_id: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=10000)
    evidence_id: str


class JobInput(Input):
    province: Province
    profile: Profile
    mode: Literal['demo','live'] = 'demo'
    idempotency_key: str = Field(min_length=1, max_length=200)
    max_results: int = Field(default=200, ge=1, le=200)
    call_budget: int = Field(default=10, ge=0, le=1000)
    cost_budget: float = Field(default=1, ge=0, le=100)
    items: list[dict] = Field(default_factory=list, max_length=200)


class PolicyInput(Input):
    enabled: bool = False
    terms_url: str = Field(pattern=r'^https://')
    provenance_license: str = Field(min_length=1)
    purposes: list[Literal['discovery','enrichment','score','outreach','export','draft','reply']]
    expires_at: datetime
    request_limit: int = Field(ge=1, le=10000)
    requests_per_minute: int = Field(ge=1, le=120)
    cost_per_call: float = Field(ge=0, le=10)
    allowed_urls: list[str] = Field(default_factory=list)
    allowed_dataset_ids: list[str] = Field(default_factory=list)
    business_content_only: bool = True
    reviewed_terms: bool
    reason: str = Field(min_length=10)


class Override(Input):
    points: dict[str, int]
    evidence_ids: list[str]
    reason: str = Field(min_length=20)


class StageInput(Input):
    stage: Literal['new','meeting','rfq','partner_review','won','lost']
    reason: str = Field(min_length=10)
    owner: str | None = None


class TaskInput(Input):
    status: Literal['open','done','cancelled']
    owner: str
    reason: str = Field(min_length=10)


class PartnerInput(Input):
    state: Literal['application','review','approved','activated','rejected']
    reason: str = Field(min_length=10)
    evidence_ids: list[str]
    first_action_evidence_id: str | None = None


class ProfileInput(Input):
    keywords: dict[Province, list[str]]

    @field_validator('keywords')
    @classmethod
    def keywords_valid(cls, value):
        if set(value) != {'QC','ON'} or any(not words or len(words)>20 or any(not x.strip() or len(x)>200 for x in words) for words in value.values()):
            raise ValueError('Provide 1–20 keywords for each province')
        return value
