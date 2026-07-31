# wigolo integration

Adapter around [wigolo](https://github.com/KnockOutEZ/wigolo), a local-first
web search/fetch/crawl/research service exposed over an MCP HTTP transport.

The VPS only ever talks to wigolo through this package; the upstream codebase is
**never** modified (AGPL-3.0).

## Operations

| Operation | wigolo tool | Purpose |
| --- | --- | --- |
| `search`   | `tools/call search`   | Run query variations in parallel |
| `fetch`    | `tools/call fetch`    | Retrieve selected pages |
| `extract`  | `tools/call extract`  | Extract article metadata + structured content |
| `cache`    | (implicit, wigolo-side) | Prevent repeated work for the same keyword |

## Usage

```python
from vvf_wigolo import WigoloClient, MockWigoloClient, normalize_search_results

client = MockWigoloClient()              # or WigoloClient() against the live service
result = client.search("gempa bali terkini", language="id-ID")
sources = normalize_search_results(result)
```

Raw normalized results are persisted to `source_documents`; LLM summaries are
never the sole source of truth.
