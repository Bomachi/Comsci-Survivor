"""Stage 2 scenery: marble floor tiles, props (desks, shelves...) and ambience.

The map is endless, so props are placed per 640x640 chunk with a random
generator seeded from the chunk coordinates. The same chunk always gets the
same layout, nothing has to be stored, and only chunks near the camera exist.
"""
import math
import os
import random

import pygame

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROP_DIR = os.path.join(BASE_DIR, "assets", "sprites", "props")
CHUNK = 640
TILE = 64
SAFE_RADIUS = 260   # keep the player's start area clear

# name: (draw scale, solid footprint as fraction of sprite (x, y, w, h) from the sprite's top-left)
PROP_TYPES = {
    "desk": (1.12, (0.06, 0.55, 0.88, 0.42)),
    "bookshelf": (1.35, (0.05, 0.62, 0.9, 0.36)),
    "cabinet": (1.25, (0.08, 0.62, 0.84, 0.36)),
    "plant": (1.1, (0.25, 0.7, 0.5, 0.28)),
}
DECOR_TYPES = {"coins": 1.3}
AI_PROP_TYPES = {
    "ai_server": ((72, 102), (0.06, 0.62, 0.88, 0.36)),
    "ai_terminal": ((96, 72), (0.06, 0.60, 0.88, 0.38)),
}


def _marble_tile(seed):
    """Procedural 64x64 marble floor tile with a dark-green inlay border."""
    rng = random.Random(seed)
    surf = pygame.Surface((TILE, TILE))
    base = (226, 232, 220)
    surf.fill(base)
    for _ in range(60):  # soft mottling
        x, y = rng.randrange(TILE), rng.randrange(TILE)
        shade = rng.randint(-8, 6)
        pygame.draw.circle(surf, tuple(max(0, min(255, c + shade)) for c in base), (x, y), rng.randint(2, 5))
    for _ in range(rng.randint(1, 3)):  # veins: random walks
        x, y = rng.uniform(0, TILE), rng.uniform(0, TILE)
        angle = rng.uniform(0, math.tau)
        colour = (210, 217, 206) if rng.random() < 0.75 else (198, 208, 196)
        for _ in range(rng.randint(30, 70)):
            angle += rng.uniform(-0.5, 0.5)
            nx, ny = x + math.cos(angle) * 1.5, y + math.sin(angle) * 1.5
            pygame.draw.line(surf, colour, (x % TILE, y % TILE), (nx % TILE, ny % TILE))
            x, y = nx, ny
    pygame.draw.rect(surf, (178, 192, 176), (0, 0, TILE, TILE), 1)   # grout
    return surf


def build_tiles(count=6):
    tiles = [_marble_tile(i * 7919) for i in range(count)]
    # One tile in every 4x4 block gets a green inlay diamond for rhythm.
    accent = tiles[0].copy()
    c = TILE // 2
    pygame.draw.polygon(accent, (58, 120, 80), [(c, c - 10), (c + 10, c), (c, c + 10), (c - 10, c)])
    pygame.draw.polygon(accent, (230, 200, 90), [(c, c - 4), (c + 4, c), (c, c + 4), (c - 4, c)])
    return tiles, accent


def build_ai_tiles(count=6):
    """Code-native circuit floor; no external texture is needed at runtime."""
    tiles = []
    for i in range(count):
        rng = random.Random(7919 * i + 3)
        tile = pygame.Surface((TILE, TILE))
        tile.fill((17 + i % 3, 25 + i % 2, 43 + i % 4))
        pygame.draw.rect(tile, (32, 47, 68), tile.get_rect(), 1)
        for _ in range(2):
            x, y = rng.randrange(10, 50), rng.randrange(12, 50)
            color = rng.choice([(28, 80, 95), (35, 59, 110), (32, 94, 88)])
            pygame.draw.lines(tile, color, False, [(0, y), (x, y), (x, 0)], 1)
            pygame.draw.circle(tile, (50, 139, 151), (x, y), 2, 1)
        tiles.append(tile)
    accent = tiles[0].copy()
    pygame.draw.rect(accent, (44, 112, 140), (23, 23, 18, 18), 2)
    pygame.draw.rect(accent, (38, 63, 94), (27, 27, 10, 10))
    return tiles, accent


