"""Automatic weapons. All timers use seconds of active gameplay."""
import math
import pygame

from item_art import draw_item

MAX_WEAPONS = 3
MAX_LEVEL = 5
MAX_PROJECTILES = 180
WEAPONS = {
    "enter": ("Enter Key", "Fire keys at the nearest enemy. Gain multishot and piercing.", (100, 210, 255)),
    "book": ("Project Books", "Books orbit you. Gain books, orbit speed and reach.", (255, 185, 90)),
    "lan": ("LAN Whip", "Sweep a line toward the nearest enemy. Gain reach and width.", (90, 235, 170)),
    "bug": ("Bug Army", "Homing bugs explode on contact. Later levels slow enemies.", (220, 120, 245)),
    "wifi": ("Dept. Wi-Fi", "Pulse around you, damaging and pushing enemies away.", (100, 150, 255)),
    "recursion": ("Recursion", "Braces split on impact. Split generations are limited.", (255, 125, 140)),
}


def draw_icon(surface, kind, center, size=16):
    draw_item(surface, kind, center, size * 2)


class Projectile:
    def __init__(self, x, y, angle, damage, kind="enter", level=1, generation=0, excluded=()):
        self.x, self.y = x, y
        self.angle, self.damage, self.kind = angle, damage, kind
        self.level, self.generation = level, generation
        self.speed = 240 if kind == "bug" else 520
        self.radius = 8
        self.life = 2.5
        self.hits_left = 2 if kind == "enter" and level >= 4 else 1
        self.hit = set(excluded)

    def update(self, dt, enemies, additions, effects):
        living = [e for e in enemies if e.hp > 0 and e not in self.hit]
        if self.kind == "bug" and living:
            target = min(living, key=lambda e: math.hypot(e.x-self.x,e.y-self.y))
            self.angle = math.atan2(target.y-self.y,target.x-self.x)
        old_x, old_y = self.x, self.y
        self.x += math.cos(self.angle)*self.speed*dt
        self.y += math.sin(self.angle)*self.speed*dt
        self.life -= dt
        # Swept collision prevents fast keys passing through a target at low FPS.
        vx, vy = self.x-old_x, self.y-old_y
        length_sq = vx*vx+vy*vy
        collisions = []
        for enemy in living:
            t = max(0, min(1, ((enemy.x-old_x)*vx+(enemy.y-old_y)*vy)/(length_sq or 1)))
            if math.hypot(enemy.x-(old_x+t*vx),enemy.y-(old_y+t*vy)) <= enemy.radius+self.radius:
                collisions.append((t, enemy))
        for t, enemy in sorted(collisions, key=lambda pair: pair[0]):
            if enemy.hp <= 0:
                continue
            self.hit.add(enemy)
            impact_x, impact_y = old_x+t*vx, old_y+t*vy
            if self.kind == "bug":
                radius = 42+self.level*9
                for victim in enemies:
                    if victim.hp > 0 and math.hypot(victim.x-impact_x,victim.y-impact_y) <= radius+victim.radius:
                        victim.hp -= self.damage
                        if self.level >= 3:
                            victim.slow_remaining = max(victim.slow_remaining, 2)
                effects.append(Effect("bug",impact_x,impact_y,radius))
            else:
                enemy.hp -= self.damage
            if self.kind == "recursion" and self.generation < (2 if self.level >= 4 else 1):
                count = 3 if self.level >= 3 else 2
                for i in range(count):
                    angle = self.angle + (i-(count-1)/2)*0.9
                    additions.append(Projectile(impact_x,impact_y,angle,self.damage*0.6,"recursion",self.level,self.generation+1,self.hit))
            self.hits_left -= 1
            if self.hits_left <= 0:
                self.life = 0
                break

    def draw(self, surface, cam_x, cam_y):
        size = {"enter": 30, "bug": 26, "recursion": 24}[self.kind]
        angle = -math.degrees(self.angle)-90 if self.kind == "bug" else 0
        draw_item(surface, self.kind, (self.x-cam_x, self.y-cam_y), size, angle)


