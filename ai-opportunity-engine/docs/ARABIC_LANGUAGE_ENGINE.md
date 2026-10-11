# docs/ARABIC_LANGUAGE_ENGINE.md

`arabic_lang.py`: language ∈ {ar, en, unknown}; Arabizi (latin-script Arabic) → ar/arabizi
via digit-words (3/7/2/5) + ≥2 known words or ≥3 known words — plain English stays en.
Dialects: egyptian, gulf, levantine, iraqi, maghrebi, sudanese, msa. Each needs
≥2 DISTINCT boundary-safe markers (Arabic punctuation ،؛؟ handled as separators);
shared words (مش، يعني، ليش…) can never decide alone; ties impossible by construction
(first max wins, needs 2+). Mixed ar/en lowers confidence. Stored: normalized.dialect,
normalized.lang_confidence; raw_requests.language upgraded (Arabizi now ar, was en).

`region.py`: 19-region gazetteer (Arabic + English + demonyms at medium confidence),
boundary-safe, orthography-normalized. Bare عمان → Unknown (ambiguous) unless
Jordan/Oman context disambiguates. Stored: explicit_region, region_evidence,
region_confidence. Invariant (tested): Egyptian-dialect text with no place → Unknown.
