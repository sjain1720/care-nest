"""API response models. They mirror frontend/src/app/models/models.ts – keep both in sync."""
from __future__ import annotations
from typing import Literal
from datetime import date

from pydantic import BaseModel, Field, field_validator
import unicodedata

Verdict = Literal["covered", "partial", "not_covered", "needs_checking", "cant_confirm", "info"]
Trust = Literal["supported", "check", "unknown"]
ProductType = Literal["health_indemnity", "travel", "hospital_cash", "critical_illness", "personal_accident", "other"]
BillCategory = Literal["room", "icu", "nursing", "doctor", "surgery", "anaesthesia", "procedure", "pharmacy", "consumables",
                       "implants", "investigations", "equipment", "food", "admin", "other"]
_ISO_DATE = r"^\d{4}-\d{2}-\d{2}$"

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
    demoAssumptions: list[str] = []
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


class AnswerCheck(BaseModel):
    kind: Literal['source', 'quote', 'support', 'dates', 'treatment']
    status: Literal['passed', 'not_confirmed', 'not_run']
    label: str
    detail: str


class WaitingDateEvidence(BaseModel):
    periodId: str
    label: str
    duration: str
    startDate: str
    startDateOrigin: str
    comparisonDate: str
    endDate: str
    periodEnded: bool
    daysRemaining: int
    citation: Citation


class WaitingTreatmentEvidence(BaseModel):
    periodId: str
    treatment: str
    ruleCitation: Citation
    listCitation: Citation
    conditionCitation: Citation | None = None


class AnswerVerification(BaseModel):
    policyId: str
    policyName: str
    scope: Literal['explanation', 'timing_only'] = 'explanation'
    checks: list[AnswerCheck]
    dates: list[WaitingDateEvidence] = Field(default_factory=list)
    treatment: WaitingTreatmentEvidence | None = None
    missingInputs: list[str] = Field(default_factory=list)
    qualification: str = 'These checks support the explanation. They do not confirm coverage or claim approval.'


class AnswerCard(BaseModel):
    verdict: Verdict
    headline: str
    summary: str
    citations: list[Citation]
    toConfirm: list[str]
    nextAction: NextAction | None = None
    secondaryAction: NextAction | None = None
    # True when the answer comes from general insurance knowledge, not the user's own documents.
    general: bool = False
    investigation: DisputeReview | None = None
    # Server-authored evidence; never accepted from a model's answer JSON.
    verification: AnswerVerification | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    language: Literal["en", "hi"] = "en"
    conversationId: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{8,64}$")
    generalOnly: bool = False


class ChecklistUpdate(BaseModel):
    status: Literal["collected", "missing", "requested"]


class QueryHelpRequest(BaseModel):
    queryText: str = Field(min_length=10, max_length=3000)


class TimelineEventIn(BaseModel):
    """Something the family did: sent the claim or a letter, answered a query, filed a complaint, or closed the claim."""
    kind: Literal["claim_sent", "letter_sent", "query_answered", "complaint_filed", "closed"]
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    letterKind: Literal["clarification", "reconsideration", "grievance", "cover_letter"] | None = None
    level: int | None = Field(default=None, ge=1, le=3)
    reference: str | None = Field(default=None, max_length=60)
    note: str | None = Field(default=None, max_length=300)


class ReplyRequest(BaseModel):
    """The insurer's reply, pasted from an email or letter."""
    text: str = Field(min_length=20, max_length=6000)


class BillReviewItem(BaseModel):
    description: str = Field(min_length=1, max_length=200)
    category: BillCategory
    amount: float = Field(ge=0, le=100_000_000)
    rate: float | None = Field(default=None, ge=0, le=100_000_000)
    qty: float | None = Field(default=None, ge=0, le=10_000)
    page: int = Field(default=1, ge=1, le=500)
    date: str | None = Field(default=None, pattern=_ISO_DATE)


class BillReviewIn(BaseModel):
    """What the family checked or corrected from the bill reading, before anything is worked out from it."""
    hospital: str | None = Field(default=None, max_length=120)
    billNumber: str | None = Field(default=None, max_length=60)
    billDate: str | None = Field(default=None, pattern=_ISO_DATE)
    patientName: str | None = Field(default=None, max_length=60)
    admissionDate: str | None = Field(default=None, pattern=_ISO_DATE)
    dischargeDate: str | None = Field(default=None, pattern=_ISO_DATE)
    statedTotal: float | None = Field(default=None, ge=0, le=100_000_000)
    items: list[BillReviewItem] = Field(max_length=400)


class PastClaimIn(BaseModel):
    """A claim made before using CareNest, typed in from the insurer's payment letter."""
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    approvedAmount: float = Field(ge=0, le=100_000_000)
    claimedAmount: float | None = Field(default=None, gt=0, le=100_000_000)
    title: str | None = Field(default=None, max_length=80)
    patient: str | None = Field(default=None, max_length=60)
    hospital: str | None = Field(default=None, max_length=80)
    claimNumber: str | None = Field(default=None, max_length=40)


