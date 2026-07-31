# Content policy

Every video the factory produces must be source-backed and safe. This document
captures the rules in IMPLEMENTATION_PLAN.md §12.

## Provenance

- Every output has a provenance manifest: candidate, sources, timestamps,
  model settings, script, and asset sources.
- All LLM-produced claims must be grounded in stored source excerpts. Display
  source links and captured factual excerpts to the administrator.
- Raw normalized results are always persisted; never rely solely on an LLM
  summary.

## Risk flags

Flag content involving:

- violence
- minors
- medical claims
- legal claims
- financial claims
- political misinformation
- copyright risk
- unverified breaking news

Flagged candidates still appear for review but require explicit admin approval
(which is mandatory for every render in MVP).

## Domain controls

- Maintain a blocked-domain list (configured in `source_filters.blocked_domains`).
- Optional allowed-domain allowlist (`source_filters.allowed_domains`).
- Filter by language, date (within `period_days`), and minimum source quality.

## Approval gate

- Admin approval is **mandatory** before any expensive rendering begins.
- No automatic rendering without approval (MVP non-goal).
- No automatic publishing to TikTok/Instagram/YouTube (MVP non-goal).
