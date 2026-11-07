"""Broad-phase collision: naive O(n^2) pair checks vs. a uniform-grid spatial hash.

Used to push overlapping enemies apart (crowd separation). Both strategies
find the same overlapping pairs; the spatial hash only tests enemies in the same
or neighbouring grid cells, so the number of distance checks grows ~linearly with the enemy count
instead of quadratically. `PairStats.checks` records the work done so the debug
overlay (F3) and the benchmark can show the difference.
"""
from collections import defaultdict

CELL_SIZE = 48


class PairStats:
    def __init__(self):
        self.checks = 0     # distance tests performed
        self.overlaps = 0   # pairs that actually overlapped


def naive_pairs(items, stats):
    """Every item against every other item: n(n-1)/2 checks."""
    n = len(items)
    for i in range(n):
        a = items[i]
        for j in range(i + 1, n):
            stats.checks += 1
            yield a, items[j]


class SpatialHash:
    """Uniform grid keyed by each item's centre cell.

    Every item lives in exactly one cell, so no duplicate-pair bookkeeping is
    needed: each cell is checked against itself and 4 "forward" neighbours
    (half of the 8-neighbourhood), which visits every nearby pair exactly once.
    This is correct while two touching items are at most one cell apart, i.e.
    cell_size >= the largest diameter. Items bigger than that (bosses) are kept
    in a separate list and tested with a bounding-box query instead.
    """

    FORWARD = ((1, 0), (-1, 1), (0, 1), (1, 1))

    def __init__(self, cell_size=CELL_SIZE):
        self.cell_size = cell_size
        self.cells = defaultdict(list)
        self.large = []

    def build(self, items):
        cs = self.cell_size
        self.cells = defaultdict(list)
        self.large = []
        for item in items:
            if item.radius * 2 > cs:
                self.large.append(item)
            self.cells[(int(item.x // cs), int(item.y // cs))].append(item)
        return self

    def query(self, x, y, r):
        """Items whose centre cell lies within the circle's bounding box grown by one cell."""
        cs = self.cell_size
        found = []
        for cx in range(int((x - r) // cs) - 1, int((x + r) // cs) + 2):
            for cy in range(int((y - r) // cs) - 1, int((y + r) // cs) + 2):
                found.extend(self.cells.get((cx, cy), ()))
        return found + [item for item in self.large if item not in found]

    def pairs(self, stats):
        """Unique pairs of nearby items."""
        cells = self.cells
        large_ids = {id(item) for item in self.large}
        for (cx, cy), bucket in cells.items():
            n = len(bucket)
            for i in range(n):
                a = bucket[i]
                for j in range(i + 1, n):
                    stats.checks += 1
                    yield a, bucket[j]
            for dx, dy in self.FORWARD:
                other = cells.get((cx + dx, cy + dy))
                if not other:
                    continue
                for a in bucket:
                    for b in other:
                        stats.checks += 1
                        yield a, b
        # Large items can touch items several cells away: query around them,
        # skipping pairs the cell pass above already produced.
        cs = self.cell_size
        for big in self.large:
            bx, by = int(big.x // cs), int(big.y // cs)
            reach = int(big.radius // cs) + 2
            for cx in range(bx - reach, bx + reach + 1):
                for cy in range(by - reach, by + reach + 1):
                    if max(abs(cx - bx), abs(cy - by)) <= 1:
                        continue  # already covered by the neighbour pass
                    for other in cells.get((cx, cy), ()):
                        if id(other) in large_ids and id(other) < id(big):
                            continue  # each large-large pair once
                        stats.checks += 1
                        yield big, other


def separate(items, mode="hash", strength=0.8, cell_size=CELL_SIZE):
    """Push overlapping circles apart. Heavier items (bosses) move less.

    Returns PairStats so callers can display or benchmark the work done.
    """
    stats = PairStats()
    pairs = naive_pairs(items, stats) if mode == "naive" else SpatialHash(cell_size).build(items).pairs(stats)
    for a, b in pairs:
        dx, dy = b.x - a.x, b.y - a.y
        min_dist = a.radius + b.radius
        dist_sq = dx * dx + dy * dy
        if dist_sq >= min_dist * min_dist:
            continue
        stats.overlaps += 1
        dist = dist_sq ** 0.5
        if dist == 0:
            dx, dy, dist = 1.0, 0.0, 1.0
        push = (min_dist - dist) * strength
        mass_a, mass_b = getattr(a, "mass", 1.0), getattr(b, "mass", 1.0)
        share_a = mass_b / (mass_a + mass_b)
        nx, ny = dx / dist, dy / dist
        a.x -= nx * push * share_a
        a.y -= ny * push * share_a
        b.x += nx * push * (1 - share_a)
        b.y += ny * push * (1 - share_a)
    return stats
