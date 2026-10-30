"""Hand control logic, tested with synthetic landmarks (no camera needed)."""
import math
import os
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame
from hand_control import DEAD_ZONE, HandController, is_fist, joystick, palm_center


def hand(cx, cy, folded=False, size=0.12):
    """21 landmarks of an upright hand centred near (cx, cy)."""
    pts = [(cx, cy + size)]                                   # 0 wrist
    pts += [(cx - size * 0.6, cy + size * (0.6 - i * 0.25)) for i in range(4)]   # 1-4 thumb
    for f, fx in enumerate((-0.3, -0.1, 0.1, 0.3)):             # index, middle, ring, little
        base = (cx + fx * size, cy)
        pts.append(base)                                       # MCP
        pts.append((base[0], cy - size * 0.35))                 # PIP (middle joint)
        if folded:
            pts.append((base[0], cy + size * 0.05))
            pts.append((base[0], cy + size * 0.15))             # tip curled back toward the wrist
        else:
            pts.append((base[0], cy - size * 0.6))
            pts.append((base[0], cy - size * 0.85))
    return pts


class HandLogicTests(unittest.TestCase):
    def test_landmark_count_and_palm(self):
        pts = hand(0.5, 0.5)
        self.assertEqual(len(pts), 21)
        px, py = palm_center(pts)
        self.assertAlmostEqual(px, 0.5, delta=0.03)

    def test_fist_and_open_hand(self):
        self.assertTrue(is_fist(hand(0.5, 0.5, folded=True)))
        self.assertFalse(is_fist(hand(0.5, 0.5)))

    def test_joystick_dead_zone_direction_and_speed(self):
        self.assertEqual(joystick((0.52, 0.5), (0.5, 0.5)), (0.0, 0.0))
        dx, dy = joystick((0.9, 0.5), (0.5, 0.5))
        self.assertAlmostEqual(dx, 1.0)
        self.assertAlmostEqual(dy, 0.0)
        slow = joystick((0.5 + DEAD_ZONE + 0.03, 0.5), (0.5, 0.5))
        self.assertTrue(0 < slow[0] < 0.5)                       # analog: small push = slow walk
        ux, uy = joystick((0.3, 0.3), (0.5, 0.5))
        self.assertLess(ux, 0)
        self.assertLess(uy, 0)                                  # up-left

    def test_controller_process_fist_lost_hand_and_recenter(self):
        hc = HandController()
        right = hand(0.8, 0.5)
        right_palm_y = palm_center(right)[1]
        hc.anchor = (0.5, right_palm_y)
        for _ in range(6):
            d = hc.process(right, 1.0)
        self.assertGreater(d[0], 0.5)
        self.assertAlmostEqual(d[1], 0.0, delta=0.05)
        self.assertEqual(hc.process(hand(0.8, 0.5, folded=True), 1.1), (0.0, 0.0))   # fist = stop
        hc.process(None, 1.2)
        self.assertEqual(hc.status, "tracking")                 # brief dropout tolerated
        hc.process(None, 2.0)
        self.assertEqual((hc.status, hc.direction), ("no hand", (0.0, 0.0)))
        hc.recenter()
        hc.process(right, 3.0)
        self.assertAlmostEqual(hc.anchor[0], palm_center(right)[0])

    def test_missing_model_reports_error_without_crashing(self):
        hc = HandController()
        import hand_control
        old = hand_control.MODEL_PATH
        hand_control.MODEL_PATH = "/nonexistent/hand.task"
        try:
            hc._running = True
            hc._run()
        finally:
            hand_control.MODEL_PATH = old
        self.assertEqual(hc.status, "error")


class GameHandIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from main import Game
        cls.game = Game()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_analog_input_moves_player_and_panel_renders(self):
        game = self.game
        game.reset_game()
        game.hand.status = "tracking"
        game.hand.direction = (0.5, 0.0)
        game.hand._last_seen = 1e12            # keep "tracking" during poll()
        game.hand.landmarks = hand(0.7, 0.5)
        x0 = game.player.x
        game.update(0.1)
        self.assertAlmostEqual(game.player.x - x0, game.player.move_speed * 0.5 * 0.1, places=3)
        game.render()
        game.hand.status = "off"


if __name__ == "__main__":
    unittest.main()
