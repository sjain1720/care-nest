# CareNest development order and verification

Current pass: 13–14 October 2026. Read `REPO_MAP.md` for navigation, then this queue.
The earlier merge fixes are committed in `6ce5542`; the older handoff's statement
that they are uncommitted is now historical. Status below is updated at release.

## Ordered work

| Order | Application task | Current state / completion gate |
|---|---|---|
| 1 | Compact AI repository navigation | Added root `AGENTS.md`, feature map and dependency-free `scripts/repo-map.py`. Query by path, symbol or endpoint; bounded output avoids loading whole folders. |
| 2 | Guest identity, ownership and deletion | Implemented server-issued Firestore registry, fixed seven-day expiry, revocation and session-scoped private policy IDs. Deletion traverses policy subcollections and removes originals plus claims. Synthetic demo templates remain shared. 112 tests pass, including forged/expired identity and two-guest SSE isolation checks. Daily cleanup verified against a disposable expired guest: identity, selection, case, past claims, policy, pages, clauses and both Storage prefixes were removed. |
| 3 | Honest mock/live AI demo | Settings now has a real-AI sample action. Backend reports fictional live context; header distinguishes it. Guest deletion is available in settings. Build passes. Demo loading replaces policy choice and merges sample documents into the current guest claim, so use an empty guest for the judging run. |
| 4 | Deploy and verify synthetic complete workflow | Deploy source, configure daily cleanup job, run `scripts/verify-release.py --full`, inspect browser. Completed: deployed revision and synthetic verification recorded below. |
| 5 | Evidence-backed bill-to-policy analysis | Next feature: map bill rows to selected clauses and show source pages, assumptions and missing facts. Current rules/estimates are useful but do not prove every coverage conclusion. |
| 6 | Reliable coverage and follow-up context | Move balance calculation to typed backend; associate claim ledger with policy and completeness state. Add bounded follow-up conversation context and test policy switches. |
| 7 | Quality evaluation and dependency triage | Review 20–30 representative questions across unseen policies. Measure retrieval recall, semantic answer support, arithmetic, abstention, latency and cost. Triage dependency audit paths with compatible fixes. |
| 8 | Small fine-tuning comparison | Recheck local synthetic checkpoints, finish validation and human review, estimate cost, then compare against untuned retrieval. No trained/deployed custom model is currently claimed. |

## Test strategy for a hackathon

Tests should protect the demo and evidence, not maximize a count. Keep fast tests
for API/service compatibility (the merge previously broke chat), guest isolation,
payment arithmetic, waiting dates, source verification and unsupported answers.
Use mocks for cloud calls here: these checks run in well under a second and use
no model credits. They cannot establish actual cloud/model behavior.

Use one repeatable real-cloud check after a meaningful release:

```sh
backend/.venv/bin/python scripts/verify-release.py \
  --url https://carenest-17055771987.asia-south1.run.app --full \
  --bill-image /path/to/synthetic-bill.png
```

The optional image fixture must contain the known synthetic total ₹17,250.
The script creates independent visitors, checks general/personal routing, loads
synthetic demo PDFs, checks policy citations, reviews an unseen bill image,
generates a draft, checks cross-visitor document access and deletes its guests.
It prints no bearer tokens. Reports go to ignored `eval/results/`.
Without `--full`, only the basic API/routing/session checks run; this still calls
Gemini for two answers. Full runs incur OCR/extraction/QA charges and should not
be repeated for CSS-only edits.

For UI polish, production build plus desktop/phone browser inspection is enough.
A three-minute recorded demo and a prepared synthetic fallback are useful
complements. Manual checks are acceptable, but record the input and expected
result so another person can reproduce them.

## Retention design

The registry `guestSessions/{sid}` authenticates a random bearer cookie and stores
its fixed `expiresAt`. Expired/revoked/unissued identities get a new empty guest.
`sessions/{sid}` holds selection/schedule, `cases/{sid}` and `pastClaims` hold
claims. Private policy IDs include the guest scope; their root `ownerSessionId`
allows cleanup of every uploaded policy, not just the active one.

`app.cleanup` is a daily Cloud Run job invoked by Cloud Scheduler at 03:00 India
time. It revokes access first, recursively removes owned policy pages/clauses,
deletes originals and guest claim blobs, deletes session state, then removes the
registry identity. Failed deletions retain a revoked record for retry. This uses
explicit graph cleanup rather than relying on Firestore TTL to cascade (it does
not cascade). Service failures can delay cleanup beyond its normal next-day run.
No guaranteed deletion claim should be made while job execution is unverified.

Legacy policies and sessions from older deployed revisions have no ownership
registry. They require a separate inventory/migration decision; do not blindly
delete unowned records. These IDs are not accepted as issued new-session cookies.
The expiry gate is checked at request start; an already-running AI operation can
outlive expiry. Additional race protection for deletion during an in-flight upload
remains to be hardened before private multiuser use.

## Release evidence

Deployed revision: `carenest-00004-dqk`, serving 100% traffic.
Scheduler is enabled at 03:00 Asia/Kolkata; execution
`carenest-guest-cleanup-gztn6` succeeded and the nine cleanup checks passed.
The deployed settings page was inspected in the browser. Full synthetic AI
workflow passed 33 checks: two cookie jars, general/personal routing,
shared fictional context, page-7 policy citation, unseen bill image totaling
₹17,250, reviewed recomputation, editable draft, cross-visitor file refusal,
private policy upload/context change, streaming guarantee refusal and guest
deletion. Reports remain local in ignored `eval/results/`. Unit tests and build success are not evidence
of semantic AI accuracy or complete production readiness.

## Remaining limits before a broader private-data trial

- Inventory legacy unowned data, and harden deletion during an in-flight upload.
- Add a clean first-visit choice screen and an explicit reset/cloning flow for the live demo.
- Browser verification covered deployed settings; a full desktop/phone matrix and
  backup judging video remain.
- Current bill photos are interpreted directly by Gemini; policy PDFs use Document
  AI OCR. Do not claim Document AI runs on every explicitly typed bill image.
- No semantic accuracy score, successful fine-tuning experiment or exhaustive
  security guarantee is established by these smoke checks.
