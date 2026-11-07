"""Stage 2 (Accounting Faculty) mechanics: enemy shots, ranged enemies and the boss.

All timers use seconds of active gameplay (dt), like the rest of the game.
"""
import math
import random

import pygame

SHOT_LIFE = 4.0
CALC_SHOT_SPEED = 230.0
COIN_SHOT_SPEED = 170.0


class EnemyShot:
    """A projectile fired by an enemy. Damages the player on contact."""

    def __init__(self, x, y, angle, damage, kind="calc", speed=CALC_SHOT_SPEED):
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(angle) * speed, math.sin(angle) * speed
        self.damage = damage
        self.kind = kind
        self.radius = 8 if kind == "calc" else 7
        self.life = SHOT_LIFE
        self.spin = random.uniform(0, math.tau)

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        self.spin += dt * 8

    def hits(self, player):
        return math.hypot(self.x - player.x, self.y - player.y) < self.radius + player.radius

    def draw(self, surface, cam_x, cam_y):
        sx, sy = int(self.x - cam_x), int(self.y - cam_y)
        if self.kind == "coin":
            pygame.draw.circle(surface, (120, 80, 10), (sx, sy), 8)
            pygame.draw.circle(surface, (255, 205, 60), (sx, sy), 6)
            pygame.draw.line(surface, (150, 100, 20), (sx, sy - 3), (sx, sy + 3), 2)
            return
        # Small pixel calculator: grey body, green screen, key dots.
        body = pygame.Rect(sx - 6, sy - 8, 12, 16)
        pygame.draw.rect(surface, (30, 30, 40), body.inflate(2, 2))
        pygame.draw.rect(surface, (170, 175, 185), body)
        pygame.draw.rect(surface, (120, 200, 120), (sx - 4, sy - 6, 8, 4))
        for row in range(2):
            for col in range(3):
                pygame.draw.rect(surface, (60, 60, 75), (sx - 4 + col * 3, sy + row * 3, 2, 2))


def update_ranged(enemy, player, dt, shots, player_vel=(0.0, 0.0)):
    """Calculator-throwing enemies fire at where the player is going to be.

    Lead targeting: aim at position + velocity * flight time (one refinement
    step), so walking in a straight line no longer dodges every throw.
    """
    enemy.shoot_timer -= dt
    if enemy.shoot_timer > 0:
        return
    enemy.shoot_timer = enemy.shoot_cooldown
    dist = math.hypot(player.x - enemy.x, player.y - enemy.y)
    if dist > 520:
        return
    t = dist / CALC_SHOT_SPEED
    tx, ty = player.x + player_vel[0] * t, player.y + player_vel[1] * t
    t = math.hypot(tx - enemy.x, ty - enemy.y) / CALC_SHOT_SPEED
    tx, ty = player.x + player_vel[0] * t * 0.85, player.y + player_vel[1] * t * 0.85
    angle = math.atan2(ty - enemy.y, tx - enemy.x)
    shots.append(EnemyShot(enemy.x, enemy.y, angle, enemy.shot_damage, "calc"))


class BossBrain:
    """Finite state machine for the Chief Auditor.

    CHASE --(timer)--> next attack in ATTACK_CYCLE
    AUDIT   : wind up, fire a ring of coins            --> CHASE
    AIM     : stop and telegraph a dash (red line)      --> CHARGE
    CHARGE  : dash along the locked direction           --> RECOVER
    RECOVER : stand still, open to punishment           --> CHASE
    SUMMON  : call accounting freshmen                  --> CHASE
    Below 50% HP the boss is ENRAGED: shorter timers, denser rings.
    """

    ATTACK_CYCLE = ("AUDIT", "AIM", "SUMMON")
    DURATIONS = {"CHASE": 2.6, "AUDIT": 0.6, "AIM": 0.9, "CHARGE": 0.6, "RECOVER": 1.2, "SUMMON": 0.6}
    TRANSITIONS = {
        "CHASE": "next attack",
        "AUDIT": "CHASE",
        "AIM": "CHARGE",
        "CHARGE": "RECOVER",
        "RECOVER": "CHASE",
        "SUMMON": "CHASE",
    }
    CHARGE_SPEED = 520.0

    def __init__(self):
        self.state = "CHASE"
        self.timer = self.DURATIONS["CHASE"]
        self.attack_index = 0
        self.dash_angle = 0.0
        self.history = ["CHASE"]

    def enraged(self, boss):
        return boss.hp <= boss.max_hp / 2

    def duration(self, state, boss):
        return self.DURATIONS[state] * (0.65 if self.enraged(boss) and state in ("CHASE", "RECOVER") else 1)

    def enter(self, state, boss, player):
        self.state = state
        self.timer = self.duration(state, boss)
        self.history = (self.history + [state])[-12:]
        if state == "AIM":
            self.dash_angle = math.atan2(player.y - boss.y, player.x - boss.x)

    def next_state(self):
        target = self.TRANSITIONS[self.state]
        if target == "next attack":
            target = self.ATTACK_CYCLE[self.attack_index % len(self.ATTACK_CYCLE)]
            self.attack_index += 1
        return target

    def update(self, boss, player, dt, shots, summon):
        if self.state == "CHASE":
            boss.update(player.x, player.y, dt)
        elif self.state == "AIM":
            # Keep tracking until the last 0.25 s so the player can dodge the dash.
            if self.timer > 0.25:
                self.dash_angle = math.atan2(player.y - boss.y, player.x - boss.x)
        elif self.state == "CHARGE":
            boss.x += math.cos(self.dash_angle) * self.CHARGE_SPEED * dt
            boss.y += math.sin(self.dash_angle) * self.CHARGE_SPEED * dt
            boss.facing_right = math.cos(self.dash_angle) > 0
        self.timer -= dt
        if self.timer > 0:
            return
        # Actions that happen when a state finishes.
        if self.state == "AUDIT":
            count = 16 if self.enraged(boss) else 12
            offset = random.uniform(0, math.tau)
            for i in range(count):
                shots.append(EnemyShot(boss.x, boss.y, offset + i * math.tau / count,
                                       boss.shot_damage, "coin", COIN_SHOT_SPEED))
        elif self.state == "SUMMON":
            for i in range(5 if self.enraged(boss) else 4):
                angle = i * math.tau / 4 + random.uniform(-0.3, 0.3)
                summon("acc_freshman", boss.x + math.cos(angle) * 70, boss.y + math.sin(angle) * 70)
        self.enter(self.next_state(), boss, player)


def update_boss(boss, player, dt, shots, summon):
    """Advance the boss state machine. `summon(kind, x, y)` adds an enemy."""
    if getattr(boss, "brain", None) is None:
        boss.brain = BossBrain()
    boss.brain.update(boss, player, dt, shots, summon)


def draw_boss_telegraph(surface, boss, cam_x, cam_y):
    """Red warning line while the boss aims its dash."""
    brain = getattr(boss, "brain", None)
    if not brain or brain.state != "AIM":
        return
    sx, sy = boss.x - cam_x, boss.y - cam_y
    length = BossBrain.CHARGE_SPEED * BossBrain.DURATIONS["CHARGE"]
    ex = sx + math.cos(brain.dash_angle) * length
    ey = sy + math.sin(brain.dash_angle) * length
    blink = 255 if int(brain.timer * 10) % 2 else 150
    pygame.draw.line(surface, (blink, 40, 40), (sx, sy), (ex, ey), 5)