class AskResponse(BaseModel):
    steps: list[AgentStep]
    answer: AnswerCard


class UploadResult(BaseModel):
    detectedType: str
    pages: int
    policyId: str | None = None
    reused: bool = False
    message: str | None = None


class CoverageClaim(BaseModel):
    id: str
    title: str = ''
    date: str = ''
    approvedAmount: float | None = None


class CoverageExcluded(BaseModel):
    id: str
    reason: str


class CoverageYear(BaseModel):
    from_: str = Field(alias='from')
    to: str


class CoverageEstimate(BaseModel):
    status: Literal['missing_policy', 'missing_sum_insured', 'missing_start_date', 'not_started', 'unsupported_product', 'recorded_only']
    policyId: str | None
    asOf: str
    year: CoverageYear | None
    sumInsured: float | None
    used: float | None
    remaining: float | None
    pct: int | None
    counted: list[CoverageClaim]
    excluded: list[CoverageExcluded]
    pending: bool
    floater: bool
    demo: bool
    historyComplete: bool
    warnings: list[str]


class PreviewClaim(BaseModel):
    id: str = Field(max_length=100)
    title: str = Field(default='', max_length=200)
    policyId: str | None = Field(default=None, max_length=100)
    date: str = Field(default='', max_length=10)
    approvedAmount: float | None = Field(default=None, ge=0, le=100_000_000, allow_inf_nan=False)
    status: Literal['paid', 'part_paid', 'refused', 'in_progress']
    claimNumber: str = Field(default='', max_length=100)


class CoveragePreviewInput(BaseModel):
    policy: PolicyFacts
    claims: list[PreviewClaim] = Field(max_length=200)


class DisputeInputIssue(BaseModel):
    code: str
    message: str
    route: str


class DisputeReconciliation(BaseModel):
    claimedAmount: float
    approvedAmount: float
    decisionDifference: float
    itemizedDeductions: float
    unexplainedGap: float
    arithmeticOk: bool


class DisputePreparation(BaseModel):
    status: Literal['needs_inputs', 'ready_for_review']
    decision: Literal['none', 'settlement', 'rejection', 'conflicting']
    availableDocuments: list[str]
    missingInputs: list[DisputeInputIssue]
    warnings: list[str]
    reconciliation: DisputeReconciliation | None = None
    deductionsWithoutReason: list[str]


class DisputeReviewRow(BaseModel):
    id: str
    label: str
    amount: float | None = None
    insurerReason: str
    assessment: Literal['related_wording', 'needs_information', 'no_stated_reason', 'unverified']
    explanation: str
    citations: list[Citation]
    missingInformation: list[str]
    evidence: dict | None = None


class DisputeReview(BaseModel):
    status: Literal['needs_inputs', 'reviewed', 'unavailable', 'stale']
    engine: Literal['adk_investigation'] = 'adk_investigation'
    preparation: DisputePreparation
    metrics: dict = Field(default_factory=dict)
    actions: list[dict] = Field(default_factory=list)
    rows: list[DisputeReviewRow] = Field(default_factory=list)
    steps: list[AgentStep] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TreatmentPlanInput(BaseModel):
    procedure: str = Field(min_length=2, max_length=200)
    plannedAdmission: date | None = None
    normalRoomRatePerDay: float | None = Field(default=None, gt=0, le=1_000_000, allow_inf_nan=False)


class PlannedWaitingPeriod(BaseModel):
    label: str
    appliesTo: str
    endDate: str | None = None
    dateStatus: Literal['ends_by_planned_date', 'running_on_planned_date', 'end_date_unknown', 'planned_date_missing']
    daysRemainingAtAdmission: int | None = None
    citation: Citation | None = None


class PlannedRoomRisk(BaseModel):
    status: Literal['above_recorded_limit', 'within_recorded_limit']
    recordedLimitPerDay: float
    proposedRatePerDay: float
    dailyExcess: float
    citation: Citation | None = None


class TreatmentPlanPreparation(BaseModel):
    status: Literal['needs_policy', 'prepared']
    engine: Literal['backend_calculations'] = 'backend_calculations'
    procedure: str
    plannedAdmission: str | None = None
    waitingPeriods: list[PlannedWaitingPeriod] = Field(default_factory=list)
    roomRisk: PlannedRoomRisk | None = None
    coPay: LimitFact | None = None
    deductible: LimitFact | None = None
    questionsToConfirm: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


AnswerCard.model_rebuild()


class DisplayNameInput(BaseModel):
    displayName: str = Field(min_length=1, max_length=60)

    @field_validator('displayName')
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if not value or any(unicodedata.category(c).startswith('C') or c in '<>' for c in value):
            raise ValueError('Enter a name or nickname without markup or control characters.')
        return value


class VisitorProfile(BaseModel):
    displayName: str | None = None
    expiresAt: str
