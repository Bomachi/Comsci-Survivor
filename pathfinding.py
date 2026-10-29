"""Obstacles and flow-field pathfinding.

ObstacleMap  stores solid rectangles (desks, shelves...) in a coarse grid so a
             circle can be pushed out of nearby rectangles cheaply.
FlowField    runs one breadth-first search (BFS) outward from the player over a
             window of grid cells. Every reachable cell then stores the
             direction of a shortest path toward the player, so hundreds of
             enemies can walk around obstacles while the search runs only once
             per player move instead of once per enemy (A* per enemy would cost
             n searches per frame).
"""
import math
from collections import deque

import pygame

FLOW_CELL = 32
FLOW_COLS, FLOW_ROWS = 56, 42          # window of 1792 x 1344 px around the player
OBSTACLE_BUCKET = 128
NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))


class ObstacleMap:
    def __init__(self):
        self.rects = []
        self.buckets = {}

    def set_rects(self, rects):
        self.rects = list(rects)
        self.buckets = {}
        for rect in self.rects:
            for bx in range(rect.left // OBSTACLE_BUCKET, (rect.right - 1) // OBSTACLE_BUCKET + 1):
                for by in range(rect.top // OBSTACLE_BUCKET, (rect.bottom - 1) // OBSTACLE_BUCKET + 1):
                    self.buckets.setdefault((bx, by), []).append(rect)

    def nearby(self, x, y, r):
        found = []
        for bx in range(int((x - r) // OBSTACLE_BUCKET), int((x + r) // OBSTACLE_BUCKET) + 1):
            for by in range(int((y - r) // OBSTACLE_BUCKET), int((y + r) // OBSTACLE_BUCKET) + 1):
                for rect in self.buckets.get((bx, by), ()):
                    if rect not in found:
                        found.append(rect)
        return found

    def blocked(self, x, y, r=0):
        return any(rect.inflate(r * 2, r * 2).collidepoint(x, y) for rect in self.nearby(x, y, r))

    def push_out(self, body):
        """Move a circle (x, y, radius) out of any rectangle it overlaps."""
        for rect in self.nearby(body.x, body.y, body.radius):
            nx = min(max(body.x, rect.left), rect.right)
            ny = min(max(body.y, rect.top), rect.bottom)
            dx, dy = body.x - nx, body.y - ny
            dist_sq = dx * dx + dy * dy
            if dist_sq >= body.radius * body.radius:
                continue
            if dist_sq == 0:
                # Centre is inside the rectangle: leave by the closest side.
                exits = ((body.x - rect.left, -1, 0), (rect.right - body.x, 1, 0),
                         (body.y - rect.top, 0, -1), (rect.bottom - body.y, 0, 1))
                depth, ex, ey = min(exits)
                body.x += ex * (depth + body.radius)
                body.y += ey * (depth + body.radius)
                continue
            dist = math.sqrt(dist_sq)
            push = body.radius - dist
            body.x += dx / dist * push
            body.y += dy / dist * push


class FlowField:
    def __init__(self, obstacles, clearance=14):
        self.obstacles = obstacles
        self.clearance = clearance       # keep paths this far from obstacle edges
        self.origin = (0, 0)             # world position of cell (0, 0)
        self.dist = {}
        self.dirs = {}
        self.target_cell = None
        self.blocked_cells = set()
        self.rebuilds = 0
        self.last_build_ms = 0.0

    def cell_of(self, x, y):
        ox, oy = self.origin
        return int((x - ox) // FLOW_CELL), int((y - oy) // FLOW_CELL)

    def cell_center(self, cx, cy):
        ox, oy = self.origin
        return ox + (cx + 0.5) * FLOW_CELL, oy + (cy + 0.5) * FLOW_CELL

    def rebuild(self, px, py):
        """BFS from the player's cell. O(cells) per rebuild."""
        import time
        started = time.perf_counter()
        self.rebuilds += 1
        self.origin = (int(px // FLOW_CELL) * FLOW_CELL - FLOW_COLS // 2 * FLOW_CELL,
                       int(py // FLOW_CELL) * FLOW_CELL - FLOW_ROWS // 2 * FLOW_CELL)
        self.blocked_cells = set()
        ox, oy = self.origin
        window = pygame.Rect(ox, oy, FLOW_COLS * FLOW_CELL, FLOW_ROWS * FLOW_CELL)
        pad = self.clearance
        for rect in self.obstacles.rects:
            grown = rect.inflate(pad * 2, pad * 2)
            if not grown.colliderect(window):
                continue
            for cx in range(max(0, (grown.left - ox) // FLOW_CELL), min(FLOW_COLS, (grown.right - 1 - ox) // FLOW_CELL + 1)):
                for cy in range(max(0, (grown.top - oy) // FLOW_CELL), min(FLOW_ROWS, (grown.bottom - 1 - oy) // FLOW_CELL + 1)):
                    self.blocked_cells.add((cx, cy))
        start = self.cell_of(px, py)
        self.target_cell = start
        self.blocked_cells.discard(start)
        dist = {start: 0}
        queue = deque([start])
        while queue:
            cx, cy = queue.popleft()
            d = dist[(cx, cy)] + 1
            for dx, dy in NEIGHBOURS[:4]:
                nxt = (cx + dx, cy + dy)
                if (0 <= nxt[0] < FLOW_COLS and 0 <= nxt[1] < FLOW_ROWS
                        and nxt not in dist and nxt not in self.blocked_cells):
                    dist[nxt] = d
                    queue.append(nxt)
        self.dist = dist
        # Direction per cell: step to the neighbour with the lowest distance.
        # Diagonal steps are allowed only when both side cells are open, so
        # enemies never cut through the corner of a desk.
        dirs = {}
        for (cx, cy), d in dist.items():
            if d == 0:
                continue
            best, best_d = None, d
            for dx, dy in NEIGHBOURS:
                nd = dist.get((cx + dx, cy + dy))
                if nd is None:
                    continue
                if dx and dy and ((cx + dx, cy) not in dist or (cx, cy + dy) not in dist):
                    continue
                weight = nd + (0.4 if dx and dy else 0)
                if weight < best_d:
                    best, best_d = (dx, dy), weight
            if best:
                length = math.hypot(*best)
                dirs[(cx, cy)] = (best[0] / length, best[1] / length)
        self.dirs = dirs
        self.last_build_ms = (time.perf_counter() - started) * 1000

    def update(self, px, py):
        """Rebuild only when the player enters a new cell."""
        if self.target_cell is None or self.cell_of(px, py) != self.target_cell:
            self.rebuild(px, py)

    def direction(self, x, y):
        """Unit vector toward the player along a shortest path, or None."""
        return self.dirs.get(self.cell_of(x, y))

    def path_length(self, x, y):
        return self.dist.get(self.cell_of(x, y))

    def draw(self, surface, cam_x, cam_y):
        """Debug: arrows on reachable cells and red blocked cells."""
        ox, oy = self.origin
        w, h = surface.get_size()
        for (cx, cy) in self.blocked_cells:
            x, y = ox + cx * FLOW_CELL - cam_x, oy + cy * FLOW_CELL - cam_y
            if -FLOW_CELL < x < w and -FLOW_CELL < y < h:
                pygame.draw.rect(surface, (220, 50, 50, 70), (x, y, FLOW_CELL, FLOW_CELL))
        for (cx, cy), (dx, dy) in self.dirs.items():
            x, y = self.cell_center(cx, cy)
            x, y = x - cam_x, y - cam_y
            if not (0 < x < w and 0 < y < h):
                continue
            tip = (x + dx * 11, y + dy * 11)
            pygame.draw.line(surface, (60, 90, 200, 140), (x - dx * 6, y - dy * 6), tip, 1)
            pygame.draw.circle(surface, (60, 90, 200, 160), tip, 2)
