#!/usr/bin/env python3
"""Find upgrade candidates for the weakest cards in each package slot.

For each card in a package, scores its 'replaceability' based on CMC vs the
package's ideal CMC, EDHREC rank, and archetype keyword match. Then searches
Scryfall for alternatives that do the same job better: lower CMC, higher synergy,
or budget-friendlier. Surfaces the top N swap targets with concrete replacements.

Usage:
    python engine/slot_upgrade.py decks/001_example-aesi-landfall --auto
    python engine/slot_upgrade.py decks/001_example-aesi-landfall --package ramp --top 5
    python engine/slot_upgrade.py decks/001_example-aesi-landfall --card "Solemn Simulacrum"
"""
import argparse
import pathlib
import sys

import fetch_scryfall as FS
import library as L

# ──────────────────────────────────────────────────────────────
# CMC targets — anything above these is expensive for the slot
# ──────────────────────────────────────────────────────────────
_IDEAL_CMC = {
    "ramp": 2.5,
    "draw": 2.8,
    "removal": 2.5,
    "protection": 2.0,
    "wincon": 5.5,
    "synergy": 4.0,
    "utility": 3.5,
    "required": 1.0,
}

# Package-specific Scryfall queries for finding replacements
# Uses {COLORS} as placeholder for the commander's color identity string
_UPGRADE_QUERIES = {
    "ramp": [
        "f:commander ci:{COLORS} (o:'search your library for a basic land' or o:'add {') cmc<=3 -t:legendary",
        "f:commander ci:{COLORS} t:artifact o:'add {' cmc<=2",
    ],
    "draw": [
        "f:commander ci:{COLORS} (o:'draw a card' or o:'draw two cards') cmc<=3 t:instant",
        "f:commander ci:{COLORS} (o:'draw a card' or o:'draw two cards') cmc<=2",
        "f:commander ci:{COLORS} o:'scry' (o:'draw') cmc<=2",
    ],
    "removal": [
        "f:commander ci:{COLORS} (o:'destroy target' or o:'exile target') t:instant cmc<=3",
        "f:commander ci:{COLORS} o:'return target' t:instant cmc<=3",
    ],
    "protection": [
        "f:commander ci:{COLORS} o:'counter target spell' cmc<=2",
        "f:commander ci:{COLORS} (o:hexproof or o:indestructible) t:instant cmc<=2",
    ],
    "wincon": [
        "f:commander ci:{COLORS} pow>=5 t:creature cmc<=6 -t:land",
        "f:commander ci:{COLORS} (o:'each opponent loses' or o:'trample' or o:'flying') t:creature cmc<=6",
    ],
    "synergy": [
        "f:commander ci:{COLORS} cmc<=3 -t:land",
    ],
    "utility": [
        "f:commander ci:{COLORS} cmc<=4 -t:land (o:'draw' or o:'search' or o:'add')",
    ],
}


# ──────────────────────────────────────────────────────────────
# Weakness scorer
# ──────────────────────────────────────────────────────────────

def weakness_score(card_name, package, commander_data):
    """Return a weakness score for a card in its package slot.

    Higher score = more replaceable. A score of 0 means the card is well-suited.
    """
    card = FS.card_by_name(card_name)
    if not card:
        return 0, None

    score = 0
    reasons = []
    cmc = float(card.get("cmc") or 0)
    type_line = (card.get("type_line") or "").lower()
    oracle = (card.get("oracle_text") or "").lower()

    # CMC above package ideal
    ideal = _IDEAL_CMC.get(package, 3.5)
    if cmc > ideal + 1.5:
        delta = cmc - ideal
        score += delta * 8
        reasons.append(f"CMC {int(cmc)} is {delta:.0f} above package ideal ({ideal})")

    # Legendary creature in a non-commander role
    if "legendary" in type_line and "creature" in type_line:
        score += 6
        reasons.append("Legendary creature — high-profile removal target")

    # Ramp: sorcery-speed only (instants and permanents are better)
    if package == "ramp" and "sorcery" in type_line and cmc >= 3:
        score += 5
        reasons.append("Sorcery-speed ramp above CMC 3")

    # Draw: enchantments that require a condition
    if package == "draw" and "enchantment" in type_line and "whenever" in oracle:
        score += 3
        reasons.append("Conditional draw engine — may be unreliable")

    # Archetype keyword mismatch
    archetype = (commander_data.get("archetype") or "").lower().replace("_", " ")
    strategy = (commander_data.get("strategy") or "").lower()
    archetype_words = set(archetype.split() + strategy.split())
    matches = sum(1 for w in archetype_words if len(w) >= 4 and w in oracle)
    if matches == 0 and package not in ("ramp", "draw", "removal", "protection"):
        score += 4
        reasons.append("No archetype keyword overlap in oracle text")

    # Price signal — very expensive cards with mediocre scores could be upgraded cheaply
    try:
        prices = card.get("prices") or {}
        usd = float(prices.get("usd") or 0)
        if usd > 10 and score > 8:
            reasons.append(f"${usd:.2f} — expensive for its current role")
    except (TypeError, ValueError):
        pass

    return score, reasons


