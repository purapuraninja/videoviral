"""wigolo integration client and result mapper."""

from vvf_wigolo.client import (
    MockWigoloClient,
    WigoloClient,
    WigoloClientProtocol,
    WigoloError,
    WigoloSearchHit,
    WigoloSearchResult,
    hit_from_result,
)
from vvf_wigolo.mapper import canonicalize_url, normalize_search_results

__all__ = [
    "MockWigoloClient",
    "WigoloClient",
    "WigoloClientProtocol",
    "WigoloError",
    "WigoloSearchHit",
    "WigoloSearchResult",
    "canonicalize_url",
    "hit_from_result",
    "normalize_search_results",
]
