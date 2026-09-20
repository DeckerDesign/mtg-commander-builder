"""Resolve a deck selection config into a concrete 100-card model.

The Engine is person-agnostic. Everything about the pilot lives in the Profile
(`profile/`): identity, packages, commander overlays, cardpool, and layout config.
The agent emits a small deck_selection.yaml per intent; this module merges it over
the Profile and the chosen commander's overlay.

Commander overlays are data (files under `profile/commanders/`), never a hardcoded enum.
"""
import pathlib
import re
import yaml

BASIC_LANDS = {"Plains", "Island", "Swamp", "Mountain", "Forest",
               "Wastes", "Snow-Covered Plains", "Snow-Covered Island",
               "Snow-Covered Swamp", "Snow-Covered Mountain", "Snow-Covered Forest"}

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROFILE = ROOT / "profile"
COMMANDERS = PROFILE / "commanders"
PACKAGES = PROFILE / "packages"
DECKS = ROOT / "decks"


def _load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_profile():
    return {
        "identity": _load_yaml(PROFILE / "identity.yaml"),
        "cardpool": _load_yaml(PROFILE / "cardpool.yaml"),
        "layout": _load_yaml(PROFILE / "layout.yaml"),
    }


def load_layout():
    return _load_yaml(PROFILE / "layout.yaml")


def load_packages():
    """Load all package files. Returns {package_name: [card_name, ...]}."""
    pkgs = {}
    for p in sorted(PACKAGES.glob("*.yaml")):
        data = _load_yaml(p)
        pkgs[p.stem] = data.get("cards", [])
    return pkgs


def list_commanders():
    return sorted(p.stem for p in COMMANDERS.glob("*.yaml"))


def load_commander(slug):
    path = COMMANDERS / f"{slug}.yaml"
    if not path.exists():
        raise KeyError(
            f"Commander overlay '{slug}' not found. "
            f"Existing: {', '.join(list_commanders())}. "
            f"Add profile/commanders/{slug}.yaml to introduce it."
        )
    return _load_yaml(path)


def load_selection(deck_dir):
    return _load_yaml(pathlib.Path(deck_dir) / "deck_selection.yaml")


def slug(name):
    """Filesystem-safe slug. Keeps letters, digits, underscores, hyphens."""
    name = (name or "deck").strip()
    name = re.sub(r"[\s/\\|,.']+", "-", name)
    name = re.sub(r"[^A-Za-z0-9_-]+", "", name)
    name = re.sub(r"-+", "-", name).strip("-")
    return name.lower() or "deck"


def next_seq():
    highest = 0
    if DECKS.exists():
        for p in DECKS.iterdir():
            m = re.match(r"(\d+)_", p.name) if p.is_dir() else None
            if m:
                highest = max(highest, int(m.group(1)))
    return highest + 1


def output_stub(selection):
    """Output filename stub: <CommanderSlug>_<Archetype>."""
    cmd = slug(selection.get("commander", "deck"))
    arch = slug(selection.get("archetype", ""))
    return f"{cmd}_{arch}" if arch else cmd


def resolve_deck(selection, profile=None, commander_data=None):
    """Return a flat 100-card model ready for the checks and export pipeline.

    Model keys:
      commander     — the commander card name
      commander_data — loaded commander overlay
      cards         — OrderedDict-like list of {name, package, role}
      lands         — list of land names
      archetype
      power_level
      strategy_hook
      gaps
      acquire       — cards not in cardpool
    """
    profile = profile or load_profile()
    if commander_data is None:
        commander_data = load_commander(selection["commander"])

    cardpool_owned = set(profile["cardpool"].get("owned", []))
    cardpool_proxy = set(profile["cardpool"].get("proxy", []))
    in_pool = cardpool_owned | cardpool_proxy

    # Collect all card slots from selection
    cards = []
    seen = set()

    def _add(name, package, role=""):
        if name in seen:
            return  # singleton enforcement — first occurrence wins
        seen.add(name)
        cards.append({
            "name": name,
            "package": package,
            "role": role,
            "owned": name in cardpool_owned,
            "proxy": name in cardpool_proxy,
            "acquire": name not in in_pool,
        })

    # 1. Cards from selected packages
    for pkg_name, card_list in (selection.get("packages") or {}).items():
        for card in (card_list or []):
            _add(card, pkg_name)

    # 2. Explicit synergy cards
    for card in (selection.get("synergy_cards") or []):
        _add(card, "synergy")

    # 3. Commander defaults not already included
    for card in (commander_data.get("required_cards") or []):
        _add(card, "required")

    # 4. Utility / mana base staples
    for card in (selection.get("utility") or []):
        _add(card, "utility")

    # 5. Lands — support "N Card Name" count notation for basics, e.g. "8 Forest"
    lands = []
    land_seen = {}  # name -> count (basic lands allowed multiple times)
    for entry in (selection.get("lands") or []):
        entry = str(entry).strip()
        parts = entry.split(" ", 1)
        if len(parts) == 2 and parts[0].isdigit():
            count, name = int(parts[0]), parts[1].strip()
        else:
            count, name = 1, entry
        for _ in range(count):
            if name not in BASIC_LANDS:
                # non-basics: singleton only
                if name not in seen:
                    seen.add(name)
                    lands.append(name)
            else:
                lands.append(name)

    gaps = (selection.get("gaps") or [])
    acquire = [c for c in cards if c["acquire"]] + [
        {"name": l, "package": "lands", "acquire": True}
        for l in lands if l not in in_pool
    ]

    return {
        "commander": commander_data.get("name") or selection.get("commander"),
        "commander_slug": selection["commander"],
        "commander_data": commander_data,
        "archetype": selection.get("archetype", ""),
        "power_level": selection.get("power_level", 0),
        "power_level_fit": selection.get("power_level_fit", ""),
        "strategy_hook": selection.get("strategy_hook", ""),
        "cards": cards,
        "lands": lands,
        "gaps": gaps,
        "acquire": acquire,
        "total": 1 + len(cards) + len(lands),  # 1 = commander in command zone
    }
