"""AI data center, multipart combat and campaign progression (headless SDL)."""
import math
import os
import random
import unittest
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame

from ai_enemies import Hydra, AIShot, MAX_AI_SHOTS, fire_ring, update_ai
from main import Enemy, Game, Player, start_at_stage3
from stages import Stage2, Stage3
from weapons import Projectile, WEAPONS


class AIAttackTests(unittest.TestCase):
    def test_spawn_phases_and_density(self):
        stage = Stage3()
        self.assertLess(stage.spawn_interval, Stage2().spawn_interval)
        for time, roll, kind in [(0, 0.34, "ai_chatgpt"), (44, 0.35, "ai_claude"),
                                 (45, 0.24, "ai_chatgpt"), (45, 0.25, "ai_claude"),
                                 (104, 0.79, "ai_claude"), (45, 0.80, "ai_gemini"),
                                 (105, 0.19, "ai_chatgpt"), (105, 0.20, "ai_claude"),
                                 (180, 0.70, "ai_gemini")]:
            with self.subTest(time=time, roll=roll), patch("stages.stage3.random.random", return_value=roll):
                self.assertEqual(stage.get_enemy_spawn_type(time), kind)

    def test_chatgpt_single_shot_and_predictive_aim(self):
        enemy, player, shots = Enemy(0, 0, "ai_chatgpt"), Player(300, 0), []
        enemy.attack_timer = 0
        update_ai(enemy, player, 0, shots, (0, 150))
        self.assertEqual(len(shots), 1)
        self.assertTrue(all(s.kind == "token" and s.damage == 14 for s in shots))
        self.assertGreater(shots[0].vy, 0)
        start = (shots[0].x, shots[0].y)
        shots[0].update(0.5)
        self.assertAlmostEqual(math.hypot(shots[0].x - start[0], shots[0].y - start[1]), 75)
        for _ in range(34):
            update_ai(enemy, player, 0.1, shots)
        self.assertEqual(len(shots), 1)
        update_ai(enemy, player, 0.1, shots)
        self.assertEqual(len(shots), 2)

    def test_claude_warning_and_locked_lunge(self):
        enemy = Enemy(0, 0, "ai_claude")
        enemy.lunge_cooldown = 0
        update_ai(enemy, Player(100, 0), 0.01, [])
        self.assertEqual(enemy.lunge_state, "windup")
        for _ in range(3):
            update_ai(enemy, Player(0, 100), 0.1, [])
        self.assertEqual((enemy.x, enemy.y), (0, 0))
        for _ in range(3):
            update_ai(enemy, Player(0, 100), 0.1, [])
        self.assertGreater(enemy.x, 0)
        self.assertAlmostEqual(enemy.y, 0)

    def test_gemini_warns_before_ring(self):
        enemy, player, shots = Enemy(0, 0, "ai_gemini"), Player(280, 0), []
        enemy.attack_timer = 0
        update_ai(enemy, player, 0.01, shots)
        self.assertGreater(enemy.attack_windup, 0)
        for _ in range(5):
            update_ai(enemy, player, 0.1, shots)
        self.assertFalse(shots)
        update_ai(enemy, player, 0.1, shots)
        self.assertEqual(len(shots), 8)
        self.assertTrue(all(s.damage == 16 for s in shots))

    def test_cadence_matches_at_30_and_60_fps(self):
        for kind in ("ai_chatgpt", "ai_gemini"):
            counts = []
            for fps in (30, 60):
                random.seed(5)
                enemy, shots = Enemy(0, 0, kind), []
                enemy.attack_timer = 0
                for _ in range(12 * fps):
                    update_ai(enemy, Player(280, 0), 1 / fps, shots)
                counts.append(len(shots))
            self.assertEqual(counts[0], counts[1], kind)

    def test_shots_are_capped_and_have_finite_life(self):
        shots = []
        for _ in range(100):
            fire_ring(shots, 0, 0, 0)
        self.assertEqual(len(shots), MAX_AI_SHOTS)
        shot = AIShot(0, 0, 0, 16, "star", 190)
        self.assertTrue(shot.hits(Player(0, 0)))
        shot.update(4.1)
        self.assertLess(shot.life, 0)


