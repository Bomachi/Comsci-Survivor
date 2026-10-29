"""Spatial hash tests: same pairs as the naive method, far fewer checks."""
import random
import unittest

from spatial import PairStats, SpatialHash, naive_pairs, separate


class Circle:
    def __init__(self, x, y, r, mass=1.0):
        self.x, self.y, self.radius, self.mass = x, y, r, mass


def overlapping(pairs):
    return {tuple(sorted((id(a), id(b)))) for a, b in pairs
            if (a.x - b.x) ** 2 + (a.y - b.y) ** 2 < (a.radius + b.radius) ** 2}


class SpatialHashTests(unittest.TestCase):
    def setUp(self):
        random.seed(11)
        self.items = [Circle(random.uniform(-800, 800), random.uniform(-800, 800), random.choice([14, 16, 21, 40]))
                      for _ in range(600)]

    def test_hash_finds_exactly_the_same_overlaps_as_naive(self):
        naive_stats, hash_stats = PairStats(), PairStats()
        expected = overlapping(naive_pairs(self.items, naive_stats))
        found = overlapping(SpatialHash().build(self.items).pairs(hash_stats))
        self.assertEqual(found, expected)
        self.assertEqual(naive_stats.checks, 600 * 599 // 2)
        self.assertLess(hash_stats.checks, naive_stats.checks / 20)

    def test_pairs_are_unique_for_items_spanning_many_cells(self):
        big, small = Circle(0, 0, 200), Circle(10, 10, 5)
        stats = PairStats()
        self.assertEqual(len(list(SpatialHash(32).build([big, small]).pairs(stats))), 1)

    def test_query_returns_neighbors(self):
        grid = SpatialHash().build(self.items)
        near = grid.query(0, 0, 100)
        for item in self.items:
            if abs(item.x) + abs(item.y) < 50:
                self.assertIn(item, near)

    def test_separation_resolves_overlap_and_heavy_items_move_less(self):
        for mode in ("naive", "hash"):
            a, b = Circle(0, 0, 10), Circle(5, 0, 10)
            for _ in range(20):
                separate([a, b], mode)
            self.assertGreaterEqual(b.x - a.x, 19.5)
            boss, minion = Circle(0, 0, 40, mass=8), Circle(30, 0, 14)
            separate([boss, minion], mode, strength=1.0)
            self.assertLess(abs(boss.x), abs(minion.x - 30))


if __name__ == "__main__":
    unittest.main()
