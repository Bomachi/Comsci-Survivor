"""Hand-control interface: gesture handling on paused screens and the camera preview panel."""
import pygame

from settings import SCREEN_HEIGHT, COLOR_WHITE, COLOR_GOLD
from ui import GameState


class HandMenuMixin:
    """Hand gestures for menus, and the camera preview, for Game."""

    HAND_PICK_SECONDS = 0.6
    HAND_RESTART_SECONDS = 1.2

    def update_hand_menus(self, dt):
        """Hand gestures for screens that pause gameplay.

        Level-up: move the hand left/middle/right to point at a card, hold a fist
        to choose it. Game over / victory: hold a fist to restart.
        """
        hand = self.hand
        if self.state != GameState.PLAYING or hand.status != "tracking" or not hand.landmarks:
            self.hand_pick_index, self.hand_hold = None, 0.0
            return
        if not hand.fist:
            self.hand_hold, self.hand_armed = 0.0, True
        if self.is_level_up and self.current_upgrades:
            count = len(self.current_upgrades)
            x = hand.landmarks[8][0]          # index fingertip
            if not hand.fist:   # pointing chooses the card; the fist only confirms
                self.hand_pick_index = max(0, min(count - 1, int(x * count)))
            if hand.fist and self.hand_armed and self.hand_pick_index is not None:
                self.hand_hold += dt
                if self.hand_hold >= self.HAND_PICK_SECONDS:
                    self.hand_hold, self.hand_armed = 0.0, False
                    self.apply_upgrade(self.current_upgrades[min(self.hand_pick_index, count - 1)])
        elif self.is_game_over or self.is_victory:
            self.hand_pick_index = None
            if hand.fist and self.hand_armed:
                self.hand_hold += dt
                if self.hand_hold >= self.HAND_RESTART_SECONDS:
                    self.hand_hold, self.hand_armed = 0.0, False
                    self.reset_game()
        else:
            self.hand_pick_index, self.hand_hold = None, 0.0

    def draw_hand_panel(self):
        """Camera preview with hand landmarks and the pointing arrow."""
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
            if dx or dy:
                tip = pts[8]
                pygame.draw.line(self.screen, COLOR_GOLD, tip, (tip[0] + dx * 45, tip[1] + dy * 45), 4)
                pygame.draw.circle(self.screen, COLOR_GOLD, (tip[0] + dx * 45, tip[1] + dy * 45), 5)
        tracking_label = {"point": "HAND: pointing - walk", "fist": "HAND: fist - stop",
                          "open": "HAND: point a finger to walk"}.get(hand.gesture, "HAND: tracking")
        label = {"loading": "HAND: loading...", "tracking": tracking_label,
                 "no hand": "HAND: show your hand", "error": "HAND: " + hand.error}.get(hand.status, hand.status)
        colour = (255, 120, 120) if hand.status == "error" else COLOR_WHITE
        self.screen.blit(self.small_font.render(label[:34], True, colour), (x, y + h + 4))
        fps = self.small_font.render(f"{hand.fps:.0f} fps  [F7] camera off", True, (170, 170, 185))
        self.screen.blit(fps, (x, y + h + 18))

    def draw_hand_hold_bar(self, rect, seconds):
        if self.hand_hold <= 0:
            return
        ratio = min(1.0, self.hand_hold / seconds)
        bar = pygame.Rect(rect.x + 20, rect.bottom + 12, rect.width - 40, 10)
        pygame.draw.rect(self.screen, (30, 30, 45), bar, border_radius=4)
        pygame.draw.rect(self.screen, COLOR_GOLD, (bar.x, bar.y, int(bar.width * ratio), bar.height), border_radius=4)
