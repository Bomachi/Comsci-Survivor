class BaseStage:
    def __init__(self, name: str, target_time_seconds: int, ground_tile_name: str):
        self.name = name
        self.target_time = target_time_seconds
        self.ground_tile_name = ground_tile_name
        # Optional per-stage settings; stages override what they need.
        self.spawn_interval = 2/3
        self.boss_type = None
        self.boss_time = None
        self.decorated = False   # True: props, obstacles and flow-field pathfinding
    def get_enemy_spawn_type(self, elapsed_seconds: int) -> str:
        raise NotImplementedError()