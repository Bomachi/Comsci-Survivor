# Comsci Survivor

A Pygame survival game for our university team project.

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Move with **WASD / arrow keys**. Weapons attack automatically. Pick a level-up
card with the mouse or **1 / 2 / 3**. Press **R** after defeat to restart, or
**Esc** to quit.

## Stages

| Stage | Length | Enemies |
| --- | --- | --- |
| 1: Ancient Cemetery | 3 minutes, then Stage 2 | TA, professor, rector |
| 2: Accounting Faculty / ด่านบุกคณะบัญชี | Boss at 2:30, beat it to enter Stage 3 | Accounting students and the Chief Auditor |
| 3: AI Data Center / ศูนย์ข้อมูล AI | Boss at 3:00, destroy all three heads to win | ChatGPT robots, Claude Code creatures, Gemini robots and the AI Overlord Hydra |

Clearing Stage 1 keeps your level and weapons, restores 30 HP and clears the
field. Stage 2 enemies give more EXP:

| Enemy | Behavior |
| --- | --- |
| Accounting Freshman / หนุ่มบัญชีปี 1 | Fast, weak, crowds surround you; crouches then lunges when close |
| Calculator Thrower / สายเครื่องคิดเลข | Keeps about 240 px away, strafes, and leads its calculator throws (12 damage) |
| Accounting Senior / รุ่นพี่บัญชี | Slow, tanky, heavy contact damage |
| The Chief Auditor / ประธานตรวจสอบบัญชี (boss) | 3200 HP. State machine: chase, coin ring, telegraphed dash (red line) and summoning freshmen; below 50% HP it attacks faster with 16 coins. Drops EXP and food |

Enemy shots use the same 0.75-second hit grace as contact damage. Practice
Stage 2 directly with `python main.py --stage 2` (starts at level 12 with
Enter Key L4, Project Books L3, LAN Whip L3).

### Stage 3: AI Data Center

Defeating the Chief Auditor keeps the same player, level, EXP and weapons,
restores 30 HP (up to maximum), and clears enemies, shots and combat effects.
Stage 3 has dark circuit floors, server racks and computer consoles. Its layout
is deterministic, with open aisles and the existing flow-field pathfinding.

Enemies spawn every **0.40 seconds**, compared with Stage 2's 0.55 seconds.
The normal crowd cap remains 120; while the boss lives, the spawn interval is
multiplied by 1.6 as in Stage 2. Enemy shot damage shares the existing
0.75-second hit grace with contact damage.

| Enemy | HP / contact damage / EXP | Behavior |
| --- | --- | --- |
| ChatGPT robot | 110 / 16 / 4 | Keeps about 260 px away; fires one predictive token shot (14 damage, 150 px/s) every 3.5 seconds; first shot is delayed by 1.75–3.5 seconds |
| Claude Code creature | 90 / 18 / 4 | Fast blocky orange attacker; warns for 0.4 seconds before lunging along a locked direction |
| Gemini robot | 180 / 24 / 7 | Warns for 0.6 seconds, then fires eight stars (16 damage each); repeats every 3 seconds |

Spawn proportions (ChatGPT / Claude / Gemini) are **35/65/0%** before 0:45,
**25/55/20%** from 0:45 to 1:45, and **20/50/30%** thereafter.

The **AI Overlord Hydra** appears once at 3:00. Each head has **1,800 HP**:

- **ChatGPT:** a seven-shot token fan, 18 damage per shot.
- **Claude:** an aimed body charge, 32 contact damage.
- **Gemini:** a sixteen-star ring, 18 damage per shot.

Living heads take turns, with a **0.8-second warning** before strong attacks.
Move around the boss to aim automatic weapons at the nearest living head or
enemy. Every weapon can damage heads; area attacks can hit several heads.
Heads stay attached during knockback, one Wi-Fi pulse pushes the body once,
and Bug Army slow affects the body.

