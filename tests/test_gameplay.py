"""Run without opening a window: python -m unittest discover -s tests -v."""
import math
import os
import random
import unittest
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame
from main import Coffee, Enemy, Game, Gem, Player
from upgrades import apply_upgrade, available_upgrades
from weapons import MAX_LEVEL, MAX_PROJECTILES, Projectile, WEAPONS


class WeaponTests(unittest.TestCase):
    def test_loadout_limit_and_maxed_fallback(self):
        player = Player(0, 0)
        self.assertEqual(len(available_upgrades(player)), 6)
        self.assertTrue(player.weapons.upgrade("book"))
        self.assertTrue(player.weapons.upgrade("wifi"))
        self.assertFalse(player.weapons.upgrade("bug"))
        self.assertEqual({c["id"] for c in available_upgrades(player)}, {"enter", "book", "wifi"})
        for kind in player.weapons.levels:
            while player.weapons.upgrade(kind):
                pass
            self.assertEqual(player.weapons.levels[kind], MAX_LEVEL)
        cards = available_upgrades(player)
        self.assertEqual([c["id"] for c in cards], ["recovery"])
        player.hp = 90
        self.assertTrue(apply_upgrade(player, cards[0]))
        self.assertEqual(player.hp, 100)

    def test_all_weapons_damage_enemies(self):
        for kind in WEAPONS:
            with self.subTest(kind=kind):
                player = Player(0, 0)
                player.weapons.levels = {kind: 1}
                enemy = Enemy(66, 0)
                enemy.hp = 1000
                for _ in range(120):
                    player.weapons.update(1/60, player, [enemy])
                self.assertLess(enemy.hp, 1000)

    def test_auto_aim_selects_nearest_living_enemy(self):
        player = Player(0, 0)
        far, near, dead = Enemy(200, 0), Enemy(0, 100), Enemy(-10, 0)
        dead.hp = 0
        player.weapons.update(1/60, player, [far, dead, near])
        self.assertAlmostEqual(player.weapons.projectiles[0].angle, math.pi/2)

    def test_swept_piercing_hits_once_and_in_distance_order(self):
        near, far = Enemy(25, 0), Enemy(45, 0)
        near.hp = far.hp = 100
        shot = Projectile(0, 0, 0, 10, level=4)
        shot.update(0.1, [far, near], [], [])
        self.assertEqual((near.hp, far.hp), (90, 90))
        self.assertEqual(shot.life, 0)
        # A piercing projectile cannot hit the same enemy again next frame.
        shot = Projectile(0, 0, 0, 10, level=4)
        shot.update(0.04, [near], [], [])
        shot.update(0.01, [near], [], [])
        self.assertEqual(near.hp, 80)

    def test_bug_homing_splash_and_slow(self):
        enemy, neighbor = Enemy(0, 25), Enemy(20, 35)
        enemy.hp = neighbor.hp = 100
        shot = Projectile(0, 0, 0, 20, "bug", level=3)
        shot.update(0.1, [enemy, neighbor], [], [])
        self.assertAlmostEqual(shot.angle, math.pi/2)
        self.assertEqual((enemy.hp, neighbor.hp), (80, 80))
        self.assertEqual(neighbor.slow_remaining, 2)
        before = neighbor.x
        neighbor.update(1000, neighbor.y, 0.1)
        self.assertAlmostEqual(neighbor.x-before, neighbor.speed*0.55*0.1)

    def test_recursion_generations_and_ancestor_exclusion(self):
        enemy = Enemy(20, 0)
        enemy.hp = 1000
        parent = Projectile(0, 0, 0, 20, "recursion", level=5)
        children = []
        parent.update(0.05, [enemy], children, [])
        self.assertEqual(len(children), 3)
        for child in children:
            self.assertIn(enemy, child.hit)
        last = Projectile(0, 0, 0, 20, "recursion", level=5, generation=2)
        terminal_children = []
        last.update(0.05, [enemy], terminal_children, [])
        self.assertEqual(terminal_children, [])

    def test_wifi_push_and_lan_multiple_targets(self):
        for kind in ("wifi", "lan"):
            player = Player(0, 0)
            player.weapons.levels = {kind: 1}
            enemies = [Enemy(50, 0), Enemy(85, 0)]
            for e in enemies:
                e.hp = 100
            player.weapons.update(1/60, player, enemies)
            self.assertTrue(all(e.hp < 100 for e in enemies))
            if kind == "wifi":
                self.assertGreater(enemies[0].x, 50)

    def test_coffee_rate_and_orbit_multiplier(self):
        plain, buffed = Player(0, 0), Player(0, 0)
        buffed.drink_coffee()
        for player in (plain, buffed):
            player.weapons.timers["enter"] = 1
            player.weapons.update(0.1, player, [])
        self.assertAlmostEqual(buffed.weapons.timers["enter"], 0.875)
        self.assertAlmostEqual(plain.weapons.timers["enter"], 0.9)
        self.assertAlmostEqual(buffed.weapons.orbit_angle/plain.weapons.orbit_angle, 1.25)

    def test_frame_rate_independent_movement_and_attack_count(self):
        results = []
        for fps in (30, 60):
            player = Player(0, 0)
            enemy = Enemy(10000, 0)
            shots = 0
            for _ in range(fps*10):
                enemy.update(0, 0, 1/fps)
                player.weapons.update(1/fps, player, [enemy])
                shots += len(player.weapons.projectiles)
                player.weapons.projectiles.clear()
            results.append((enemy.x, shots))
        self.assertAlmostEqual(results[0][0], results[1][0])
        self.assertLessEqual(abs(results[0][1]-results[1][1]), 1)


class GameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = Game()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        random.seed(7)
        self.game.reset_game()
        pygame.event.clear()

    def test_pickups_refresh_buff_and_exp_queues_choices(self):
        game = self.game
        game.coffees.append(Coffee(0, 0))
        game.gems.append(Gem(0, 0, 20))
        game.update()
        self.assertEqual(game.player.coffee_remaining, 10)
        self.assertAlmostEqual(game.player.move_speed, 172.5)
        self.assertEqual(game.player.pending_level_ups, 2)
        self.assertTrue(game.is_level_up)
        original_time = game.elapsed_seconds
        game.update(0.1)
        self.assertEqual(game.player.coffee_remaining, 10)
        self.assertEqual(game.elapsed_seconds, original_time)
        game.apply_upgrade(game.current_upgrades[0])
        self.assertTrue(game.is_level_up)
        game.apply_upgrade(game.current_upgrades[0])
        self.assertFalse(game.is_level_up)
        game.update(0.1)
        self.assertAlmostEqual(game.player.coffee_remaining, 9.9)
        game.coffees.append(Coffee(0, 0))
        game.update()
        self.assertEqual(game.player.coffee_remaining, 10)
        self.assertAlmostEqual(game.player.move_speed, 172.5)

    def test_coffee_expiration_and_restart(self):
        game = self.game
        game.player.drink_coffee()
        game.player.coffee_remaining = 0.01
        game.update(0.02)
        self.assertEqual(game.player.move_speed, 150)
        coffee = Coffee(500, 500)
        coffee.life = 0.01
        game.coffees.append(coffee)
        game.update(0.02)
        self.assertFalse(game.coffees)
        game.player.drink_coffee()
        game.player.weapons.upgrade("book")
        game.reset_game()
        self.assertEqual(game.player.weapons.levels, {"enter": 1})
        self.assertEqual(game.player.coffee_remaining, 0)

    def test_death_drops_once_and_dead_enemy_cannot_attack(self):
        game = self.game
        enemy = Enemy(0, 0)
        enemy.hp = 0
        game.enemies.append(enemy)
        with patch("main.random.random", return_value=0):
            game.update()
            game.update()
        self.assertEqual(game.kill_count, 1)
        self.assertEqual(game.player.hp, 100)
        self.assertEqual(game.player.exp, 1)
        self.assertGreater(game.player.coffee_remaining, 9)

    def test_contact_grace_and_no_pickups_after_death(self):
        game = self.game
        game.player.weapons.levels = {}
        game.enemies = [Enemy(0, 0)]
        game.update()
        self.assertEqual(game.player.hp, 92)
        game.update()
        self.assertEqual(game.player.hp, 92)
        game.player.hp = 1
        game.player.hurt_remaining = 0
        game.gems = [Gem(0, 0, 20)]
        game.update()
        self.assertTrue(game.is_game_over)
        self.assertFalse(game.is_level_up)

    def test_stage_spawn_types_at_boundaries(self):
        for time in (0, 59, 60, 119, 120, 180):
            self.game.timer_seconds = time
            for _ in range(20):
                self.game.spawn_enemy()
            self.assertTrue(all(e.hp > 0 for e in self.game.enemies))
        self.assertIsNotNone(self.game.professor_sprite)

    def test_keyboard_and_mouse_upgrade_selection(self):
        game = self.game
        game.player.add_exp(20)
        game.trigger_level_up()
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1))
        game.handle_events()
        self.assertEqual(game.player.pending_level_ups, 1)
        pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=game.upgrade_rects[0].center))
        game.handle_events()
        self.assertEqual(game.player.pending_level_ups, 0)

    def test_full_combat_and_render_smoke(self):
        game = self.game
        for kinds in (("enter", "book", "lan"), ("bug", "wifi", "recursion")):
            game.reset_game()
            game.player.weapons.levels = {kind: 5 for kind in kinds}
            game.player.drink_coffee()
            game.player.hp = game.player.max_hp = 100000
            for index in range(80):
                angle = index*math.tau/80
                game.enemies.append(Enemy(math.cos(angle)*150, math.sin(angle)*150, "rector"))
            for frame in range(300):
                if game.is_level_up:
                    game.apply_upgrade(game.current_upgrades[0])
                game.update(1/30)
                if frame % 30 == 0:
                    game.render()
                self.assertLessEqual(len(game.player.weapons.projectiles), MAX_PROJECTILES)
            self.assertGreater(game.kill_count, 0)
            game.player.add_exp(100)
            game.trigger_level_up()
            game.render()


if __name__ == "__main__":
    unittest.main()
