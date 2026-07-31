"""wigolo integration client and result mapper."""

from vvf_wigolo.client import (
    MockWigoloClient,
    WigoloClient,
    WigoloClientProtocol,
    WigoloSearchHit,
    WigoloSearchResult,
)
from vvf_wigolo.mapper import canonicalize_url, normalize_search_results

__all__ = [
    "MockWigoloClient",
    "WigoloClient",
    "WigoloClientProtocol",
    "WigoloSearchHit",
    "WigoloSearchResult",
    "canonicalize_url",
    "normalize_search_results",
]