def draw_floor(screen, tiles, accent, cam_x, cam_y, theme="accounting"):
    w, h = screen.get_size()
    c0, c1 = int(cam_x // TILE) - 1, int((cam_x + w) // TILE) + 1
    r0, r1 = int(cam_y // TILE) - 1, int((cam_y + h) // TILE) + 1
    for c in range(c0, c1 + 1):
        for r in range(r0, r1 + 1):
            if c % 4 == 0 and r % 4 == 0:
                tile = accent
            else:
                tile = tiles[(c * 73856093 ^ r * 19349663) % len(tiles)]
            screen.blit(tile, (c * TILE - int(cam_x), r * TILE - int(cam_y)))
    if theme == "ai":
        return
    # A green carpet runner every 8 rows gives the hall some structure.
    for r in range(r0, r1 + 1):
        if r % 8 == 4:
            y = r * TILE - int(cam_y) + 12
            pygame.draw.rect(screen, (70, 120, 86), (0, y, w, 40))
            pygame.draw.rect(screen, (220, 190, 90), (0, y + 3, w, 2))
            pygame.draw.rect(screen, (220, 190, 90), (0, y + 35, w, 2))


class Prop:
    def __init__(self, kind, image, x, y, solid=None):
        self.kind = kind
        self.image = image
        self.x, self.y = x, y          # bottom-centre (feet) position, used for depth sorting
        self.rect = image.get_rect(midbottom=(round(x), round(y)))
        self.solid = solid             # pygame.Rect footprint, or None for floor decor

    @property
    def sort_y(self):
        return self.y

    def draw(self, surface, cam_x, cam_y):
        surface.blit(self.image, (self.rect.x - cam_x, self.rect.y - cam_y))


class Scenery:
    def __init__(self, seed=2026, theme="accounting"):
        self.seed = seed
        self.theme = theme
        self.images = {}
        self.prop_types = AI_PROP_TYPES if theme == "ai" else PROP_TYPES
        image_types = self.prop_types if theme == "ai" else {**PROP_TYPES, **{k: (v, None) for k, v in DECOR_TYPES.items()}}
        for name, (scale, _) in image_types.items():
            folder = os.path.join(BASE_DIR, "assets", "sprites", "ai") if theme == "ai" else PROP_DIR
            path = os.path.join(folder, name + ".png")
            if os.path.exists(path):
                img = pygame.image.load(path).convert_alpha()
                if theme == "ai":
                    img = img.subsurface(img.get_bounding_rect(min_alpha=8)).copy()
                    factor = min(scale[0] / img.get_width(), scale[1] / img.get_height())
                    size = (max(1, round(img.get_width() * factor)), max(1, round(img.get_height() * factor)))
                else:
                    size = (round(img.get_width() * scale), round(img.get_height() * scale))
                self.images[name] = pygame.transform.scale(img, size)
        self.tiles, self.accent = build_ai_tiles() if theme == "ai" else build_tiles()
        self.chunks = {}
        self.vignette = None
        self.dust = [[random.uniform(0, 1000), random.uniform(0, 700), random.uniform(6, 16), random.uniform(0, math.tau)]
                     for _ in range(45)]

    def _make_chunk(self, cx, cy):
        rng = random.Random((cx * 92837111) ^ (cy * 689287499) ^ self.seed)
        if self.theme == "ai":
            return self._make_ai_chunk(cx, cy, rng)
        props = []
        kinds = [k for k in PROP_TYPES if k in self.images]
        if not kinds:
            return props
        # Desks in a little classroom grid, plus shelves/cabinets/plants around.
        layout = rng.choice(["classroom", "office", "open"])
        origin_x, origin_y = cx * CHUNK, cy * CHUNK
        spots = []
        if layout == "classroom" and "desk" in self.images:
            for i in range(rng.randint(2, 4)):
                for j in range(2):
                    spots.append(("desk", origin_x + 130 + i * 120, origin_y + 230 + j * 150))
        elif layout == "office":
            for i in range(rng.randint(3, 5)):
                spots.append((rng.choice(["bookshelf", "cabinet"]), origin_x + 80 + i * 105, origin_y + 140))
            spots.append(("plant", origin_x + 90, origin_y + 470))
            spots.append(("plant", origin_x + 540, origin_y + 470))
        else:
            for _ in range(rng.randint(2, 4)):
                spots.append((rng.choice(kinds), origin_x + rng.uniform(80, CHUNK - 80), origin_y + rng.uniform(100, CHUNK - 60)))
        for kind, x, y in spots:
            if kind not in self.images or math.hypot(x, y) < SAFE_RADIUS:
                continue
            img = self.images[kind]
            fx, fy, fw, fh = PROP_TYPES[kind][1]
            left, top = x - img.get_width() / 2, y - img.get_height()
            solid = pygame.Rect(round(left + fx * img.get_width()), round(top + fy * img.get_height()),
                                round(fw * img.get_width()), round(fh * img.get_height()))
            props.append(Prop(kind, img, x, y, solid))
        if "coins" in self.images:
            for _ in range(rng.randint(0, 3)):
                x, y = origin_x + rng.uniform(40, CHUNK - 40), origin_y + rng.uniform(40, CHUNK - 40)
                if not any(p.solid and p.solid.inflate(30, 30).collidepoint(x, y) for p in props):
                    props.append(Prop("coins", self.images["coins"], x, y))
        return props

    def _make_ai_chunk(self, cx, cy, rng):
        props = []
        # Widely separated racks leave continuous aisles for the 88px-wide boss.
        spots = [("ai_server", x, y) for x in (120, 520) for y in (180, 510)]
        spots.append(("ai_terminal", 320 + rng.randint(-30, 30), 345))
        for kind, ox, oy in spots:
            x, y = cx * CHUNK + ox, cy * CHUNK + oy
            if kind not in self.images or math.hypot(x, y) < SAFE_RADIUS:
                continue
            img = self.images[kind]
            fx, fy, fw, fh = self.prop_types[kind][1]
            left, top = x - img.get_width() / 2, y - img.get_height()
            solid = pygame.Rect(round(left + fx * img.get_width()), round(top + fy * img.get_height()),
                                round(fw * img.get_width()), round(fh * img.get_height()))
            props.append(Prop(kind, img, x, y, solid))
        return props

    def update(self, px, py, radius=1):
        """Keep chunks around the player; returns True when the solid set changed."""
        pcx, pcy = int(px // CHUNK), int(py // CHUNK)
        wanted = {(pcx + dx, pcy + dy) for dx in range(-radius - 1, radius + 2) for dy in range(-radius - 1, radius + 2)}
        changed = False
        for key in wanted - self.chunks.keys():
            self.chunks[key] = self._make_chunk(*key)
            changed = True
        for key in list(self.chunks.keys() - wanted):
            del self.chunks[key]
            changed = True
        return changed

    def props(self):
        for chunk in self.chunks.values():
            yield from chunk

    def solid_rects(self):
        return [p.solid for p in self.props() if p.solid]

    def visible(self, cam_x, cam_y, w, h):
        view = pygame.Rect(cam_x - 100, cam_y - 100, w + 200, h + 200)
        return [p for p in self.props() if view.colliderect(p.rect)]

    def draw_floor(self, screen, cam_x, cam_y):
        draw_floor(screen, self.tiles, self.accent, cam_x, cam_y, self.theme)
        # Floor decor (coins) is flat: draw it under everything.
        for p in self.visible(cam_x, cam_y, *screen.get_size()):
            if not p.solid:
                p.draw(screen, cam_x, cam_y)

    def draw_ambience(self, screen, dt):
        w, h = screen.get_size()
        for mote in self.dust:  # slow drifting paper dust
            mote[3] += dt * 0.6
            mote[0] = (mote[0] + math.cos(mote[3]) * mote[2] * dt) % w
            mote[1] = (mote[1] - mote[2] * dt * 0.5) % h
            color = (70, 165, 200) if self.theme == "ai" else (255, 255, 240)
            pygame.draw.rect(screen, color, (mote[0], mote[1], 2, 2))
        if self.vignette is None or self.vignette.get_size() != (w, h):
            self.vignette = _radial_vignette(w, h)
        screen.blit(self.vignette, (0, 0))


def _radial_vignette(w, h, strength=120):
    small = pygame.Surface((w // 8, h // 8), pygame.SRCALPHA)
    cx, cy = small.get_width() / 2, small.get_height() / 2
    max_d = math.hypot(cx, cy)
    for x in range(small.get_width()):
        for y in range(small.get_height()):
            d = math.hypot(x - cx, y - cy) / max_d
            a = int(strength * max(0, d - 0.55) / 0.45) if d > 0.55 else 0
            small.set_at((x, y), (8, 18, 12, min(255, a)))
    return pygame.transform.smoothscale(small, (w, h))
