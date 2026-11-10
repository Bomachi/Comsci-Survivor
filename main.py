"""Comsci Survivor - entry point and the Game class (game loop, stages, spawning, combat).

Where the rest lives:
    settings.py    window size, FPS, colours
    resources.py   image loading
    entities.py    Player, Enemy, Gem, Coffee
    ui.py          GameState, Button, main menu / stage select / pause menu
    hud.py         HUD, boss bars, level-up cards, game over / victory screens
    debug_view.py  F3 debug overlay
    hand_ui.py     hand-control menus and camera preview
"""
import os
import sys
import math
import random
import time
import pygame

from settings import BASE_DIR, SCREEN_WIDTH, SCREEN_HEIGHT, FPS
from resources import load_sprite, load_ai_sprite
from entities import Player, Enemy, Gem, Coffee
from ui import GameState, Button, MenuMixin   # Button is re-exported for the tests
from hud import HudMixin
from debug_view import DebugMixin
from hand_ui import HandMenuMixin
from stages import STAGES
from upgrades import level_up_choices, apply_choice
from supplies import Supplies, Food
from accounting import update_ranged, update_boss, draw_boss_telegraph
from ai_enemies import AI_STATS, AI_COLORS, Hydra, update_ai, draw_ai_warning
from spatial import separate
from pathfinding import ObstacleMap, FlowField
from animation import Effects
from stage_art import Scenery
from hand_control import HandController


