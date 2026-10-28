"""Build only valid cards for the player's current loadout."""
from weapons import MAX_LEVEL, WEAPONS

UPGRADE_POOL = [
    {"id": kind, "title": data[0], "detail": data[1], "type": "weapon"}
    for kind, data in WEAPONS.items()
]


def available_upgrades(player):
    cards = []
    for entry in UPGRADE_POOL:
        kind = entry["id"]
        if player.weapons.can_upgrade(kind):
            level = player.weapons.levels.get(kind, 0)
            cards.append({**entry, "desc": f"Level {level} -> {level+1}" if level else "New weapon"})
    if not cards:
        cards.append({"id": "recovery", "title": "Study Break", "type": "recovery",
                      "desc": "Recover 25 HP", "detail": f"All equipped weapons reached level {MAX_LEVEL}. Restore health."})
    return cards


def apply_upgrade(player, card):
    if card["id"] == "recovery":
        if any(player.weapons.can_upgrade(kind) for kind in WEAPONS):
            return False
        player.hp = min(player.max_hp, player.hp+25)
        return True
    return player.weapons.upgrade(card["id"])
