"""Things that live in the game world: the player, enemies and pickups."""
import math
import random
import pygame

from settings import COLOR_HP_GREEN, COLOR_HP_RED
from weapons import WeaponSystem
from item_art import draw_item
from ai_enemies import AI_STATS, configure_ai
from animation import Animator


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
        self.lunge_windup = 0.28
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

        elif enemy_type in AI_STATS:
            configure_ai(self)
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
            self.lunge_state, self.lunge_timer = "windup", self.lunge_windup
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
