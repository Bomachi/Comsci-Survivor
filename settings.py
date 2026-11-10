"""Constants shared by every module: window size, frame rate, colours and folders."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SPRITES_DIR = os.path.join(BASE_DIR, "assets", "sprites")

SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 700
FPS = 60

COLOR_WHITE = (245, 245, 250)
COLOR_HP_GREEN = (46, 204, 113)
COLOR_HP_RED = (231, 76, 60)
COLOR_EXP = (52, 152, 219)
COLOR_GOLD = (255, 215, 0)
COLOR_CARD_BG = (35, 30, 50)
COLOR_CARD_BORDER = (100, 90, 130)
