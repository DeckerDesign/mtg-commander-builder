#!/usr/bin/env python3
"""Fetch and model opponent decks for playtesting.

Three sources:
  1. User-imported decklists (paste or file) — parsed into card lists, analyzed for archetype.
  2. EDHREC top commanders — fetched live, filtered by power level, used as heuristic models.
  3. Auto-fill — automatically selects opponents matching the pilot's typical table power.

An opponent "model" is a heuristic statistical profile: archetype, win-turn distribution,
threat-deployment turn, interaction density, and whether they target draw engines early.
This is NOT a full deck — it's enough to simulate game-state competition.

Usage:
    python engine/fetch_opponents.py --top 100 --power 7
    python engine/fetch_opponents.py --auto --power 7
    python engine/fetch_opponents.py --parse decklist.txt
    python engine/fetch_opponents.py --name "Yuriko, the Tiger's Shadow"
"""
import argparse
import json
import pathlib
import random
import sys
import time

# ──────────────────────────────────────────────────────────────
# Archetype base models (heuristic parameters).
# win_turn_avg / std: Gaussian distribution of the turn they win if uncontested.
# threat_turn: when they typically deploy their main threat.
# interaction: probability 0-1 they have an answer in any given interaction window.
# targets_draw_engine: True if they will prioritize removing Rhystic Study / Consecrated Sphinx.
# ──────────────────────────────────────────────────────────────
ARCHETYPE_MODELS = {
    "cedh_combo": {
        "label": "cEDH Combo",
        "win_turn_avg": 4, "win_turn_std": 1.5,
        "threat_turn": 3, "interaction": 0.35,
        "targets_draw_engine": True, "power_level": 10,
    },
    "fast_combo": {
        "label": "Fast Combo",
        "win_turn_avg": 6, "win_turn_std": 2,
        "threat_turn": 4, "interaction": 0.20,
        "targets_draw_engine": True, "power_level": 8,
    },
    "midrange_value": {
        "label": "Midrange Value",
        "win_turn_avg": 9, "win_turn_std": 2.5,
        "threat_turn": 6, "interaction": 0.18,
        "targets_draw_engine": True, "power_level": 7,
    },
    "aggro_tokens": {
        "label": "Aggro Tokens",
        "win_turn_avg": 8, "win_turn_std": 2,
        "threat_turn": 5, "interaction": 0.12,
        "targets_draw_engine": False, "power_level": 6,
    },
    "voltron": {
        "label": "Voltron",
        "win_turn_avg": 9, "win_turn_std": 2.5,
        "threat_turn": 5, "interaction": 0.14,
        "targets_draw_engine": False, "power_level": 6,
    },
    "control": {
        "label": "Control",
        "win_turn_avg": 12, "win_turn_std": 3,
        "threat_turn": 7, "interaction": 0.30,
        "targets_draw_engine": True, "power_level": 7,
    },
    "stax": {
        "label": "Stax",
        "win_turn_avg": 11, "win_turn_std": 3,
        "threat_turn": 4, "interaction": 0.22,
        "targets_draw_engine": False, "power_level": 8,
    },
    "reanimator": {
        "label": "Reanimator",
        "win_turn_avg": 7, "win_turn_std": 2,
        "threat_turn": 5, "interaction": 0.15,
        "targets_draw_engine": False, "power_level": 7,
    },
    "lands": {
        "label": "Lands / Landfall",
        "win_turn_avg": 9, "win_turn_std": 2.5,
        "threat_turn": 5, "interaction": 0.16,
        "targets_draw_engine": True, "power_level": 7,
    },
    "casual_midrange": {
        "label": "Casual Midrange",
        "win_turn_avg": 11, "win_turn_std": 3,
        "threat_turn": 7, "interaction": 0.10,
        "targets_draw_engine": False, "power_level": 5,
    },
}