# ──────────────────────────────────────────────────────────────
# Upgrade finder
# ──────────────────────────────────────────────────────────────

def find_upgrades(card_name, package, commander_data, existing_names, n=5, budget_max=None):
    """Search Scryfall for cards that do the job of `card_name` better."""
    colors = commander_data.get("color_identity") or []
    color_str = "".join(c.lower() for c in colors)

    queries = _UPGRADE_QUERIES.get(package, _UPGRADE_QUERIES["synergy"])
    candidates = {}

    for q_template in queries:
        q = q_template.replace("{COLORS}", color_str or "c")
        results = FS.search_cards(q, order="edhrec")
        for c in results:
            name = c["name"]
            if name not in candidates and name not in existing_names and name != card_name:
                candidates[name] = c

    # Score each candidate
    archetype = (commander_data.get("archetype") or "").lower().replace("_", " ")
    strategy = (commander_data.get("strategy") or "").lower()
    archetype_words = set(archetype.split() + strategy.split())
    synergy_cards = set(s.lower() for s in (commander_data.get("synergy_cards") or []))
    do_not_include = set(s.lower() for s in (commander_data.get("do_not_include") or []))

    scored = []
    for card in candidates.values():
        name = card["name"]
        if name.lower() in do_not_include:
            continue
        oracle = (card.get("oracle_text") or "").lower()
        cmc = float(card.get("cmc") or 0)

        # Price filter
        price = None
        try:
            prices = card.get("prices") or {}
            usd = prices.get("usd")
            price = float(usd) if usd else None
        except (TypeError, ValueError):
            price = None

        if budget_max is not None and price and price > budget_max:
            continue

        score = 0
        # Lower CMC than incumbent is better
        incumbent = FS.card_by_name(card_name) or {}
        incumbent_cmc = float(incumbent.get("cmc") or 0)
        if cmc < incumbent_cmc:
            score += (incumbent_cmc - cmc) * 6
        # EDHREC rank (lower rank = more popular)
        rank = card.get("edhrec_rank") or 9999
        score += max(0, 30 - rank / 60)
        # Archetype match
        for w in archetype_words:
            if len(w) >= 4 and w in oracle:
                score += 5
        # Synergy card bonus
        if name.lower() in synergy_cards:
            score += 15
        # Instant speed bonus for interaction slots
        type_line = (card.get("type_line") or "").lower()
        if package in ("removal", "protection") and "instant" in type_line:
            score += 8
        # Budget bonus
        if price and price < 2.0:
            score += 5

        scored.append({
            "name": name,
            "cmc": cmc,
            "type_line": card.get("type_line", ""),
            "oracle_text": (card.get("oracle_text") or "").replace("\n", " "),
            "price_usd": price,
            "edhrec_rank": rank,
            "upgrade_score": round(score, 1),
        })

    scored.sort(key=lambda x: -x["upgrade_score"])
    return scored[:n]


# ──────────────────────────────────────────────────────────────
# Scan all slots
# ──────────────────────────────────────────────────────────────

def scan_all_slots(deck_dir, top_targets=3, upgrades_per_target=3, budget_max=None):
    """Find the top N weakest cards across all packages and suggest replacements."""
    deck_dir = pathlib.Path(deck_dir)
    selection = L.load_selection(deck_dir)
    model = L.resolve_deck(selection)
    commander_data = model["commander_data"]
    existing_names = {c["name"] for c in model["cards"]} | set(model["lands"])

    # Score all non-land, non-required cards
    candidates = []
    for card in model["cards"]:
        pkg = card.get("package", "synergy")
        if pkg in ("lands", "required"):
            continue
        wscore, reasons = weakness_score(card["name"], pkg, commander_data)
        if wscore > 0:
            candidates.append({
                "name": card["name"],
                "package": pkg,
                "weakness": wscore,
                "reasons": reasons,
            })

    candidates.sort(key=lambda x: -x["weakness"])
    targets = candidates[:top_targets]

    results = []
    for t in targets:
        print(f"[slot_upgrade] Finding upgrades for {t['name']} ({t['package']})...", flush=True)
        upgrades = find_upgrades(
            t["name"], t["package"], commander_data,
            existing_names, n=upgrades_per_target, budget_max=budget_max
        )
        results.append({**t, "upgrades": upgrades})

    return results


