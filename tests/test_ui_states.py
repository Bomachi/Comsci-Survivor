"""Main menu / pause menu behaviour, and how it interacts with the stage3 features.

Run without opening a window: python -m unittest discover -s tests -v
"""
import os
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame

from main import Button, Game, GameState, create_game
from stages import STAGES


def press(game, key):
    pygame.event.clear()
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0))
    game.handle_events()


def click_at(game, pos):
    pygame.event.clear()
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
    game.handle_events()


def click(game, button):
    click_at(game, button.rect.center)


def open_stage_select():
    game = Game(start_in_menu=True)
    click(game, game.btn_start)
    return game


class StartupStateTest(unittest.TestCase):
    def test_game_defaults_to_playing_so_headless_code_still_works(self):
        self.assertEqual(Game().state, GameState.PLAYING)

    def test_start_in_menu_option(self):
        self.assertEqual(Game(start_in_menu=True).state, GameState.MAIN_MENU)

    def test_create_game_opens_menu_by_default(self):
        self.assertEqual(create_game(["main.py"]).state, GameState.MAIN_MENU)

    def test_stage_flag_skips_menu_and_jumps_to_stage(self):
        for flag, index in (("2", 1), ("3", 2)):
            with self.subTest(stage=flag):
                game = create_game(["main.py", "--stage", flag])
                self.assertEqual(game.state, GameState.PLAYING)
                self.assertEqual(game.stage_index, index)
                self.assertEqual(game.selected_stage, index)


class ButtonTest(unittest.TestCase):
    def setUp(self):
        pygame.init()

    def test_hover_follows_mouse(self):
        button = Button(10, 10, 100, 40)
        button.update((20, 20))
        self.assertTrue(button.is_hovered)
        button.update((500, 500))
        self.assertFalse(button.is_hovered)

    def test_hover_highlight_follows_the_button_shape(self):
        art = pygame.Surface((40, 20), pygame.SRCALPHA)
        art.fill((255, 215, 0, 255))
        art.set_at((0, 0), (0, 0, 0, 0))           # a transparent rounded corner
        button = Button(0, 0, 40, 20, image=art)
        self.assertEqual(button.hover_overlay.get_at((0, 0)).a, 0)       # corner stays clean
        self.assertGreater(button.hover_overlay.get_at((20, 10)).a, 0)   # body is highlighted

    def test_click_uses_event_position_not_stale_hover(self):
        button = Button(10, 10, 100, 40)
        inside = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(20, 20))
        outside = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(500, 500))
        right_click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=3, pos=(20, 20))
        self.assertTrue(button.is_clicked(inside))
        self.assertFalse(button.is_clicked(outside))
        self.assertFalse(button.is_clicked(right_click))


class MainMenuTest(unittest.TestCase):
    def setUp(self):
        self.game = Game(start_in_menu=True)

    def test_world_is_frozen_in_menu(self):
        before = self.game.elapsed_seconds
        self.game.update(0.1)
        self.assertEqual(self.game.elapsed_seconds, before)

    def test_start_button_opens_the_stage_select_without_starting_a_run(self):
        self.game.elapsed_seconds = 99.0
        click(self.game, self.game.btn_start)
        self.assertEqual(self.game.state, GameState.STAGE_SELECT)
        self.game.update(0.1)
        self.assertEqual(self.game.elapsed_seconds, 99.0)

    def test_quit_button_stops_the_game(self):
        click(self.game, self.game.btn_quit)
        self.assertFalse(self.game.is_running)

    def test_pause_buttons_do_nothing_in_menu(self):
        click(self.game, self.game.btn_resume)
        self.assertEqual(self.game.state, GameState.MAIN_MENU)

    def test_gameplay_keys_do_nothing_in_menu(self):
        press(self.game, pygame.K_ESCAPE)
        press(self.game, pygame.K_F5)
        self.assertEqual(self.game.state, GameState.MAIN_MENU)
        self.assertEqual(self.game.enemies, [])


