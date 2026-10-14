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
- `main.py`: pickups, player/enemy updates, game loop and UI.
- `item_art.py`: loads artwork relative to the project, preserves aspect ratio,
  and caches scaled images and rotations. Replace the corresponding PNG in
  `assets/sprites/items/` and restart the game to change an icon.
- All movement and combat timers use seconds (`dt`), with a 0.1-second clamp
  for long window stalls. Contact damage has a 0.75-second grace period.
- Keep the same `Player` when adding stage transitions to preserve EXP, level
  and weapon levels. Clear transient weapon projectiles/effects on transition.
  This branch currently implements Stage 1; bosses and stage transitions are
  separate future work.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests use SDL's dummy display/audio drivers and do not open a game window.
