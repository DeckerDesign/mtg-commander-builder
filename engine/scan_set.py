#!/usr/bin/env python3
"""Scan a new set release for cards that fit a built deck.

Fetches every Commander-legal card from a set in the commander's color identity,
classifies each one into a package slot (ramp/draw/removal/protection/wincon/synergy),
scores its fit against the commander's archetype and strategy keywords, then surfaces
the top N candidates the pilot hasn't already included.

Usage:
    python engine/scan_set.py MH3 decks/001_example-aesi-landfall --top 10
    python engine/scan_set.py BLB decks/001_example-aesi-landfall --top 8 --budget 5
    python engine/scan_set.py OTJ decks/001_example-aesi-landfall --package ramp
"""
import argparse
import pathlib
import sys

import fetch_scryfall as FS
import library as L

# ──────────────────────────────────────────────────────────────
# Package classification heuristics
# ──────────────────────────────────────────────────────────────

# Oracle text keywords that signal a package slot
_PKG_SIGNALS = {
    "ramp": [
        "search your library for a", "land", "add {", "add one mana",
        "add two mana", "untap target land", "put a land", "additional land",
        "land card", "basic land card", "fetch", "mana rock", "signet",
    ],
    "draw": [
        "draw a card", "draw two", "draw three", "draw x", "draw cards",
        "look at the top", "scry", "surveil", "impulse", "brainstorm",
        "put that card into your hand", "investigate",
    ],
    "removal": [
        "destroy target", "exile target", "return target", "deals",
        "damage to target", "-x/-x", "sacrifice a", "counter target",
        "put on the bottom", "tuck",
    ],
    "protection": [
        "counter target spell", "counter that spell", "hexproof",
        "indestructible", "shroud", "can't be countered",
        "regenerate", "prevent", "protection from",
    ],
    "wincon": [
        "trample", "flying", "double strike", "infect", "annihilator",
        "each opponent loses", "you win the game", "storm", "emblem",
        "create x", "token", "double your", "combat damage",
    ],
}

# Type-line keywords that help classify
_TYPE_SIGNALS = {
    "ramp": ["land", "dork"],
    "removal": ["instant", "sorcery"],
    "protection": ["instant", "enchantment"],
    "wincon": ["creature"],
}

# Synergy-score ceiling above which we call a card "strong" regardless of package
_STRONG_SYNERGY = 0.25

# CMC targets per package (cards above these are weaker incumbents)
_IDEAL_CMC = {
    "ramp": 2.5,
    "draw": 3.0,
    "removal": 2.5,
    "protection": 2.0,
    "wincon": 6.0,
    "synergy": 4.0,
    "lands": 0,
}


def classify_package(card):
    """Return best-guess package slot for a card."""
    oracle = (card.get("oracle_text") or "").lower()
    type_line = (card.get("type_line") or "").lower()
    cmc = card.get("cmc", 0)

    # Lands always go in lands
    if "land" in type_line and "creature" not in type_line:
        return "lands"

    # Score each package slot
    scores = {pkg: 0 for pkg in _PKG_SIGNALS}
    for pkg, keywords in _PKG_SIGNALS.items():
        for kw in keywords:
            if kw in oracle:
                scores[pkg] += 1

    # Ramp bonus: cheap artifacts and creatures that produce mana
    if "artifact" in type_line and cmc <= 3 and "add" in oracle:
        scores["ramp"] += 3
    if "creature" in type_line and "add" in oracle and cmc <= 3:
        scores["ramp"] += 2

    # Win-con bonus: big creatures and finishers
    power = card.get("power")
    try:
        if power and int(power) >= 5:
            scores["wincon"] += 2
    except (ValueError, TypeError):
        pass

    # Pick highest score; fall back to synergy
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "synergy"


def score_fit(card, commander_data, package, existing_names):
    """Return a 0-100 fit score for a card against a commander's archetype."""
    oracle = (card.get("oracle_text") or "").lower()
    name = card.get("name", "")
    cmc = float(card.get("cmc") or 0)
    score = 0

    # Already in the deck — skip
    if name in existing_names:
        return -1

    # Base: EDHREC synergy_score if present (0.0-1.0 → 0-40 pts)
    synergy = float(card.get("edhrec_rank") or 0)
    # edhrec_rank is an int rank (lower = more popular); invert to a 0-40 signal
    if synergy > 0:
        score += max(0, 40 - synergy / 50)

    # Archetype keyword match — commander strategy_hint words in oracle text
    strategy = (commander_data.get("strategy") or "").lower()
    archetype = (commander_data.get("archetype") or "").lower()
    archetype_words = set(archetype.replace("_", " ").split() + strategy.split())
    synergy_cards = set(s.lower() for s in (commander_data.get("synergy_cards") or []))
    do_not_include = set(s.lower() for s in (commander_data.get("do_not_include") or []))

    if name.lower() in do_not_include:
        return -1

    # Synergy card bonus
    if name.lower() in synergy_cards:
        score += 20

    # Keyword match with archetype
    for word in archetype_words:
        if len(word) >= 4 and word in oracle:
            score += 8

    # CMC fit — cards near the package ideal score higher
    ideal = _IDEAL_CMC.get(package, 4.0)
    cmc_delta = abs(cmc - ideal)
    score += max(0, 15 - cmc_delta * 4)

    # Cheap interaction gets a bonus (EDH tempo matters)
    if package in ("removal", "protection") and cmc <= 2:
        score += 10
    if package == "ramp" and cmc <= 2:
        score += 10

    # Penalise very expensive non-wincons
    if cmc >= 6 and package not in ("wincon", "synergy"):
        score -= 15

    return max(0, score)


