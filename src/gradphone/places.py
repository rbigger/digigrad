"""Business lookup for the assistant-mode voice agent, via Google Places.

When the caller asks the agent to *call* a business ("find a cafe near my
hotel and call the best one"), the agent needs a real, dialable phone number —
not a prose web-search answer. Linkup (web_search) reliably finds *which*
business but often returns no usable number. Google Places Text Search (New)
returns structured results with a verified ``internationalPhoneNumber`` and a
rating in a single fast call (~hundreds of ms), which is exactly what
``place_call`` needs.

Set in .env:
    GOOGLE_PLACES_API_KEY=your-api-key   (enable "Places API (New)")

find_businesses() returns a ranked list of candidates (name, address, rating,
phone in E.164), or raises PlacesNotConfigured / PlacesError so the caller can
tell the model the lookup isn't available rather than crashing the call.

The HTTP call is synchronous (stdlib urllib), so the bridge runs it via
asyncio.to_thread under a timeout — same pattern as web_search.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

_ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
# Only the fields we need — a tight field mask keeps the call cheap and fast.
_FIELD_MASK = (
    "places.displayName,places.formattedAddress,places.rating,"
    "places.userRatingCount,places.internationalPhoneNumber,"
    "places.nationalPhoneNumber,places.businessStatus"
)
_MAX_RESULTS = 5
_TIMEOUT = 8.0


class PlacesNotConfigured(RuntimeError):
    """GOOGLE_PLACES_API_KEY not set."""


class PlacesError(RuntimeError):
    """Google Places request failed."""


def available() -> bool:
    """True when Google Places is configured (a key is present)."""
    return bool(os.environ.get("GOOGLE_PLACES_API_KEY", "").strip())


def _to_e164(raw: str) -> str:
    """Google returns e.g. '+1 650-483-3368'; strip to strict E.164 (+digits)."""
    raw = raw or ""
    digits = "".join(ch for ch in raw if ch.isdigit())
    return "+" + digits if digits else ""


def find_businesses(query: str, max_results: int = _MAX_RESULTS) -> list[dict]:
    """Run a Google Places text search and return ranked candidates.

    Each candidate: {"name", "address", "rating", "rating_count", "phone"}
    where ``phone`` is E.164 (or "" if Google has none). Results are sorted by
    rating (desc), with phone-bearing places first so "call the best one" lands
    on something dialable.

    Raises PlacesNotConfigured if the key is missing, PlacesError on any
    request/parse failure.
    """
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
    if not api_key:
        raise PlacesNotConfigured("GOOGLE_PLACES_API_KEY not set — places lookup is not configured.")

    query = (query or "").strip()
    if not query:
        raise PlacesError("Empty places query.")

    body = json.dumps({"textQuery": query, "maxResultCount": max(1, min(max_results, 20))}).encode()
    req = urllib.request.Request(
        _ENDPOINT,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": _FIELD_MASK,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        log.warning("places search HTTP %s: %s", exc.code, detail)
        raise PlacesError(f"Google Places HTTP {exc.code}") from exc
    except Exception as exc:  # noqa: BLE001 - network/parse
        log.warning("places search failed: %s", exc)
        raise PlacesError(f"Google Places search failed: {exc}") from exc

    out: list[dict] = []
    for p in data.get("places", []):
        name = ((p.get("displayName") or {}).get("text") or "").strip()
        phone = _to_e164(p.get("internationalPhoneNumber") or "")
        if not name:
            continue
        out.append({
            "name": name[:120],
            "address": (p.get("formattedAddress") or "")[:200],
            "rating": p.get("rating"),
            "rating_count": p.get("userRatingCount"),
            "phone": phone,
        })
    # Highest-rated first, but keep dialable (has phone) places ahead of those
    # Google has no number for — "call the best one" should reach something.
    out.sort(key=lambda c: (c["phone"] != "", c["rating"] or 0), reverse=True)
    return out[:max_results]
