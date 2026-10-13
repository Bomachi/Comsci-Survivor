UPGRADE_POOL = [
    {
        "id": "heavy_book",
        "type": "projectile",
        "icon": "card_book.png",
        "title": "Heavy Textbook",
        "desc": "",
        "detail": "Throw the heavy book at the approaching enemy",
        "apply": lambda p: setattr(p, "has_book_weapon", True)
    }
]