# ──────────────────────────────────────────────────────────────
# Main scan function
# ──────────────────────────────────────────────────────────────

def scan_set(set_code, deck_dir, top_n=10, budget_max=None, package_filter=None):
    """Return top-N cards from `set_code` that fit the deck at `deck_dir`."""
    deck_dir = pathlib.Path(deck_dir)
    selection = L.load_selection(deck_dir)
    model = L.resolve_deck(selection)
    commander_data = model["commander_data"]
    colors = commander_data.get("color_identity") or []
    color_str = "".join(c.lower() for c in colors)

    existing_names = {c["name"] for c in model["cards"]} | set(model["lands"])
    existing_names.add(model.get("commander") or "")

    # Scryfall search — all Commander-legal cards from the set in color identity
    query = f"e:{set_code} f:commander ci:{color_str or 'c'}"
    print(f"[scan_set] Searching Scryfall: {query!r}", flush=True)
    cards = FS.search_cards(query, order="edhrec")

    if not cards:
        print(f"[scan_set] No cards found for set {set_code!r} with color identity {color_str!r}.")
        return []

    print(f"[scan_set] {len(cards)} candidates fetched. Scoring...", flush=True)

    results = []
    for card in cards:
        pkg = classify_package(card)
        if package_filter and pkg != package_filter:
            continue

        fit = score_fit(card, commander_data, pkg, existing_names)
        if fit < 0:
            continue

        price = None
        try:
            prices = card.get("prices") or {}
            usd = prices.get("usd") or prices.get("usd_foil")
            price = float(usd) if usd else None
        except (TypeError, ValueError):
            price = None

        if budget_max is not None and price and price > budget_max:
            continue

        results.append({
            "name": card["name"],
            "package": pkg,
            "cmc": card.get("cmc", 0),
            "type_line": card.get("type_line", ""),
            "oracle_text": (card.get("oracle_text") or "").replace("\n", " "),
            "price_usd": price,
            "edhrec_rank": card.get("edhrec_rank"),
            "fit_score": round(fit, 1),
        })

    results.sort(key=lambda x: -x["fit_score"])
    return results[:top_n]


def print_results(results, set_code, deck_dir):
    W = 84
    print("=" * W)
    print(f"SET SCAN — {set_code.upper()}  →  {pathlib.Path(deck_dir).name}")
    print("=" * W)
    if not results:
        print("  No matching cards found.")
        return

    # Group by package
    by_pkg = {}
    for r in results:
        by_pkg.setdefault(r["package"], []).append(r)

    for pkg, cards in sorted(by_pkg.items()):
        print(f"\n── {pkg.upper()}")
        for c in cards:
            price = f"${c['price_usd']:.2f}" if c["price_usd"] else "??"
            cmc_str = f"CMC {int(c['cmc'])}"
            rank = f"EDHREC #{c['edhrec_rank']}" if c["edhrec_rank"] else ""
            score_str = f"fit {c['fit_score']}"
            header = f"  {c['name']:<30} {cmc_str:<7} {price:<7} {rank:<14} {score_str}"
            print(header)
            # Truncate oracle text
            oracle = c["oracle_text"]
            if len(oracle) > 90:
                oracle = oracle[:87] + "..."
            print(f"    {oracle}")

    print(f"\n{'=' * W}")
    print(f"Run /brew or edit deck_selection.yaml to add approved cards.")
    print("=" * W)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Scan a new set for cards that fit a Commander deck.")
    ap.add_argument("set_code", help="Scryfall set code, e.g. MH3, BLB, OTJ")
    ap.add_argument("deck_dir", help="Deck directory (must have deck_selection.yaml)")
    ap.add_argument("--top", type=int, default=10, help="Number of results to return (default 10)")
    ap.add_argument("--budget", type=float, default=None, metavar="USD",
                    help="Maximum price per card in USD")
    ap.add_argument("--package", default=None,
                    choices=["ramp", "draw", "removal", "protection", "wincon", "synergy", "lands"],
                    help="Filter to a specific package slot")
    args = ap.parse_args()

    results = scan_set(args.set_code, args.deck_dir, args.top, args.budget, args.package)
    print_results(results, args.set_code, args.deck_dir)