Destroyed heads disappear permanently and cannot attack or be targeted again.
Severing a head interrupts its pending attack; shots already fired remain until
they expire. The remaining heads' rest interval falls to **85%** with two heads
and **70%** with one. Three separate named health bars show progress. Only the
final defeat counts as one boss kill and drops boss loot; defeating all three
heads wins the campaign.

Practice directly with:

```powershell
.\.venv\Scripts\python.exe main.py --stage 3
```

This starts at level 20 with Enter Key L5, Project Books L5 and LAN Whip L5.
Restart returns to Stage 1, as it does in Stage 2 practice. Keyboard and optional
hand controls are unchanged.

New sprites live in `assets/sprites/ai/`. Characters, the hydra body and props
were made with the built-in image generation tool using the supplied references;
head artwork uses those references. Prompts and provenance are recorded in that
folder's `prompts.json`. The game trims transparent margins and preserves aspect
ratios when loading them. Renderer previews: `docs/stage3_look.png` and
`docs/stage3_heads.png`.

## Debug overlay and CS systems

Press **F3** in game to show the debug overlay: FPS, frame time, collision pair
checks, the spatial-hash grid, hit circles and the boss state machine.
**F2** switches crowd separation between the spatial hash and the naive
O(n²) method, **F4** toggles invincibility while automatic weapons keep firing,
and **F5** adds 300 enemies for a stress test. Press F4 again to disable
invincibility and resume taking damage after the existing hit grace expires.

- `spatial.py`: uniform-grid spatial hash for enemy separation (~O(n)).
  Benchmark: `python benchmarks/collision_benchmark.py`.
- `accounting.py` `BossBrain`: the Chief Auditor's finite state machine
  (CHASE, AUDIT, AIM, CHARGE, RECOVER, SUMMON).
- `pathfinding.py`: obstacle map and a BFS flow field so enemies walk around desks.
- `animation.py`: procedural walk bob, shadows, hit flash, death particles, damage numbers.
- `stage_art.py`: Stage 2 marble floor, props placed per chunk (deterministic), vignette.
- `docs/PRESENTATION.md`: talking points, demo order, benchmark results and diagrams.

## Hand control (webcam, optional)

Run `install_hand.bat` once (installs MediaPipe and downloads the 8 MB hand
model), then press **F7** in game.

| Gesture | Effect |
| --- | --- |
| Point with the index finger (other fingers folded) | Walk where the finger points |
| Fist or open hand | Stand still |
| Level-up: point at a card, then hold a fist 0.6 s | Pick that card |
| Game over / victory: hold a fist 1.2 s | Restart |

The keyboard always wins over hand input. Code: `hand_control.py`.

## Weapons and items

Start with Enter Key. Equip at most **three weapon types**, each upgradable to
**level 5**. Once slots are full, cards only upgrade equipped weapons. At maximum
levels, Study Break restores 25 HP so later level-ups still have a valid choice.

| Weapon | Behavior | Upgrades |
| --- | --- | --- |
| Enter Key / ปุ่ม Enter พิฆาต | Aims at the nearest living enemy | Damage, rate, multishot at L3/L5, piercing at L4 |
| Project Books / เล่มโปรเจกต์มหาประลัย | Books orbit the player; contact damage has a short cooldown | Damage, orbit speed/reach, more books at L3/L5 |
| LAN Whip / สาย LAN ฟาดเกรด | Sweeps toward the nearest enemy, hitting multiple targets | Damage, rate, length/width, second sweep at L4 |
| Bug Army / กองทัพ Bug | Homing bugs explode on contact | Damage, rate, count, blast radius, slow at L3 |
| Dept. Wi-Fi / Wi-Fi ภาควิชา | Circular damage pulse with knockback | Damage, rate, radius and push strength |
| Recursion / Recursion ไม่รู้จบ | Braces split into smaller projectiles on impact | Damage, rate, third child at L3, second generation at L4 |

