"""Shared artwork for cards, HUD icons, weapons and pickups."""
from functools import lru_cache
from pathlib import Path

import pygame

ART_DIR = Path(__file__).resolve().parent / "assets" / "sprites" / "items"


@lru_cache(maxsize=8)
def _load_art(kind):
    image = pygame.image.load(str(ART_DIR / f"{kind}.png")).convert_alpha()
    # Fit the visible object rather than the transparent canvas around it.
    bounds = image.get_bounding_rect(min_alpha=8)
    return image.subsurface(bounds).copy()


@lru_cache(maxsize=256)
def _sized_art(kind, width, height, angle):
    source = _load_art(kind)
    scale = min(width / source.get_width(), height / source.get_height())
    dimensions = (max(1, round(source.get_width() * scale)),
                  max(1, round(source.get_height() * scale)))
    image = pygame.transform.smoothscale(source, dimensions)
    if angle:
        image = pygame.transform.rotate(image, angle)
    return image


def draw_item(surface, kind, center, size=32, angle=0):
    """Draw centered art; cache sizes and 15-degree rotations for moving bugs."""
    if isinstance(size, int):
        width = height = size
    else:
        width, height = size
    rotation = (round(angle / 15) * 15) % 360
    image = _sized_art(kind, width, height, rotation)
    surface.blit(image, image.get_rect(center=(round(center[0]), round(center[1]))))
