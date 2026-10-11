class BaseStage:
    def __init__(self, name: str, target_time_seconds: int, ground_tile_name: str):
        self.name = name
        self.target_time = target_time_seconds
        self.ground_tile_name = ground_tile_name
    def get_enemy_spawn_type(self, elapsed_seconds: int) -> str:
        raise NotImplementedError()