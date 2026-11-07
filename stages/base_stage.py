STAGE_DURATION_SECONDS = 20 * 60


class BaseStage:
    def __init__(self, name: str, ground_tile_name: str, duration_seconds: int = STAGE_DURATION_SECONDS):
        self.name = name
        self.duration = duration_seconds
        self.ground_tile_name = ground_tile_name
        # Optional per-stage settings; stages override what they need.
        self.spawn_interval = 2/3
        self.boss_type = None
        self.boss_time = None
        self.boss_name = ""
        self.scenery_theme = "accounting"
        self.victory_text = "STAGE CLEARED!"
        self.decorated = False   # True: props, obstacles and flow-field pathfinding
    def get_enemy_spawn_type(self, elapsed_seconds: int) -> str:
        raise NotImplementedError()