"""Procedural animation and hit effects for single-frame sprites.

The sprites have one frame each, so movement is sold with procedural motion:
a walk bob with squash and stretch, a contact shadow, a white flash on hit,
a fade-in when spawning, pixel bursts on death and floating damage numbers.
Transformed images are cached per sprite so 900 enemies stay cheap to draw.
"""
import math
import random

import pygame

SQUASH = [(1.00, 1.00), (1.06, 0.94), (1.00, 1.00), (0.95, 1.05)]   # walk cycle
WINDUP = (1.18, 0.82)                                               # crouch before a lunge

_cache = {}
_shadow_cache = {}


def _variant(sprite, key, make):
    k = (id(sprite), key)
    if k not in _cache:
        _cache[k] = make()
    return _cache[k]


def frame(sprite, sx, sy, flip=False, white=False):
    def make():
        img = sprite
        if sx != 1 or sy != 1:
            img = pygame.transform.scale(img, (max(1, round(img.get_width() * sx)), max(1, round(img.get_height() * sy))))
        if flip:
            img = pygame.transform.flip(img, True, False)
        if white:
            mask = pygame.mask.from_surface(img)
            img = mask.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))
        return img
    return _variant(sprite, (sx, sy, flip, white), make)


def shadow(width):
    width = max(8, int(width))
    if width not in _shadow_cache:
        surf = pygame.Surface((width, max(4, width // 3)), pygame.SRCALPHA)
        pygame.draw.ellipse(surf, (0, 0, 0, 70), surf.get_rect())
        _shadow_cache[width] = surf
    return _shadow_cache[width]


class Animator:
    """Per-character animation state. Call update() every frame, then draw()."""

    def __init__(self):
        self.phase = random.uniform(0, math.tau)
        self.flash = 0.0
        self.spawn = 0.35          # fade-in time left
        self.last_x = self.last_y = None
        self.moving = False

    def update(self, x, y, dt, speed_hint=120):
        if self.last_x is not None:
            moved = math.hypot(x - self.last_x, y - self.last_y)
            self.moving = moved > 0.05
            # Faster walkers step faster: one cycle per ~38 px travelled.
            self.phase += moved / 38 * math.tau
        self.last_x, self.last_y = x, y
        self.flash = max(0.0, self.flash - dt)
        self.spawn = max(0.0, self.spawn - dt)

    def hit(self):
        self.flash = 0.09

    def draw(self, surface, sprite, sx, sy, facing_right=True, windup=False, alpha=255):
        """Draw `sprite` with its feet near (sx, sy + h/2) like the original centred blit."""
        if windup:
            scale = WINDUP
        elif self.moving:
            scale = SQUASH[int(self.phase / (math.tau / 4)) % 4]
        else:
            scale = SQUASH[0]
        bob = -abs(math.sin(self.phase)) * 3 if self.moving else 0
        img = frame(sprite, scale[0], scale[1], not facing_right, self.flash > 0)
        base_h = sprite.get_height()
        feet_y = sy + base_h / 2
        sh = shadow(sprite.get_width() * 0.7)
        surface.blit(sh, (sx - sh.get_width() / 2, feet_y - sh.get_height() / 2))
        rect = img.get_rect(midbottom=(round(sx), round(feet_y + bob)))
        if self.spawn > 0:
            rise = self.spawn / 0.35
            img = img.copy()
            img.set_alpha(int(255 * (1 - rise)))
            rect.y += int(rise * 10)
        elif alpha < 255:
            img = img.copy()
            img.set_alpha(alpha)
        surface.blit(img, rect)


def sprite_colours(sprite, count=6):
    """A few opaque colours from a sprite, for death particles."""
    key = ("colours", id(sprite))
    if key not in _cache:
        colours = []
        w, h = sprite.get_size()
        for y in range(0, h, 3):
            for x in range(0, w, 3):
                c = sprite.get_at((x, y))
                if c.a > 200:
                    colours.append((c.r, c.g, c.b))
        random.shuffle(colours)
        _cache[key] = colours[:count] or [(200, 200, 200)]
    return _cache[key]


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "colour", "size")

    def __init__(self, x, y, colour, speed=160, life=0.55, size=3):
        angle = random.uniform(0, math.tau)
        s = random.uniform(0.3, 1.0) * speed
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(angle) * s, math.sin(angle) * s - 60
        self.life = self.max_life = random.uniform(0.6, 1.0) * life
        self.colour = colour
        self.size = size


class FloatingText:
    __slots__ = ("x", "y", "text", "life", "colour", "value")

    def __init__(self, x, y, value, colour=(255, 240, 200)):
        self.x, self.y = x + random.uniform(-6, 6), y
        self.value = value
        self.text = None
        self.life = 0.7
        self.colour = colour


class Effects:
    """Particles and damage numbers in world space."""

    MAX_PARTICLES = 900
    MAX_TEXTS = 60

    def __init__(self):
        self.particles = []
        self.texts = []
        self._text_cache = {}

    def burst(self, x, y, sprite=None, count=12, colours=None):
        colours = colours or (sprite_colours(sprite) if sprite else [(220, 220, 220)])
        room = self.MAX_PARTICLES - len(self.particles)
        for _ in range(min(count, max(0, room))):
            self.particles.append(Particle(x, y, random.choice(colours)))

    def damage(self, x, y, amount, colour=(255, 240, 200)):
        if len(self.texts) < self.MAX_TEXTS and amount >= 1:
            self.texts.append(FloatingText(x, y, int(amount), colour))

    def update(self, dt):
        for p in self.particles:
            p.life -= dt
            p.vy += 420 * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vx *= 0.96
        self.particles = [p for p in self.particles if p.life > 0]
        for t in self.texts:
            t.life -= dt
            t.y -= 38 * dt
        self.texts = [t for t in self.texts if t.life > 0]

    def clear(self):
        self.particles.clear()
        self.texts.clear()

    def draw(self, surface, cam_x, cam_y, font):
        for p in self.particles:
            size = max(1, round(p.size * p.life / p.max_life + 1))
            pygame.draw.rect(surface, p.colour, (p.x - cam_x, p.y - cam_y, size, size))
        for t in self.texts:
            key = (t.value, t.colour)
            if key not in self._text_cache:
                if len(self._text_cache) > 400:
                    self._text_cache.clear()
                front = font.render(str(t.value), True, t.colour)
                back = font.render(str(t.value), True, (30, 20, 20))
                surf = pygame.Surface((front.get_width() + 2, front.get_height() + 2), pygame.SRCALPHA)
                surf.blit(back, (2, 2))
                surf.blit(front, (0, 0))
                self._text_cache[key] = surf
            img = self._text_cache[key]
            img.set_alpha(int(255 * min(1, t.life / 0.3)))
            surface.blit(img, (t.x - cam_x - img.get_width() / 2, t.y - cam_y))