- **Coffee / กาแฟคืนก่อนเดดไลน์:** 8% drop chance per kill. Walk over it for
  +25% attack frequency (+25% orbit speed for books) and +15% movement speed
  for 10 seconds. Another cup refreshes duration without stacking strength.
  The HUD shows remaining time; uncollected cups expire after 20 seconds.
- **EXP:** each enemy drops a gem; nearby gems move toward the player.
  Collected EXP grants level-up choices. Multiple earned choices are queued.
- **Supply crates / กล่องอาหาร:** crates are scattered throughout the map, with
  the first visible to the right of the starting position. Touch a crate and
  stand still for **5 continuous gameplay seconds** to open it. Moving or leaving
  resets progress. Enemies keep attacking; the upgrade menu pauses the timer.
  A progress bar appears above the crate. Each crate opens once per run and drops
  food beside it. Walk over food to restore **30 HP**, capped at maximum HP.
  Food stays on the ground when HP is full and does not expire or use a weapon
  slot. Restart creates fresh crates and clears food. The user-supplied food image
  is stored unchanged in `assets/sprites/items/food.png`.
- Pickups use no weapon slots. Gameplay, coffee and combat timers pause while
  the upgrade menu is open. Restart clears the loadout and buffs.
- Values are initial balancing values. Weapon and pickup artwork uses transparent
  PNG sprites in `assets/sprites/items/`, shared by cards, the HUD and combat.
  The Enter key is the user-supplied image; the matching sprites were generated
  with the built-in image generation tool. Prompts are saved in that folder.

## Team integration

- `weapons.py`: weapon catalog, loadout limits, combat, projectiles and effects.
  Use `player.weapons.upgrade(id)` to enforce slot/level limits.
- `upgrades.py`: eligible cards and upgrade application.
- `main.py`: the `Game` class - game loop, stages, spawning, combat and pickups.
- `entities.py`: `Player`, `Enemy`, `Gem` and `Coffee`.
- `ui.py`: `GameState`, `Button`, main menu, stage select and pause menu.
- `hud.py`: HUD, boss bars, level-up cards, game over and victory screens.
- `debug_view.py`: the F3 debug overlay. `hand_ui.py`: hand-control menus and camera preview.
- `settings.py`: window size, FPS and colours. `resources.py`: image loading.
- `supplies.py`: map crate placement, continuous opening timer and healing food.
- `item_art.py`: loads artwork relative to the project, preserves aspect ratio,
  and caches scaled images and rotations. Replace the corresponding PNG in
  `assets/sprites/items/` and restart the game to change an icon.
- All movement and combat timers use seconds (`dt`), with a 0.1-second clamp
  for long window stalls. Contact damage has a 0.75-second grace period.
- Keep the same `Player` when adding stage transitions to preserve EXP, level
  and weapon levels. Clear transient weapon projectiles/effects on transition.
- `stages/`: each stage sets its spawn table, length, tile, spawn interval and
  optional boss. `stages.STAGES` is the play order; `Game.start_stage()` moves
  to a stage while keeping the player.
- `accounting.py`: enemy projectiles, ranged enemy fire and the Chief Auditor's
  attack pattern.
- `ai_enemies.py`: AI projectiles, enemy attacks and the hydra's head targets,
  attack state machine and multipart rendering. `Game.combat_targets()` exposes
  living heads to weapons without adding them to crowd separation or loot.
- Stage metadata includes `boss_name`, `scenery_theme` and `victory_text` so
  scenery, banners and the victory screen follow the current stage.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests use SDL's dummy display/audio drivers and do not open a game window.

Stage 3 tests cover campaign transitions, spawn phases, attack warnings and
frame-rate consistency, all six weapons against independent heads, piercing,
homing, AoE/knockback, severed-head interruption, pause/restart, boss loot,
scenery and a full 185-second simulation.

Known pre-existing baseline failure: `test_healing_cap_full_health_and_distance`
in `test_supplies.py` expects food to remain when HP is full, but the existing
supply code consumes it. This is independent of Stage 3.