class PauseMenuTest(unittest.TestCase):
    def setUp(self):
        self.game = Game()
        for _ in range(30):
            self.game.update(0.1)

    def test_escape_pauses_and_resumes(self):
        press(self.game, pygame.K_ESCAPE)
        self.assertEqual(self.game.state, GameState.PAUSED)
        press(self.game, pygame.K_ESCAPE)
        self.assertEqual(self.game.state, GameState.PLAYING)

    def test_world_is_frozen_while_paused(self):
        press(self.game, pygame.K_ESCAPE)
        before = (self.game.elapsed_seconds, [(e.x, e.y) for e in self.game.enemies],
                  self.game.player.weapons.levels.copy())
        for _ in range(20):
            self.game.update(0.1)
        after = (self.game.elapsed_seconds, [(e.x, e.y) for e in self.game.enemies],
                 self.game.player.weapons.levels.copy())
        self.assertEqual(before, after)

    def test_resume_button(self):
        press(self.game, pygame.K_ESCAPE)
        click(self.game, self.game.btn_resume)
        self.assertEqual(self.game.state, GameState.PLAYING)

    def test_restart_button_resets_the_run(self):
        press(self.game, pygame.K_ESCAPE)
        self.game.kill_count = 12
        click(self.game, self.game.btn_restart)
        self.assertEqual(self.game.state, GameState.PLAYING)
        self.assertEqual(self.game.elapsed_seconds, 0.0)
        self.assertEqual(self.game.kill_count, 0)
        self.assertEqual(self.game.stage_index, 0)

    def test_main_menu_button(self):
        press(self.game, pygame.K_ESCAPE)
        click(self.game, self.game.btn_main_menu)
        self.assertEqual(self.game.state, GameState.MAIN_MENU)

    def test_debug_keys_are_ignored_while_paused(self):
        press(self.game, pygame.K_ESCAPE)
        debug_before, demo_before = self.game.show_debug, self.game.demo_mode
        press(self.game, pygame.K_F3)
        press(self.game, pygame.K_F4)
        self.assertEqual((self.game.show_debug, self.game.demo_mode), (debug_before, demo_before))

    def test_stage3_debug_keys_still_work_while_playing(self):
        before = self.game.show_debug
        press(self.game, pygame.K_F3)
        self.assertNotEqual(self.game.show_debug, before)


class LevelUpWhilePausedTest(unittest.TestCase):
    def setUp(self):
        self.game = Game()
        self.game.player.pending_level_ups = 1
        self.game.trigger_level_up()
        self.assertTrue(self.game.is_level_up)

    def test_cards_cannot_be_picked_while_paused(self):
        press(self.game, pygame.K_ESCAPE)
        self.assertEqual(self.game.state, GameState.PAUSED)
        press(self.game, pygame.K_1)
        pygame.event.clear()
        pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                                             pos=self.game.upgrade_rects[0].center))
        self.game.handle_events()
        self.assertTrue(self.game.is_level_up)
        self.assertEqual(self.game.player.pending_level_ups, 1)

    def test_cards_work_again_after_resume(self):
        press(self.game, pygame.K_ESCAPE)
        press(self.game, pygame.K_ESCAPE)
        press(self.game, pygame.K_1)
        self.assertFalse(self.game.is_level_up)


class GameOverAndVictoryTest(unittest.TestCase):
    """stage3 added a victory screen; the menus must not break it."""

    def test_escape_quits_on_game_over_instead_of_pausing(self):
        game = Game()
        game.is_game_over = True
        press(game, pygame.K_ESCAPE)
        self.assertFalse(game.is_running)
        self.assertEqual(game.state, GameState.PLAYING)

    def test_escape_on_victory_returns_to_the_main_menu(self):
        game = Game()
        game.is_victory = True
        press(game, pygame.K_ESCAPE)
        self.assertTrue(game.is_running)
        self.assertEqual(game.state, GameState.MAIN_MENU)

    def test_enter_and_the_button_return_to_the_main_menu_on_victory(self):
        game = Game()
        game.is_victory = True
        press(game, pygame.K_RETURN)
        self.assertEqual(game.state, GameState.MAIN_MENU)
        game = Game()
        game.is_victory = True
        click(game, game.btn_victory_menu)
        self.assertEqual(game.state, GameState.MAIN_MENU)

    def test_victory_button_is_inactive_while_still_playing(self):
        game = Game()
        click(game, game.btn_victory_menu)
        self.assertEqual(game.state, GameState.PLAYING)
        press(game, pygame.K_RETURN)
        self.assertEqual(game.state, GameState.PLAYING)

    def test_r_restarts_after_game_over_and_victory(self):
        for flag in ("is_game_over", "is_victory"):
            with self.subTest(flag=flag):
                game = Game()
                setattr(game, flag, True)
                press(game, pygame.K_r)
                self.assertFalse(getattr(game, flag))
                self.assertEqual(game.state, GameState.PLAYING)


