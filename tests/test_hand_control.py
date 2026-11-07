"""Hand control logic, tested with synthetic landmarks (no camera needed)."""
import math
import os
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame
from hand_control import HandController, gesture, is_fist, pointing_direction


def hand(cx=0.5, cy=0.5, extended=(False, False, False, False), size=0.12, angle=-math.pi / 2):
    """21 landmarks. `extended` = (index, middle, ring, little).

    Fingers grow from the knuckles along `angle` (default: straight up).
    Folded fingers curl their tips back toward the wrist.
    """
    ux, uy = math.cos(angle), math.sin(angle)        # finger direction
    px, py = -uy, ux                                # across the palm
    wrist = (cx - ux * size, cy - uy * size)
    pts = [wrist]
    pts += [(cx + px * size * 0.6 - ux * size * (0.6 - i * 0.2), cy + py * size * 0.6 - uy * size * (0.6 - i * 0.2))
            for i in range(4)]                       # thumb 1-4
    for f, offset in enumerate((-0.3, -0.1, 0.1, 0.3)):
        bx, by = cx + px * offset * size, cy + py * offset * size
        pts.append((bx, by))                                     # knuckle
        pts.append((bx + ux * size * 0.35, by + uy * size * 0.35))   # middle joint
        if extended[f]:
            pts.append((bx + ux * size * 0.6, by + uy * size * 0.6))
            pts.append((bx + ux * size * 0.85, by + uy * size * 0.85))
        else:
            pts.append((bx - ux * size * 0.05, by - uy * size * 0.05))
            pts.append((bx - ux * size * 0.15, by - uy * size * 0.15))
    return pts


POINT = (True, False, False, False)
OPEN = (True, True, True, True)


class GestureTests(unittest.TestCase):
    def test_gestures(self):
        self.assertEqual(len(hand()), 21)
        self.assertEqual(gesture(hand(extended=POINT)), "point")
        self.assertEqual(gesture(hand()), "fist")
        self.assertTrue(is_fist(hand()))
        self.assertEqual(gesture(hand(extended=OPEN)), "open")

    def test_pointing_direction_follows_the_finger(self):
        for angle, expected in ((-math.pi / 2, (0, -1)), (0.0, (1, 0)), (math.pi, (-1, 0)),
                                (math.pi / 2, (0, 1)), (-math.pi / 4, (0.707, -0.707))):
            with self.subTest(angle=angle):
                dx, dy = pointing_direction(hand(extended=POINT, angle=angle))
                self.assertAlmostEqual(dx, expected[0], delta=0.02)
                self.assertAlmostEqual(dy, expected[1], delta=0.02)

    def test_finger_pointing_at_camera_does_not_move(self):
        pts = hand(extended=POINT)
        bx, by = pts[5]
        pts[8] = (bx + 0.005, by - 0.01)              # tip right in front of the knuckle
        self.assertIsNone(pointing_direction(pts))


class ControllerTests(unittest.TestCase):
    def test_point_moves_fist_and_open_stop_lost_hand_stops(self):
        hc = HandController()
        for _ in range(4):
            d = hc.process(hand(extended=POINT, angle=0.0), 1.0)
        self.assertAlmostEqual(d[0], 1.0, delta=0.02)
        self.assertEqual(hc.process(hand(), 1.1), (0.0, 0.0))                 # fist
        self.assertTrue(hc.fist)
        self.assertEqual(hc.process(hand(extended=OPEN), 1.2), (0.0, 0.0))    # open hand
        hc.process(hand(extended=POINT, angle=math.pi / 2), 1.3)
        hc.process(None, 1.4)
        self.assertEqual(hc.status, "tracking")                               # brief dropout tolerated
        hc.process(None, 2.0)
        self.assertEqual((hc.status, hc.direction), ("no hand", (0.0, 0.0)))

    def test_smoothing_turns_gradually(self):
        hc = HandController()
        hc.process(hand(extended=POINT, angle=0.0), 1.0)
        dx, dy = hc.process(hand(extended=POINT, angle=math.pi / 2), 1.03)
        self.assertGreater(dx, 0.3)
        self.assertGreater(dy, 0.3)                                           # half-way between right and down
        self.assertAlmostEqual(math.hypot(dx, dy), 1.0, places=5)

    def test_missing_model_reports_error_without_crashing(self):
        import hand_control
        hc = HandController()
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

    def setUp(self):
        self.game.reset_game()
        self.game.hand._last_seen = 1e12        # keep "tracking" during poll()

    def tearDown(self):
        self.game.hand.status = "off"

    def track(self, landmarks):
        self.game.hand.status = "tracking"
        self.game.hand.process(landmarks, 1e12)

    def test_pointing_moves_player_and_panel_renders(self):
        game = self.game
        self.track(hand(extended=POINT, angle=0.0))
        x0 = game.player.x
        game.update(0.1)
        self.assertAlmostEqual(game.player.x - x0, game.player.move_speed * 0.1, delta=0.5)
        game.render()

    def test_point_at_card_then_hold_fist_to_pick(self):
        game = self.game
        game.player.add_exp(20)
        game.trigger_level_up()
        pending = game.player.pending_level_ups
        self.track(hand(cx=0.85, extended=POINT))          # fingertip on the right third
        game.update_hand_menus(0.1)
        self.assertEqual(game.hand_pick_index, len(game.current_upgrades) - 1)
        game.render()
        self.track(hand(cx=0.85))                           # fist
        game.update_hand_menus(0.3)
        self.assertEqual(game.player.pending_level_ups, pending)   # not yet: hold longer
        game.update_hand_menus(0.4)
        self.assertEqual(game.player.pending_level_ups, pending - 1)
        game.update_hand_menus(1.0)                         # still a fist: no second pick
        self.assertEqual(game.player.pending_level_ups, pending - 1)

    def test_hold_fist_to_restart_after_game_over(self):
        game = self.game
        game.is_game_over = True
        game.kill_count = 9
        self.track(hand())
        game.update_hand_menus(0.6)
        self.assertTrue(game.is_game_over)
        game.render()
        game.update_hand_menus(0.7)
        self.assertFalse(game.is_game_over)
        self.assertEqual(game.kill_count, 0)


if __name__ == "__main__":
    unittest.main()
