"""In-game interface drawn over the world: HUD bars, boss health, banners and level-up cards."""
import pygame

from settings import (SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_WHITE, COLOR_HP_GREEN, COLOR_EXP,
                      COLOR_GOLD, COLOR_CARD_BG, COLOR_CARD_BORDER)
from entities import draw_coffee
from weapons import WEAPONS, draw_icon
from ai_enemies import AI_COLORS, Hydra


class HudMixin:
    """HUD and level-up drawing for Game."""

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
        total = self.current_stage.duration
        time_txt = self.font.render(f"TIME: {mins:02d}:{secs:02d} / {total // 60:02d}:{total % 60:02d}",
                                    True, COLOR_WHITE)
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
        if isinstance(self.boss, Hydra):
            self.draw_hydra_bars()
            return
        w, h, y = 520, 16, SCREEN_HEIGHT - 46
        x = SCREEN_WIDTH // 2 - w // 2
        ratio = max(0, self.boss.hp / self.boss.max_hp)
        pygame.draw.rect(self.screen, (20, 20, 30), (x - 3, y - 3, w + 6, h + 6), border_radius=4)
        pygame.draw.rect(self.screen, (70, 25, 30), (x, y, w, h))
        pygame.draw.rect(self.screen, (60, 190, 100), (x, y, int(w * ratio), h))
        label = self.small_font.render(self.current_stage.boss_name, True, COLOR_GOLD)
        box = pygame.Rect(0, 0, label.get_width() + 16, label.get_height() + 6)
        box.midbottom = (SCREEN_WIDTH // 2, y - 4)
        pygame.draw.rect(self.screen, (20, 20, 30), box, border_radius=4)
        self.screen.blit(label, (box.x + 8, box.y + 3))

    def draw_hydra_bars(self):
        width, gap, y = 176, 10, SCREEN_HEIGHT - 42
        start = (SCREEN_WIDTH - (3 * width + 2 * gap)) // 2
        label = self.small_font.render(self.current_stage.boss_name, True, COLOR_GOLD)
        label_rect = label.get_rect(midbottom=(SCREEN_WIDTH // 2, y - 25))
        pygame.draw.rect(self.screen, (15, 20, 35), label_rect.inflate(14, 6), border_radius=4)
        self.screen.blit(label, label_rect)
        for index, head in enumerate(self.boss.heads):
            x = start + index * (width + gap)
            pygame.draw.rect(self.screen, (15, 20, 35), (x - 3, y - 22, width + 6, 43), border_radius=4)
            pygame.draw.rect(self.screen, (65, 30, 45), (x, y, width, 15))
            pygame.draw.rect(self.screen, AI_COLORS[head.kind],
                             (x, y, round(width * max(0, head.hp) / head.max_hp), 15))
            name = {"chatgpt": "ChatGPT", "claude": "Claude", "gemini": "Gemini"}[head.kind]
            status = f"{name} {max(0, round(head.hp))}/{head.max_hp}" if head.hp > 0 else name + " DESTROYED"
            text = self.small_font.render(status, True, AI_COLORS[head.kind] if head.hp > 0 else (155, 155, 170))
            self.screen.blit(text, (x + 3, y - 18))

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
            is_hover = rect.collidepoint(mouse_pos) or idx == self.hand_pick_index

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
                self.draw_passive_icon(upg["id"], rect.centerx, rect.y + 100)

            desc_surf = self.font.render(upg["desc"], True, COLOR_HP_GREEN)
            self.screen.blit(desc_surf, (rect.centerx - desc_surf.get_width() // 2, rect.y + 162))

            if idx == self.hand_pick_index:
                self.draw_hand_hold_bar(rect, self.HAND_PICK_SECONDS)
            self.draw_wrapped_text(
                text=upg["detail"],
                font=self.small_font,
                color=(200, 200, 210),
                max_width=200,
                start_x=rect.centerx,
                start_y=rect.y + 208,
                line_spacing=18
            )

    def draw_passive_icon(self, card_id, cx, cy):
        if card_id == "vitality":        # red heart
            pygame.draw.circle(self.screen, (220, 60, 70), (cx - 9, cy - 6), 11)
            pygame.draw.circle(self.screen, (220, 60, 70), (cx + 9, cy - 6), 11)
            pygame.draw.polygon(self.screen, (220, 60, 70), [(cx - 20, cy - 2), (cx + 20, cy - 2), (cx, cy + 20)])
        elif card_id == "sneakers":      # shoe with speed lines
            pygame.draw.rect(self.screen, (80, 150, 230), (cx - 14, cy - 12, 14, 18), border_radius=4)
            pygame.draw.rect(self.screen, (80, 150, 230), (cx - 14, cy, 32, 10), border_radius=5)
            pygame.draw.rect(self.screen, COLOR_WHITE, (cx - 14, cy + 8, 32, 4))
            for i in range(3):
                pygame.draw.line(self.screen, (200, 200, 210), (cx - 30, cy - 8 + i * 7), (cx - 20, cy - 8 + i * 7), 2)
        elif card_id == "magnet":        # horseshoe magnet
            pygame.draw.arc(self.screen, (210, 50, 50), (cx - 18, cy - 16, 36, 36), 3.14, 6.28, 9)
            pygame.draw.rect(self.screen, (210, 50, 50), (cx - 18, cy - 20, 9, 22))
            pygame.draw.rect(self.screen, (210, 50, 50), (cx + 9, cy - 20, 9, 22))
            pygame.draw.rect(self.screen, (220, 220, 230), (cx - 18, cy - 26, 9, 7))
            pygame.draw.rect(self.screen, (220, 220, 230), (cx + 9, cy - 26, 9, 7))
        else:                            # green plus (Study Break)
            pygame.draw.line(self.screen, COLOR_HP_GREEN, (cx - 15, cy), (cx + 15, cy), 7)
            pygame.draw.line(self.screen, COLOR_HP_GREEN, (cx, cy - 15), (cx, cy + 15), 7)