class Game(MenuMixin, HudMixin, DebugMixin, HandMenuMixin):
    def __init__(self, start_in_menu=False):
        pygame.init()
        pygame.font.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Comsci Survivor")
        self.clock = pygame.time.Clock()

        self.load_fonts()
        self.load_sprites()

        # Debug overlay (F3) and collision strategy (F2) for demos/benchmarks.
        self.show_debug = False
        self.collision_mode = "hash"
        self.demo_mode = False  # F4: invincible; automatic weapons stay active
        self.frame_ms = 0.0
        self.sep_history = []
        self.effects = Effects()
        self.hand = HandController()
        self.hand_pick_index = None    # card under the hand during level-up
        self.hand_hold = 0.0           # seconds the fist has been held
        self.hand_armed = True         # must open the hand again between picks
        self.obstacles = ObstacleMap()
        self.flow = FlowField(self.obstacles)
        self.scenery = None
        self.player_vel = (0.0, 0.0)
        self.last_dt = 1 / FPS
        self.flow_ms = 0.0

        self.init_menus(start_in_menu)
        self.reset_game()

    def load_fonts(self):
        font_path = os.path.join(BASE_DIR, "assets", "fonts", "Minecraft.ttf")
        if os.path.exists(font_path):
            self.font = pygame.font.Font(font_path, 18)
            self.small_font = pygame.font.Font(font_path, 13)
            self.title_font = pygame.font.Font(font_path, 36)
        else:
            self.font = pygame.font.SysFont("tahoma", 18)
            self.small_font = pygame.font.SysFont("tahoma", 13)
            self.title_font = pygame.font.SysFont("tahoma", 36)

    def load_sprites(self):
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
            "ai_chatgpt": load_ai_sprite("ai_chatgpt.png", (48, 52)),
            "ai_claude": load_ai_sprite("ai_claude.png", (50, 45)),
            "ai_gemini": load_ai_sprite("ai_gemini.png", (56, 60)),
            "ai_hydra": load_ai_sprite("ai_hydra_body.png", (146, 106)),
        }
        self.hydra_head_sprites = {kind: load_ai_sprite("head_" + kind + ".png", (46, 46))
                                   for kind in AI_COLORS}
        self.stage_tiles = {"stage1_tile.png": self.stage1_tile}
        self.card_frame = load_sprite("card_frame.png", (240, 300))
        self.card_frame_hover = load_sprite("card_frame_hover.png", (240, 300))

    def stage_tile(self):
        name = self.current_stage.ground_tile_name
        if self.current_stage.scenery_theme == "ai" and self.scenery:
            return self.scenery.tiles[0]
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
        self.scenery = Scenery(theme=self.current_stage.scenery_theme) if self.current_stage.decorated else None
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
        self.start_stage(self.selected_stage)

    def spawn_enemy(self):
        angle = random.uniform(0, math.tau)
        dist = random.uniform(600, 750)
        ex = self.player.x + math.cos(angle) * dist
        ey = self.player.y + math.sin(angle) * dist
        stage_time = self.timer_seconds - int(self.stage_start_seconds)
        etype = self.current_stage.get_enemy_spawn_type(stage_time)
        self.add_enemy(etype, ex, ey)

    def add_enemy(self, etype, x, y):
        if etype == "ai_hydra":
            enemy = Hydra(x, y, self.enemy_sprites[etype], self.hydra_head_sprites)
        else:
            enemy = Enemy(x, y, etype, sprite=self.enemy_sprites.get(etype))
        self.obstacles.push_out(enemy)
        self.enemies.append(enemy)
        return enemy

    def stress_spawn(self, count):
        """Demo: add a crowd around the player, ignoring the normal enemy cap."""
        kind = ("ai_chatgpt" if self.current_stage.scenery_theme == "ai" else
                "acc_freshman" if self.current_stage.boss_type else "TA")
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
        self.banner_text = "BOSS: " + stage.boss_name
        self.banner_remaining = 3.0

    def update_stage_progress(self):
        """Spawn the stage boss on schedule and win the stage once its time is up.

        A stage is won when its full duration has passed AND any boss that has
        appeared is defeated. Winning ends the run (it does not chain into the
        next stage).
        """
        stage = self.current_stage
        stage_time = self.elapsed_seconds - self.stage_start_seconds
        if stage.boss_type and not self.boss_spawned and stage_time >= stage.boss_time:
            self.spawn_boss()
        boss_alive = self.boss_spawned and self.boss is not None and self.boss.hp > 0
        if stage_time >= stage.duration and not boss_alive:
            self.is_victory = True
            return True
        return False

    def combat_targets(self):
        """Weapons see heads; movement, contact, separation and loot see bodies."""
        targets = []
        for enemy in self.enemies:
            if isinstance(enemy, Hydra):
                targets.extend(enemy.living_heads)
            elif enemy.hp > 0:
                targets.append(enemy)
        return targets

    def trigger_level_up(self):
        self.is_level_up = True
        self.current_upgrades = level_up_choices(self.player, random)
        num_options = len(self.current_upgrades)

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
        if upgrade_data not in self.current_upgrades or not apply_choice(self.player, upgrade_data):
            return
        self.player.pending_level_ups -= 1

        if self.player.pending_level_ups > 0:
            self.trigger_level_up()
        else:
            self.is_level_up = False

    def handle_events(self):
        mouse_pos = pygame.mouse.get_pos()
        for button in self.menu_buttons():
            button.update(mouse_pos)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.is_running = False
            elif self.state == GameState.MAIN_MENU:
                self.handle_main_menu_event(event)
            elif self.state == GameState.STAGE_SELECT:
                self.handle_stage_select_event(event)
            elif self.state == GameState.PAUSED:
                self.handle_pause_event(event)
            else:
                self.handle_play_event(event)

    def handle_play_event(self, event):
        if self.is_victory and self.btn_victory_menu.is_clicked(event):
            self.go_to_main_menu()
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.is_victory:
                    self.go_to_main_menu()
                elif self.is_game_over:
                    self.is_running = False   # matches the on-screen "[ ESC ] to Quit"
                else:
                    self.state = GameState.PAUSED
            elif event.key == pygame.K_RETURN and self.is_victory:
                self.go_to_main_menu()
            elif event.key == pygame.K_F3:
                self.show_debug = not self.show_debug
            elif event.key == pygame.K_F2:
                self.collision_mode = "naive" if self.collision_mode == "hash" else "hash"
                self.sep_history.clear()
            elif event.key == pygame.K_F7:
                self.hand.toggle()
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
        """One simulation step. Each part of the frame has its own method below."""
        if self.state != GameState.PLAYING or self.is_game_over or self.is_level_up or self.is_victory:
            return
        # A stalled window must not jump the simulation several seconds ahead.
        dt = min(max(dt, 0), 0.1)
        self.update_timers(dt)
        moved = self.update_player(dt)
        self.update_camera(dt)
        self.update_spawning(dt)
        self.update_enemies(dt)
        self.separate_enemies()
        self.update_weapons(dt)
        self.update_hit_feedback(dt)
        self.resolve_kills()
        if self.update_stage_progress():
            return
        if self.update_player_damage(dt):
            return      # the player died this frame
        self.update_pickups(dt, moved)
        if self.player.pending_level_ups > 0:
            self.trigger_level_up()

    def update_timers(self, dt):
        self.elapsed_seconds += dt
        self.timer_seconds = int(self.elapsed_seconds)
        self.banner_remaining = max(0, self.banner_remaining - dt)
        self.player.coffee_remaining = max(0, self.player.coffee_remaining-dt)
        self.player.hurt_remaining = max(0, self.player.hurt_remaining-dt)
        self.last_dt = dt

    def update_player(self, dt):
        """Move the player (keyboard or hand), then rebuild the flow field. True if they moved."""
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
        return moved

    def update_camera(self, dt):
        smoothing = 1 - 0.9 ** (dt*60)
        self.camera_x += (self.player.x - SCREEN_WIDTH//2 - self.camera_x)*smoothing
        self.camera_y += (self.player.y - SCREEN_HEIGHT//2 - self.camera_y)*smoothing

    def update_spawning(self, dt):
        self.spawn_timer += dt
        interval = self.current_stage.spawn_interval * (1.6 if self.boss and self.boss.hp > 0 else 1)
        if self.spawn_timer >= interval:
            if len(self.enemies) < 120:
                self.spawn_enemy()
            self.spawn_timer %= interval

    def update_enemies(self, dt):
        """Move every living enemy with the behaviour that matches its type."""
        for enemy in self.enemies:
            if enemy.hp > 0:
                if enemy.is_boss:
                    # The boss state machine decides when and how it moves.
                    if isinstance(enemy, Hydra):
                        enemy.brain.update(enemy, self.player, dt, self.enemy_shots, self.steer_for(enemy))
                    else:
                        update_boss(enemy, self.player, dt, self.enemy_shots, self.add_enemy)
                    continue
                if enemy.enemy_type in AI_STATS:
                    update_ai(enemy, self.player, dt, self.enemy_shots, self.player_vel, self.steer_for(enemy))
                    continue
                enemy.update(self.player.x, self.player.y, dt, self.steer_for(enemy))
                if enemy.shoot_cooldown:
                    update_ranged(enemy, self.player, dt, self.enemy_shots, self.player_vel)

    def separate_enemies(self):
        """Crowd separation: naive O(n^2) or spatial hash (toggle with F2)."""
        living = [e for e in self.enemies if e.hp > 0]
        started = time.perf_counter()
        self.pair_stats = separate(living, self.collision_mode)
        self.pair_n = len(living)
        self.separation_ms = (time.perf_counter() - started) * 1000
        if self.obstacles.rects:
            for enemy in living:
                self.obstacles.push_out(enemy)

    def update_weapons(self, dt):
        self.player.weapons.update(dt, self.player, self.combat_targets())
        if isinstance(self.boss, Hydra):
            self.obstacles.push_out(self.boss)

    def update_hit_feedback(self, dt):
        """Flash + damage number whenever an enemy lost HP."""
        for enemy in self.enemies:
            enemy.anim.update(enemy.x, enemy.y, dt)
            if isinstance(enemy, Hydra):
                enemy.update_feedback(dt, self.effects)
            elif enemy.prev_hp is not None and enemy.hp < enemy.prev_hp:
                enemy.anim.hit()
                lost = enemy.prev_hp - max(0, enemy.hp)
                self.effects.damage(enemy.x, enemy.y - enemy.radius - 18, lost,
                                    (255, 120, 90) if enemy.is_boss else (255, 240, 200))
            enemy.prev_hp = enemy.hp
        self.effects.update(dt)

    def resolve_kills(self):
        """Remove dead enemies before contact damage; each enemy drops loot once."""
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

    def update_player_damage(self, dt):
        """Enemy shots and contact damage. Returns True if the player died."""
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
                self.effects.damage(self.player.x, self.player.y - self.player.radius - 18,
                                    damage, (255, 70, 70))
                if self.player.hp <= 0:
                    self.is_game_over = True
                    return True
        self.enemy_shots = [shot for shot in self.enemy_shots if shot.life > 0]
        return False

    def update_pickups(self, dt, moved):
        """Food, coffee and EXP gems."""
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


    def render(self):
        if self.state == GameState.MAIN_MENU:
            self.draw_main_menu()
        elif self.state == GameState.STAGE_SELECT:
            self.draw_stage_select()
        else:
            self.draw_world()
            self.draw_interface()
        pygame.display.flip()

    def draw_world(self):
        """Everything that lives in world coordinates: ground, pickups, characters, shots."""
        self.draw_background()
        self.supplies.draw(self.screen, self.camera_x, self.camera_y, self.small_font, self.player)

        for g in self.gems:
            g.draw(self.screen, self.camera_x, self.camera_y)
        for coffee in self.coffees:
            coffee.draw(self.screen, self.camera_x, self.camera_y)
        if self.boss and self.boss.hp > 0:
            if isinstance(self.boss, Hydra):
                self.boss.draw_telegraph(self.screen, self.camera_x, self.camera_y)
            else:
                draw_boss_telegraph(self.screen, self.boss, self.camera_x, self.camera_y)
        for enemy in self.enemies:
            if enemy.enemy_type in AI_STATS:
                draw_ai_warning(self.screen, enemy, self.camera_x, self.camera_y)

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

    def draw_interface(self):
        """Everything drawn on top of the world: HUD, debug, pop-up screens, pause menu."""
        if self.show_debug:
            self.draw_debug_world()
        self.draw_hud()
        if self.show_debug:
            self.draw_debug_panel()
        self.draw_banner()

        if self.is_level_up:
            self.draw_level_up_modal()
        elif self.is_game_over:
            self.draw_game_over_screen()
        elif self.is_victory:
            self.draw_victory_screen()

        if self.hand.status != "off":
            if (self.is_game_over or self.is_victory) and self.hand_hold > 0:
                self.draw_hand_hold_bar(pygame.Rect(SCREEN_WIDTH // 2 - 150, 380, 300, 0), self.HAND_RESTART_SECONDS)
            self.draw_hand_panel()
        if self.state == GameState.PAUSED:
            self.draw_pause_menu()

    def run(self):
        while self.is_running:
            dt = self.clock.tick(FPS)/1000.0
            was_paused = (self.is_level_up or self.is_game_over or self.is_victory
                          or self.state != GameState.PLAYING)
            self.handle_events()
            # Do not charge the last modal frame to active gameplay.
            started = time.perf_counter()
            self.update_hand_menus(dt)
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
    game.selected_stage = 1
    game.start_stage(1)


def start_at_stage3(game):
    """Practice the data center with a fully upgraded, three-weapon loadout."""
    player = game.player
    player.level = 20
    player.exp = player.pending_level_ups = 0
    player.exp_to_next = 5
    for _ in range(player.level - 1):
        player.exp_to_next = int(player.exp_to_next * 1.35) + 3
    player.weapons.levels = {"enter": 5, "book": 5, "lan": 5}
    game.selected_stage = 2
    game.start_stage(2)


def create_game(argv=None):
    """Build the Game from command-line flags (used by main() and the tests).

    python main.py             opens the main menu.
    python main.py --stage 2   skips the menu and starts at the Accounting Faculty.
    python main.py --stage 3   skips the menu and starts at the data center.
    """
    argv = sys.argv if argv is None else argv
    has_stage_flag = "--stage" in argv
    stage = argv[argv.index("--stage") + 1:][:1] if has_stage_flag else []
    game = Game(start_in_menu=not has_stage_flag)
    if stage == ["2"]:
        start_at_stage2(game)
    elif stage == ["3"]:
        start_at_stage3(game)
    return game


def main():
    create_game().run()


if __name__ == "__main__":
    main()
