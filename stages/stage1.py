import random
from stages.base_stage import BaseStage

class Stage1(BaseStage):
    def __init__(self):
        super().__init__(
            name="Stage 1: Ancient Cemetery",
            target_time_seconds=180,
            ground_tile_name="stage1_tile.png"
        )

    def get_enemy_spawn_type(self, elapsed_seconds: int) -> str:
        if elapsed_seconds < 60:
            return "TA"
        elif elapsed_seconds < 120:
            return "professor" if random.random() < 0.5 else "TA"
        else:
            return "rector"