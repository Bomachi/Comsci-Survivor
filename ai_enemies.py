"""AI enemies and a multipart boss. Head targets never enter the crowd/loot lists."""
import math
import random

import pygame

from accounting import EnemyShot
from animation import Animator, frame

AI_COLORS = {"chatgpt": (90, 230, 180), "claude": (218, 126, 91),
             "gemini": (115, 150, 255)}
AI_STATS = {
    "ai_chatgpt": (110, 95.0, 19, 16, 4, AI_COLORS["chatgpt"]),
    "ai_claude": (90, 160.0, 20, 18, 4, AI_COLORS["claude"]),
    "ai_gemini": (180, 90.0, 23, 24, 7, AI_COLORS["gemini"]),
}
MAX_AI_SHOTS = 240
CHATGPT_SHOT_SPEED = 150.0
CHATGPT_SHOT_COOLDOWN = 3.5


def configure_ai(enemy):
    (enemy.hp, enemy.speed, enemy.radius, enemy.damage,
     enemy.exp_value, enemy.color) = AI_STATS[enemy.enemy_type]
    enemy.attack_timer = random.uniform(0.8, 2.0)
    enemy.attack_windup = 0.0
    if enemy.enemy_type == "ai_chatgpt":
        enemy.preferred_range = 260
        enemy.attack_timer = random.uniform(CHATGPT_SHOT_COOLDOWN / 2, CHATGPT_SHOT_COOLDOWN)
    elif enemy.enemy_type == "ai_claude":
        enemy.can_lunge = True
        enemy.lunge_windup = 0.4
    else:
        enemy.preferred_range = 280


class AIShot(EnemyShot):
    def __init__(self, x, y, angle, damage, kind, speed):
        super().__init__(x, y, angle, damage, kind, speed)
        self.radius = 7

    def draw(self, surface, cam_x, cam_y):
        x, y = round(self.x - cam_x), round(self.y - cam_y)
        if self.kind == "token":
            pygame.draw.circle(surface, (12, 45, 40), (x, y), 9)
            for sign in (-1, 1):
                pygame.draw.lines(surface, AI_COLORS["chatgpt"], False,
                                  [(x + sign * 2, y - 5), (x + sign * 6, y),
                                   (x + sign * 2, y + 5)], 2)
        else:
            points = [(x, y - 9), (x + 3, y - 3), (x + 9, y), (x + 3, y + 3),
                      (x, y + 9), (x - 3, y + 3), (x - 9, y), (x - 3, y - 3)]
            pygame.draw.polygon(surface, (25, 25, 65), points)
            pygame.draw.polygon(surface, AI_COLORS["gemini"], points, 2)
            pygame.draw.line(surface, (255, 190, 225), (x, y - 5), (x, y + 4), 2)


def fire_fan(shots, x, y, angle, count=3, damage=14, speed=260):
    for i in range(count):
        if len(shots) < MAX_AI_SHOTS:
            shots.append(AIShot(x, y, angle + (i - (count - 1) / 2) * 0.18,
                                damage, "token", speed))


def fire_ring(shots, x, y, angle, count=8, damage=16):
    for i in range(count):
        if len(shots) < MAX_AI_SHOTS:
            shots.append(AIShot(x, y, angle + i * math.tau / count,
                                damage, "star", 190))


def update_ai(enemy, player, dt, shots, player_vel=(0, 0), steer=None):
    if enemy.enemy_type == "ai_claude":
        enemy.update(player.x, player.y, dt, steer)
        return
    if enemy.attack_windup > 0:
        enemy.attack_windup = max(0, enemy.attack_windup - dt)
        enemy.slow_remaining = max(0, enemy.slow_remaining - dt)
        if enemy.attack_windup <= 1e-9:
            enemy.attack_windup = 0
            angle = math.atan2(player.y - enemy.y, player.x - enemy.x)
            fire_ring(shots, enemy.x, enemy.y, angle)
            enemy.attack_timer = 2.4  # 0.6 s warning + 2.4 s rest = 3 s
        return
    enemy.update(player.x, player.y, dt, steer)
    enemy.attack_timer -= dt
    if enemy.attack_timer > 1e-9:
        return
    distance = math.hypot(player.x - enemy.x, player.y - enemy.y)
    if distance > 520:
        return
    if enemy.enemy_type == "ai_gemini":
        enemy.attack_windup = 0.6
    else:
        lead = min(0.6, distance / CHATGPT_SHOT_SPEED) * 0.85
        angle = math.atan2(player.y + player_vel[1] * lead - enemy.y,
                           player.x + player_vel[0] * lead - enemy.x)
        fire_fan(shots, enemy.x, enemy.y, angle, count=1, speed=CHATGPT_SHOT_SPEED)
        enemy.attack_timer = CHATGPT_SHOT_COOLDOWN


