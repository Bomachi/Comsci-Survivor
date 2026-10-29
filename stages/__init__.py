from .base_stage import BaseStage
from .stage1 import Stage1
from .stage2 import Stage2

STAGES = [Stage1, Stage2]

__all__ = ["BaseStage", "Stage1", "Stage2", "STAGES"]