class StageSelectTest(unittest.TestCase):
    def test_there_is_one_card_per_stage_and_all_fit_on_screen(self):
        game = open_stage_select()
        self.assertEqual(len(game.stage_card_rects), len(STAGES))
        self.assertEqual(len(game.stage_card_rects), 3)
        screen = pygame.Rect(0, 0, 1000, 700)
        for rect in game.stage_card_rects:
            self.assertTrue(screen.contains(rect))
        for a, b in zip(game.stage_card_rects, game.stage_card_rects[1:]):
            self.assertFalse(a.colliderect(b))
        self.assertEqual(len(game.stage_previews), 3)

    def test_clicking_a_card_starts_that_stage_fresh(self):
        for index in range(3):
            with self.subTest(stage=index + 1):
                game = open_stage_select()
                game.elapsed_seconds, game.kill_count = 99.0, 7
                click_at(game, game.stage_card_rects[index].center)
                self.assertEqual(game.state, GameState.PLAYING)
                self.assertEqual(game.stage_index, index)
                self.assertEqual(game.selected_stage, index)
                self.assertEqual((game.elapsed_seconds, game.kill_count), (0.0, 0))
                self.assertFalse(game.is_victory or game.is_game_over)
                game.update(0.1)
                self.assertGreater(game.elapsed_seconds, 0)

    def test_number_keys_pick_a_stage(self):
        for index, key in enumerate((pygame.K_1, pygame.K_2, pygame.K_3)):
            with self.subTest(key=key):
                game = open_stage_select()
                press(game, key)
                self.assertEqual((game.state, game.stage_index), (GameState.PLAYING, index))

    def test_other_keys_and_misses_do_nothing(self):
        game = open_stage_select()
        press(game, pygame.K_4)
        press(game, pygame.K_F5)
        click_at(game, (5, 5))
        self.assertEqual(game.state, GameState.STAGE_SELECT)
        self.assertEqual(game.enemies, [])

    def test_escape_and_the_back_button_return_to_the_main_menu(self):
        game = open_stage_select()
        press(game, pygame.K_ESCAPE)
        self.assertEqual(game.state, GameState.MAIN_MENU)
        game = open_stage_select()
        click(game, game.btn_stage_back)
        self.assertEqual(game.state, GameState.MAIN_MENU)

    def test_cards_show_the_stage_details(self):
        game = open_stage_select()
        game.render()           # must not raise; also exercises boss and no-boss cards
        self.assertFalse(STAGES[0]().boss_type)
        self.assertTrue(STAGES[1]().boss_type and STAGES[2]().boss_type)

    def test_restart_from_the_pause_menu_replays_the_chosen_stage(self):
        game = open_stage_select()
        press(game, pygame.K_3)
        press(game, pygame.K_ESCAPE)
        click(game, game.btn_restart)
        self.assertEqual((game.state, game.stage_index), (GameState.PLAYING, 2))
        self.assertEqual(game.elapsed_seconds, 0.0)

    def test_r_after_game_over_replays_the_chosen_stage(self):
        game = open_stage_select()
        press(game, pygame.K_2)
        game.is_game_over = True
        press(game, pygame.K_r)
        self.assertEqual((game.is_game_over, game.stage_index), (False, 1))

    def test_after_the_main_menu_another_stage_can_be_chosen(self):
        game = open_stage_select()
        press(game, pygame.K_3)
        press(game, pygame.K_ESCAPE)
        click(game, game.btn_main_menu)
        self.assertEqual(game.state, GameState.MAIN_MENU)
        click(game, game.btn_start)
        press(game, pygame.K_1)
        self.assertEqual((game.state, game.stage_index, game.selected_stage), (GameState.PLAYING, 0, 0))