def draw_ai_warning(surface, enemy, cam_x, cam_y):
    x, y = round(enemy.x - cam_x), round(enemy.y - cam_y)
    if getattr(enemy, "attack_windup", 0) > 0:
        pygame.draw.circle(surface, AI_COLORS["gemini"], (x, y), enemy.radius + 11, 2)
        for i in range(8):
            angle = i * math.tau / 8
            pygame.draw.line(surface, AI_COLORS["gemini"],
                             (x + math.cos(angle) * 28, y + math.sin(angle) * 28),
                             (x + math.cos(angle) * 40, y + math.sin(angle) * 40), 2)
    if enemy.enemy_type == "ai_claude" and enemy.lunge_state == "windup":
        dx, dy = enemy.lunge_dir
        pygame.draw.line(surface, AI_COLORS["claude"], (x, y),
                         (x + dx * 130, y + dy * 130), 3)


class HydraHead:
    """Weapon-compatible target anchored to its owner, with independent health."""
    radius = 25
    max_hp = 1800

    def __init__(self, owner, kind, offset, sprite):
        self.owner, self.kind, self.offset, self.sprite = owner, kind, offset, sprite
        self.hp = self.max_hp
        self.prev_hp = self.hp
        self.flash = 0.0
        self.death_announced = False

    @property
    def x(self):
        return self.owner.x + self.offset[0]

    @property
    def y(self):
        return self.owner.y + self.offset[1]

    @property
    def slow_remaining(self):
        return self.owner.slow_remaining

    @slow_remaining.setter
    def slow_remaining(self, value):
        self.owner.slow_remaining = value

    @property
    def knockback_body(self):
        return self.owner


class HydraBrain:
    """Only living heads get turns. Severing the active head interrupts its turn."""
    CHARGE_SPEED = 430.0

    def __init__(self):
        self.state, self.timer = "CHASE", 1.8
        self.attack_index = 0
        self.active_head = None
        self.dash_angle = 0.0
        self.history = ["CHASE"]

    def enter(self, state, timer):
        self.state, self.timer = state, timer
        self.history = (self.history + [state])[-16:]

    def enraged(self, boss):
        return len(boss.living_heads) < 3

    def rest(self, boss):
        return 1.8 * {3: 1.0, 2: 0.85, 1: 0.7, 0: 0.7}[len(boss.living_heads)]

    def recover(self, boss):
        self.enter("CHASE", self.rest(boss))
        self.active_head = None

    def cancel_if_destroyed(self, boss):
        if self.active_head is not None and self.active_head.hp <= 0:
            self.recover(boss)

    def update(self, boss, player, dt, shots, steer=None):
        self.cancel_if_destroyed(boss)
        if not boss.living_heads:
            return
        if self.state == "CHASE":
            boss.update(player.x, player.y, dt, steer)
        elif self.state == "TELEGRAPH" and self.active_head.kind == "claude":
            if self.timer > 0.25:
                self.dash_angle = math.atan2(player.y - boss.y, player.x - boss.x)
        elif self.state == "CHARGE":
            speed = self.CHARGE_SPEED * (0.55 if boss.slow_remaining > 0 else 1)
            boss.x += math.cos(self.dash_angle) * speed * dt
            boss.y += math.sin(self.dash_angle) * speed * dt
        boss.slow_remaining = max(0, boss.slow_remaining - dt)
        self.timer -= dt
        if self.timer > 1e-9:
            return
        if self.state == "CHASE":
            for _ in range(3):
                head = boss.heads[self.attack_index % 3]
                self.attack_index += 1
                if head.hp > 0:
                    self.active_head = head
                    break
            self.enter("TELEGRAPH", 0.8)
            self.dash_angle = math.atan2(player.y - boss.y, player.x - boss.x)
        elif self.state == "TELEGRAPH":
            head = self.active_head
            angle = math.atan2(player.y - head.y, player.x - head.x)
            if head.kind == "claude":
                self.enter("CHARGE", 0.45)
            else:
                if head.kind == "chatgpt":
                    fire_fan(shots, head.x, head.y, angle, 7, 18)
                else:
                    fire_ring(shots, head.x, head.y, angle, 16, 18)
                self.recover(boss)
        elif self.state == "CHARGE":
            self.enter("RECOVER", 0.8)
        else:
            self.recover(boss)


