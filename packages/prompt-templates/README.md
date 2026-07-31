# VVF prompt templates

Research, validation, and script prompt templates used by the discovery worker
and the MoneyPrinterTurbo adapter. Kept as plain text so they can be versioned
and audited alongside the content policy.

## Files

| File | Purpose |
| --- | --- |
| `research.txt`     | Shapes query variations and candidate framing from a keyword |
| `validation.txt`   | Grounds LLM claims against stored source excerpts |
| `script.txt`       | Produces a 9:16 short-video script (hook + body + CTA) |

Templates use simple `{keyword}`, `{language}`, `{facts}`, `{sources}` placeholders.