# Known commander → archetype mapping for EDHREC top commanders.
# Extend as needed; unknown commanders default to midrange_value for their power band.
COMMANDER_ARCHETYPES = {
    "Yuriko, the Tiger's Shadow": "fast_combo",
    "Kenrith, the Returned King": "cedh_combo",
    "Najeela, the Blade-Blossom": "cedh_combo",
    "The Gitrog Monster": "fast_combo",
    "Atraxa, Praetors' Voice": "midrange_value",
    "Muldrotha, the Gravetide": "midrange_value",
    "Edgar Markov": "aggro_tokens",
    "Prossh, Skyraider of Kher": "fast_combo",
    "Tymna the Weaver": "cedh_combo",
    "Thrasios, Triton Hero": "cedh_combo",
    "Zur the Enchanter": "control",
    "Scion of the Ur-Dragon": "midrange_value",
    "Kaalia of the Vast": "aggro_tokens",
    "Nekusar, the Mindrazer": "control",
    "Aesi, Tyrant of Gyre Strait": "lands",
    "Tatyova, Benthic Druid": "lands",
    "Wilhelt, the Rotcleaver": "aggro_tokens",
    "Isshin, Two Heavens as One": "aggro_tokens",
    "Lathril, Blade of the Elves": "aggro_tokens",
    "Omnath, Locus of Creation": "midrange_value",
    "The Locust God": "midrange_value",
    "Krenko, Mob Boss": "aggro_tokens",
    "Oloro, Ageless Ascetic": "control",
    "Animar, Soul of Elements": "fast_combo",
    "Inalla, Archmage Ritualist": "fast_combo",
    "Marwyn, the Nurturer": "fast_combo",
    "Meren of Clan Nel Toth": "reanimator",
    "Karador, Ghost Chieftain": "reanimator",
    "Sidisi, Brood Tyrant": "reanimator",
    "Breya, Etherium Shaper": "fast_combo",
    "Jodah, Archmage Eternal": "midrange_value",
    "Golos, Tireless Pilgrim": "midrange_value",  # banned but kept for reference
    "Shorikai, Genesis Engine": "control",
    "Tovolar, Dire Overlord": "aggro_tokens",
    "Korvold, Fae-Cursed King": "midrange_value",
    "Niv-Mizzet Reborn": "midrange_value",
    "Rhys the Redeemed": "aggro_tokens",
    "Syr Konrad, the Grim": "midrange_value",
    "Kinnan, Bonder Prodigy": "cedh_combo",
    "Winota, Joiner of Forces": "fast_combo",
    "Narset, Enlightened Master": "stax",
}

CACHE_DIR = pathlib.Path(__file__).resolve().parent.parent / ".scryfall_cache" / "opponents"


def _cache_path(key):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{key[:80]}.json"


def archetype_for_commander(name):
    """Return the archetype key for a commander name, defaulting by common sense."""
    return COMMANDER_ARCHETYPES.get(name, "midrange_value")


def power_level_for_archetype(archetype_key):
    return ARCHETYPE_MODELS.get(archetype_key, ARCHETYPE_MODELS["midrange_value"])["power_level"]


def build_opponent_model(commander_name, archetype_key=None, custom_power=None):
    """Return a complete opponent model dict for simulation use."""
    if archetype_key is None:
        archetype_key = archetype_for_commander(commander_name)
    base = ARCHETYPE_MODELS.get(archetype_key, ARCHETYPE_MODELS["midrange_value"]).copy()
    base["commander"] = commander_name
    base["archetype_key"] = archetype_key
    if custom_power is not None:
        base["power_level"] = custom_power
    return base


def get_edhrec_top_commanders(n=100, power_filter=None):
    """Fetch EDHREC's top commanders. Falls back to a hardcoded list if unavailable.

    Returns a list of {commander, archetype_key, power_level, rank} dicts.
    """
    cache = _cache_path(f"top_commanders_{n}")
    if cache.exists():
        data = json.loads(cache.read_text())
    else:
        data = _fetch_edhrec_top(n)
        cache.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    if power_filter is not None:
        data = [c for c in data if abs(c.get("power_level", 7) - power_filter) <= 1]
    return data[:n]