# ──────────────────────────────────────────────────────────────
# Report
# ──────────────────────────────────────────────────────────────

def print_report(results, deck_dir):
    W = 84
    print("=" * W)
    print(f"SLOT UPGRADE FINDER — {pathlib.Path(deck_dir).name}")
    print("=" * W)

    if not results:
        print("  No weak slots detected. Deck is well-tuned.")
        return

    for i, t in enumerate(results, 1):
        print(f"\n[{i}] SWAP OUT: {t['name']}  ({t['package'].upper()})  "
              f"weakness score: {t['weakness']:.0f}")
        for r in t.get("reasons", []):
            print(f"     · {r}")

        upgrades = t.get("upgrades", [])
        if not upgrades:
            print("     No upgrade candidates found within constraints.")
            continue

        print(f"\n     SWAP IN candidates:")
        for u in upgrades:
            price = f"${u['price_usd']:.2f}" if u["price_usd"] else "??"
            cmc_str = f"CMC {int(u['cmc'])}"
            rank = f"EDHREC #{u['edhrec_rank']}" if u["edhrec_rank"] < 9999 else ""
            print(f"       → {u['name']:<30} {cmc_str:<7} {price:<7} {rank}")
            oracle = u["oracle_text"]
            if len(oracle) > 90:
                oracle = oracle[:87] + "..."
            print(f"         {oracle}")

    print(f"\n{'=' * W}")
    print("Approve swaps and edit deck_selection.yaml, then re-run preview + playtest.")
    print("=" * W)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Find upgrade targets and replacements for a Commander deck.")
    ap.add_argument("deck_dir", help="Deck directory (must have deck_selection.yaml)")

    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--auto", action="store_true",
                      help="Scan all package slots and surface the top 3 weakest cards")
    mode.add_argument("--package", metavar="PKG",
                      choices=["ramp", "draw", "removal", "protection", "wincon", "synergy", "utility"],
                      help="Scan a specific package slot only")
    mode.add_argument("--card", metavar="CARD_NAME",
                      help="Find upgrades for a specific card by name")

    ap.add_argument("--top", type=int, default=3, help="Number of swap targets (default 3)")
    ap.add_argument("--suggestions", type=int, default=3,
                    help="Upgrade candidates per target (default 3)")
    ap.add_argument("--budget", type=float, default=None, metavar="USD",
                    help="Maximum price per card in USD")
    args = ap.parse_args()

    deck_dir = pathlib.Path(args.deck_dir)
    selection = L.load_selection(deck_dir)
    model = L.resolve_deck(selection)
    commander_data = model["commander_data"]
    existing_names = {c["name"] for c in model["cards"]} | set(model["lands"])

    if args.card:
        # Single-card mode
        card_obj = next((c for c in model["cards"] if c["name"].lower() == args.card.lower()), None)
        if not card_obj:
            print(f"Card '{args.card}' not found in deck.")
            sys.exit(1)
        pkg = card_obj.get("package", "synergy")
        wscore, reasons = weakness_score(args.card, pkg, commander_data)
        upgrades = find_upgrades(args.card, pkg, commander_data, existing_names,
                                 n=args.suggestions, budget_max=args.budget)
        print_report([{"name": args.card, "package": pkg,
                        "weakness": wscore, "reasons": reasons, "upgrades": upgrades}], deck_dir)

    elif args.package:
        # Package-mode: find weakest in that package
        pkg_cards = [c for c in model["cards"] if c.get("package") == args.package]
        targets = []
        for card in pkg_cards:
            ws, reasons = weakness_score(card["name"], args.package, commander_data)
            if ws > 0:
                targets.append({"name": card["name"], "package": args.package,
                                 "weakness": ws, "reasons": reasons})
        targets.sort(key=lambda x: -x["weakness"])
        targets = targets[:args.top]
        for t in targets:
            print(f"[slot_upgrade] Finding upgrades for {t['name']}...", flush=True)
            t["upgrades"] = find_upgrades(
                t["name"], args.package, commander_data,
                existing_names, n=args.suggestions, budget_max=args.budget
            )
        print_report(targets, deck_dir)

    else:
        # Auto mode
        results = scan_all_slots(deck_dir, args.top, args.suggestions, args.budget)
        print_report(results, deck_dir)
