#!/usr/bin/env python3
"""Fetch commander archetype data from EDHREC.

EDHREC exposes JSON at json.edhrec.com — unofficial but stable and widely used.
Results are cached locally. Fetches: top recommended cards with synergy scores,
archetype themes, and theme-specific card lists.

Usage:
    python engine/fetch_edhrec.py "Aesi, Tyrant of Gyre Strait"
    python engine/fetch_edhrec.py "Aesi, Tyrant of Gyre Strait" --theme landfall
    python engine/fetch_edhrec.py "Aesi, Tyrant of Gyre Strait" --top 20
"""
import argparse
import json
import pathlib
import time
import urllib.error
import urllib.request

EDHREC_JSON = "https://json.edhrec.com/pages"
CACHE_DIR = pathlib.Path(__file__).resolve().parent.parent / ".scryfall_cache" / "edhrec"
RATE_LIMIT = 0.5  # EDHREC requests: be polite

_HEADERS = {"User-Agent": "mtg-commander-builder/1.0", "Accept": "application/json"}


def _slug(name):
    """Convert a card name to an EDHREC URL slug."""
    return name.lower().replace(",", "").replace("'", "").replace(" ", "-")


def _cache_path(key):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe = key.replace("/", "_")[:80]
    return CACHE_DIR / f"{safe}.json"


_last_request = 0.0


def _fetch(url):
    global _last_request
    elapsed = time.time() - _last_request
    if elapsed < RATE_LIMIT:
        time.sleep(RATE_LIMIT - elapsed)
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            _last_request = time.time()
            return json.loads(r.read())
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        raise RuntimeError(f"EDHREC fetch error: {e}") from e


def _cached_fetch(key, url):
    p = _cache_path(key)
    if p.exists():
        return json.loads(p.read_text())
    data = _fetch(url)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return data


def commander_page(name):
    """Fetch the EDHREC commander page JSON for a commander name."""
    slug = _slug(name)
    return _cached_fetch(f"commander_{slug}", f"{EDHREC_JSON}/commanders/{slug}.json")


def theme_page(name, theme):
    """Fetch the EDHREC theme page for a commander + theme (e.g. 'landfall')."""
    slug = _slug(name)
    theme_slug = theme.lower().replace(" ", "-")
    return _cached_fetch(
        f"commander_{slug}_theme_{theme_slug}",
        f"{EDHREC_JSON}/commanders/{slug}/{theme_slug}.json"
    )


def top_cards(commander_name, n=40, theme=None):
    """Return the top N recommended cards for a commander, sorted by synergy score.

    Each result: {name, synergy_score, inclusion_pct, salt_score, cmc, type}
    """
    try:
        if theme:
            page = theme_page(commander_name, theme)
        else:
            page = commander_page(commander_name)
    except RuntimeError as e:
        print(f"[edhrec] Could not fetch data for '{commander_name}': {e}")
        return []

    cardlist = (page.get("container", {})
                    .get("json_dict", {})
                    .get("cardlists", []))

    cards = []
    for section in cardlist:
        for card in section.get("cardviews", []):
            # EDHREC card view fields
            name = card.get("name") or card.get("n")
            if not name:
                continue
            synergy = card.get("synergy", 0) or 0
            inclusion = card.get("inclusion", 0) or 0
            salt = card.get("salt", 0) or 0
            label = section.get("header", "")
            cards.append({
                "name": name,
                "synergy_score": round(synergy, 3),
                "inclusion_pct": round(inclusion, 1),
                "salt_score": round(salt, 3),
                "section": label,
            })

    cards.sort(key=lambda c: c["synergy_score"], reverse=True)
    return cards[:n]


def available_themes(commander_name):
    """Return the list of EDHREC theme/archetype names for a commander."""
    try:
        page = commander_page(commander_name)
    except RuntimeError:
        return []
    links = (page.get("container", {})
                 .get("json_dict", {})
                 .get("links", []))
    return [l.get("value") for l in links if l.get("value")]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Fetch EDHREC commander data.")
    ap.add_argument("name", help="Commander name (e.g. 'Aesi, Tyrant of Gyre Strait')")
    ap.add_argument("--theme", help="Theme/archetype filter (e.g. 'landfall')")
    ap.add_argument("--top", type=int, default=30, help="Number of top cards to show")
    ap.add_argument("--themes", action="store_true", help="List available themes only")
    args = ap.parse_args()

    if args.themes:
        themes = available_themes(args.name)
        print(f"Themes for {args.name}:")
        for t in themes:
            print(f"  {t}")
    else:
        cards = top_cards(args.name, n=args.top, theme=args.theme)
        header = f"Top {len(cards)} cards for {args.name}"
        if args.theme:
            header += f" [{args.theme}]"
        print(header)
        print(f"{'Name':<40} {'Synergy':>8} {'Incl%':>7} {'Salt':>6}  Section")
        print("-" * 75)
        for c in cards:
            print(f"{c['name']:<40} {c['synergy_score']:>8.3f} {c['inclusion_pct']:>6.1f}%"
                  f" {c['salt_score']:>6.3f}  {c['section']}")
