"""Image loading helpers. A missing file returns None so callers can draw a fallback."""
import os
import pygame

from settings import SPRITES_DIR


def load_sprite(filename: str, size=None):
    path = os.path.join(SPRITES_DIR, filename)
    if os.path.exists(path):
        surf = pygame.image.load(path).convert_alpha()
        if size:
            surf = pygame.transform.scale(surf, size)
        return surf
    return None


def load_ai_sprite(filename, bounds):
    """Trim transparent margins, then fit new artwork without distorting logos."""
    image = load_sprite(os.path.join("ai", filename))
    if image is None:
        return None
    # The supplied white logo uses a black matte rather than an alpha channel.
    # Interpret its matte while rendering; keep the reference PNG unchanged.
    if filename == "head_chatgpt.png":
        image.set_colorkey((0, 0, 0))
    rect = image.get_bounding_rect(min_alpha=8)
    if not rect.width or not rect.height:
        return None
    image = image.subsurface(rect).copy()
    scale = min(bounds[0] / rect.width, bounds[1] / rect.height)
    return pygame.transform.scale(image, (max(1, round(rect.width * scale)),
                                         max(1, round(rect.height * scale))))
