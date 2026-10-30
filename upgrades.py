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


# ---------------------------------------------------------------------------
# Always offer three cards: when fewer than three weapon upgrades are possible
# (slots full or weapons maxed), fill the rest with stat boosts.
# ---------------------------------------------------------------------------
CHOICES = 3
MAX_SPEED_BONUS = 1.4          # sneakers stop at +40% base speed

PASSIVE_CARDS = {
    "vitality": {"title": "Vitality", "desc": "Max HP +20",
                 "detail": "Late-night snacks. Raise max HP by 20 and heal 20."},
    "sneakers": {"title": "Sneakers", "desc": "Move speed +8%",
                 "detail": "Run between classes faster. Up to +40% speed."},
    "magnet": {"title": "Magnet", "desc": "Pickup range +30",
               "detail": "Pull EXP gems from further away."},
    "study_break": {"title": "Study Break", "desc": "Recover 25 HP",
                    "detail": "Take a breather and restore 25 HP."},
}


def _passive_allowed(player, card_id):
    if card_id == "sneakers":
        base = getattr(player, "base_speed", player.speed)
        return player.speed < base * MAX_SPEED_BONUS - 1e-6
    return True


def level_up_choices(player, rng, count=CHOICES):
    """Up to `count` weapon cards, topped up with passive cards to always reach `count`."""
    weapons = [card for card in available_upgrades(player) if card["id"] != "recovery"]
    picked = rng.sample(weapons, min(count, len(weapons)))
    passives = [cid for cid in PASSIVE_CARDS if _passive_allowed(player, cid)]
    rng.shuffle(passives)
    for cid in passives[:count - len(picked)]:
        picked.append({"id": cid, "type": "passive", **PASSIVE_CARDS[cid]})
    return picked


def apply_choice(player, card):
    """Apply a weapon card (via apply_upgrade) or a passive card."""
    cid = card["id"]
    if cid not in PASSIVE_CARDS:
        return apply_upgrade(player, card)
    if cid == "vitality":
        player.max_hp += 20
        player.hp = min(player.max_hp, player.hp + 20)
    elif cid == "sneakers":
        if not hasattr(player, "base_speed"):
            player.base_speed = player.speed
        player.speed = min(player.base_speed * MAX_SPEED_BONUS, player.speed + player.base_speed * 0.08)
    elif cid == "magnet":
        player.magnet_range += 30
    elif cid == "study_break":
        player.hp = min(player.max_hp, player.hp + 25)
    return True
