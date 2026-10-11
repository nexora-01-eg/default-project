# docs/OPPORTUNITY_VALIDATION.md — methodology (Phase 3.5)

## Principle

Embedding similarity alone never creates or sustains an opportunity. Every pair must
also pass the cross-domain guard; every opportunity carries an explicit validation
state. Reclassification writes validation_* columns only — members, requests, scores,
feedback are never deleted.

## Guard (`domains.py`)

Canonical signature per request: problem domains (12-class AR/EN taxonomy with Arabic
morphological stemming, e.g. video/plural forms collapse), request-type family (ai vs
human), tech entities. Pair verdicts: `pass` (PRIMARY domain overlap/compat; primary
means translation/design/video/software_dev/ai_ml/data), `flagged` (disjoint primaries,
actively disagreeing secondary signals, ai-vs-human mismatch), `unknown-domain`
(linked-only or silent sides: group only if similarity at least 0.85). Secondary
domains support but never decide: a shared incidental word cannot group a catalog
request with a book translation. Shared entities are supporting evidence only.

## States (`validation.py`)

SINGLE_OBSERVATION (n=1, decent evidence) · REPEATED_SAME_AUTHOR (n>1, one author) ·
INDEPENDENT_DEMAND (≥2 independent, one source) · CROSS_SOURCE_DEMAND (≥2 independent,
≥2 sources) · VALIDATED_OPPORTUNITY (cross/independent + high/medium revenue + problem
≥60 chars + feasible + gap-or-solutions) · SPURIOUS_MATCH (guard leaves <2 coherent
members) · INSUFFICIENT_EVIDENCE (empty, or weak+unknown-revenue).

Stored per opportunity: validation_state, validation_reason, independent_evidence_count,
independent_source_count, same_problem_count, cross_domain_guard (full pair detail).

## Cross-evidence sweep

Every high-intent Arabic request is searched across ALL sources (guard must not flag,
similarity ≥ threshold, same author excluded). Real matches attach as
`cross-evidence` rows; absence attaches nothing. Counts reported per run.

## Reclassification ledger (2026-09-23, evidence preserved)

#1 REPEATED_SAME_AUTHOR (clubanderson ×2) · #2 INDEPENDENT_DEMAND but human-rejected
(status untouched — validation describes, humans decide) · #3 INDEPENDENT_DEMAND
(genuine pair) · #4 SPURIOUS_MATCH (translation vs religious_content, same_problem=1) ·
#5/#6 REPEATED_SAME_AUTHOR.

## FIRST-MONEY view

Shows only: not archived/rejected, not spurious/insufficient, high/medium intent,
problem ≥40 chars, feasible, AI-relevant members, public source URL. Singles included
with SINGLE_OBSERVATION badge. Actions reuse feedback decisions (Investigate / Build /
Contact manually / Ignore). No sending capability exists anywhere.
