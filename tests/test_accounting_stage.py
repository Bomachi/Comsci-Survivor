"""Stage 2 (Accounting Faculty) tests. Run: python -m unittest discover -s tests -v"""
import math
import os
import random
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame
from accounting import BossBrain, EnemyShot
from main import Enemy, Game, Player
from stages import Stage2


class AccountingStageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = Game()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        random.seed(3)
        self.game.reset_game()

    def advance(self, seconds, step=0.1):
        for _ in range(int(seconds / step)):
            self.game.update(step)
            if self.game.is_level_up:
                self.game.apply_upgrade(self.game.current_upgrades[0])

    def test_stage1_clear_moves_to_stage2_and_keeps_player(self):
        game = self.game
        game.player.hp = game.player.max_hp = 10 ** 6
        game.player.weapons.levels = {"enter": 3}
        player = game.player
        game.elapsed_seconds = game.current_stage.target_time - 0.05
        game.update(0.1)
        self.assertIsInstance(game.current_stage, Stage2)
        self.assertIs(game.player, player)
        self.assertEqual(game.player.weapons.levels["enter"], 3)
        self.assertFalse(game.player.weapons.projectiles)
        self.assertEqual(game.stage_seconds, 0)

    def test_stage2_spawns_only_accounting_enemies(self):
        stage = Stage2()
        for t in (0, 44, 45, 99, 100, 149):
            for _ in range(30):
                self.assertTrue(stage.get_enemy_spawn_type(t).startswith("acc_"))
        self.assertEqual({stage.get_enemy_spawn_type(0) for _ in range(30)}, {"acc_freshman"})

    def test_calculator_keeps_distance_and_shot_hurts_player(self):
        game = self.game
        game.start_stage(1)
        game.player.hp = 100
        thrower = game.add_enemy("acc_calculator", 100, 0)
        thrower.update(0, 0, 0.5)
        self.assertGreater(thrower.x, 100)          # backed away
        game.enemy_shots.append(EnemyShot(30, 0, math.pi, 12))
        game.update(0.1)
        self.assertEqual(game.player.hp, 88)
        self.assertGreater(game.player.hurt_remaining, 0)

    def test_boss_spawns_once_attacks_and_victory(self):
        game = self.game
        game.start_stage(1)
        game.player.hp = game.player.max_hp = 10 ** 6
        game.elapsed_seconds = game.stage_start_seconds + Stage2.BOSS_TIME - 0.05
        game.update(0.1)
        boss = game.boss
        self.assertIsNotNone(boss)
        self.assertTrue(boss.is_boss)
        self.assertEqual(sum(e.is_boss for e in game.enemies), 1)
        game.update(0.1)
        self.assertEqual(sum(e.is_boss for e in game.enemies), 1)

        brain_test = BossBrain()
        shots, summoned = [], []
        far_boss = Enemy(0, 0, "acc_boss")
        target = Player(300, 0)
        visited = []
        for _ in range(int(20 / 0.05)):
            brain_test.update(far_boss, target, 0.05, shots, lambda *args: summoned.append(args))
            if not visited or visited[-1] != brain_test.state:
                visited.append(brain_test.state)
        # The FSM visits every state in the documented order.
        self.assertEqual(visited[:9], ["CHASE", "AUDIT", "CHASE", "AIM", "CHARGE", "RECOVER",
                                       "CHASE", "SUMMON", "CHASE"])
        self.assertEqual(len([s for s in shots if s.kind == "coin"]) % 12, 0)
        self.assertGreater(len(shots), 0)
        self.assertGreaterEqual(len(summoned), 4)

        boss.hp = 0
        game.update(0.1)
        self.assertTrue(game.is_victory)
        self.assertNotIn(boss, game.enemies)
        game.update(0.1)                             # frozen after victory
        game.render()

    def test_stage2_full_run_smoke(self):
        game = self.game
        game.player.hp = game.player.max_hp = 10 ** 6
        game.player.weapons.levels = {"enter": 5, "book": 5, "lan": 5}
        game.start_stage(1)
        for frame in range(int((Stage2.BOSS_TIME + 5) / 0.1)):
            self.advance(0.1)
            if frame % 100 == 0:
                game.render()
        self.assertTrue(game.boss_spawned)
        self.assertTrue(any(e.enemy_type == "acc_calculator" for e in game.enemies) or game.kill_count > 0)
        game.render()

    def test_sprites_and_tile_load(self):
        for kind in ("acc_freshman", "acc_calculator", "acc_senior", "acc_boss"):
            self.assertIsNotNone(self.game.enemy_sprites[kind], kind)
        self.game.start_stage(1)
        self.assertIsNotNone(self.game.stage_tile())


if __name__ == "__main__":
    unittest.main()


class BossBrainTests(unittest.TestCase):
    def test_charge_moves_along_locked_direction_and_enrage_speeds_up(self):
        boss, player = Enemy(0, 0, "acc_boss"), Player(0, 300)
        brain = BossBrain()
        brain.enter("AIM", boss, player)
        self.assertAlmostEqual(brain.dash_angle, math.pi / 2)
        brain.enter("CHARGE", boss, player)
        brain.update(boss, Player(500, 0), 0.1, [], lambda *a: None)
        self.assertAlmostEqual(boss.x, 0, places=5)
        self.assertAlmostEqual(boss.y, BossBrain.CHARGE_SPEED * 0.1)
        normal = brain.duration("CHASE", boss)
        boss.hp = boss.max_hp // 3
        self.assertLess(brain.duration("CHASE", boss), normal)
        brain.enter("AUDIT", boss, player)
        shots = []
        brain.update(boss, player, 1.0, shots, lambda *a: None)
        self.assertEqual(len(shots), 16)
        self.assertEqual(brain.state, "CHASE")
