"""Pathfinding, smarter enemies, animation effects and scenery."""
import math
import os
import random
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame
from accounting import EnemyShot, update_ranged
from animation import Effects
from main import Enemy, Game, Player
from pathfinding import FlowField, ObstacleMap


class Body:
    def __init__(self, x, y, r=14):
        self.x, self.y, self.radius = x, y, r


class FlowFieldTests(unittest.TestCase):
    def setUp(self):
        self.obstacles = ObstacleMap()
        # A wall between the enemy (left) and the player (right), open at the bottom.
        self.obstacles.set_rects([pygame.Rect(-20, -400, 40, 600)])
        self.field = FlowField(self.obstacles)
        self.field.rebuild(200, 0)

    def test_bfs_routes_around_the_wall(self):
        walker = Body(-200, 0)
        for _ in range(2000):
            d = self.field.direction(walker.x, walker.y)
            if d is None:
                break
            walker.x += d[0] * 4
            walker.y += d[1] * 4
            self.obstacles.push_out(walker)
            self.assertFalse(self.obstacles.blocked(walker.x, walker.y), "walked into the wall")
        self.assertLess(math.hypot(walker.x - 200, walker.y), 40)

    def test_distance_is_shortest_path_not_straight_line(self):
        behind = self.field.path_length(-200, 0)
        open_side = self.field.path_length(200, 300)
        self.assertGreater(behind, 400 / 32)       # must go round the wall
        self.assertLess(open_side, behind)

    def test_push_out_of_rectangle(self):
        body = Body(0, 0)
        self.obstacles.push_out(body)
        self.assertFalse(pygame.Rect(-20, -400, 40, 600).inflate(-2, -2).collidepoint(body.x, body.y))


class EnemyBehaviourTests(unittest.TestCase):
    def test_freshman_telegraphs_then_lunges(self):
        e = Enemy(0, 0, "acc_freshman")
        e.lunge_cooldown = 0
        e.update(100, 0, 0.05)
        self.assertEqual(e.lunge_state, "windup")
        x = e.x
        e.update(100, 0, 0.1)
        self.assertEqual(e.x, x)                   # crouching, not moving
        for _ in range(4):
            e.update(100, 0, 0.05)
        self.assertEqual(e.lunge_state, "dash")
        before = e.x
        e.update(100, 0, 0.05)
        self.assertGreater(e.x - before, e.speed * 0.05 * 2)

    def test_calculator_leads_a_moving_target(self):
        thrower, player = Enemy(0, 0, "acc_calculator"), Player(300, 0)
        thrower.shoot_timer = 0
        shots = []
        update_ranged(thrower, player, 0.1, shots, (0, 150))
        self.assertGreater(shots[0].vy, 0)         # aimed below, where the player is heading

    def test_calculator_strafes_in_range(self):
        thrower = Enemy(0, 0, "acc_calculator")
        thrower.update(240, 0, 0.1)
        self.assertNotEqual(thrower.y, 0)          # moved sideways
        self.assertAlmostEqual(thrower.x, 0, delta=0.5)


class GameIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = Game()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        random.seed(5)
        self.game.demo_mode = False
        self.game.reset_game()

    def test_stage2_has_props_obstacles_and_flow_field(self):
        game = self.game
        game.start_stage(1)
        self.assertTrue(game.obstacles.rects)
        for rect in game.obstacles.rects:
            self.assertGreater(math.hypot(rect.centerx, rect.centery), 150)  # start area is clear
        game.update(1 / 60)
        self.assertTrue(game.flow.dirs)
        layout = sorted((p.kind, p.x, p.y) for p in game.scenery.props())
        game.start_stage(1)
        self.assertEqual(layout, sorted((p.kind, p.x, p.y) for p in game.scenery.props()))  # deterministic

    def test_enemies_never_end_inside_obstacles(self):
        game = self.game
        game.start_stage(1)
        game.demo_mode = True
        game.stress_spawn(150)
        for _ in range(120):
            game.update(1 / 30)
        for e in game.enemies:
            for rect in game.obstacles.nearby(e.x, e.y, 0):
                self.assertFalse(rect.inflate(-4, -4).collidepoint(e.x, e.y))

    def test_hits_create_numbers_and_deaths_create_particles(self):
        game = self.game
        game.start_stage(1)
        game.player.hp = game.player.max_hp = 10 ** 6
        game.player.weapons.levels = {"enter": 5, "lan": 5}
        for i in range(12):
            game.add_enemy("acc_freshman", 60 + i * 4, 0)
        for _ in range(60):
            game.update(1 / 30)
            if game.is_level_up:
                game.apply_upgrade(game.current_upgrades[0])
        self.assertGreater(game.kill_count, 0)
        self.assertTrue(game.effects.particles or game.effects.texts)
        game.show_debug = True
        game.render()
        game.show_debug = False

    def test_effects_are_capped(self):
        fx = Effects()
        for _ in range(500):
            fx.burst(0, 0, None, 20)
            fx.damage(0, 0, 5)
        self.assertLessEqual(len(fx.particles), Effects.MAX_PARTICLES)
        self.assertLessEqual(len(fx.texts), Effects.MAX_TEXTS)


if __name__ == "__main__":
    unittest.main()