class HydraCombatTests(unittest.TestCase):
    def test_every_weapon_damages_heads(self):
        for kind in WEAPONS:
            with self.subTest(weapon=kind):
                player, boss = Player(0, 0), Hydra(0, 47)
                player.weapons.levels = {kind: 5}
                for _ in range(180):
                    player.weapons.update(1 / 60, player, boss.living_heads)
                self.assertLess(boss.hp, boss.max_hp)

    def test_wifi_hits_all_heads_but_pushes_body_once(self):
        player, boss = Player(0, 0), Hydra(0, 47)
        player.weapons.levels = {"wifi": 5}
        player.weapons.update(0, player, boss.living_heads)
        self.assertEqual([h.hp for h in boss.heads], [1747] * 3)
        self.assertAlmostEqual(math.hypot(boss.x, boss.y - 47), 64)
        self.assertEqual([(h.x - boss.x, h.y - boss.y) for h in boss.heads],
                         [h.offset for h in boss.heads])

    def test_bug_slow_reaches_body_and_dead_heads_are_ignored(self):
        boss = Hydra(0, 47)
        boss.heads[0].hp = 0
        head = boss.heads[1]
        projectile = Projectile(head.x, head.y, 0, 40, "bug", 3)
        projectile.update(0, boss.living_heads, [], [])
        self.assertGreater(boss.slow_remaining, 0)
        self.assertEqual(boss.heads[0].hp, 0)
        self.assertLess(head.hp, head.max_hp)

    def test_piercing_hits_each_head_once(self):
        boss = Hydra(0, 47)
        shot = Projectile(-120, 0, 0, 40, "enter", 4)
        for _ in range(4):
            shot.update(0.1, boss.living_heads, [], [])
        self.assertEqual([h.hp for h in boss.heads], [1760, 1800, 1760])
        self.assertEqual(len(shot.hit), 2)

    def test_recursion_children_exclude_parent_hit_head(self):
        boss = Hydra(0, 47)
        head = boss.heads[0]
        shot = Projectile(head.x, head.y, 0, 40, "recursion", 4)
        children = []
        shot.update(0, boss.living_heads, children, [])
        self.assertEqual(len(children), 3)
        self.assertTrue(all(head in child.hit for child in children))

    def test_severing_active_head_cancels_attack_and_accelerates_rest(self):
        boss, player, shots = Hydra(0, 0), Player(300, 0), []
        brain = boss.brain
        brain.timer = 0
        brain.update(boss, player, 0, shots)
        self.assertEqual(brain.active_head.kind, "chatgpt")
        self.assertEqual(brain.state, "TELEGRAPH")
        boss.heads[0].hp = 0
        brain.update(boss, player, 0, shots)
        self.assertFalse(shots)
        self.assertEqual(brain.state, "CHASE")
        self.assertAlmostEqual(brain.timer, 1.8 * 0.85)
        boss.heads[1].hp = 0
        self.assertAlmostEqual(brain.rest(boss), 1.8 * 0.7)
        for _ in range(100):
            brain.update(boss, player, 0.05, shots)
        self.assertTrue(shots)
        self.assertTrue(all(shot.kind == "star" for shot in shots))

    def test_all_three_heads_attack_and_claude_dash_locks(self):
        boss, player, shots = Hydra(0, 0), Player(300, 0), []
        states = set()
        for _ in range(240):
            boss.brain.update(boss, player, 0.05, shots)
            states.add(boss.brain.state)
        self.assertEqual({s.kind for s in shots}, {"token", "star"})
        self.assertIn("CHARGE", states)
        brain = boss.brain
        brain.active_head = boss.heads[1]
        brain.state, brain.timer, brain.dash_angle = "CHARGE", 0.45, math.pi / 2
        x, y = boss.x, boss.y
        brain.update(boss, Player(999, 0), 0.1, [])
        self.assertAlmostEqual(boss.x, x)
        self.assertAlmostEqual(boss.y - y, brain.CHARGE_SPEED * 0.1)


class AIStageIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = Game()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        random.seed(11)
        self.game.demo_mode = False
        self.game.show_debug = False
        self.game.reset_game()

    def test_killing_the_stage2_boss_does_not_end_the_stage(self):
        game = self.game
        game.start_stage(1)
        game.player.hp = 40
        game.player.level, game.player.exp = 17, 9
        game.player.weapons.levels = {"enter": 5, "wifi": 4}
        player = game.player
        game.spawn_boss()
        game.boss.hp = 0
        game.update(0)
        self.assertIsInstance(game.current_stage, Stage2)   # no chaining to Stage 3
        self.assertIs(game.player, player)
        self.assertEqual((player.hp, player.level, player.exp), (40, 17, 9))   # no free heal
        self.assertEqual(player.weapons.levels, {"enter": 5, "wifi": 4})
        self.assertFalse(game.is_victory)
        game.elapsed_seconds = game.stage_start_seconds + game.current_stage.duration
        game.update(0)
        self.assertTrue(game.is_victory)

    def test_heads_are_targets_but_not_crowd_members(self):
        game = self.game
        game.start_stage(2)
        boss = game.add_enemy("ai_hydra", 0, 0)
        mob = game.add_enemy("ai_claude", 200, 0)
        self.assertEqual(len(game.enemies), 2)
        self.assertEqual(len(game.combat_targets()), 4)
        self.assertNotIn(boss, game.combat_targets())
        boss.heads[1].hp = 0
        self.assertNotIn(boss.heads[1], game.combat_targets())
        self.assertIn(mob, game.combat_targets())
        # With no nearby mob, the ordinary auto-aim chooses the closest live head.
        game.enemies.remove(mob)
        game.player.x, game.player.y = -150, -47
        game.player.weapons.update(0, game.player, game.combat_targets())
        shot = game.player.weapons.projectiles[0]
        self.assertAlmostEqual(shot.angle, 0)

    def test_boss_once_partial_kills_one_loot_drop_then_victory_on_time(self):
        game = self.game
        game.start_stage(2)
        game.demo_mode = True
        game.elapsed_seconds = game.stage_start_seconds + Stage3.BOSS_TIME
        game.update(0)
        boss = game.boss
        game.update(0)
        self.assertEqual(sum(e.is_boss for e in game.enemies), 1)
        for head in boss.heads[:2]:
            head.hp = 0
            game.update(0)
            self.assertFalse(game.is_victory)
            self.assertEqual(game.kill_count, 0)
            self.assertFalse(game.supplies.foods)
        boss.heads[2].hp = 0
        game.update(0)
        self.assertFalse(game.is_victory)          # boss dead, but the stage timer is not up
        self.assertEqual(game.kill_count, 1)
        self.assertEqual(len(game.supplies.foods), 1)
        self.assertNotIn(boss, game.enemies)
        game.elapsed_seconds = game.stage_start_seconds + game.current_stage.duration
        game.update(0)
        self.assertTrue(game.is_victory)
        game.update(1)
        self.assertEqual(game.kill_count, 1)
        game.render()

    def test_pause_freezes_attacks_and_restart_clears_hydra(self):
        game = self.game
        start_at_stage3(game)
        self.assertEqual(game.player.level, 20)
        self.assertEqual(game.player.weapons.levels, {"enter": 5, "book": 5, "lan": 5})
        game.spawn_boss()
        boss = game.boss
        shot = AIShot(0, 0, 0, 14, "token", 260)
        game.enemy_shots.append(shot)
        before = (game.elapsed_seconds, boss.brain.timer, shot.x, shot.life)
        game.is_level_up = True
        game.update(0.1)
        self.assertEqual(before, (game.elapsed_seconds, boss.brain.timer, shot.x, shot.life))
        game.reset_game()
        self.assertEqual(game.stage_index, 0)
        self.assertIsNone(game.boss)
        self.assertFalse(game.enemy_shots)

    def test_art_scenery_and_boss_render_with_severed_heads(self):
        game = self.game
        game.start_stage(2)
        self.assertIsNotNone(game.stage_tile())
        for kind in ("ai_chatgpt", "ai_claude", "ai_gemini", "ai_hydra"):
            self.assertIsNotNone(game.enemy_sprites[kind], kind)
        self.assertTrue(all(game.hydra_head_sprites.values()))
        self.assertTrue(game.obstacles.rects)
        self.assertTrue(all(math.hypot(r.centerx, r.centery) > 150 for r in game.obstacles.rects))
        layout = sorted((p.kind, p.x, p.y) for p in game.scenery.props())
        game.start_stage(2)
        self.assertEqual(layout, sorted((p.kind, p.x, p.y) for p in game.scenery.props()))
        game.spawn_boss()
        game.boss.heads[0].hp = 0
        game.boss.brain.active_head = game.boss.heads[1]
        game.boss.brain.state = "TELEGRAPH"
        game.show_debug = True
        game.render()
        game.show_debug = False

    def test_full_stage_smoke_with_obstacles_and_enemy_cap(self):
        game = self.game
        start_at_stage3(game)
        game.demo_mode = True
        for frame in range(1850):
            game.update(0.1)
            while game.is_level_up:
                game.apply_upgrade(game.current_upgrades[0])
            if frame % 300 == 0:
                game.render()
        self.assertTrue(game.boss_spawned)
        self.assertLessEqual(len(game.enemies), 121)  # regular cap + the boss
        self.assertLessEqual(len(game.enemy_shots), MAX_AI_SHOTS)
        self.assertTrue(all(e.enemy_type.startswith("ai_") for e in game.enemies))
        for enemy in game.enemies:
            for rect in game.obstacles.nearby(enemy.x, enemy.y, 0):
                self.assertFalse(rect.inflate(-2, -2).collidepoint(enemy.x, enemy.y))


if __name__ == "__main__":
    unittest.main()
