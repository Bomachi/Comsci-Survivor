import random
from stages.base_stage import BaseStage


class Stage2(BaseStage):
    """Stage 2: invade the Accounting Faculty and defeat the Chief Auditor."""

    BOSS_TIME = 150  # seconds into the stage

    def __init__(self):
        super().__init__(
            name="Stage 2: Accounting Faculty",
            target_time_seconds=self.BOSS_TIME,
            ground_tile_name="stage2_tile.png"
        )
        self.spawn_interval = 0.55
        self.boss_type = "acc_boss"
        self.boss_time = self.BOSS_TIME

    def get_enemy_spawn_type(self, elapsed_seconds: int) -> str:
        roll = random.random()
        if elapsed_seconds < 45:
            return "acc_freshman"
        if elapsed_seconds < 100:
            return "acc_calculator" if roll < 0.3 else "acc_freshman"
        if roll < 0.2:
            return "acc_senior"
        if roll < 0.5:
            return "acc_calculator"
        return "acc_freshman"
