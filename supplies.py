"""Explorable supply crates and healing food; all timers use gameplay seconds."""
import math
import random

import pygame

from item_art import draw_item

CRATE_OPEN_SECONDS = 5.0
FOOD_HEAL = 30
CELL_SIZE = 800


class Food:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.radius = 14

    def draw(self, surface, cam_x, cam_y):
        center = (round(self.x - cam_x), round(self.y - cam_y))
        pygame.draw.circle(surface, (70, 180, 100), center, 24, 2)
        draw_item(surface, "food", center, 40)


class SupplyCrate:
    radius = 24

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.progress = 0.0

    def touching(self, player):
        return math.hypot(self.x - player.x, self.y - player.y) <= self.radius + player.radius

    def update(self, dt, holding):
        self.progress = min(CRATE_OPEN_SECONDS, self.progress + dt) if holding else 0.0
        return self.progress >= CRATE_OPEN_SECONDS - 1e-9

    def draw(self, surface, cam_x, cam_y, font, touching):
        x, y = round(self.x - cam_x), round(self.y - cam_y)
        rect = pygame.Rect(x - 24, y - 20, 48, 40)
        pygame.draw.rect(surface, (95, 55, 32), rect, border_radius=4)
        pygame.draw.rect(surface, (225, 173, 85), rect, 3, border_radius=4)
        pygame.draw.line(surface, (225, 173, 85), (x - 23, y - 5), (x + 23, y - 5), 3)
        pygame.draw.rect(surface, (245, 215, 120), (x - 5, y - 8, 10, 15), border_radius=2)
        if touching or self.progress > 0:
            pygame.draw.rect(surface, (25, 25, 35), (x - 35, y - 36, 70, 8))
            width = round(70 * self.progress / CRATE_OPEN_SECONDS)
            pygame.draw.rect(surface, (90, 220, 135), (x - 35, y - 36, width, 8))
            text = font.render(f"HOLD STILL {self.progress:.1f}/5s", True, (245, 245, 250))
            label_rect = text.get_rect(midbottom=(x, y - 41))
            pygame.draw.rect(surface, (25, 25, 35), label_rect.inflate(10, 6), border_radius=3)
            surface.blit(text, label_rect)


class Supplies:
    """One stable crate per map cell, loaded nearby; opened crates stay consumed."""
    def __init__(self, seed):
        self.seed = seed
        self.crates = {}
        self.opened_cells = set()
        self.foods = []

    def populate(self, x, y):
        cx, cy = math.floor((x + CELL_SIZE / 2) / CELL_SIZE), math.floor((y + CELL_SIZE / 2) / CELL_SIZE)
        nearby = {(cx + dx, cy + dy) for dx in range(-2, 3) for dy in range(-2, 3)}
        self.crates = {cell: crate for cell, crate in self.crates.items() if cell in nearby}
        for cell in sorted(nearby - self.opened_cells - self.crates.keys()):
            if cell == (0, 0):
                # A first crate is visible from the starting position.
                position = (140, 0)
            else:
                rng = random.Random(self.seed ^ (cell[0] * 73856093) ^ (cell[1] * 19349663))
                position = (cell[0] * CELL_SIZE + rng.uniform(-220, 220),
                            cell[1] * CELL_SIZE + rng.uniform(-220, 220))
            self.crates[cell] = SupplyCrate(*position)

    def update(self, dt, player, moved):
        self.populate(player.x, player.y)
        touching = [(cell, crate) for cell, crate in self.crates.items() if crate.touching(player)]
        target = min(touching, key=lambda entry: math.hypot(entry[1].x - player.x, entry[1].y - player.y))[0] if touching else None
        for cell, crate in list(self.crates.items()):
            if crate.update(dt, cell == target and not moved):
                self.opened_cells.add(cell)
                del self.crates[cell]
                # Drop beside the crate so the player sees and walks over the food.
                self.foods.append(Food(crate.x + 64, crate.y))
        for food in self.foods[:]:
            if math.hypot(food.x - player.x, food.y - player.y) <= food.radius + player.radius:
                player.hp = min(player.max_hp, player.hp + FOOD_HEAL)
                self.foods.remove(food)

    def draw(self, surface, cam_x, cam_y, font, player):
        for crate in self.crates.values():
            if -80 < crate.x - cam_x < surface.get_width() + 80 and -80 < crate.y - cam_y < surface.get_height() + 80:
                crate.draw(surface, cam_x, cam_y, font, crate.touching(player))
        for food in self.foods:
            food.draw(surface, cam_x, cam_y)