class Hydra:
    enemy_type = "ai_hydra"
    radius, speed, damage, mass = 44, 72.0, 32, 12.0
    exp_value, is_boss = 120, True
    color = (70, 220, 200)
    facing_right = True
    flank = 0.0
    max_hp = 5400

    def __init__(self, x, y, sprite=None, head_sprites=None):
        self.x, self.y, self.sprite = x, y, sprite
        self.slow_remaining = 0.0
        self.anim, self.brain = Animator(), HydraBrain()
        head_sprites = head_sprites or {}
        self.heads = [HydraHead(self, kind, offset, head_sprites.get(kind))
                      for kind, offset in (("chatgpt", (-64, -47)),
                                           ("claude", (0, -90)),
                                           ("gemini", (64, -47)))]
        self.prev_hp = self.hp

    @property
    def hp(self):
        return sum(max(0, head.hp) for head in self.heads)

    @hp.setter
    def hp(self, value):
        # Also supports the same debug defeat operation as ordinary enemies.
        for head in self.heads:
            head.hp = max(0, min(head.max_hp, value / 3))

    @property
    def living_heads(self):
        return [head for head in self.heads if head.hp > 0]

    @property
    def feet_y(self):
        return self.y + (self.sprite.get_height() / 2 if self.sprite else self.radius)

    def update(self, px, py, dt, steer=None):
        dx, dy = px - self.x, py - self.y
        dist = math.hypot(dx, dy)
        direction = steer or ((dx / dist, dy / dist) if dist else (0, 0))
        step = min(dist, self.speed * dt * (0.55 if self.slow_remaining > 0 else 1))
        self.x += direction[0] * step
        self.y += direction[1] * step

    def update_feedback(self, dt, effects):
        for head in self.heads:
            head.flash = max(0, head.flash - dt)
            if head.hp < head.prev_hp:
                head.flash = 0.09
                effects.damage(head.x, head.y - 30, head.prev_hp - max(0, head.hp),
                               AI_COLORS[head.kind])
            if head.hp <= 0 and not head.death_announced:
                effects.burst(head.x, head.y, head.sprite, 18)
                head.death_announced = True
            head.prev_hp = max(0, head.hp)
        self.brain.cancel_if_destroyed(self)

    def draw(self, surface, cam_x, cam_y):
        x, y = round(self.x - cam_x), round(self.y - cam_y)
        for head in self.living_heads:
            end = (round(head.x - cam_x), round(head.y - cam_y))
            start = (x + head.offset[0] // 3, y - 8)
            middle = (end[0], y - 18)
            pygame.draw.lines(surface, (12, 28, 42), False, [start, middle, end], 16)
            pygame.draw.lines(surface, AI_COLORS[head.kind], False, [start, middle, end], 8)
            pygame.draw.lines(surface, (110, 235, 230), False, [start, middle, end], 2)
        if self.sprite:
            self.anim.draw(surface, self.sprite, x, y)
        else:
            pygame.draw.ellipse(surface, self.color, (x - 55, y - 30, 110, 65))
        for head in self.living_heads:
            center = (round(head.x - cam_x), round(head.y - cam_y))
            pygame.draw.circle(surface, (15, 23, 40), center, 28)
            pygame.draw.circle(surface, AI_COLORS[head.kind], center, 28, 2)
            if head.sprite:
                img = frame(head.sprite, 1, 1, white=head.flash > 0)
                surface.blit(img, img.get_rect(center=center))

    def draw_telegraph(self, surface, cam_x, cam_y):
        brain = self.brain
        head = brain.active_head
        if brain.state != "TELEGRAPH" or head is None or head.hp <= 0:
            return
        center = (round(head.x - cam_x), round(head.y - cam_y))
        color = AI_COLORS[head.kind]
        pygame.draw.circle(surface, color, center, 34 + round(brain.timer * 8), 3)
        if head.kind == "claude":
            start = (round(self.x - cam_x), round(self.y - cam_y))
            length = brain.CHARGE_SPEED * 0.45
            end = (start[0] + math.cos(brain.dash_angle) * length,
                   start[1] + math.sin(brain.dash_angle) * length)
            pygame.draw.line(surface, color, start, end, 6)
