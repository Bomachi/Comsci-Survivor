import os
import sys
import math
import random
import pygame

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SPRITES_DIR = os.path.join(BASE_DIR, "assets", "sprites")

from stages.stage1 import Stage1

SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 700
FPS = 60

COLOR_WHITE = (245, 245, 250)
COLOR_HP_GREEN = (46, 204, 113)
COLOR_HP_RED = (231, 76, 60)
COLOR_EXP = (52, 152, 219)
COLOR_MISSILE = (231, 76, 60)
COLOR_GOLD = (255, 215, 0)

def load_sprite(filename: str, size=None):
    path = os.path.join(SPRITES_DIR, filename)
    if os.path.exists(path):
        surf = pygame.image.load(path).convert_alpha()
        if size:
            surf = pygame.transform.scale(surf, size)
        return surf
    return None

class Player:
    def __init__(self, x, y, sprite=None):
        self.x = x
        self.y = y
        self.radius = 18
        self.speed = 2.5
        self.max_hp = 100
        self.hp = 100
        self.facing_right = True
        self.sprite = sprite

        self.level = 1
        self.exp = 0
        self.exp_to_next = 5

        self.shoot_cooldown = 60
        self.shoot_timer = 0
        self.damage = 25

    def handle_input(self):
        keys = pygame.key.get_pressed()
        dx, dy = 0, 0
        if keys[pygame.K_w] or keys[pygame.K_UP]:    dy -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  dy += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  dx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx += 1

        if dx < 0:
            self.facing_right = False
        elif dx > 0:
            self.facing_right = True

        if dx != 0 and dy != 0:
            dx *= 0.7071
            dy *= 0.7071

        self.x += dx * self.speed
        self.y += dy * self.speed

    def update_weapon(self, enemies, missiles):
        self.shoot_timer -= 1
        if self.shoot_timer <= 0 and enemies:
            nearest = min(enemies, key=lambda e: math.hypot(e.x - self.x, e.y - self.y))
            missiles.append(Missile(self.x, self.y, nearest.x, nearest.y, self.damage))
            self.shoot_timer = self.shoot_cooldown

    def add_exp(self, amount):
        self.exp += amount
        if self.exp >= self.exp_to_next:
            self.exp -= self.exp_to_next
            self.level += 1
            self.exp_to_next = int(self.exp_to_next * 1.35) + 3
            self.hp = min(self.max_hp, self.hp + 20)

    def draw(self, surface, cam_x, cam_y):
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)

        if self.sprite:
            img = self.sprite if self.facing_right else pygame.transform.flip(self.sprite, True, False)
            rect = img.get_rect(center=(sx, sy))
            surface.blit(img, rect)
        else:
            pygame.draw.circle(surface, (80, 200, 120), (sx, sy), self.radius)

        bar_w = 40
        bar_h = 6
        hp_pct = max(0, self.hp / self.max_hp)
        pygame.draw.rect(surface, COLOR_HP_RED, (sx - bar_w // 2, sy - 30, bar_w, bar_h))
        pygame.draw.rect(surface, COLOR_HP_GREEN, (sx - bar_w // 2, sy - 30, int(bar_w * hp_pct), bar_h))


class Enemy:
    def __init__(self, x, y, enemy_type="TA", sprite=None):
        self.x = x
        self.y = y
        self.enemy_type = enemy_type
        self.sprite = sprite
        self.facing_right = True

        if enemy_type == "TA":
            self.hp = 20
            self.speed = 2.4
            self.radius = 14
            self.damage = 8
            self.color = (180, 60, 170)
        elif enemy_type == "proffessor":
            self.hp = 45
            self.speed = 1.3
            self.radius = 17
            self.damage = 15
            self.color = (70, 140, 80)
        elif enemy_type == "rector":
            self.hp = 85
            self.speed = 1.7
            self.radius = 18
            self.damage = 22
            self.color = (220, 215, 200)

    def update(self, px, py):
        dx = px - self.x
        dy = py - self.y
        dist = math.hypot(dx, dy)
        if dist > 0:
            self.x += (dx / dist) * self.speed
            self.y += (dy / dist) * self.speed
            self.facing_right = (dx > 0)

    def draw(self, surface, cam_x, cam_y):
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)

        if self.sprite:
            img = self.sprite if self.facing_right else pygame.transform.flip(self.sprite, True, False)
            rect = img.get_rect(center=(sx, sy))
            surface.blit(img, rect)
        else:
            pygame.draw.circle(surface, self.color, (sx, sy), self.radius)

class Missile:
    def __init__(self, x, y, target_x, target_y, damage):
        self.x = x
        self.y = y
        self.damage = damage
        self.speed = 10.0
        self.radius = 6
        self.lifetime = 80

        dx = target_x - x
        dy = target_y - y
        dist = math.hypot(dx, dy) or 1
        self.vx = (dx / dist) * self.speed
        self.vy = (dy / dist) * self.speed

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.lifetime -= 1

    def draw(self, surface, cam_x, cam_y):
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        pygame.draw.circle(surface, COLOR_MISSILE, (sx, sy), self.radius)


class Gem:
    def __init__(self, x, y, value=1):
        self.x = x
        self.y = y
        self.value = value
        self.radius = 6

    def draw(self, surface, cam_x, cam_y):
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        pygame.draw.circle(surface, COLOR_EXP, (sx, sy), self.radius)


class Game:
    def __init__(self):
        pygame.init()
        pygame.font.init()

        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Classroom Survivor - Pygame Edition")
        self.clock = pygame.time.Clock()


        font_path = os.path.join(BASE_DIR, "assets", "fonts", "Minecraft.ttf")
        self.font = pygame.font.Font(font_path, 20)
        self.title_font = pygame.font.Font(font_path, 36)

        self.stage1_tile = load_sprite("stage1_tile.png", (64, 64))
        self.player_sprite = load_sprite("player.png", (48, 48))
        self.TA_sprite = load_sprite("TA.png", (36, 36))
        self.proffessor_sprite = load_sprite("proffessor.png", (40, 40))
        self.skel_sprite = load_sprite("rector.png", (44, 44))

        self.current_stage = Stage1()
        self.reset_game()

    def reset_game(self):
        self.player = Player(0, 0, sprite=self.player_sprite)
        self.enemies = []
        self.missiles = []
        self.gems = []

        self.camera_x = 0
        self.camera_y = 0

        self.spawn_timer = 0
        self.timer_seconds = 0
        self.frame_count = 0
        self.kill_count = 0
        self.is_game_over = False
        self.is_running = True

    def spawn_enemy(self):
        angle = random.uniform(0, math.tau)
        dist = random.uniform(600, 750)
        ex = self.player.x + math.cos(angle) * dist
        ey = self.player.y + math.sin(angle) * dist

        etype = self.current_stage.get_enemy_spawn_type(self.timer_seconds)

        spr = self.TA_sprite
        if etype == "proffessor":
            spr = self.proffessor_sprite
        elif etype == "rector":
            spr = self.skel_sprite

        self.enemies.append(Enemy(ex, ey, etype, sprite=spr))

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.is_running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.is_running = False
                elif event.key == pygame.K_r and self.is_game_over:
                    self.reset_game()

    def update(self):
        if self.is_game_over:
            return

        self.frame_count += 1
        if self.frame_count % FPS == 0:
            self.timer_seconds += 1

        self.player.handle_input()
        self.player.update_weapon(self.enemies, self.missiles)

        self.camera_x += (self.player.x - SCREEN_WIDTH // 2 - self.camera_x) * 0.1
        self.camera_y += (self.player.y - SCREEN_HEIGHT // 2 - self.camera_y) * 0.1

        self.spawn_timer += 1
        if self.spawn_timer >= 40:
            self.spawn_enemy()
            self.spawn_timer = 0

        for m in self.missiles[:]:
            m.update()
            if m.lifetime <= 0:
                self.missiles.remove(m)
                continue

            for e in self.enemies:
                if math.hypot(e.x - m.x, e.y - m.y) < e.radius + m.radius:
                    e.hp -= m.damage
                    if m in self.missiles:
                        self.missiles.remove(m)
                    break

        for e in self.enemies[:]:
            e.update(self.player.x, self.player.y)

            if math.hypot(e.x - self.player.x, e.y - self.player.y) < e.radius + self.player.radius:
                self.player.hp -= e.damage * 0.05
                if self.player.hp <= 0:
                    self.player.hp = 0
                    self.is_game_over = True

            if e.hp <= 0:
                self.gems.append(Gem(e.x, e.y))
                self.kill_count += 1
                self.enemies.remove(e)

        for g in self.gems[:]:
            if math.hypot(g.x - self.player.x, g.y - self.player.y) < self.player.radius + 60:
                g.x += (self.player.x - g.x) * 0.15
                g.y += (self.player.y - g.y) * 0.15

            if math.hypot(g.x - self.player.x, g.y - self.player.y) < self.player.radius + g.radius:
                self.player.add_exp(g.value)
                self.gems.remove(g)

    def draw_background(self):
        if self.stage1_tile:
            tile_w, tile_h = 64, 64
            start_col = int(self.camera_x // tile_w) - 1
            end_col = int((self.camera_x + SCREEN_WIDTH) // tile_w) + 2
            start_row = int(self.camera_y // tile_h) - 1
            end_row = int((self.camera_y + SCREEN_HEIGHT) // tile_h) + 2

            for c in range(start_col, end_col):
                for r in range(start_row, end_row):
                    sx = c * tile_w - int(self.camera_x)
                    sy = r * tile_h - int(self.camera_y)
                    self.screen.blit(self.stage1_tile, (sx, sy))
        else:
            self.screen.fill(self.current_stage.bg_color)

    def draw_hud(self):
        bar_h = 12
        ratio = min(1.0, self.player.exp / self.player.exp_to_next)
        pygame.draw.rect(self.screen, (20, 20, 30), (0, 0, SCREEN_WIDTH, bar_h))
        pygame.draw.rect(self.screen, COLOR_EXP, (0, 0, int(SCREEN_WIDTH * ratio), bar_h))

        lvl_txt = self.font.render(f"LV {self.player.level}", True, COLOR_WHITE)
        self.screen.blit(lvl_txt, (15, bar_h + 10))

        mins = self.timer_seconds // 60
        secs = self.timer_seconds % 60
        time_txt = self.font.render(f"TIME: {mins:02d}:{secs:02d}", True, COLOR_WHITE)
        self.screen.blit(time_txt, (SCREEN_WIDTH // 2 - time_txt.get_width() // 2, bar_h + 10))

        kill_txt = self.font.render(f"KILLS: {self.kill_count}", True, (240, 90, 90))
        self.screen.blit(kill_txt, (SCREEN_WIDTH - kill_txt.get_width() - 15, bar_h + 10))

    def render(self):
        self.draw_background()

        for g in self.gems:
            g.draw(self.screen, self.camera_x, self.camera_y)

        for m in self.missiles:
            m.draw(self.screen, self.camera_x, self.camera_y)

        for e in self.enemies:
            e.draw(self.screen, self.camera_x, self.camera_y)

        self.player.draw(self.screen, self.camera_x, self.camera_y)

        self.draw_hud()

        if self.is_game_over:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((40, 10, 15, 200))
            self.screen.blit(overlay, (0, 0))

            over_txt = self.title_font.render("GAME OVER", True, (255, 70, 70))
            self.screen.blit(over_txt, (SCREEN_WIDTH // 2 - over_txt.get_width() // 2, 250))

            restart_txt = self.font.render("Press [ R ] to Restart | Press [ ESC ] to Quit", True, COLOR_GOLD)
            self.screen.blit(restart_txt, (SCREEN_WIDTH // 2 - restart_txt.get_width() // 2, 330))

        pygame.display.flip()

    def run(self):
        while self.is_running:
            self.handle_events()
            self.update()
            self.render()
            self.clock.tick(FPS)

        pygame.quit()
        sys.exit()


def main():
    game = Game()
    game.run()


if __name__ == "__main__":
    main()