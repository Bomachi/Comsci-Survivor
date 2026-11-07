import random
import unittest

import upgrades
from upgrades import level_up_choices, apply_choice, available_upgrades


class FakePlayer:
    def __init__(self):
        self.hp, self.max_hp = 50, 100
        self.speed = 150.0
        self.magnet_range = 60


class LevelUpChoicesTest(unittest.TestCase):
    def maxed_player(self):
        from main import Player
        import pygame
        pygame.init()
        player = Player(0, 0)
        for _ in range(100):
            cards = [c for c in available_upgrades(player) if c["id"] != "recovery"]
            if not cards:
                break
            upgrades.apply_upgrade(player, cards[0])
        return player

    def test_always_three_cards_when_maxed(self):
        player = self.maxed_player()
        self.assertEqual([c["id"] for c in available_upgrades(player)], ["recovery"])
        for seed in range(20):
            cards = level_up_choices(player, random.Random(seed))
            self.assertEqual(len(cards), 3)
            self.assertEqual(len({c["id"] for c in cards}), 3)

    def test_passive_effects(self):
        p = FakePlayer()
        apply_choice(p, {"id": "vitality"})
        self.assertEqual((p.max_hp, p.hp), (120, 70))
        apply_choice(p, {"id": "magnet"})
        self.assertEqual(p.magnet_range, 90)
        for _ in range(10):
            apply_choice(p, {"id": "sneakers"})
        self.assertAlmostEqual(p.speed, 150 * upgrades.MAX_SPEED_BONUS)
        self.assertFalse(upgrades._passive_allowed(p, "sneakers"))
        apply_choice(p, {"id": "study_break"})
        self.assertEqual(p.hp, 95)


if __name__ == "__main__":
    unittest.main()
