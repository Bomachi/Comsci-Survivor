import os
import sys
import math
import random
import pygame

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SPRITES_DIR = os.path.join(BASE_DIR, "assets", "sprites")

from stages import STAGES
from upgrades import available_upgrades, apply_upgrade
from weapons import WeaponSystem, WEAPONS, draw_icon
from item_art import draw_item
from supplies import Supplies, Food
from accounting import update_ranged, update_boss, draw_boss_telegraph
from spatial import separate, CELL_SIZE
from pathfinding import ObstacleMap, FlowField
from animation import Animator, Effects
from stage_art import Scenery
from hand_control import HandController, DEAD_ZONE, FULL_SPEED
import time

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
        self.anim = Animator()
        self.anim.spawn = 0

    @property
    def move_speed(self):
        return self.speed * (1.15 if self.coffee_remaining > 0 else 1.0)

    def drink_coffee(self):
        self.coffee_remaining = 10.0

    def handle_input(self, dt, analog=None):
        """Keyboard first; otherwise an analog vector (length 0..1), e.g. from hand control."""
        keys = pygame.key.get_pressed()
        dx = int(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - int(keys[pygame.K_a] or keys[pygame.K_LEFT])
        dy = int(keys[pygame.K_s] or keys[pygame.K_DOWN]) - int(keys[pygame.K_w] or keys[pygame.K_UP])
        if not dx and not dy and analog and (analog[0] or analog[1]):
            ax, ay = analog
            if abs(ax) > 0.05:
                self.facing_right = ax > 0
            self.x += ax * self.move_speed * dt
            self.y += ay * self.move_speed * dt
            return
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
            # Blink while invulnerable after a hit.
            alpha = 110 if self.hurt_remaining > 0 and int(self.hurt_remaining * 14) % 2 else 255
            self.anim.draw(surface, self.sprite, sx, sy, self.facing_right, alpha=alpha)
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
        # Stage 2 behaviour (defaults keep Stage 1 enemies unchanged).
        self.exp_value = 1
        self.preferred_range = 0
        self.shoot_cooldown = 0
        self.shoot_timer = 0
        self.shot_damage = 0
        self.is_boss = False
        self.mass = 1.0
        # Smarter movement and animation
        self.anim = Animator()
        self.prev_hp = None
        self.flank = random.uniform(-0.7, 0.7)     # approach angle offset -> enemies surround
        self.can_lunge = False
        self.lunge_state = ""                      # "", "windup" or "dash"
        self.lunge_timer = 0.0
        self.lunge_cooldown = random.uniform(0.5, 2.0)
        self.lunge_dir = (0.0, 0.0)
        self.strafe_sign = random.choice((-1, 1))
        self.strafe_timer = random.uniform(1.5, 3.0)

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
        # --- Stage 2: Accounting Faculty ---
        elif enemy_type == "acc_freshman":
            self.hp = 32
            self.speed = 150.0
            self.radius = 14
            self.damage = 10
            self.color = (60, 150, 90)
            self.exp_value = 2
            self.can_lunge = True
        elif enemy_type == "acc_calculator":
            self.hp = 55
            self.speed = 85.0
            self.radius = 16
            self.damage = 10
            self.color = (120, 190, 140)
            self.exp_value = 3
            self.preferred_range = 240
            self.shoot_cooldown = 2.4
            self.shoot_timer = random.uniform(0.8, 2.4)
            self.shot_damage = 12
        elif enemy_type == "acc_senior":
            self.hp = 160
            self.speed = 70.0
            self.radius = 21
            self.damage = 26
            self.color = (40, 110, 60)
            self.exp_value = 5
        elif enemy_type == "acc_boss":
            self.hp = 3200
            self.speed = 64.0
            self.radius = 40
            self.damage = 30
            self.color = (30, 90, 50)
            self.exp_value = 60
            self.shot_damage = 14
            self.is_boss = True
            self.mass = 8.0
            self.brain = None  # BossBrain state machine, created on first update

        else:
            raise ValueError(f"Unknown enemy type: {enemy_type}")
        self.max_hp = self.hp
        self.prev_hp = self.hp

    def update(self, px, py, dt, steer=None):
        """Move toward (px, py). `steer` is an optional unit vector from the
        Game (flow field around obstacles, or a flanking angle)."""
        speed = self.speed * (0.55 if self.slow_remaining > 0 else 1.0)
        self.slow_remaining = max(0, self.slow_remaining - dt)
        dx = px - self.x
        dy = py - self.y
        dist = math.hypot(dx, dy)
        if self.can_lunge and self.update_lunge(dx, dy, dist, speed, dt):
            return
        if self.preferred_range and dist > 0:
            low, high = self.preferred_range * 0.75, self.preferred_range * 1.25
            self.strafe_timer -= dt
            if self.strafe_timer <= 0:
                self.strafe_sign *= -1
                self.strafe_timer = random.uniform(1.5, 3.0)
            if dist < low:
                # Too close: back away while throwing.
                dx, dy = -dx, -dy
                speed *= 0.6
                steer = None
            elif dist < high:
                # In range: circle-strafe so the player cannot just walk up.
                dx, dy = -dy * self.strafe_sign, dx * self.strafe_sign
                speed *= 0.5
                steer = None
        if steer is not None:
            self.x += steer[0] * speed * dt
            self.y += steer[1] * speed * dt
            self.facing_right = (px > self.x)
        elif dist > 0:
            step = min(dist, speed * dt)
            self.x += (dx / dist) * step
            self.y += (dy / dist) * step
            self.facing_right = (px > self.x)

    def update_lunge(self, dx, dy, dist, speed, dt):
        """Freshmen crouch (telegraph) then dash at the player. True = handled."""
        self.lunge_cooldown -= dt
        if self.lunge_state == "windup":
            self.lunge_timer -= dt
            if self.lunge_timer <= 0:
                self.lunge_state, self.lunge_timer = "dash", 0.32
            return True
        if self.lunge_state == "dash":
            self.lunge_timer -= dt
            self.x += self.lunge_dir[0] * speed * 2.7 * dt
            self.y += self.lunge_dir[1] * speed * 2.7 * dt
            if self.lunge_timer <= 0:
                self.lunge_state, self.lunge_cooldown = "", random.uniform(1.8, 2.8)
            return True
        if 40 < dist < 120 and self.lunge_cooldown <= 0:
            self.lunge_state, self.lunge_timer = "windup", 0.28
            self.lunge_dir = (dx / dist, dy / dist)
            self.facing_right = dx > 0
            return True
        return False

    def draw(self, surface, cam_x, cam_y):
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        if self.sprite:
            self.anim.draw(surface, self.sprite, sx, sy, self.facing_right, windup=self.lunge_state == "windup")
        else:
            pygame.draw.circle(surface, self.color, (sx, sy), self.radius)

    @property
    def feet_y(self):
        return self.y + (self.sprite.get_height() / 2 if self.sprite else self.radius)


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
        pygame.display.set_caption("Classroom Survivor - Pygame Edition")
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
        self.enemy_sprites = {
            "TA": self.TA_sprite,
            "professor": self.professor_sprite,
            "rector": self.skel_sprite,
            "acc_freshman": load_sprite("acc_freshman.png", (40, 40)),
            "acc_calculator": load_sprite("acc_calculator.png", (42, 42)),
            "acc_senior": load_sprite("acc_senior.png", (50, 50)),
            "acc_boss": load_sprite("acc_boss.png", (104, 104)),
        }
        self.stage_tiles = {"stage1_tile.png": self.stage1_tile}

        # Debug overlay (F3) and collision strategy (F2) for demos/benchmarks.
        self.show_debug = False
        self.collision_mode = "hash"
        self.demo_mode = False  # F4: weapons off + invincible, for crowd demos
        self.frame_ms = 0.0
        self.sep_history = []
        self.effects = Effects()
        self.hand = HandController()
        self.obstacles = ObstacleMap()
        self.flow = FlowField(self.obstacles)
        self.scenery = None
        self.player_vel = (0.0, 0.0)
        self.last_dt = 1 / FPS
        self.flow_ms = 0.0

        self.card_frame = load_sprite("card_frame.png", (240, 300))
        self.card_frame_hover = load_sprite("card_frame_hover.png", (240, 300))

        self.reset_game()

    def stage_tile(self):
        name = self.current_stage.ground_tile_name
        if name not in self.stage_tiles:
            self.stage_tiles[name] = load_sprite(name, (64, 64))
        return self.stage_tiles[name]

    def start_stage(self, index):
        """Enter a stage, keeping the same Player (EXP, level and weapons)."""
        self.stage_index = index
        self.current_stage = STAGES[index]()
        self.stage_start_seconds = self.elapsed_seconds
        self.enemies = []
        self.enemy_shots = []
        self.gems = []
        self.coffees = []
        self.boss = None
        self.boss_spawned = False
        self.spawn_timer = 0
        self.player.weapons.projectiles.clear()
        self.player.weapons.effects.clear()
        self.player.weapons.book_hits.clear()
        self.banner_text = self.current_stage.name.upper()
        self.banner_remaining = 3.0
        self.effects.clear()
        self.scenery = Scenery() if self.current_stage.decorated else None
        self.obstacles.set_rects([])
        self.flow.target_cell = None
        self.refresh_scenery()

    def refresh_scenery(self):
        if self.scenery and self.scenery.update(self.player.x, self.player.y):
            self.obstacles.set_rects(self.scenery.solid_rects())
            self.flow.target_cell = None   # obstacles changed: rebuild the field
            self.obstacles.push_out(self.player)

    def steer_for(self, enemy):
        """Unit vector for an enemy, or None for a straight line to the player.

        Near obstacles the BFS flow field is used when it points away from the
        straight line (something is in the way). In the open, enemies keep an
        individual angle offset so a crowd spreads out and surrounds the player
        instead of forming a queue; the offset fades as they get close.
        """
        dx, dy = self.player.x - enemy.x, self.player.y - enemy.y
        dist = math.hypot(dx, dy)
        if dist < 1:
            return None
        ux, uy = dx / dist, dy / dist
        if self.obstacles.rects:
            field = self.flow.direction(enemy.x, enemy.y)
            if field and field[0] * ux + field[1] * uy < 0.9:   # > ~25 degrees off the straight line
                return field
        if dist > 140:
            angle = enemy.flank * min(1.0, (dist - 140) / 320)
            c, s = math.cos(angle), math.sin(angle)
            return (ux * c - uy * s, ux * s + uy * c)
        return None

    @property
    def stage_seconds(self):
        return int(self.elapsed_seconds - self.stage_start_seconds)

    def reset_game(self):
        self.player = Player(0, 0, sprite=self.player_sprite)
        self.enemies = []
        self.coffees = []
        self.gems = []
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
        self.is_victory = False
        self.pair_stats = None
        self.separation_ms = 0.0
        self.is_running = True
        self.start_stage(0)

    def spawn_enemy(self):
        angle = random.uniform(0, math.tau)
        dist = random.uniform(600, 750)
        ex = self.player.x + math.cos(angle) * dist
        ey = self.player.y + math.sin(angle) * dist
        stage_time = self.timer_seconds - int(self.stage_start_seconds)
        etype = self.current_stage.get_enemy_spawn_type(stage_time)
        self.add_enemy(etype, ex, ey)

    def add_enemy(self, etype, x, y):
        enemy = Enemy(x, y, etype, sprite=self.enemy_sprites.get(etype))
        self.obstacles.push_out(enemy)
        self.enemies.append(enemy)
        return enemy

    def stress_spawn(self, count):
        """Demo: add a crowd around the player, ignoring the normal enemy cap."""
        kind = "acc_freshman" if self.current_stage.boss_type else "TA"
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            dist = random.uniform(250, 650)
            self.add_enemy(kind, self.player.x + math.cos(angle) * dist, self.player.y + math.sin(angle) * dist)

    def spawn_boss(self):
        stage = self.current_stage
        angle = random.uniform(0, math.tau)
        self.boss = self.add_enemy(stage.boss_type, self.player.x + math.cos(angle) * 420,
                                   self.player.y + math.sin(angle) * 420)
        self.boss_spawned = True
        self.banner_text = "BOSS: THE CHIEF AUDITOR"
        self.banner_remaining = 3.0

    def update_stage_progress(self):
        stage = self.current_stage
        stage_time = self.elapsed_seconds - self.stage_start_seconds
        if stage.boss_type:
            if not self.boss_spawned and stage_time >= stage.boss_time:
                self.spawn_boss()
            elif self.boss_spawned and self.boss.hp <= 0:
                self.is_victory = True
        elif stage_time >= stage.target_time and self.stage_index + 1 < len(STAGES):
            self.player.hp = min(self.player.max_hp, self.player.hp + 30)
            self.start_stage(self.stage_index + 1)

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
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.is_running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.is_running = False
                elif event.key == pygame.K_F3:
                    self.show_debug = not self.show_debug
                elif event.key == pygame.K_F2:
                    self.collision_mode = "naive" if self.collision_mode == "hash" else "hash"
                    self.sep_history.clear()
                elif event.key == pygame.K_F7:
                    self.hand.toggle()
                elif event.key == pygame.K_F8:
                    self.hand.recenter()
                elif event.key == pygame.K_F4:
                    self.demo_mode = not self.demo_mode
                elif event.key == pygame.K_F5 and not (self.is_level_up or self.is_game_over or self.is_victory):
                    self.stress_spawn(300)
                elif self.is_level_up and event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    index = event.key - pygame.K_1
                    if index < len(self.current_upgrades):
                        self.apply_upgrade(self.current_upgrades[index])
                elif event.key == pygame.K_r and (self.is_game_over or self.is_victory):
                    self.reset_game()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.is_level_up:
                mx, my = event.pos
                for idx, rect in enumerate(self.upgrade_rects):
                    if rect.collidepoint(mx, my):
                        self.apply_upgrade(self.current_upgrades[idx])
                        break

    def update(self, dt=1/FPS):
        if self.is_game_over or self.is_level_up or self.is_victory:
            return
        # A stalled window must not jump the simulation several seconds ahead.
        dt = min(max(dt, 0), 0.1)
        self.elapsed_seconds += dt
        self.timer_seconds = int(self.elapsed_seconds)
        self.banner_remaining = max(0, self.banner_remaining - dt)
        self.player.coffee_remaining = max(0, self.player.coffee_remaining-dt)
        self.player.hurt_remaining = max(0, self.player.hurt_remaining-dt)
        self.last_dt = dt
        previous_position = (self.player.x, self.player.y)
        if self.hand.status != "off":
            self.player.handle_input(dt, self.hand.poll())
        else:
            self.player.handle_input(dt)
        self.obstacles.push_out(self.player)
        moved = math.hypot(self.player.x - previous_position[0], self.player.y - previous_position[1]) > 1e-6
        self.player_vel = ((self.player.x - previous_position[0]) / dt if dt else 0,
                           (self.player.y - previous_position[1]) / dt if dt else 0)
        self.player.anim.update(self.player.x, self.player.y, dt)
        self.refresh_scenery()
        if self.obstacles.rects:
            started = time.perf_counter()
            self.flow.update(self.player.x, self.player.y)
            self.flow_ms = (time.perf_counter() - started) * 1000

        smoothing = 1 - 0.9 ** (dt*60)
        self.camera_x += (self.player.x - SCREEN_WIDTH//2 - self.camera_x)*smoothing
        self.camera_y += (self.player.y - SCREEN_HEIGHT//2 - self.camera_y)*smoothing
        self.spawn_timer += dt
        interval = self.current_stage.spawn_interval * (1.6 if self.boss and self.boss.hp > 0 else 1)
        if self.spawn_timer >= interval:
            if len(self.enemies) < 120:
                self.spawn_enemy()
            self.spawn_timer %= interval

        for enemy in self.enemies:
            if enemy.hp > 0:
                if enemy.is_boss:
                    # The boss state machine decides when and how it moves.
                    update_boss(enemy, self.player, dt, self.enemy_shots, self.add_enemy)
                    continue
                enemy.update(self.player.x, self.player.y, dt, self.steer_for(enemy))
                if enemy.shoot_cooldown:
                    update_ranged(enemy, self.player, dt, self.enemy_shots, self.player_vel)
        # Crowd separation: naive O(n^2) or spatial hash (toggle with F2).
        living = [e for e in self.enemies if e.hp > 0]
        started = time.perf_counter()
        self.pair_stats = separate(living, self.collision_mode)
        self.pair_n = len(living)
        self.separation_ms = (time.perf_counter() - started) * 1000
        if self.obstacles.rects:
            for enemy in living:
                self.obstacles.push_out(enemy)
        if not self.demo_mode:
            self.player.weapons.update(dt, self.player, self.enemies)
        # Hit feedback: flash + damage number whenever an enemy lost HP.
        for enemy in self.enemies:
            enemy.anim.update(enemy.x, enemy.y, dt)
            if enemy.prev_hp is not None and enemy.hp < enemy.prev_hp:
                enemy.anim.hit()
                lost = enemy.prev_hp - max(0, enemy.hp)
                self.effects.damage(enemy.x, enemy.y - enemy.radius - 18, lost,
                                    (255, 120, 90) if enemy.is_boss else (255, 240, 200))
            enemy.prev_hp = enemy.hp
        self.effects.update(dt)
        # Resolve kills before contact damage; each enemy drops loot once.
        for enemy in self.enemies[:]:
            if enemy.hp <= 0:
                self.effects.burst(enemy.x, enemy.y, enemy.sprite, 40 if enemy.is_boss else 10)
                self.gems.append(Gem(enemy.x, enemy.y, enemy.exp_value))
                if enemy.is_boss:
                    for i in range(12):
                        angle = i * math.tau / 12
                        self.gems.append(Gem(enemy.x + math.cos(angle) * 40, enemy.y + math.sin(angle) * 40, 5))
                    self.supplies.foods.append(Food(enemy.x, enemy.y))
                if random.random() < 0.08:
                    self.coffees.append(Coffee(enemy.x, enemy.y))
                self.kill_count += 1
                self.enemies.remove(enemy)
        self.update_stage_progress()
        for shot in self.enemy_shots:
            shot.update(dt)
        if self.demo_mode:
            self.player.hurt_remaining = 0.75
        if self.player.hurt_remaining <= 0:
            contacts = [enemy for enemy in self.enemies
                        if math.hypot(enemy.x-self.player.x, enemy.y-self.player.y) < enemy.radius+self.player.radius]
            hits = [shot for shot in self.enemy_shots if shot.hits(self.player)]
            damage = max([e.damage for e in contacts] + [s.damage for s in hits], default=0)
            for shot in hits:
                shot.life = 0
            if damage:
                self.player.hp = max(0, self.player.hp-damage)
                self.player.hurt_remaining = 0.75
                if self.player.hp <= 0:
                    self.is_game_over = True
                    return
        self.enemy_shots = [shot for shot in self.enemy_shots if shot.life > 0]

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
        if self.scenery:
            self.scenery.draw_floor(self.screen, self.camera_x, self.camera_y)
            return
        tile = self.stage_tile()
        if tile:
            tile_w, tile_h = 64, 64
            start_col = int(self.camera_x // tile_w) - 1
            end_col = int((self.camera_x + SCREEN_WIDTH) // tile_w) + 2
            start_row = int(self.camera_y // tile_h) - 1
            end_row = int((self.camera_y + SCREEN_HEIGHT) // tile_h) + 2
            for c in range(start_col, end_col):
                for r in range(start_row, end_row):
                    sx = c * tile_w - int(self.camera_x)
                    sy = r * tile_h - int(self.camera_y)
                    self.screen.blit(tile, (sx, sy))
        else:
            self.screen.fill((24, 20, 34))

    def draw_hud(self):
        bar_h = 12
        pygame.draw.rect(self.screen, (28, 30, 45), (0, bar_h, SCREEN_WIDTH, 35))
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

        stage_txt = self.small_font.render(self.current_stage.name.split(":")[0].upper(), True, (190, 200, 220))
        self.screen.blit(stage_txt, (15 + lvl_txt.get_width() + 18, bar_h + 13))
        if self.boss and self.boss.hp > 0:
            self.draw_boss_bar()

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

    def draw_boss_bar(self):
        w, h, y = 520, 16, SCREEN_HEIGHT - 46
        x = SCREEN_WIDTH // 2 - w // 2
        ratio = max(0, self.boss.hp / self.boss.max_hp)
        pygame.draw.rect(self.screen, (20, 20, 30), (x - 3, y - 3, w + 6, h + 6), border_radius=4)
        pygame.draw.rect(self.screen, (70, 25, 30), (x, y, w, h))
        pygame.draw.rect(self.screen, (60, 190, 100), (x, y, int(w * ratio), h))
        label = self.small_font.render("THE CHIEF AUDITOR", True, COLOR_GOLD)
        box = pygame.Rect(0, 0, label.get_width() + 16, label.get_height() + 6)
        box.midbottom = (SCREEN_WIDTH // 2, y - 4)
        pygame.draw.rect(self.screen, (20, 20, 30), box, border_radius=4)
        self.screen.blit(label, (box.x + 8, box.y + 3))

    def draw_debug_world(self):
        """Spatial-hash grid (occupied cells shaded), hit circles, flow field and boss state."""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        if self.obstacles.rects:
            self.flow.draw(overlay, self.camera_x, self.camera_y)
            for rect in self.obstacles.rects:
                pygame.draw.rect(overlay, (255, 60, 60, 200), rect.move(-self.camera_x, -self.camera_y), 2)
        cs = CELL_SIZE
        counts = {}
        for e in self.enemies:
            if e.hp > 0:
                for cx in range(int((e.x - e.radius) // cs), int((e.x + e.radius) // cs) + 1):
                    for cy in range(int((e.y - e.radius) // cs), int((e.y + e.radius) // cs) + 1):
                        counts[(cx, cy)] = counts.get((cx, cy), 0) + 1
        if self.collision_mode == "hash":
            for (cx, cy), n in counts.items():
                rect = (cx * cs - self.camera_x, cy * cs - self.camera_y, cs, cs)
                pygame.draw.rect(overlay, (255, 140, 0, min(90, 10 + n * 18)), rect)
            x0 = int(self.camera_x // cs) * cs
            for x in range(x0, int(self.camera_x) + SCREEN_WIDTH + cs, cs):
                pygame.draw.line(overlay, (40, 60, 120, 90), (x - self.camera_x, 0), (x - self.camera_x, SCREEN_HEIGHT))
            y0 = int(self.camera_y // cs) * cs
            for y in range(y0, int(self.camera_y) + SCREEN_HEIGHT + cs, cs):
                pygame.draw.line(overlay, (40, 60, 120, 90), (0, y - self.camera_y), (SCREEN_WIDTH, y - self.camera_y))
        for e in self.enemies:
            if e.hp > 0:
                pygame.draw.circle(overlay, (255, 40, 40, 170), (e.x - self.camera_x, e.y - self.camera_y), e.radius, 1)
        self.screen.blit(overlay, (0, 0))
        if self.boss and self.boss.hp > 0 and self.boss.brain:
            label = self.font.render(self.boss.brain.state, True, (255, 80, 80))
            pos = (self.boss.x - self.camera_x - label.get_width() // 2, self.boss.y - self.camera_y - self.boss.radius - 34)
            pygame.draw.rect(self.screen, (10, 10, 20), label.get_rect(topleft=pos).inflate(10, 4))
            self.screen.blit(label, pos)

    def draw_debug_panel(self):
        n = getattr(self, "pair_n", 0)
        checks = self.pair_stats.checks if self.pair_stats else 0
        rows = [
            ("DEBUG [F3]", COLOR_GOLD),
            (f"FPS {self.clock.get_fps():5.1f}   frame {self.frame_ms:5.1f} ms", COLOR_WHITE),
            (f"enemies {n}   shots {len(self.enemy_shots)}   proj {len(self.player.weapons.projectiles)}", COLOR_WHITE),
            (f"collision [F2]: {self.collision_mode.upper()}", (120, 220, 255)),
            (f"pair checks {checks:,}   (n^2/2 = {n * (n - 1) // 2:,})", (120, 220, 255)),
            (f"separation {self.separation_ms:6.2f} ms", (120, 220, 255)),
            (f"flow field BFS: {len(self.flow.dist)} cells, {self.flow.last_build_ms:.2f} ms/rebuild, rebuilds {self.flow.rebuilds}"
             if self.obstacles.rects else "flow field: off (no obstacles in this stage)", (150, 170, 255)),
            ("[F5] spawn 300 enemies   [F4] demo mode: " + ("ON" if self.demo_mode else "off"),
             (255, 200, 80) if self.demo_mode else (180, 180, 190)),
        ]
        if self.boss and self.boss.hp > 0 and self.boss.brain:
            brain = self.boss.brain
            rows.append((f"boss FSM: {brain.state} ({brain.timer:.1f}s)" + ("  ENRAGED" if brain.enraged(self.boss) else ""), (255, 120, 120)))
            rows.append((" > ".join(brain.history[-5:]), (200, 150, 150)))
        w, h = 430, 22 + len(rows) * 19 + 70
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill((10, 10, 20, 215))
        for i, (text, color) in enumerate(rows):
            panel.blit(self.small_font.render(text, True, color), (12, 10 + i * 19))
        # Separation time graph (last 180 frames); the red line marks one 60 FPS frame.
        gx, gy, gw, gh = 12, h - 62, w - 24, 52
        pygame.draw.rect(panel, (30, 30, 45), (gx, gy, gw, gh))
        scale = max(17.0, max(self.sep_history, default=0)) / gh
        pygame.draw.line(panel, (200, 60, 60), (gx, gy + gh - 16.7 / scale), (gx + gw, gy + gh - 16.7 / scale))
        for i, v in enumerate(self.sep_history[-gw:]):
            pygame.draw.line(panel, (120, 220, 255), (gx + i, gy + gh), (gx + i, gy + gh - min(gh, v / scale)))
        self.screen.blit(panel, (15, 100))

    def draw_hand_panel(self):
        """Camera preview with hand landmarks and the virtual joystick."""
        hand = self.hand
        if hand.status == "off":
            return
        w, h = 192, 144
        x, y = 15, SCREEN_HEIGHT - h - 40
        pygame.draw.rect(self.screen, (10, 10, 20), (x - 4, y - 4, w + 8, h + 34), border_radius=6)
        preview = hand.preview
        if preview is not None and preview.shape[1] == w:
            surf = pygame.image.frombuffer(preview.tobytes(), (w, h), "RGB")
            self.screen.blit(surf, (x, y))
        else:
            pygame.draw.rect(self.screen, (30, 30, 45), (x, y, w, h))
        ax, ay = x + hand.anchor[0] * w, y + hand.anchor[1] * h
        pygame.draw.circle(self.screen, (255, 255, 255), (ax, ay), DEAD_ZONE * w, 1)
        pygame.draw.circle(self.screen, (120, 120, 140), (ax, ay), FULL_SPEED * w, 1)
        points = hand.landmarks
        if points:
            pts = [(x + px * w, y + py * h) for px, py in points]
            for a, b in ((0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (5, 9), (9, 10),
                         (10, 11), (11, 12), (9, 13), (13, 14), (14, 15), (15, 16), (13, 17), (0, 17),
                         (17, 18), (18, 19), (19, 20)):
                pygame.draw.line(self.screen, (90, 230, 140), pts[a], pts[b], 2)
            for p in pts:
                pygame.draw.circle(self.screen, (255, 90, 90), p, 2)
            dx, dy = hand.direction
            colour = (255, 80, 80) if hand.fist else COLOR_GOLD
            pygame.draw.line(self.screen, colour, (ax, ay), (ax + dx * 60, ay + dy * 60), 4)
        label = {"loading": "HAND: loading...", "tracking": "HAND: FIST = STOP" if hand.fist else "HAND: tracking",
                 "no hand": "HAND: show your hand", "error": "HAND: " + hand.error}.get(hand.status, hand.status)
        colour = (255, 120, 120) if hand.status == "error" else COLOR_WHITE
        self.screen.blit(self.small_font.render(label[:34], True, colour), (x, y + h + 4))
        fps = self.small_font.render(f"{hand.fps:.0f} fps  [F7] off [F8] centre", True, (170, 170, 185))
        self.screen.blit(fps, (x, y + h + 18))

    def draw_banner(self):
        if self.banner_remaining <= 0:
            return
        alpha = min(1.0, self.banner_remaining / 0.6)
        text = self.title_font.render(self.banner_text, True, COLOR_GOLD)
        text.set_alpha(int(255 * alpha))
        band = pygame.Surface((SCREEN_WIDTH, text.get_height() + 30), pygame.SRCALPHA)
        band.fill((10, 10, 20, int(170 * alpha)))
        y = SCREEN_HEIGHT // 3
        self.screen.blit(band, (0, y - 15))
        self.screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, y))

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
        self.draw_background()
        self.supplies.draw(self.screen, self.camera_x, self.camera_y, self.small_font, self.player)

        for g in self.gems:
            g.draw(self.screen, self.camera_x, self.camera_y)
        for coffee in self.coffees:
            coffee.draw(self.screen, self.camera_x, self.camera_y)
        if self.boss and self.boss.hp > 0:
            draw_boss_telegraph(self.screen, self.boss, self.camera_x, self.camera_y)

        # Depth sorting: whatever stands lower on screen is drawn in front,
        # so characters walk behind and in front of desks correctly.
        view = pygame.Rect(self.camera_x - 120, self.camera_y - 120, SCREEN_WIDTH + 240, SCREEN_HEIGHT + 240)
        drawables = [(e.feet_y, 1, e) for e in self.enemies if view.collidepoint(e.x, e.y)]
        player_feet = self.player.y + (self.player.sprite.get_height() / 2 if self.player.sprite else self.player.radius)
        drawables.append((player_feet, 2, self.player))
        if self.scenery:
            drawables += [(p.sort_y, 0, p) for p in self.scenery.visible(self.camera_x, self.camera_y, SCREEN_WIDTH, SCREEN_HEIGHT) if p.solid]
        drawables.sort(key=lambda d: (d[0], d[1]))
        for _, _, thing in drawables:
            thing.draw(self.screen, self.camera_x, self.camera_y)

        for shot in self.enemy_shots:
            shot.draw(self.screen, self.camera_x, self.camera_y)
        self.player.weapons.draw(self.screen, self.player, self.camera_x, self.camera_y)
        self.effects.draw(self.screen, self.camera_x, self.camera_y, self.small_font)
        if self.scenery:
            self.scenery.draw_ambience(self.screen, self.last_dt)
        if self.show_debug:
            self.draw_debug_world()
        self.draw_hud()
        self.draw_hand_panel()
        if self.show_debug:
            self.draw_debug_panel()
        self.draw_banner()

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
        elif self.is_victory:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((10, 35, 20, 200))
            self.screen.blit(overlay, (0, 0))
            lines = [(self.title_font, "ACCOUNTING FACULTY CLEARED!", COLOR_GOLD, 230),
                     (self.font, f"Time {self.timer_seconds // 60:02d}:{self.timer_seconds % 60:02d}"
                                 f"   Kills {self.kill_count}   Level {self.player.level}", COLOR_WHITE, 300),
                     (self.font, "Press [ R ] to Play Again | Press [ ESC ] to Quit", COLOR_GOLD, 350)]
            for font, text, color, y in lines:
                surf = font.render(text, True, color)
                self.screen.blit(surf, (SCREEN_WIDTH // 2 - surf.get_width() // 2, y))

        pygame.display.flip()

    def run(self):
        while self.is_running:
            dt = self.clock.tick(FPS)/1000.0
            was_paused = self.is_level_up or self.is_game_over or self.is_victory
            self.handle_events()
            # Do not charge the last modal frame to active gameplay.
            started = time.perf_counter()
            if not was_paused:
                self.update(dt)
                self.sep_history = (self.sep_history + [self.separation_ms])[-400:]
            self.render()
            self.frame_ms = (time.perf_counter() - started) * 1000
        self.hand.stop()
        pygame.quit()
        sys.exit()


def start_at_stage2(game):
    """Debug/practice: jump to Stage 2 with a loadout similar to clearing Stage 1."""
    player = game.player
    player.level = 12
    player.weapons.levels = {"enter": 4, "book": 3, "lan": 3}
    game.start_stage(1)


def main():
    game = Game()
    # python main.py --stage 2  starts directly at the Accounting Faculty.
    if "--stage" in sys.argv and sys.argv[sys.argv.index("--stage") + 1:][:1] == ["2"]:
        start_at_stage2(game)
    game.run()


if __name__ == "__main__":
    main()