class Effect:
    def __init__(self, kind, x, y, radius, angle=0, width=0):
        self.kind,self.x,self.y,self.radius = kind,x,y,radius
        self.angle,self.width,self.life = angle,width,0.24

    def draw(self, surface, cam_x, cam_y):
        center = (round(self.x-cam_x), round(self.y-cam_y))
        color = WEAPONS[self.kind][2]
        progress = max(0, min(1, 1-self.life/0.24))
        if self.kind == "lan":
            # A curved cable with an outlined jacket, highlight and visible plug.
            ux, uy = math.cos(self.angle), math.sin(self.angle)
            points = []
            for index in range(13):
                t = index/12
                bend = math.sin(t*math.pi)*self.width*(1-progress)*0.6
                points.append((round(center[0]+ux*t*self.radius-uy*bend),
                               round(center[1]+uy*t*self.radius+ux*bend)))
            pygame.draw.lines(surface, (20, 19, 45), False, points, 7)
            pygame.draw.lines(surface, color, False, points, 4)
            pygame.draw.aalines(surface, (190, 255, 225), False, points)
            draw_item(surface, "lan", points[-1], 26)
        else:
            extent = math.ceil(self.radius)+8
            halo = pygame.Surface((extent*2, extent*2), pygame.SRCALPHA)
            origin = (extent, extent)
            radius = max(2, round(self.radius*(0.2+progress*0.8)))
            alpha = round(210*(1-progress))
            pygame.draw.circle(halo, (*color, alpha//5), origin, radius)
            pygame.draw.circle(halo, (*color, alpha), origin, radius, 3)
            pygame.draw.circle(halo, (240, 245, 255, alpha//2), origin, max(2, radius-4), 1)
            if self.kind == "wifi":
                pygame.draw.circle(halo, (*color, alpha//2), origin, max(2, round(radius*0.65)), 2)
            surface.blit(halo, (center[0]-extent, center[1]-extent))


class WeaponSystem:
    def __init__(self):
        self.levels = {"enter": 1}
        self.timers = {}
        self.projectiles = []
        self.effects = []
        self.orbit_angle = 0
        self.book_hits = {}

    def can_upgrade(self, kind):
        return kind in WEAPONS and (self.levels.get(kind,0) < MAX_LEVEL) and (kind in self.levels or len(self.levels) < MAX_WEAPONS)

    def upgrade(self, kind):
        if not self.can_upgrade(kind):
            return False
        self.levels[kind] = self.levels.get(kind,0)+1
        return True

    def book_positions(self, player):
        level = self.levels.get("book",0)
        count = 1+(level-1)//2
        radius = 58+level*8
        return [(player.x+math.cos(self.orbit_angle+i*math.tau/count)*radius,
                 player.y+math.sin(self.orbit_angle+i*math.tau/count)*radius) for i in range(count)] if level else []

    def update(self, dt, player, enemies):
        rate = 1.25 if player.coffee_remaining > 0 else 1.0
        self.effects = [fx for fx in self.effects if fx.life > dt]
        for fx in self.effects:
            fx.life -= dt
        self.book_hits = {e:t-dt for e,t in self.book_hits.items() if t > dt and e in enemies and e.hp > 0}
        self.orbit_angle = (self.orbit_angle+dt*(2+self.levels.get("book",0)*0.25)*rate)%math.tau
        for x,y in self.book_positions(player):
            for enemy in enemies:
                if enemy.hp > 0 and enemy not in self.book_hits and math.hypot(enemy.x-x,enemy.y-y) < enemy.radius+13:
                    enemy.hp -= 14+8*self.levels["book"]
                    self.book_hits[enemy] = 0.35
        for kind,level in self.levels.items():
            if kind == "book":
                continue
            self.timers[kind] = self.timers.get(kind,0)-dt*rate
            living = [e for e in enemies if e.hp > 0]
            if self.timers[kind] > 0 or not living:
                continue
            target = min(living,key=lambda e: math.hypot(e.x-player.x,e.y-player.y))
            angle = math.atan2(target.y-player.y,target.x-player.x)
            damage = 18+level*7
            cooldown = {"enter":0.95,"lan":1.3,"bug":1.8,"wifi":2.0,"recursion":1.5}[kind]
            self.timers[kind] = cooldown/(1+0.12*(level-1))
            if kind == "lan":
                reach,width = 105+level*20, 22+level*5
                for sweep in range(2 if level >= 4 else 1):
                    direction = angle+(0.28 if sweep else 0)
                    ux,uy = math.cos(direction),math.sin(direction)
                    for enemy in living:
                        dx,dy = enemy.x-player.x,enemy.y-player.y
                        along = max(0,min(reach,dx*ux+dy*uy))
                        if math.hypot(dx-along*ux,dy-along*uy) <= width/2+enemy.radius:
                            enemy.hp -= damage
                    self.effects.append(Effect(kind,player.x,player.y,reach,direction,width))
            elif kind == "wifi":
                radius = 85+level*20
                for enemy in living:
                    dx,dy = enemy.x-player.x,enemy.y-player.y
                    dist = math.hypot(dx,dy)
                    if dist <= radius+enemy.radius:
                        enemy.hp -= damage
                        push = 24+level*8
                        enemy.x += (dx/dist if dist else 1)*push
                        enemy.y += (dy/dist if dist else 0)*push
                self.effects.append(Effect(kind,player.x,player.y,radius))
            else:
                count = 1+(level-1)//2 if kind in ("enter","bug") else 1
                for i in range(count):
                    if len(self.projectiles) < MAX_PROJECTILES:
                        self.projectiles.append(Projectile(player.x,player.y,angle+(i-(count-1)/2)*0.13,damage,kind,level))
        additions = []
        for projectile in self.projectiles:
            projectile.update(dt,enemies,additions,self.effects)
        self.projectiles = [p for p in self.projectiles if p.life > 0]
        self.projectiles.extend(additions[:max(0,MAX_PROJECTILES-len(self.projectiles))])

    def draw(self, surface, player, cam_x, cam_y):
        for projectile in self.projectiles:
            projectile.draw(surface,cam_x,cam_y)
        for effect in self.effects:
            effect.draw(surface,cam_x,cam_y)
        for x,y in self.book_positions(player):
            center = (round(x-cam_x),round(y-cam_y))
            draw_item(surface, "book", center, 32)
