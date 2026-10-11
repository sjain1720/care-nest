"""Gemini reads bills and settlement letters straight from the PDF (page images), which copes with scans and handwriting."""
from typing import Literal

from google.genai import types
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.gcp import gemini

Category = Literal["room", "icu", "nursing", "doctor", "surgery", "anaesthesia", "procedure", "pharmacy", "consumables",
                   "implants", "investigations", "equipment", "food", "admin", "other"]


class BillItemOut(BaseModel):
    description: str
    category: Category
    amount: float
    rate: float | None = None
    qty: float | None = None
    page: int
    date: str | None = None


class PageMarker(BaseModel):
    pdfPage: int
    printedPage: int | None = None
    printedTotal: int | None = None


class BillOut(BaseModel):
    hospital: str | None = None
    billNumber: str | None = None
    billDate: str | None = None
    patientName: str | None = None
    patientAge: int | None = None
    admissionDate: str | None = None
    dischargeDate: str | None = None
    roomCategory: str | None = None
    diagnosis: str | None = None
    payer: str | None = None
    items: list[BillItemOut] = []
    statedTotal: float | None = None
    discount: float | None = None
    tax: float | None = None
    pageMarkers: list[PageMarker] = []
    unreadableLines: int = 0


class DeductionOut(BaseModel):
    label: str
    amount: float
    insurerReason: str
    page: int


class SettlementOut(BaseModel):
    letterType: Literal["settlement", "rejection", "query", "other"] = "settlement"
    insurer: str | None = None
    claimNumber: str | None = None
    letterDate: str | None = None
    patientName: str | None = None
    claimedAmount: float | None = None
    approvedAmount: float | None = None
    deductions: list[DeductionOut] = []
    rejectionReason: str | None = None
    rejectionReasonPage: int | None = None


BILL_PROMPT = """This PDF is an Indian hospital or pharmacy bill (it may be scanned, photographed or handwritten).
Extract it as JSON. Rules:
- items: every individual charge line, NOT subtotals, section totals or the grand total. Copy the description as printed.
  amount, rate and qty are plain numbers in rupees (no commas). page = page number within THIS PDF (first page = 1).
- category: room (ward/room/bed charges), icu, nursing, doctor (visits/consultations), surgery (surgeon/OT), anaesthesia,
  procedure, pharmacy (medicines/drugs), consumables, implants, investigations (lab/radiology/scans), equipment
  (monitors/ventilator/oxygen), food, admin (registration/documentation/service), other.
- For room/ICU lines give rate per day and qty = number of days when shown.
- statedTotal: the bill's grand total before payments/advances. discount and tax only if printed separately.
- pageMarkers: for each PDF page, any printed "Page X of N" / "X/N" (printedPage = X, printedTotal = N).
- Dates as YYYY-MM-DD. patientName and patientAge only; do NOT copy addresses, phone numbers or ID numbers.
- If a line's amount cannot be read, skip it and count it in unreadableLines. Never invent numbers."""

SETTLEMENT_PROMPT = """This PDF is a letter from an Indian health insurer or TPA (settlement, rejection or query).
Extract it as JSON. Rules:
- letterType: settlement (payment with or without deductions), rejection (claim denied), query (asks for documents), other.
- claimedAmount, approvedAmount and each deduction amount as plain numbers in rupees.
- deductions: every deducted / disallowed / non-payable row. insurerReason = the remark exactly as printed, or "-" if none.
- rejectionReason (rejection letters only): the reason given, copied as printed, and the page it is on.
- Dates as YYYY-MM-DD. Do NOT copy addresses, phone numbers or ID numbers. Never invent numbers."""


def _read_pdf(pdf_bytes: bytes, prompt: str, schema: type[BaseModel]) -> BaseModel:
    response = gemini().models.generate_content(
        model=get_settings().gemini_model,
        contents=[types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"), prompt],
        config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema,
                                           temperature=0, max_output_tokens=32768),
    )
    return response.parsed if isinstance(response.parsed, schema) else schema.model_validate_json(response.text)


def extract_bill(pdf_bytes: bytes) -> BillOut:
    return _read_pdf(pdf_bytes, BILL_PROMPT, BillOut)


def extract_settlement(pdf_bytes: bytes) -> SettlementOut:
    return _read_pdf(pdf_bytes, SETTLEMENT_PROMPT, SettlementOut)