def _fetch_edhrec_top(n):
    """Attempt to fetch EDHREC top commanders; fall back to hardcoded list."""
    try:
        import requests, time
        time.sleep(0.5)
        resp = requests.get("https://json.edhrec.com/pages/top.json", timeout=10)
        if resp.ok:
            raw = resp.json()
            commanders = (raw.get("container", {})
                             .get("json_dict", {})
                             .get("cardlists", [{}])[0]
                             .get("cardviews", []))
            result = []
            for i, c in enumerate(commanders[:n]):
                name = c.get("name") or c.get("n", "")
                arch = archetype_for_commander(name)
                result.append({
                    "commander": name,
                    "archetype_key": arch,
                    "power_level": ARCHETYPE_MODELS.get(arch, {}).get("power_level", 7),
                    "rank": i + 1,
                })
            if result:
                return result
    except Exception:
        pass
    return _hardcoded_top_commanders()[:n]


def _hardcoded_top_commanders():
    """Fallback: a representative sample of top EDHREC commanders with archetypes."""
    entries = [
        ("Atraxa, Praetors' Voice", "midrange_value"),
        ("Yuriko, the Tiger's Shadow", "fast_combo"),
        ("Edgar Markov", "aggro_tokens"),
        ("Muldrotha, the Gravetide", "midrange_value"),
        ("The Ur-Dragon", "midrange_value"),
        ("Wilhelt, the Rotcleaver", "aggro_tokens"),
        ("Omnath, Locus of Creation", "midrange_value"),
        ("Isshin, Two Heavens as One", "aggro_tokens"),
        ("Krenko, Mob Boss", "aggro_tokens"),
        ("The Locust God", "midrange_value"),
        ("Nekusar, the Mindrazer", "control"),
        ("Prossh, Skyraider of Kher", "fast_combo"),
        ("Shorikai, Genesis Engine", "control"),
        ("Lathril, Blade of the Elves", "aggro_tokens"),
        ("Korvold, Fae-Cursed King", "midrange_value"),
        ("Meren of Clan Nel Toth", "reanimator"),
        ("Zur the Enchanter", "control"),
        ("Scion of the Ur-Dragon", "midrange_value"),
        ("Kaalia of the Vast", "aggro_tokens"),
        ("Animar, Soul of Elements", "fast_combo"),
        ("Winota, Joiner of Forces", "fast_combo"),
        ("Kenrith, the Returned King", "cedh_combo"),
        ("Najeela, the Blade-Blossom", "cedh_combo"),
        ("Kinnan, Bonder Prodigy", "cedh_combo"),
        ("Jodah, Archmage Eternal", "midrange_value"),
        ("Rhys the Redeemed", "aggro_tokens"),
        ("Breya, Etherium Shaper", "fast_combo"),
        ("Inalla, Archmage Ritualist", "fast_combo"),
        ("Sidisi, Brood Tyrant", "reanimator"),
        ("Niv-Mizzet Reborn", "midrange_value"),
        ("Syr Konrad, the Grim", "midrange_value"),
        ("Oloro, Ageless Ascetic", "control"),
        ("Tovolar, Dire Overlord", "aggro_tokens"),
        ("Aesi, Tyrant of Gyre Strait", "lands"),
        ("Tatyova, Benthic Druid", "lands"),
        ("Narset, Enlightened Master", "stax"),
        ("Tymna the Weaver", "cedh_combo"),
        ("Thrasios, Triton Hero", "cedh_combo"),
        ("The Gitrog Monster", "fast_combo"),
        ("Karador, Ghost Chieftain", "reanimator"),
    ]
    result = []
    for i, (name, arch) in enumerate(entries):
        result.append({
            "commander": name,
            "archetype_key": arch,
            "power_level": ARCHETYPE_MODELS.get(arch, {}).get("power_level", 7),
            "rank": i + 1,
        })
    return result


