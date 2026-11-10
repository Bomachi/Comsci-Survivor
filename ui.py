"""Menus: the game states, the Button widget and every menu screen.

MenuMixin holds the main menu, stage select and pause menu. Game inherits it,
so these methods use the same `self` (screen, fonts, sprites) as the rest of Game.
"""
from enum import Enum
import pygame

from settings import (SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_WHITE, COLOR_GOLD,
                      COLOR_CARD_BG, COLOR_CARD_BORDER)
from resources import load_sprite
from stages import STAGES
from stage_art import build_tiles, build_ai_tiles


class GameState(Enum):
    """Which screen is active. Game over and victory stay as Game flags."""
    MAIN_MENU = 1
    PLAYING = 2
    PAUSED = 3
    STAGE_SELECT = 4


# Enemies drawn on each stage card of the stage-select screen (same order as STAGES).
STAGE_PREVIEW_ENEMIES = (
    ("TA", "professor", "rector"),
    ("acc_freshman", "acc_calculator", "acc_senior"),
    ("ai_chatgpt", "ai_claude", "ai_gemini"),
)


class Button:
    """Clickable image button used by the main menu and the pause menu."""

    def __init__(self, x, y, width, height, text="", font=None, bg_color=(40, 40, 50),
                 hover_color=(70, 70, 90), text_color=(255, 255, 255), image=None):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.font = font
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.text_color = text_color
        self.is_hovered = False
        # Scale once here instead of on every frame.
        self.image = pygame.transform.scale(image, self.rect.size) if image else None
        self.hover_overlay = None
        if self.image:
            # Highlight only the opaque pixels, so rounded corners and glows stay clean.
            mask = pygame.mask.from_surface(self.image)
            self.hover_overlay = mask.to_surface(setcolor=(255, 255, 255, 45), unsetcolor=(0, 0, 0, 0))

    def update(self, mouse_pos):
        self.is_hovered = self.rect.collidepoint(mouse_pos)

    def draw(self, surface):
        if self.image:
            surface.blit(self.image, self.rect)
            if self.is_hovered:
                surface.blit(self.hover_overlay, self.rect.topleft)
        else:
            color = self.hover_color if self.is_hovered else self.bg_color
            pygame.draw.rect(surface, color, self.rect, border_radius=10)
            pygame.draw.rect(surface, (200, 200, 200), self.rect, width=2, border_radius=10)
            if self.font and self.text:
                txt_surf = self.font.render(self.text, True, self.text_color)
                surface.blit(txt_surf, txt_surf.get_rect(center=self.rect.center))

    def is_clicked(self, event):
        return (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self.rect.collidepoint(event.pos))


