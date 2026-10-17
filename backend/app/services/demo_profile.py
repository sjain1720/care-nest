"""Explicit fictional selections; these are never represented as insurer-issued facts."""
POLICY_SHA256 = '0bd43987c8812a866229f93c6f238b9b9f67de5810b4fb520e503c600b0313fc'
DEMO_DETAILS = {
    'startDate': '2024-03-12', 'sumInsured': 1000000, 'roomRentPerDay': 2500,
    'policyNumber': 'DEMO-KOTAK-1000000',
    'members': [{'name': 'Shubham Sharma', 'relation': 'Self', 'age': 32},
                {'name': 'Mohan Sharma', 'relation': 'Father', 'age': 62},
                {'name': 'Kamala Sharma', 'relation': 'Mother', 'age': 58}],
}
DEMO_ASSUMPTIONS = [
    'Fictional demonstration inputs, not an insurer-issued schedule or certificate.',
    'Rs. 10,00,000 family floater; continuous renewal from 12 March 2024; current renewal 12 March 2026 to 11 March 2027.',
    'Benefit 13 (room cap WITH proportionate deduction) is selected for this fictional example; benefit 14 is the alternative, not selected here.',
    'Normal-room eligibility is assumed at Rs. 2,500/day. No optional co-pay or deductible is selected in this fictional example.',
    'Kamala is assumed enrolled as Shubham’s mother; pages 6 and 29 allow this relationship, but actual enrollment requires the issued certificate.',
    'Original Kotak wording and its exclusions/exceptions still apply. Neither a matching amount nor a related clause establishes claim approval.',
]


def apply_demo_selections(facts: dict, notes: list[str]) -> dict:
    """Called only for an owned demo-marked session and a public demo policy."""
    amount = facts['roomRent'].get('amount')
    room = {**facts['roomRent'], 'label': f'Rs. {amount:,.0f}/day normal room (fictional selected schedule limit)' if amount is not None else 'Normal room limit not supplied',
            'amount': amount, 'unit': 'per day'}
    return {**facts, 'demoAssumptions': notes, 'policyType': 'Group family floater (fictional selection)',
            'renewalDate': '2027-03-11', 'roomRent': room,
            'coPay': {'label': 'Not selected (fictional demo assumption)', 'amount': 0, 'unit': '%'},
            'deductible': {'label': 'Not selected (fictional demo assumption)', 'amount': 0, 'unit': 'INR'}}