def parse_imported_decklist(text):
    """Parse a pasted decklist (standard '1 Card Name' format) into a card list.

    Returns {commander: str, cards: [(name, count), ...], section_counts: dict}
    """
    lines = text.strip().splitlines()
    commander = None
    cards = []
    current_section = "main"
    section_counts = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("//"):
            label = line.lstrip("/ ").strip().lower()
            current_section = label
            continue
        parts = line.split(" ", 1)
        if len(parts) == 2 and parts[0].isdigit():
            count, name = int(parts[0]), parts[1].strip()
        elif len(parts) == 1:
            count, name = 1, parts[0].strip()
        else:
            continue

        if "commander" in current_section and commander is None:
            commander = name
        else:
            cards.append((name, count))
            section_counts[current_section] = section_counts.get(current_section, 0) + count

    return {"commander": commander, "cards": cards, "section_counts": section_counts,
            "total": sum(c for _, c in cards) + (1 if commander else 0)}


def analyze_imported_deck(parsed):
    """Heuristically estimate the archetype and power level of an imported deck.

    Uses section labels and card counts to approximate archetype. For a real analysis
    the agent should use fetch_edhrec to check the commander's top archetype.
    """
    commander = parsed.get("commander", "")
    arch = archetype_for_commander(commander)
    pl = ARCHETYPE_MODELS.get(arch, {}).get("power_level", 7)
    return {
        "commander": commander,
        "archetype_key": arch,
        "power_level": pl,
        "source": "imported",
    }


def select_auto_pod(user_power_level, exclude_commander=None, n=3):
    """Auto-select N opponents whose power level is close to user_power_level."""
    top = get_edhrec_top_commanders(100)
    candidates = [c for c in top
                  if abs(c["power_level"] - user_power_level) <= 1
                  and c["commander"] != exclude_commander]
    if len(candidates) < n:
        candidates = [c for c in top if c["commander"] != exclude_commander]
    selected = random.sample(candidates[:40], min(n, len(candidates)))
    return [build_opponent_model(c["commander"], c["archetype_key"]) for c in selected]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Fetch and model opponent decks.")
    ap.add_argument("--top", type=int, default=40, help="Show top N EDHREC commanders")
    ap.add_argument("--power", type=int, default=7, help="Filter by power level (±1)")
    ap.add_argument("--auto", action="store_true", help="Auto-select pod for the given power")
    ap.add_argument("--name", help="Model a specific commander by name")
    ap.add_argument("--parse", metavar="FILE", help="Parse an imported decklist file")
    args = ap.parse_args()

    if args.parse:
        text = pathlib.Path(args.parse).read_text()
        parsed = parse_imported_decklist(text)
        info = analyze_imported_deck(parsed)
        print(f"Commander: {info['commander']}")
        print(f"Archetype: {info['archetype_key']}  |  Power level: {info['power_level']}")
        print(f"Total cards: {parsed['total']}")
    elif args.name:
        model = build_opponent_model(args.name)
        print(f"Model for {model['commander']}:")
        for k, v in model.items():
            if k != "commander":
                print(f"  {k}: {v}")
    elif args.auto:
        pod = select_auto_pod(args.power)
        print(f"Auto-selected pod (power ~{args.power}):")
        for opp in pod:
            print(f"  {opp['commander']} [{opp['label']}] — power {opp['power_level']}, "
                  f"wins ~turn {opp['win_turn_avg']}")
    else:
        commanders = get_edhrec_top_commanders(args.top, power_filter=args.power)
        print(f"Top {len(commanders)} commanders (power ~{args.power}):")
        print(f"{'#':>4}  {'Commander':<42} {'Archetype':<20} PL")
        print("-" * 75)
        for c in commanders:
            arch_label = ARCHETYPE_MODELS.get(c["archetype_key"], {}).get("label", c["archetype_key"])
            print(f"{c['rank']:>4}  {c['commander']:<42} {arch_label:<20} {c['power_level']}")