class WinAndReturnToMenuTest(unittest.TestCase):
    """The whole loop: pick a stage, survive its time, win, land on the main menu."""

    def test_win_a_stage_then_pick_another(self):
        game = open_stage_select()
        press(game, pygame.K_1)
        game.player.hp = game.player.max_hp = 10 ** 6
        game.elapsed_seconds = game.current_stage.duration - 0.05
        game.update(0.1)
        self.assertTrue(game.is_victory)
        game.render()
        press(game, pygame.K_ESCAPE)
        self.assertEqual(game.state, GameState.MAIN_MENU)
        click(game, game.btn_start)
        press(game, pygame.K_2)
        self.assertEqual((game.state, game.stage_index), (GameState.PLAYING, 1))
        self.assertFalse(game.is_victory)
        self.assertEqual(game.elapsed_seconds, 0.0)

    def test_every_stage_is_won_after_twenty_minutes(self):
        for index in range(3):
            with self.subTest(stage=index + 1):
                game = open_stage_select()
                press(game, pygame.K_1 + index)
                game.player.hp = game.player.max_hp = 10 ** 6
                if game.current_stage.boss_type:
                    game.spawn_boss()
                    for head in getattr(game.boss, "heads", None) or [game.boss]:
                        head.hp = 0
                    game.update(0)
                self.assertFalse(game.is_victory)
                game.elapsed_seconds = game.stage_start_seconds + 20 * 60 - 0.05
                game.update(0.1)
                self.assertTrue(game.is_victory)


class HandControlGateTest(unittest.TestCase):
    """A held fist restarts a finished run, but must not fire behind a menu."""

    def fist_game(self, state):
        game = Game()
        game.is_game_over = True
        game.hand.status = "tracking"
        game.hand.landmarks = [(0.5, 0.5)] * 21
        game.hand.fist = True
        game.state = state
        return game

    def test_fist_does_nothing_while_paused_or_in_menu(self):
        for state in (GameState.PAUSED, GameState.MAIN_MENU, GameState.STAGE_SELECT):
            with self.subTest(state=state):
                game = self.fist_game(state)
                for _ in range(40):
                    game.update_hand_menus(0.1)
                self.assertTrue(game.is_game_over)
                self.assertEqual(game.hand_hold, 0.0)

    def test_fist_still_restarts_while_playing(self):
        game = self.fist_game(GameState.PLAYING)
        for _ in range(40):
            game.update_hand_menus(0.1)
        self.assertFalse(game.is_game_over)


class RenderSmokeTest(unittest.TestCase):
    def test_every_screen_renders(self):
        game = Game(start_in_menu=True)
        game.render()                                  # main menu
        game.state = GameState.PLAYING
        game.render()                                  # gameplay
        game.state = GameState.PAUSED
        game.render()                                  # pause overlay
        game.is_game_over = True
        game.render()                                  # pause over game over
        game.is_game_over, game.is_victory = False, True
        game.render()                                  # pause over victory
        game.state = GameState.MAIN_MENU
        game.render()
        game.state = GameState.STAGE_SELECT
        game.render()                                  # stage select
        game.state = GameState.PLAYING
        game.is_victory = True
        game.render()                                  # victory with its Main Menu button

    def test_menus_render_without_artwork(self):
        game = Game(start_in_menu=True)
        game.menu_bg = game.stage_bg = None
        game.card_frame = game.card_frame_hover = None
        game.stage_card = game.stage_card_hover = None
        for button in (game.btn_start, game.btn_quit, game.btn_resume, game.btn_restart,
                       game.btn_main_menu, game.btn_stage_back, game.btn_victory_menu):
            button.image = None
        game.render()
        game.state = GameState.STAGE_SELECT
        game.render()
        game.state = GameState.PAUSED
        game.render()
        game.state = GameState.PLAYING
        game.is_victory = True
        game.render()


class PlayerDamageNumberTest(unittest.TestCase):
    def test_player_hit_shows_a_damage_number(self):
        game = Game()
        shown = []
        game.effects.damage = lambda x, y, amount, colour=None: shown.append((amount, colour))
        enemy = game.add_enemy("TA", game.player.x, game.player.y)
        enemy.hp = 10 ** 6          # survive the starting weapon so contact damage happens
        game.update(0.016)
        hp_lost = game.player.max_hp - game.player.hp
        self.assertGreater(hp_lost, 0)
        self.assertIn((hp_lost, (255, 70, 70)), shown)


if __name__ == "__main__":
    unittest.main()
