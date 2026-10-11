"""Items that insurers commonly refuse to pay, based on IRDAI's standard list of non-payable items (List I).

Matches are only "possibly not payable": a policy add-on (e.g. consumables cover) or the insurer's decision can differ.
"""
import re

# (pattern, plain name). Word boundaries avoid false hits such as "comb" in "combination".
_ITEMS = [
    (r"\bgloves?\b", "Gloves"),
    (r"\bppe\b|personal protective", "PPE kit"),
    (r"\b(face )?masks?\b(?! ventilation)", "Mask"),
    (r"admission kit|admission pack", "Admission kit"),
    (r"registration (fee|charge)", "Registration charges"),
    (r"admission (fee|charge)", "Admission charges"),
    (r"documentation (fee|charge)|medical records? (fee|charge)", "Documentation charges"),
    (r"toiletr|toothpaste|tooth ?brush|\bsoap\b|shampoo", "Toiletries"),
    (r"\bdiapers?\b", "Diapers"),
    (r"sanitary (pad|napkin)", "Sanitary pads"),
    (r"attendant", "Attendant charges"),
    (r"telephone|\btv\b|television", "Telephone / TV charges"),
    (r"laundry|washing charge", "Laundry"),
    (r"slippers?", "Slippers"),
    (r"\bcombs?\b", "Comb"),
    (r"tissue paper|\btissues?\b", "Tissue paper"),
    (r"baby food|\bcerelac\b", "Baby food"),
    (r"thermometer", "Thermometer"),
    (r"service charge", "Service charges"),
    (r"courier", "Courier charges"),
    (r"\bfood\b.*(attendant|relative|visitor)|(attendant|relative|visitor).*\bfood\b", "Food for attendant"),
]
_COMPILED = [(re.compile(p, re.IGNORECASE), name) for p, name in _ITEMS]


def match_non_payable(description: str) -> str | None:
    """Plain name of the non-payable item the description matches, or None."""
    for pattern, name in _COMPILED:
        if pattern.search(description):
            return name
    return None
