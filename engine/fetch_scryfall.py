#!/usr/bin/env python3
"""Fetch card data from the Scryfall API.

Scryfall is free, no auth required. Rate limit: 50-100ms between requests.
Results are cached locally in .scryfall_cache/ to avoid hammering the API.
Docs: https://scryfall.com/docs/api

Usage:
    python engine/fetch_scryfall.py "Aesi, Tyrant of Gyre Strait"
    python engine/fetch_scryfall.py --search "f:commander ci:UG t:creature o:landfall"
    python engine/fetch_scryfall.py --banned
    python engine/fetch_scryfall.py --validate-card "Sol Ring" --colors UG
"""
import argparse
import json
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SCRYFALL_BASE = "https://api.scryfall.com"
CACHE_DIR = pathlib.Path(__file__).resolve().parent.parent / ".scryfall_cache"
RATE_LIMIT = 0.1  # 100ms between requests

_last_request = 0.0
_HEADERS = {
    "User-Agent": "mtg-commander-builder/1.0",
    "Accept": "application/json",
}


def _get(url, params=None, _retries=3):
    global _last_request
    elapsed = time.time() - _last_request
    if elapsed < RATE_LIMIT:
        time.sleep(RATE_LIMIT - elapsed)
    full_url = f"{url}?{urllib.parse.urlencode(params)}" if params else url
    req = urllib.request.Request(full_url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            _last_request = time.time()
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 429 and _retries > 0:
            print("[scryfall] Rate limited — waiting 65s...", flush=True)
            time.sleep(65)
            return _get(url, params, _retries - 1)
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Scryfall HTTP {e.code}: {body[:200]}") from e


def _cache_path(key):
    CACHE_DIR.mkdir(exist_ok=True)
    safe = key.lower().replace(" ", "_").replace(",", "").replace("'", "")[:80]
    return CACHE_DIR / f"{safe}.json"


def _cached(key, fetch_fn):
    p = _cache_path(key)
    if p.exists():
        return json.loads(p.read_text())
    data = fetch_fn()
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return data


def card_by_name(name, fuzzy=True):
    """Fetch a single card by name. Returns the Scryfall card object or None."""
    key = f"card_{name}"
    try:
        return _cached(key, lambda: _get(
            f"{SCRYFALL_BASE}/cards/named",
            params={"fuzzy" if fuzzy else "exact": name}
        ))
    except (RuntimeError, urllib.error.URLError):
        return None


def search_cards(query, order="edhrec"):
    """Search Scryfall. Returns a list of card objects (auto-pages)."""
    results = []
    url = f"{SCRYFALL_BASE}/cards/search"
    params = {"q": query, "order": order}
    while url:
        data = _get(url, params=params)
        results.extend(data.get("data", []))
        url = data.get("next_page")
        params = None
    return results


def get_banned_list():
    """Return the set of Commander-banned card names (fetched live)."""
    p = _cache_path("commander_banned_list")
    if p.exists():
        return set(json.loads(p.read_text()))
    cards = search_cards("f:commander banned:commander")
    names = sorted({c["name"] for c in cards})
    CACHE_DIR.mkdir(exist_ok=True)
    p.write_text(json.dumps(names, ensure_ascii=False, indent=2))
    return set(names)


def color_identity_of(card_name):
    """Return the WUBRG color identity list for a card, or None if not found."""
    card = card_by_name(card_name)
    return card.get("color_identity") if card else None


def price_usd(card_name):
    """Return the cheapest USD price for a card (non-foil preferred), or None."""
    card = card_by_name(card_name)
    if not card:
        return None
    prices = card.get("prices", {})
    return prices.get("usd") or prices.get("usd_foil")


def is_legal_commander(card_name):
    """Return True if the card is legal in Commander format."""
    card = card_by_name(card_name)
    if not card:
        return None
    return card.get("legalities", {}).get("commander") == "legal"


def validate_card(card_name, commander_colors):
    """Check a card's legality and color identity fit for a commander.

    commander_colors: list of WUBRG letters the commander allows.
    Returns dict with keys: found, legal, color_ok, price, violations.
    """
    card = card_by_name(card_name)
    if not card:
        return {"found": False, "name": card_name}

    card_ci = set(card.get("color_identity", []))
    allowed = set(commander_colors)
    color_ok = card_ci.issubset(allowed)
    legal = card.get("legalities", {}).get("commander") == "legal"

    violations = []
    if not legal:
        violations.append("banned or not legal in Commander")
    if not color_ok:
        outside = card_ci - allowed
        violations.append(f"color identity {outside} outside commander identity {allowed}")

    return {
        "found": True,
        "name": card.get("name"),
        "legal": legal,
        "color_ok": color_ok,
        "color_identity": sorted(card_ci),
        "cmc": card.get("cmc", 0),
        "type_line": card.get("type_line", ""),
        "price": price_usd(card_name),
        "violations": violations,
    }


def search_from_url(url_or_query):
    """Accept a Scryfall search URL or raw query string and return card results.

    Handles:
      - Full URL: https://scryfall.com/search?q=e%3AMH3+ci%3AUG+order%3Aedhrec
      - API URL:  https://api.scryfall.com/cards/search?q=...
      - Raw query string: e:MH3 ci:UG order:edhrec
    """
    from urllib.parse import urlparse, parse_qs, unquote_plus

    raw = url_or_query.strip()

    if raw.startswith("http"):
        parsed = urlparse(raw)
        qs = parse_qs(parsed.query)
        query = qs.get("q", [None])[0]
        if not query:
            raise ValueError(f"No 'q' parameter found in URL: {raw!r}")
        order = qs.get("order", ["edhrec"])[0]
    else:
        # Treat the whole string as a Scryfall query
        query = raw
        order = "edhrec"

    print(f"[scryfall] Parsed query: {query!r}  order={order}", flush=True)
    return search_cards(query, order=order)


def commander_info(name):
    """Fetch and return key data for a potential commander card."""
    card = card_by_name(name)
    if not card:
        raise ValueError(f"Card '{name}' not found on Scryfall.")
    type_line = card.get("type_line", "")
    if "Legendary" not in type_line and "can be your commander" not in (card.get("oracle_text") or ""):
        raise ValueError(f"'{name}' is not a legendary creature or a valid commander.")
    return {
        "name": card["name"],
        "scryfall_id": card["id"],
        "color_identity": card.get("color_identity", []),
        "colors": card.get("colors", []),
        "type_line": type_line,
        "cmc": card.get("cmc", 0),
        "oracle_text": card.get("oracle_text", ""),
        "power": card.get("power"),
        "toughness": card.get("toughness"),
        "price_usd": price_usd(card["name"]),
        "scryfall_uri": card.get("scryfall_uri"),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Fetch Scryfall card data.")
    ap.add_argument("name", nargs="?", help="Card name to look up")
    ap.add_argument("--search", help="Scryfall search query or full scryfall.com URL")
    ap.add_argument("--url", metavar="URL_OR_QUERY",
                    help="Scryfall search URL (scryfall.com/search?q=...) or raw query string")
    ap.add_argument("--banned", action="store_true", help="Print the Commander banned list")
    ap.add_argument("--validate-card", metavar="NAME", help="Validate card legality")
    ap.add_argument("--colors", default="WUBRG", help="Commander color identity (e.g. UG)")
    args = ap.parse_args()

    if args.banned:
        banned = sorted(get_banned_list())
        print(f"Commander banned list ({len(banned)} cards):")
        for c in banned:
            print(f"  {c}")
    elif args.url:
        results = search_from_url(args.url)
        print(f"{len(results)} results")
        for c in results[:20]:
            ci = "".join(c.get("color_identity", []))
            price = (c.get("prices") or {}).get("usd", "?")
            print(f"  [{ci}] {c['name']:<34} CMC {c.get('cmc',0):<4} ${price}")
    elif args.search:
        results = search_cards(args.search)
        print(f"{len(results)} results for: {args.search}")
        for c in results[:20]:
            ci = "".join(c.get("color_identity", []))
            print(f"  [{ci}] {c['name']} — {c.get('type_line','')}")
    elif args.validate_card:
        result = validate_card(args.validate_card, list(args.colors.upper()))
        if not result.get("found"):
            print(f"NOT FOUND: {args.validate_card}", file=sys.stderr)
            sys.exit(1)
        status = "OK" if not result["violations"] else "FAIL"
        print(f"[{status}] {result['name']} | CMC {result['cmc']} | ${result['price'] or '?'}")
        for v in result["violations"]:
            print(f"  !! {v}")
    elif args.name:
        try:
            info = commander_info(args.name)
            print(f"{info['name']}")
            print(f"  Colors: {''.join(info['color_identity'])}")
            print(f"  CMC: {info['cmc']}")
            print(f"  Type: {info['type_line']}")
            print(f"  Price: ${info['price_usd'] or '?'}")
            print(f"  Text: {info['oracle_text'][:200]}")
        except ValueError as e:
            print(f"!! {e}", file=sys.stderr)
            sys.exit(1)
