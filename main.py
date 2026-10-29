import os
import sys
import math
import random
from enum import Enum
import pygame

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SPRITES_DIR = os.path.join(BASE_DIR, "assets", "sprites")

from stages.stage1 import Stage1
from upgrades import available_upgrades, apply_upgrade
from weapons import WeaponSystem, WEAPONS, draw_icon
from item_art import draw_item
from supplies import Supplies

SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 700
FPS = 60

COLOR_WHITE = (245, 245, 250)
COLOR_HP_GREEN = (46, 204, 113)
COLOR_HP_RED = (231, 76, 60)
COLOR_EXP = (52, 152, 219)
COLOR_GOLD = (255, 215, 0)
COLOR_CARD_BG = (35, 30, 50)
COLOR_CARD_BORDER = (100, 90, 130)


class GameState(Enum):
    MAIN_MENU = 1
    PLAYING = 2
    PAUSED = 3
    GAME_OVER = 4


def load_sprite(filename: str, size=None):
    path = os.path.join(SPRITES_DIR, filename)
    if os.path.exists(path):
        surf = pygame.image.load(path).convert_alpha()
        if size:
            surf = pygame.transform.scale(surf, size)
        return surf
    return None


class Button:
    def __init__(self, x, y, width, height, text="", font=None, bg_color=(40, 40, 50), hover_color=(70, 70, 90), text_color=(255, 255, 255), image=None):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.font = font
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.text_color = text_color
        self.is_hovered = False
        self.image = image

    def update(self, mouse_pos):
        self.is_hovered = self.rect.collidepoint(mouse_pos)

    def draw(self, surface):
        if self.image:
            scaled_img = pygame.transform.scale(self.image, (self.rect.width, self.rect.height))
            surface.blit(scaled_img, self.rect)
            if self.is_hovered:
                hover_overlay = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
                hover_overlay.fill((255, 255, 255, 45))
                surface.blit(hover_overlay, self.rect.topleft)
        else:
            color = self.hover_color if self.is_hovered else self.bg_color
            pygame.draw.rect(surface, color, self.rect, border_radius=10)
            pygame.draw.rect(surface, (200, 200, 200), self.rect, width=2, border_radius=10)
            if self.font and self.text:
                txt_surf = self.font.render(self.text, True, self.text_color)
                txt_rect = txt_surf.get_rect(center=self.rect.center)
                surface.blit(txt_surf, txt_rect)

    def is_clicked(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.is_hovered:
                return True
        return False


class FloatingText:
    def __init__(self, x, y, text, color=(255, 80, 80), font_size=20, duration=0.6):
        self.x = x
        self.y = y
        self.text = str(text)
        self.color = color
        self.font = pygame.font.SysFont("arial", font_size, bold=True)
        self.duration = duration
        self.timer = duration
        self.vy = -40

    def update(self, dt):
        self.timer -= dt
        self.y += self.vy * dt

    def draw(self, surface, cam_x, cam_y):
        if self.timer <= 0:
            return
        alpha = int(255 * max(0, (self.timer / self.duration)))
        txt_surf = self.font.render(self.text, True, self.color)
        txt_surf.set_alpha(alpha)
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        surface.blit(txt_surf, (sx, sy))


class Particle:
    def __init__(self, x, y, color=(255, 180, 40)):
        self.x = x
        self.y = y
        self.color = color
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(60, 250)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.radius = random.uniform(3, 6)
        self.lifetime = random.uniform(0.2, 0.5)
        self.timer = self.lifetime

    def update(self, dt):
        self.timer -= dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.radius = max(0, self.radius - dt * 8)

    def draw(self, surface, cam_x, cam_y):
        if self.timer <= 0 or self.radius <= 0:
            return
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        pygame.draw.circle(surface, self.color, (sx, sy), int(self.radius))


class Player:
    def __init__(self, x, y, sprite=None):
        self.x = x
        self.y = y
        self.radius = 18
        self.speed = 150.0
        self.max_hp = 100
        self.hp = 100
        self.facing_right = True
        self.sprite = sprite
        self.level = 1
        self.exp = 0
        self.exp_to_next = 5
        self.pending_level_ups = 0
        
        self.magnet_range = 60
        self.weapons = WeaponSystem()
        self.coffee_remaining = 0.0
        self.hurt_remaining = 0.0

    @property
    def move_speed(self):
        return self.speed * (1.15 if self.coffee_remaining > 0 else 1.0)

    def drink_coffee(self):
        self.coffee_remaining = 10.0

    def handle_input(self, dt):
        keys = pygame.key.get_pressed()
        dx = int(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - int(keys[pygame.K_a] or keys[pygame.K_LEFT])
        dy = int(keys[pygame.K_s] or keys[pygame.K_DOWN]) - int(keys[pygame.K_w] or keys[pygame.K_UP])
        if dx:
            self.facing_right = dx > 0
        length = math.hypot(dx, dy) or 1
        self.x += dx / length * self.move_speed * dt
        self.y += dy / length * self.move_speed * dt

    def add_exp(self, amount):
        self.exp += amount
        leveled_up = False
        while self.exp >= self.exp_to_next:
            self.exp -= self.exp_to_next
            self.level += 1
            self.exp_to_next = int(self.exp_to_next * 1.35) + 3
            self.pending_level_ups += 1
            leveled_up = True
        return leveled_up

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
        self.slow_remaining = 0.0
        self.enemy_type = enemy_type
        self.sprite = sprite
        self.facing_right = True

        if enemy_type == "TA":
            self.hp = 20
            self.speed = 144.0
            self.radius = 14
            self.damage = 8
            self.color = (180, 60, 170)
        elif enemy_type == "professor":
            self.hp = 45
            self.speed = 78.0
            self.radius = 17
            self.damage = 15
            self.color = (70, 140, 80)
        elif enemy_type == "rector":
            self.hp = 85
            self.speed = 102.0
            self.radius = 18
            self.damage = 22
            self.color = (220, 215, 200)
        else:
            raise ValueError(f"Unknown enemy type: {enemy_type}")

    def update(self, px, py, dt):
        speed = self.speed * (0.55 if self.slow_remaining > 0 else 1.0)
        self.slow_remaining = max(0, self.slow_remaining - dt)
        dx = px - self.x
        dy = py - self.y
        dist = math.hypot(dx, dy)
        if dist > 0:
            step = min(dist, speed * dt)
            self.x += (dx / dist) * step
            self.y += (dy / dist) * step
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


class Gem:
    def __init__(self, x, y, value=1):
        self.x = x
        self.y = y
        self.value = value
        self.radius = 6

    def draw(self, surface, cam_x, cam_y):
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        draw_item(surface, "exp", (sx, sy), 16)


def draw_coffee(surface, center):
    draw_item(surface, "coffee", center, 28)


class Coffee:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.radius = 12
        self.life = 20.0

    def draw(self, surface, cam_x, cam_y):
        draw_coffee(surface, (self.x-cam_x, self.y-cam_y))


class Game:
    def __init__(self):
        pygame.init()
        pygame.font.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Comsci Survivor")
        self.clock = pygame.time.Clock()

        font_path = os.path.join(BASE_DIR, "assets", "fonts", "Minecraft.ttf")
        if os.path.exists(font_path):
            self.font = pygame.font.Font(font_path, 18)
            self.small_font = pygame.font.Font(font_path, 13)
            self.title_font = pygame.font.Font(font_path, 36)
        else:
            self.font = pygame.font.SysFont("tahoma", 18)
            self.small_font = pygame.font.SysFont("tahoma", 13)
            self.title_font = pygame.font.SysFont("tahoma", 36)

        self.stage1_tile = load_sprite("stage1_tile.png", (64, 64))
        self.player_sprite = load_sprite("player.png", (48, 48))
        self.TA_sprite = load_sprite("TA.png", (36, 36))
        self.professor_sprite = load_sprite("professor.png", (40, 40))
        self.skel_sprite = load_sprite("rector.png", (44, 44))

        self.card_frame = load_sprite("card_frame.png", (240, 300))
        self.card_frame_hover = load_sprite("card_frame_hover.png", (240, 300))

        self.menu_bg = load_sprite("main_menu_background.jpg", (SCREEN_WIDTH, SCREEN_HEIGHT))

        self.img_start = load_sprite("start_game_button.png", (220, 60))
        self.img_quit = load_sprite("quit_button.png", (220, 60))
        self.img_resume = load_sprite("resume_button.png", (220, 60))
        self.img_restart = load_sprite("restart_button.png", (220, 60))
        self.img_main_menu = load_sprite("main_menu_button.png", (220, 60))

        self.btn_start = Button(SCREEN_WIDTH // 2 - 110, 480, 220, 60, "START GAME", self.font, image=self.img_start)
        self.btn_quit = Button(SCREEN_WIDTH // 2 - 110, 560, 220, 60, "QUIT", self.font, image=self.img_quit)

        self.btn_resume = Button(SCREEN_WIDTH // 2 - 110, 250, 220, 60, "RESUME", self.font, image=self.img_resume)
        self.btn_restart = Button(SCREEN_WIDTH // 2 - 110, 330, 220, 60, "RESTART", self.font, image=self.img_restart)
        self.btn_main_menu = Button(SCREEN_WIDTH // 2 - 110, 410, 220, 60, "MAIN MENU", self.font, image=self.img_main_menu)

        self.current_stage = Stage1()
        self.state = GameState.MAIN_MENU
        self.reset_game()

    def reset_game(self):
        self.player = Player(0, 0, sprite=self.player_sprite)
        self.enemies = []
        self.coffees = []
        self.gems = []
        self.floating_texts = []
        self.particles = []

        self.supplies = Supplies(random.getrandbits(32))
        self.supplies.populate(self.player.x, self.player.y)
        self.camera_x = self.player.x - SCREEN_WIDTH // 2
        self.camera_y = self.player.y - SCREEN_HEIGHT // 2
        self.spawn_timer = 0
        self.timer_seconds = 0
        self.elapsed_seconds = 0.0
        self.kill_count = 0

        self.is_level_up = False
        self.current_upgrades = []
        self.upgrade_rects = []

        self.is_game_over = False
        self.is_running = True

    def create_explosion(self, x, y, count=20, color=(255, 160, 30)):
        for _ in range(count):
            self.particles.append(Particle(x, y, color))

    def add_damage_text(self, x, y, text, color=(255, 80, 80)):
        self.floating_texts.append(FloatingText(x, y, text, color))

    def spawn_enemy(self):
        angle = random.uniform(0, math.tau)
        dist = random.uniform(600, 750)
        ex = self.player.x + math.cos(angle) * dist
        ey = self.player.y + math.sin(angle) * dist
        etype = self.current_stage.get_enemy_spawn_type(self.timer_seconds)

        spr = self.TA_sprite
        if etype == "professor":
            spr = self.professor_sprite
        elif etype == "rector":
            spr = self.skel_sprite

        self.enemies.append(Enemy(ex, ey, etype, sprite=spr))

    def trigger_level_up(self):
        self.is_level_up = True
        pool = available_upgrades(self.player)
        num_options = min(3, len(pool))
        self.current_upgrades = random.sample(pool, num_options)

        card_w, card_h = 240, 300
        gap = 25
        total_w = (num_options * card_w) + ((num_options - 1) * gap)
        start_x = (SCREEN_WIDTH - total_w) // 2
        card_y = 210

        self.upgrade_rects = []
        for i in range(num_options):
            cx = start_x + i * (card_w + gap)
            self.upgrade_rects.append(pygame.Rect(cx, card_y, card_w, card_h))

    def apply_upgrade(self, upgrade_data):
        if not self.is_level_up or self.player.pending_level_ups <= 0:
            return
        if upgrade_data not in self.current_upgrades or not apply_upgrade(self.player, upgrade_data):
            return
        self.player.pending_level_ups -= 1

        if self.player.pending_level_ups > 0:
            self.trigger_level_up()
        else:
            self.is_level_up = False

    def handle_events(self):
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.is_running = False

            if self.state == GameState.MAIN_MENU:
                self.btn_start.update(mouse_pos)
                self.btn_quit.update(mouse_pos)
                if self.btn_start.is_clicked(event):
                    self.reset_game()
                    self.state = GameState.PLAYING
                elif self.btn_quit.is_clicked(event):
                    self.is_running = False

            elif self.state == GameState.PAUSED:
                self.btn_resume.update(mouse_pos)
                self.btn_restart.update(mouse_pos)
                self.btn_main_menu.update(mouse_pos)

                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.state = GameState.PLAYING
                elif self.btn_resume.is_clicked(event):
                    self.state = GameState.PLAYING
                elif self.btn_restart.is_clicked(event):
                    self.reset_game()
                    self.state = GameState.PLAYING
                elif self.btn_main_menu.is_clicked(event):
                    self.state = GameState.MAIN_MENU

            elif self.state == GameState.PLAYING:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.state = GameState.PAUSED
                    elif self.is_level_up and event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                        index = event.key - pygame.K_1
                        if index < len(self.current_upgrades):
                            self.apply_upgrade(self.current_upgrades[index])
                    elif event.key == pygame.K_r and self.is_game_over:
                        self.reset_game()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.is_level_up:
                    mx, my = event.pos
                    for idx, rect in enumerate(self.upgrade_rects):
                        if rect.collidepoint(mx, my):
                            self.apply_upgrade(self.current_upgrades[idx])
                            break

    def update(self, dt=1/FPS):
        if self.state != GameState.PLAYING or self.is_game_over or self.is_level_up:
            return

        dt = min(max(dt, 0), 0.1)
        self.elapsed_seconds += dt
        self.timer_seconds = int(self.elapsed_seconds)
        self.player.coffee_remaining = max(0, self.player.coffee_remaining-dt)
        self.player.hurt_remaining = max(0, self.player.hurt_remaining-dt)
        previous_position = (self.player.x, self.player.y)
        self.player.handle_input(dt)
        moved = math.hypot(self.player.x - previous_position[0], self.player.y - previous_position[1]) > 1e-6

        smoothing = 1 - 0.9 ** (dt*60)
        self.camera_x += (self.player.x - SCREEN_WIDTH//2 - self.camera_x)*smoothing
        self.camera_y += (self.player.y - SCREEN_HEIGHT//2 - self.camera_y)*smoothing
        self.spawn_timer += dt
        if self.spawn_timer >= 2/3:
            if len(self.enemies) < 120:
                self.spawn_enemy()
            self.spawn_timer %= 2/3

        for ft in self.floating_texts[:]:
            ft.update(dt)
            if ft.timer <= 0:
                self.floating_texts.remove(ft)

        for p in self.particles[:]:
            p.update(dt)
            if p.timer <= 0 or p.radius <= 0:
                self.particles.remove(p)

        for enemy in self.enemies:
            if enemy.hp > 0:
                enemy.update(self.player.x, self.player.y, dt)
        self.player.weapons.update(dt, self.player, self.enemies)

        for enemy in self.enemies[:]:
            if enemy.hp <= 0:
                self.gems.append(Gem(enemy.x, enemy.y))
                if random.random() < 0.08:
                    self.coffees.append(Coffee(enemy.x, enemy.y))
                self.kill_count += 1
                self.create_explosion(enemy.x, enemy.y, count=18, color=enemy.color)
                self.add_damage_text(enemy.x, enemy.y, "KILL", color=(255, 215, 0))
                self.enemies.remove(enemy)

        if self.player.hurt_remaining <= 0:
            contacts = [enemy for enemy in self.enemies
                        if math.hypot(enemy.x-self.player.x, enemy.y-self.player.y) < enemy.radius+self.player.radius]
            if contacts:
                dmg = max(e.damage for e in contacts)
                self.player.hp = max(0, self.player.hp - dmg)
                self.player.hurt_remaining = 0.75
                self.add_damage_text(self.player.x, self.player.y - 10, f"-{dmg}", color=(255, 70, 70))
                if self.player.hp <= 0:
                    self.is_game_over = True
                    return

        self.supplies.update(dt, self.player, moved)
        for coffee in self.coffees[:]:
            coffee.life -= dt
            if math.hypot(coffee.x-self.player.x, coffee.y-self.player.y) < coffee.radius+self.player.radius:
                self.player.drink_coffee()
                self.coffees.remove(coffee)
            elif coffee.life <= 0:
                self.coffees.remove(coffee)
        for gem in self.gems[:]:
            if math.hypot(gem.x-self.player.x, gem.y-self.player.y) < self.player.radius+self.player.magnet_range:
                attraction = 1-0.85**(dt*60)
                gem.x += (self.player.x-gem.x)*attraction
                gem.y += (self.player.y-gem.y)*attraction
            if math.hypot(gem.x-self.player.x, gem.y-self.player.y) < self.player.radius+gem.radius:
                self.player.add_exp(gem.value)
                self.gems.remove(gem)
        if self.player.pending_level_ups > 0:
            self.trigger_level_up()

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
            self.screen.fill((24, 20, 34))

    def draw_hud(self):
        bar_h = 14
        pygame.draw.rect(self.screen, (28, 30, 45), (0, bar_h, SCREEN_WIDTH, 35))
        ratio = min(1.0, self.player.exp / self.player.exp_to_next) if self.player.exp_to_next > 0 else 0
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

        for index, (kind, level) in enumerate(self.player.weapons.levels.items()):
            x = 15 + index*190
            pygame.draw.rect(self.screen, (28, 30, 45), (x, 55, 180, 36), border_radius=6)
            draw_icon(self.screen, kind, (x+21, 73), 15)
            label = self.small_font.render(f"{WEAPONS[kind][0]} L{level}", True, COLOR_WHITE)
            self.screen.blit(label, (x+42, 66))
        if self.player.coffee_remaining > 0:
            pygame.draw.rect(self.screen, (28, 30, 45), (SCREEN_WIDTH-250, 55, 235, 61), border_radius=6)
            draw_coffee(self.screen, (SCREEN_WIDTH-185, 73))
            label = self.small_font.render(f"COFFEE {self.player.coffee_remaining:.1f}s", True, COLOR_GOLD)
            self.screen.blit(label, (SCREEN_WIDTH-165, 66))
            label = self.small_font.render("RATE +25% / MOVE +15%", True, COLOR_GOLD)
            self.screen.blit(label, (SCREEN_WIDTH-240, 96))

    def draw_wrapped_text(self, text, font, color, max_width, start_x, start_y, line_spacing=18):
        words = text.split(" ")
        lines = []
        current_line = []
        for word in words:
            test_line = " ".join(current_line + [word])
            if font.size(test_line)[0] <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
        if current_line:
            lines.append(" ".join(current_line))
        y = start_y
        for line in lines:
            line_surf = font.render(line, True, color)
            self.screen.blit(line_surf, (start_x - line_surf.get_width() // 2, y))
            y += line_spacing

    def draw_level_up_modal(self):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((12, 10, 22, 210))
        self.screen.blit(overlay, (0, 0))

        title = self.title_font.render("LEVEL UP!", True, COLOR_GOLD)
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 80))

        subtitle = self.font.render("Choose an Upgrade  [1 / 2 / 3]", True, COLOR_WHITE)
        self.screen.blit(subtitle, (SCREEN_WIDTH // 2 - subtitle.get_width() // 2, 135))

        mouse_pos = pygame.mouse.get_pos()

        for idx, (upg, rect) in enumerate(zip(self.current_upgrades, self.upgrade_rects)):
            is_hover = rect.collidepoint(mouse_pos)

            frame_img = self.card_frame_hover if (is_hover and self.card_frame_hover) else self.card_frame
            if frame_img:
                self.screen.blit(frame_img, rect.topleft)
            else:
                pygame.draw.rect(self.screen, COLOR_CARD_BG, rect, border_radius=12)
                pygame.draw.rect(self.screen, COLOR_GOLD if is_hover else COLOR_CARD_BORDER, rect, width=3, border_radius=12)

            name_surf = self.font.render(upg["title"], True, COLOR_GOLD if is_hover else COLOR_WHITE)
            self.screen.blit(name_surf, (rect.centerx - name_surf.get_width() // 2, rect.y + 22))

            if upg["id"] in WEAPONS:
                draw_icon(self.screen, upg["id"], (rect.centerx, rect.y+100), 32)
            else:
                pygame.draw.line(self.screen, COLOR_HP_GREEN, (rect.centerx-15, rect.y+100), (rect.centerx+15, rect.y+100), 7)
                pygame.draw.line(self.screen, COLOR_HP_GREEN, (rect.centerx, rect.y+85), (rect.centerx, rect.y+115), 7)

            desc_surf = self.font.render(upg["desc"], True, COLOR_HP_GREEN)
            self.screen.blit(desc_surf, (rect.centerx - desc_surf.get_width() // 2, rect.y + 162))

            self.draw_wrapped_text(
                text=upg["detail"],
                font=self.small_font,
                color=(200, 200, 210),
                max_width=200,
                start_x=rect.centerx,
                start_y=rect.y + 208,
                line_spacing=18
            )

    def render(self):
        if self.state == GameState.MAIN_MENU:
            if self.menu_bg:
                self.screen.blit(self.menu_bg, (0, 0))
            else:
                self.draw_background()
                title = self.title_font.render("COMSCI SURVIVOR", True, COLOR_GOLD)
                self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 180))

            self.btn_start.draw(self.screen)
            self.btn_quit.draw(self.screen)
        else:
            self.draw_background()
            self.supplies.draw(self.screen, self.camera_x, self.camera_y, self.small_font, self.player)

            for g in self.gems:
                g.draw(self.screen, self.camera_x, self.camera_y)
            for coffee in self.coffees:
                coffee.draw(self.screen, self.camera_x, self.camera_y)
            for e in self.enemies:
                e.draw(self.screen, self.camera_x, self.camera_y)

            for p in self.particles:
                p.draw(self.screen, self.camera_x, self.camera_y)
            for ft in self.floating_texts:
                ft.draw(self.screen, self.camera_x, self.camera_y)

            self.player.weapons.draw(self.screen, self.player, self.camera_x, self.camera_y)
            self.player.draw(self.screen, self.camera_x, self.camera_y)
            self.draw_hud()

            if self.is_level_up:
                self.draw_level_up_modal()
            elif self.is_game_over:
                overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                overlay.fill((40, 10, 15, 200))
                self.screen.blit(overlay, (0, 0))
                over_txt = self.title_font.render("GAME OVER", True, (255, 70, 70))
                self.screen.blit(over_txt, (SCREEN_WIDTH // 2 - over_txt.get_width() // 2, 250))
                restart_txt = self.font.render("Press [ R ] to Restart | Press [ ESC ] to Quit", True, COLOR_GOLD)
                self.screen.blit(restart_txt, (SCREEN_WIDTH // 2 - restart_txt.get_width() // 2, 330))

            if self.state == GameState.PAUSED:
                overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 160))
                self.screen.blit(overlay, (0, 0))

                pause_title = self.title_font.render("GAME PAUSED", True, COLOR_WHITE)
                self.screen.blit(pause_title, (SCREEN_WIDTH // 2 - pause_title.get_width() // 2, 150))

                self.btn_resume.draw(self.screen)
                self.btn_restart.draw(self.screen)
                self.btn_main_menu.draw(self.screen)

        pygame.display.flip()

    def run(self):
        while self.is_running:
            dt = self.clock.tick(FPS) / 1000.0
            was_paused = self.is_level_up or self.is_game_over or self.state in (GameState.MAIN_MENU, GameState.PAUSED)
            self.handle_events()
            if not was_paused:
                self.update(dt)
            self.render()
        pygame.quit()
        sys.exit()


def main():
    game = Game()
    game.run()


if __name__ == "__main__":
    main()