"""Debug overlay (F3): spatial-hash grid, hit circles, flow field and performance numbers."""
import pygame

from settings import SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_WHITE, COLOR_GOLD
from ai_enemies import AI_COLORS, Hydra
from spatial import CELL_SIZE


class DebugMixin:
    """Debug drawing for Game."""

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
                if isinstance(e, Hydra):
                    for head in e.living_heads:
                        pygame.draw.circle(overlay, (*AI_COLORS[head.kind], 210),
                                           (head.x - self.camera_x, head.y - self.camera_y), head.radius, 2)
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
            ("[F5] spawn 300 enemies   [F4] invincible: " + ("ON" if self.demo_mode else "off"),
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
