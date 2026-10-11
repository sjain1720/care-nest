"""API response models. They mirror frontend/src/app/models/models.ts – keep both in sync."""
from typing import Literal

from pydantic import BaseModel, Field

Verdict = Literal["covered", "partial", "not_covered", "needs_checking", "cant_confirm", "info"]
Trust = Literal["supported", "check", "unknown"]
ProductType = Literal["health_indemnity", "travel", "hospital_cash", "critical_illness", "personal_accident", "other"]

POLICY_DOC_URL = "/api/policy/document"


class Citation(BaseModel):
    docId: str = "policy"
    docName: str = "Policy wording"
    page: int
    clause: str
    quote: str
    docUrl: str | None = POLICY_DOC_URL


class Member(BaseModel):
    name: str
    relation: str
    age: int | None = None


class LimitFact(BaseModel):
    label: str
    amount: float | None = None
    unit: str | None = None
    citation: Citation | None = None


class WaitingPeriod(BaseModel):
    id: str
    label: str
    kind: Literal["initial", "specific", "ped"]
    duration: str
    startDate: str
    endDate: str
    appliesTo: str
    citation: Citation


class PolicyTrap(BaseModel):
    title: str
    explanation: str
    trust: Trust
    citation: Citation


class PolicyFlag(BaseModel):
    kind: Literal["missing_pages", "outdated", "ambiguous"]
    message: str
    citation: Citation | None = None
    code: str | None = None


class PolicyFacts(BaseModel):
    policyId: str
    insurer: str
    planName: str
    policyNumber: str
    policyType: str
    sumInsured: float
    startDate: str
    renewalDate: str
    pageCount: int
    members: list[Member]
    roomRent: LimitFact
    coPay: LimitFact
    deductible: LimitFact
    subLimits: list[LimitFact]
    waitingPeriods: list[WaitingPeriod]
    traps: list[PolicyTrap]
    flags: list[PolicyFlag]
    productType: ProductType = "health_indemnity"
    productNote: str | None = None
    isGroupPolicy: bool = False
    userProvided: list[str] = []


class MemberInput(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    relation: str = Field(min_length=1, max_length=30)
    age: int | None = Field(default=None, ge=0, le=120)


class PolicyDetailsInput(BaseModel):
    """Details from the policy schedule that a policy wording usually doesn't contain."""
    startDate: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    sumInsured: float | None = Field(default=None, gt=0, le=100_000_000)
    roomRentPerDay: float | None = Field(default=None, gt=0, le=1_000_000)
    policyNumber: str | None = Field(default=None, max_length=40)
    members: list[MemberInput] | None = Field(default=None, max_length=10)


class AgentStep(BaseModel):
    agent: str
    label: str


class NextAction(BaseModel):
    label: str
    route: str


class AnswerCard(BaseModel):
    verdict: Verdict
    headline: str
    summary: str
    citations: list[Citation]
    toConfirm: list[str]
    nextAction: NextAction | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)


class AskResponse(BaseModel):
    steps: list[AgentStep]
    answer: AnswerCard


class UploadResult(BaseModel):
    detectedType: str
    pages: int
    policyId: str | None = None
    reused: bool = False
    message: str | None = None
