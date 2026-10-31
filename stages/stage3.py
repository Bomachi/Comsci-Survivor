"""The AI data center: denser crowds and a three-headed cyber hydra."""
import random

from stages.base_stage import BaseStage


class Stage3(BaseStage):
    BOSS_TIME = 180

    def __init__(self):
        super().__init__("Stage 3: AI Data Center", self.BOSS_TIME, "stage3_tile.png")
        self.spawn_interval = 0.40
        self.boss_type = "ai_hydra"
        self.boss_time = self.BOSS_TIME
        self.boss_name = "AI OVERLORD HYDRA"
        self.scenery_theme = "ai"
        self.victory_text = "AI DATA CENTER CLEARED!"
        self.decorated = True

    def get_enemy_spawn_type(self, elapsed_seconds):
        roll = random.random()
        chatgpt, claude = ((0.35, 1.0) if elapsed_seconds < 45 else
                          (0.25, 0.80) if elapsed_seconds < 105 else (0.20, 0.70))
        if roll < chatgpt:
            return "ai_chatgpt"
        return "ai_claude" if roll < claude else "ai_gemini"