class MenuMixin:
    """Main menu, stage select and pause menu for Game."""

    def init_menus(self, start_in_menu):
        """Load menu art and build the buttons and stage cards (called from Game.__init__)."""
        # Frame made for the stage-select cards (falls back to the level-up frame if missing).
        self.stage_card = load_sprite("stage_card.png", (240, 300))
        self.stage_card_hover = load_sprite("stage_card_hover.png", (240, 300))

        # Main menu and pause menu.
        self.menu_bg = load_sprite("main_menu_background.jpg", (SCREEN_WIDTH, SCREEN_HEIGHT))
        self.stage_bg = load_sprite("stage_select_background.jpg", (SCREEN_WIDTH, SCREEN_HEIGHT))
        button_x = SCREEN_WIDTH // 2 - 110

        def make_button(y, text, image_name):
            return Button(button_x, y, 220, 60, text, self.font, image=load_sprite(image_name, (220, 60)))

        self.btn_start = make_button(480, "START GAME", "start_game_button.png")
        self.btn_quit = make_button(560, "QUIT", "quit_button.png")
        self.btn_resume = make_button(250, "RESUME", "resume_button.png")
        self.btn_restart = make_button(330, "RESTART", "restart_button.png")
        self.btn_main_menu = make_button(410, "MAIN MENU", "main_menu_button.png")
        self.btn_stage_back = make_button(580, "MAIN MENU", "main_menu_button.png")
        self.btn_victory_menu = make_button(430, "MAIN MENU", "main_menu_button.png")

        # Stage-select cards use the same frame art as the level-up cards.
        card_w, card_h, gap = 240, 300, 25
        first_x = (SCREEN_WIDTH - (len(STAGES) * card_w + (len(STAGES) - 1) * gap)) // 2
        self.stage_card_rects = [pygame.Rect(first_x + i * (card_w + gap), 190, card_w, card_h)
                                 for i in range(len(STAGES))]
        self.stage_previews = [self.build_stage_preview(i) for i in range(len(STAGES))]
        self.selected_stage = 0     # the stage chosen on the select screen; Restart replays it
        # Tests and headless runs build Game() directly and expect to be playing;
        # only main() asks for the menu.
        self.state = GameState.MAIN_MENU if start_in_menu else GameState.PLAYING

    def menu_buttons(self):
        """Buttons that are visible (and clickable) in the current state."""
        if self.state == GameState.MAIN_MENU:
            return (self.btn_start, self.btn_quit)
        if self.state == GameState.STAGE_SELECT:
            return (self.btn_stage_back,)
        if self.state == GameState.PAUSED:
            return (self.btn_resume, self.btn_restart, self.btn_main_menu)
        if self.state == GameState.PLAYING and self.is_victory:
            return (self.btn_victory_menu,)
        return ()

    def handle_main_menu_event(self, event):
        if self.btn_start.is_clicked(event):
            self.state = GameState.STAGE_SELECT
        elif self.btn_quit.is_clicked(event):
            self.is_running = False

    def start_run(self, stage_index):
        """Begin a fresh run on the chosen stage."""
        self.selected_stage = stage_index
        self.reset_game()
        self.state = GameState.PLAYING

    def go_to_main_menu(self):
        self.state = GameState.MAIN_MENU

    def handle_stage_select_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.go_to_main_menu()
            elif pygame.K_1 <= event.key < pygame.K_1 + len(STAGES):
                self.start_run(event.key - pygame.K_1)
        elif self.btn_stage_back.is_clicked(event):
            self.go_to_main_menu()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for index, rect in enumerate(self.stage_card_rects):
                if rect.collidepoint(event.pos):
                    self.start_run(index)
                    break

    def handle_pause_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.state = GameState.PLAYING
        elif self.btn_resume.is_clicked(event):
            self.state = GameState.PLAYING
        elif self.btn_restart.is_clicked(event):
            self.reset_game()
            self.state = GameState.PLAYING
        elif self.btn_main_menu.is_clicked(event):
            self.go_to_main_menu()

    def draw_main_menu(self):
        if self.menu_bg:
            self.screen.blit(self.menu_bg, (0, 0))
        else:
            self.draw_background()
            title = self.title_font.render("COMSCI SURVIVOR", True, COLOR_GOLD)
            self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 180))
        self.btn_start.draw(self.screen)
        self.btn_quit.draw(self.screen)

    def build_stage_preview(self, index):
        """Ground tiles of a stage with its enemies standing on them (card artwork)."""
        stage = STAGES[index]()
        size = (200, 96)
        preview = pygame.Surface(size)
        if stage.decorated:      # decorated stages draw their ground from generated tiles
            tile = (build_ai_tiles() if stage.scenery_theme == "ai" else build_tiles())[0][0]
        else:
            tile = load_sprite(stage.ground_tile_name, (64, 64))
        if tile is None:
            preview.fill((40, 40, 60))
        else:
            for x in range(0, size[0], tile.get_width()):
                for y in range(0, size[1], tile.get_height()):
                    preview.blit(tile, (x, y))
        names = STAGE_PREVIEW_ENEMIES[index] if index < len(STAGE_PREVIEW_ENEMIES) else ()
        sprites = [self.enemy_sprites.get(name) for name in names]
        sprites = [sprite for sprite in sprites if sprite]
        sprites = [pygame.transform.smoothscale(
                       sprite, (max(1, round(sprite.get_width() * 48 / sprite.get_height())), 48))
                   if sprite.get_height() > 48 else sprite for sprite in sprites]
        x = (size[0] - sum(sprite.get_width() + 8 for sprite in sprites) + 8) // 2
        for sprite in sprites:
            preview.blit(sprite, (x, (size[1] - sprite.get_height()) // 2))
            x += sprite.get_width() + 8
        pygame.draw.rect(preview, (15, 15, 25), preview.get_rect(), width=3)
        return preview

    def draw_stage_select(self):
        if self.stage_bg:
            self.screen.blit(self.stage_bg, (0, 0))
        else:
            self.screen.fill((18, 22, 41))
        title = self.title_font.render("SELECT STAGE", True, COLOR_GOLD)
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 80))
        subtitle = self.font.render("Click a stage or press [1 / 2 / 3]", True, COLOR_WHITE)
        self.screen.blit(subtitle, (SCREEN_WIDTH // 2 - subtitle.get_width() // 2, 135))

        mouse_pos = pygame.mouse.get_pos()
        for index, rect in enumerate(self.stage_card_rects):
            stage = STAGES[index]()
            hover = rect.collidepoint(mouse_pos)
            card, card_hover = ((self.stage_card, self.stage_card_hover) if self.stage_card
                                else (self.card_frame, self.card_frame_hover))
            frame = card_hover if (hover and card_hover) else card
            if frame:
                self.screen.blit(frame, rect.topleft)
            else:
                pygame.draw.rect(self.screen, COLOR_CARD_BG, rect, border_radius=12)
                pygame.draw.rect(self.screen, COLOR_GOLD if hover else COLOR_CARD_BORDER, rect,
                                 width=3, border_radius=12)
            number, _, place = stage.name.partition(":")
            head = self.font.render(number.upper(), True, (255, 226, 120) if hover else (240, 240, 232))
            self.screen.blit(head, (rect.centerx - head.get_width() // 2, rect.y + 22))
            self.draw_wrapped_text(place.strip(), self.small_font, (205, 210, 198), 200,
                                   rect.centerx, rect.y + 56, 18)
            self.screen.blit(self.stage_previews[index], (rect.centerx - 100, rect.y + 96))
            boss = f"BOSS: {stage.boss_name}" if stage.boss_type else "NO BOSS"
            self.draw_wrapped_text(boss, self.small_font, (255, 150, 140), 200,
                                   rect.centerx, rect.y + 212, 18)
            minutes, seconds = divmod(stage.duration, 60)
            goal = self.small_font.render(f"SURVIVE {minutes}:{seconds:02d}", True, (150, 230, 150))
            self.screen.blit(goal, (rect.centerx - goal.get_width() // 2, rect.y + 261))
        self.btn_stage_back.draw(self.screen)

    def draw_pause_menu(self):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))
        title = self.title_font.render("GAME PAUSED", True, COLOR_WHITE)
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 150))
        for button in (self.btn_resume, self.btn_restart, self.btn_main_menu):
            button.draw(self.screen)
