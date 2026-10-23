"""Supply crate timing, map persistence, healing and game integration."""
import os
import unittest
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame
from main import Enemy, Game, Player
from supplies import Food, Supplies


class SupplyTests(unittest.TestCase):
    def test_five_continuous_seconds_at_30_and_60_fps(self):
        for fps in (30, 60):
            with self.subTest(fps=fps):
                supplies, player = Supplies(7), Player(140, 0)
                for _ in range(fps * 5 - 1):
                    supplies.update(1 / fps, player, False)
                self.assertFalse(supplies.foods)
                supplies.update(1 / fps, player, False)
                self.assertEqual(len(supplies.foods), 1)
                self.assertNotIn((0, 0), supplies.crates)
                supplies.update(1 / fps, player, False)
                self.assertEqual(len(supplies.foods), 1)

    def test_movement_and_leaving_reset_opening(self):
        supplies, player = Supplies(7), Player(140, 0)
        supplies.update(3, player, False)
        supplies.update(0.1, player, True)
        self.assertEqual(supplies.crates[(0, 0)].progress, 0)
        supplies.update(3, player, False)
        player.x = 300
        supplies.update(0.1, player, False)
        self.assertEqual(supplies.crates[(0, 0)].progress, 0)
        player.x = 140
        supplies.update(2, player, False)
        self.assertFalse(supplies.foods)

    def test_healing_cap_full_health_and_distance(self):
        supplies, player = Supplies(7), Player(0, 0)
        supplies.foods = [Food(0, 0)]
        supplies.update(0.1, player, False)
        self.assertEqual(len(supplies.foods), 1)
        player.hp = 40
        player.x = 100
        supplies.update(0.1, player, False)
        self.assertEqual(player.hp, 40)
        player.x = 0
        supplies.update(0.1, player, False)
        self.assertEqual(player.hp, 70)
        self.assertFalse(supplies.foods)
        supplies.foods = [Food(0, 0)]
        player.hp = 90
        supplies.update(0.1, player, False)
        self.assertEqual(player.hp, 100)
        self.assertFalse(supplies.foods)

    def test_exploration_preserves_positions_and_consumed_crates(self):
        supplies, player = Supplies(7), Player(140, 0)
        supplies.populate(0, 0)
        original = (supplies.crates[(-1, -1)].x, supplies.crates[(-1, -1)].y)
        supplies.update(5, player, False)
        supplies.populate(-10000, 10000)
        self.assertLessEqual(len(supplies.crates), 25)
        supplies.populate(0, 0)
        self.assertNotIn((0, 0), supplies.crates)
        self.assertEqual((supplies.crates[(-1, -1)].x, supplies.crates[(-1, -1)].y), original)


class SupplyIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = Game()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.game.reset_game()
        self.game.player.x = 140

    def test_pause_damage_and_reset(self):
        game = self.game
        game.supplies.crates[(0, 0)].progress = 2
        game.is_level_up = True
        game.update(0.1)
        self.assertEqual(game.supplies.crates[(0, 0)].progress, 2)
        game.is_level_up = False
        game.enemies = [Enemy(140, 0)]
        game.player.weapons.levels = {}
        game.update(0.1)
        self.assertEqual(game.player.hp, 92)
        self.assertAlmostEqual(game.supplies.crates[(0, 0)].progress, 2.1)
        with patch.object(Player, "handle_input", lambda player, dt: setattr(player, "x", player.x + 1)):
            game.update(0.1)
        self.assertEqual(game.supplies.crates[(0, 0)].progress, 0)
        game.supplies.foods = [Food(500, 0)]
        game.supplies.opened_cells.add((0, 0))
        game.reset_game()
        self.assertFalse(game.supplies.foods)
        self.assertFalse(game.supplies.opened_cells)
        self.assertEqual(game.supplies.crates[(0, 0)].progress, 0)

    def test_cannot_open_or_heal_after_death(self):
        game = self.game
        game.player.hp = 1
        game.player.weapons.levels = {}
        game.enemies = [Enemy(140, 0)]
        game.supplies.crates[(0, 0)].progress = 4.95
        game.supplies.foods = [Food(140, 0)]
        game.update(0.1)
        self.assertTrue(game.is_game_over)
        self.assertEqual(game.player.hp, 0)
        self.assertEqual(game.supplies.crates[(0, 0)].progress, 4.95)
        self.assertEqual(len(game.supplies.foods), 1)

    def test_render_supplied_food_and_opening_bar(self):
        game = self.game
        game.supplies.crates[(0, 0)].progress = 2.5
        game.supplies.foods = [Food(220, 0)]
        game.render()


if __name__ == "__main__":
    unittest.main()
