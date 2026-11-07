"""Every stage lasts 20 minutes, then the stage is won (boss permitting).

Run without opening a window: python -m unittest discover -s tests -v
"""
import os
import random
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame

from main import Game
from stages import STAGES
from stages.base_stage import STAGE_DURATION_SECONDS


def kill_boss(game):
    heads = getattr(game.boss, "heads", None)
    if heads:                       # the hydra dies when all its heads do
        for head in heads:
            head.hp = 0
    else:
        game.boss.hp = 0


class StageDurationTests(unittest.TestCase):
    def setUp(self):
        random.seed(5)
        self.game = Game()
        self.game.player.hp = self.game.player.max_hp = 10 ** 6

    def tearDown(self):
        pygame.quit()

    def enter(self, index, boss_defeated=True):
        game = self.game
        game.reset_game()               # fresh run: clears victory/game-over from a previous case
        game.player.hp = game.player.max_hp = 10 ** 6
        game.start_stage(index)
        if boss_defeated and game.current_stage.boss_type:
            game.spawn_boss()
            kill_boss(game)
            game.update(0)          # resolve the kill
        return game

    def test_every_stage_lasts_twenty_minutes(self):
        self.assertEqual(STAGE_DURATION_SECONDS, 20 * 60)
        for stage_class in STAGES:
            self.assertEqual(stage_class().duration, 1200, stage_class.__name__)

    def test_bosses_appear_before_the_stage_ends(self):
        for stage_class in STAGES:
            stage = stage_class()
            if stage.boss_type:
                self.assertLess(stage.boss_time, stage.duration, stage_class.__name__)

    def test_each_stage_has_its_own_victory_text(self):
        texts = [stage_class().victory_text for stage_class in STAGES]
        self.assertEqual(len(set(texts)), len(STAGES))
        self.assertFalse(any("ALL STAGES" in text for text in texts))

    def test_not_won_before_time_is_up(self):
        for index in range(len(STAGES)):
            with self.subTest(stage=index + 1):
                game = self.enter(index)
                game.elapsed_seconds = game.stage_start_seconds + game.current_stage.duration - 1
                game.update(0.1)
                self.assertFalse(game.is_victory)

    def test_won_when_time_is_up_and_does_not_chain(self):
        for index in range(len(STAGES)):
            with self.subTest(stage=index + 1):
                game = self.enter(index)
                player = game.player
                game.elapsed_seconds = game.stage_start_seconds + game.current_stage.duration - 0.05
                game.update(0.1)
                self.assertTrue(game.is_victory)
                self.assertEqual(game.stage_index, index)       # stays on the cleared stage
                self.assertIs(game.player, player)

    def test_time_is_measured_from_when_the_stage_began(self):
        game = self.game
        game.elapsed_seconds = 5000.0           # a long session before this stage
        game.start_stage(0)
        game.update(0.1)
        self.assertFalse(game.is_victory)
        game.elapsed_seconds = game.stage_start_seconds + game.current_stage.duration - 0.05
        game.update(0.1)
        self.assertTrue(game.is_victory)

    def test_a_living_boss_delays_the_win_until_it_dies(self):
        for index in (1, 2):                    # Stage 2 and Stage 3 have bosses
            with self.subTest(stage=index + 1):
                game = self.enter(index, boss_defeated=False)
                game.elapsed_seconds = game.stage_start_seconds + game.current_stage.duration - 0.05
                game.update(0.1)                # time is up; the boss spawns now
                game.update(0.1)
                self.assertTrue(game.boss_spawned)
                self.assertFalse(game.is_victory)
                kill_boss(game)
                game.update(0.1)
                self.assertTrue(game.is_victory)

    def test_victory_screen_and_hud_show_the_stage_length(self):
        game = self.enter(0)
        game.render()                           # HUD with "TIME: 00:00 / 20:00"
        game.is_victory = True
        game.render()


if __name__ == "__main__":
    unittest.main()
