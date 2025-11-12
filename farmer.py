#!/usr/bin/env python3
"""
Top-down 2D RPG demo using Pygame.
Single-file demo with:
 - Three areas: Village -> Forest -> Castle (different colored maps)
 - Player movement (arrow keys / WASD)
 - NPC interaction (help spirit or not)
 - Items to pick up (potions, charm)
 - Inventory screen (I)
 - Collision-triggered turn-based combat screen
 - Branching final choice at Castle with 3 endings (GOOD / NEUTRAL / BAD)
 - Simple sprites drawn programmatically (no external assets)
 - Beginner-friendly, commented code.

Run:
    python topdown_rpg_pygame.py
"""

import pygame
import random
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# ---- Configuration ----
SCREEN_WIDTH = 960
SCREEN_HEIGHT = 640
FPS = 60

TILE_SIZE = 32
PLAYER_SPEED = 160  # pixels per second

FONT_NAME = "freesansbold.ttf"

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
VILLAGE_BG = (200, 230, 200)
FOREST_BG = (40, 80, 40)
CASTLE_BG = (180, 180, 210)
PLAYER_COLOR = (60, 130, 200)
NPC_COLOR = (220, 200, 60)
ENEMY_COLOR = (200, 60, 60)
ITEM_COLOR = (200, 120, 200)
HIGHLIGHT = (255, 220, 60)

# ---- Game Data Models ----

@dataclass
class Item:
    name: str
    description: str

@dataclass
class PlayerState:
    name: str = "Hero"
    pclass: str = "Warrior"
    strength: int = 8
    agility: int = 5
    magic: int = 2
    max_hp: int = 40
    hp: int = 40
    max_mp: int = 10
    mp: int = 10
    inventory: List[Item] = field(default_factory=list)
    gold: int = 10
    helped_spirit: bool = False
    has_charm: bool = False

@dataclass
class GameObject:
    x: float
    y: float
    w: int
    h: int
    name: str

    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

# ---- Utilities ----

def draw_text(surface, text, x, y, size=20, color=BLACK, center=False):
    font = pygame.font.Font(FONT_NAME, size)
    rendered = font.render(text, True, color)
    rect = rendered.get_rect()
    if center:
        rect.center = (x, y)
    else:
        rect.topleft = (x, y)
    surface.blit(rendered, rect)

def clamp(n, a, b):
    return max(a, min(b, n))

# ---- Scenes / Maps ----

class MapScene:
    """
    Basic scene class. Subclass for Village, Forest, Castle.
    Each scene can provide:
    - background color
    - obstacles (rects)
    - NPCs, items, enemies (GameObject list)
    """
    def __init__(self, name, bg_color):
        self.name = name
        self.bg_color = bg_color
        self.obstacles: List[pygame.Rect] = []  # blocks movement
        self.npcs: List[GameObject] = []
        self.items: List[Tuple[GameObject, Item]] = []
        self.enemies: List[GameObject] = []
        self.width = SCREEN_WIDTH
        self.height = SCREEN_HEIGHT

    def draw(self, surf):
        surf.fill(self.bg_color)
        # draw obstacles
        for r in self.obstacles:
            pygame.draw.rect(surf, (80, 80, 80), r)
        # draw items
        for go, it in self.items:
            pygame.draw.rect(surf, ITEM_COLOR, go.rect())
            draw_text(surf, it.name, go.x, go.y - 16, size=14)
        # draw npcs
        for npc in self.npcs:
            pygame.draw.rect(surf, NPC_COLOR, npc.rect())
            draw_text(surf, npc.name, npc.x, npc.y - 16, size=14)
        # draw enemies
        for en in self.enemies:
            pygame.draw.rect(surf, ENEMY_COLOR, en.rect())
            draw_text(surf, en.name, en.x, en.y - 16, size=14)

# ---- Scenes constructors ----

def create_village_scene():
    s = MapScene("Village", VILLAGE_BG)
    # Add a shop building obstacle
    s.obstacles.append(pygame.Rect(120, 80, 220, 140))
    s.obstacles.append(pygame.Rect(600, 60, 260, 160))
    # NPC: elder for tutorial
    s.npcs.append(GameObject(480, 300, 28, 32, "Elder"))
    # No enemies here; add an item chest
    s.items.append((GameObject(200, 420, 24, 24, "Chest"), Item("Small Potion", "Heals 20 HP")))
    return s

def create_forest_scene():
    s = MapScene("Forest", FOREST_BG)
    # Scatter obstacles (trees)
    for i in range(8):
        rx = 40 + i * 100
        ry = 40 + (i % 3) * 120
        s.obstacles.append(pygame.Rect(rx, ry, 48, 80))
    # Spirit NPC
    s.npcs.append(GameObject(720, 120, 28, 32, "Trapped Spirit"))
    # enemies (patrolling positions)
    s.enemies.append(GameObject(300, 240, 28, 28, "Goblin"))
    s.enemies.append(GameObject(500, 420, 28, 28, "Bandit"))
    # an extra item
    s.items.append((GameObject(100, 520, 24, 24, "Glint"), Item("Lucky Charm", "Feels lucky. Small heal + gold.")))
    return s

def create_castle_scene():
    s = MapScene("Castle", CASTLE_BG)
    # Large wall obstacle
    s.obstacles.append(pygame.Rect(0, 100, SCREEN_WIDTH, 40))
    # guard (bandit)
    s.enemies.append(GameObject(420, 160, 36, 36, "Bandit Leader"))
    # Inner guardian (placed near center; interaction will start final event)
    s.npcs.append(GameObject(480, 320, 48, 60, "Ancient Guardian"))
    # Castle item (key)
    s.items.append((GameObject(200, 200, 24, 24, "Banner"), Item("Spirit Charm", "A charm granted by a grateful spirit.")))
    return s

# ---- Combat system (turn-based visual) ----

class CombatScreen:
    """
    Minimal turn-based combat screen. Uses player's stats and a simple enemy stat model.
    Displayed when player collides an enemy.
    Controls: keys A=Attack, D=Defend, M=Magic, I=Use Item, F=Flee
    """
    def __init__(self, screen, clock, player: PlayerState, enemy_name: str):
        self.screen = screen
        self.clock = clock
        self.player = player
        self.enemy_name = enemy_name
        # enemy stats simple factory
        self.enemy = self.make_enemy(enemy_name)
        self.log: List[str] = []
        self.player.defending = False  # temp field used in combat only
        self.finished = False
        self.victory = False

    def make_enemy(self, name):
        if name == "Goblin":
            return {"name": "Goblin", "hp": 20, "str": 4, "agi": 3, "lvl": 1}
        if name == "Bandit" or name == "Bandit Leader":
            return {"name": "Bandit Leader", "hp": 30, "str": 6, "agi": 4, "lvl": 2}
        if name == "Ancient Guardian":
            return {"name": "Ancient Guardian", "hp": 70, "str": 10, "agi": 3, "lvl": 5}
        # default wolf
        return {"name": "Wolf", "hp": 18, "str": 5, "agi": 5, "lvl": 1}

    def append(self, text):
        print("[COMBAT]", text)
        self.log.append(text)
        if len(self.log) > 9:
            self.log.pop(0)

    def draw(self):
        # background and UI
        self.screen.fill((30, 30, 40))
        draw_text(self.screen, f"Combat: {self.player.name} vs {self.enemy['name']}", SCREEN_WIDTH//2, 20, size=28, color=WHITE, center=True)
        # player box
        pygame.draw.rect(self.screen, (50, 100, 150), (60, 80, 360, 220))
        draw_text(self.screen, f"{self.player.name} ({self.player.pclass})", 120, 92, size=20, color=WHITE)
        draw_text(self.screen, f"HP: {self.player.hp}/{self.player.max_hp}", 120, 120, size=18, color=WHITE)
        draw_text(self.screen, f"MP: {self.player.mp}/{self.player.max_mp}", 120, 148, size=18, color=WHITE)
        # enemy box
        pygame.draw.rect(self.screen, (140, 50, 50), (540, 80, 360, 220))
        draw_text(self.screen, f"{self.enemy['name']}", 640, 92, size=20, color=WHITE)
        draw_text(self.screen, f"HP: {self.enemy['hp']}", 640, 120, size=18, color=WHITE)

        # actions hint
        draw_text(self.screen, "Actions: [A]ttack  [D]efend  [M]agic  [I]tem  [F]lee", SCREEN_WIDTH//2, 320, size=20, center=True)

        # combat log
        for i, line in enumerate(self.log):
            draw_text(self.screen, line, 60, 360 + i * 22, size=18, color=WHITE)

        pygame.display.flip()

    def player_attack(self):
        crit = random.random() < (0.05 + self.player.agility * 0.01)
        base = 3 + self.player.strength
        dmg = base + random.randint(0, 4)
        if crit:
            dmg = int(dmg * 1.5)
            self.append("Critical hit!")
        self.enemy['hp'] -= dmg
        self.append(f"You attack for {dmg} damage.")

    def player_magic(self):
        cost = 6
        if self.player.mp < cost:
            self.append("Not enough MP.")
            return
        self.player.mp -= cost
        dmg = self.player.magic + 4 + random.randint(0, 6)
        self.enemy['hp'] -= dmg
        self.append(f"You cast a spell for {dmg} magic damage.")

    def player_defend(self):
        self.player.defending = True
        self.append("You brace to reduce incoming damage.")

    def player_use_item(self):
        # pick first usable item: Small Potion, Mana Potion, Lucky Charm, Spirit Charm
        if not self.player.inventory:
            self.append("No items to use.")
            return
        # open a tiny selection logic: use first restorative item found
        for i, it in enumerate(self.player.inventory):
            if it.name == "Small Potion":
                self.player.hp = clamp(self.player.max_hp, self.player.hp + 20, self.player.max_hp)
                self.append("Used Small Potion. Healed 20 HP.")
                self.player.inventory.pop(i)
                return
            if it.name == "Mana Potion":
                self.player.mp = clamp(self.player.mp + 12, 0, self.player.max_mp)
                self.append("Used Mana Potion. Restored MP.")
                self.player.inventory.pop(i)
                return
            if it.name == "Lucky Charm":
                self.player.hp = min(self.player.max_hp, self.player.hp + 8)
                self.player.gold += 5
                self.append("Lucky Charm used: HP +8, Gold +5.")
                self.player.inventory.pop(i)
                return
            if it.name == "Spirit Charm":
                self.player.has_charm = True
                self.append("Spirit Charm hums; you feel protected.")
                self.player.inventory.pop(i)
                return
        # nothing used
        self.append("No usable items found right now.")

    def enemy_turn(self):
        if self.enemy['hp'] <= 0:
            return
        # simple enemy action
        hit_chance = 0.7 - (self.player.agility * 0.01)
        if random.random() < hit_chance:
            dmg = self.enemy['str'] + random.randint(0, 3)
            if getattr(self.player, "defending", False):
                dmg = dmg // 2
            self.player.hp -= dmg
            self.append(f"{self.enemy['name']} hits you for {dmg} damage.")
        else:
            self.append(f"{self.enemy['name']} misses!")

    def attempt_flee(self):
        chance = 0.35 + self.player.agility * 0.02
        if random.random() < chance:
            self.append("You fled successfully.")
            self.finished = True
            self.victory = False
        else:
            self.append("Flee failed!")
            self.enemy_turn()

    def run(self):
        # main loop for combat; returns dict with outcome
        while not self.finished:
            dt = self.clock.tick(FPS) / 1000.0
            self.draw()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_a:
                        self.player_attack()
                    elif event.key == pygame.K_m:
                        self.player_magic()
                    elif event.key == pygame.K_d:
                        self.player_defend()
                    elif event.key == pygame.K_i:
                        self.player_use_item()
                    elif event.key == pygame.K_f:
                        self.attempt_flee()
                    else:
                        continue
                    # after player action, check enemy dead
                    if self.enemy['hp'] <= 0:
                        self.append(f"You defeated the {self.enemy['name']}!")
                        self.player.gold += self.enemy['lvl'] * 5
                        # simple loot: chance to drop small potion or mana potion
                        if random.random() < 0.6:
                            drop = Item("Small Potion", "Heals 20 HP")
                            self.player.inventory.append(drop)
                            self.append("Enemy dropped Small Potion.")
                        self.finished = True
                        self.victory = True
                        break
                    # enemy gets a turn
                    self.enemy_turn()
                    # reset defend flag
                    self.player.defending = False
                    # check player death
                    if self.player.hp <= 0:
                        self.append("You were defeated...")
                        self.finished = True
                        self.victory = False
                        break
        # exit combat loop
        return {"victory": self.victory, "fled": (not self.victory and self.enemy['hp']>0 and self.finished)}

# ---- Main Game class ----

class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Top-down RPG (Pygame Demo)")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.running = True
        self.scene_index = 0
        self.scenes = [create_village_scene(), create_forest_scene(), create_castle_scene()]
        self.scene = self.scenes[self.scene_index]
        self.player_obj = GameObject(80, 80, 28, 36, "Player")
        # default PlayerState (lets user choose class at start)
        self.player_state = None  # will be set via create_player()
        # small UI flags
        self.show_inventory = False
        self.message = "Press N to create a character and start."
        self.show_help = True
        # seed randomness
        random.seed()

    def create_player(self):
        # Minimal terminal-driven selection (works even in window)
        # In a fuller version you'd implement GUI forms; here keep simple:
        name = "Hero"
        pclass = "Warrior"
        # interactive choice via console input isn't great in GUI; instead random or defaults
        # To keep it simple, present a small on-screen prompt choices (press 1/2/3)
        choosing = True
        while choosing:
            # display prompt and wait for key
            self.screen.fill((20, 20, 30))
            draw_text(self.screen, "Create your character", SCREEN_WIDTH//2, 80, size=36, color=WHITE, center=True)
            draw_text(self.screen, "Press 1 for Warrior, 2 for Mage, 3 for Rogue", SCREEN_WIDTH//2, 160, size=20, color=WHITE, center=True)
            pygame.display.flip()
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_1 or ev.key == pygame.K_KP1:
                        name = "Hero"
                        pclass = "Warrior"
                        choosing = False
                    elif ev.key == pygame.K_2 or ev.key == pygame.K_KP2:
                        name = "Aria"
                        pclass = "Mage"
                        choosing = False
                    elif ev.key == pygame.K_3 or ev.key == pygame.K_KP3:
                        name = "Shade"
                        pclass = "Rogue"
                        choosing = False
            self.clock.tick(FPS)

        # set stats depending on class
        ps = PlayerState()
        ps.name = name
        ps.pclass = pclass
        if pclass == "Warrior":
            ps.strength = 8; ps.agility = 5; ps.magic = 2; ps.max_hp = 40; ps.max_mp = 10
            ps.hp = ps.max_hp; ps.mp = ps.max_mp
            ps.inventory = [Item("Small Potion","Heals 20 HP"), Item("Lucky Charm","Small heal + gold")]
        elif pclass == "Mage":
            ps.strength = 2; ps.agility = 4; ps.magic = 9; ps.max_hp = 26; ps.max_mp = 30
            ps.hp = ps.max_hp; ps.mp = ps.max_mp
            ps.inventory = [Item("Mana Potion","Restore MP"), Item("Mana Potion","Restore MP")]
        elif pclass == "Rogue":
            ps.strength = 6; ps.agility = 8; ps.magic = 4; ps.max_hp = 32; ps.max_mp = 15
            ps.hp = ps.max_hp; ps.mp = ps.max_mp
            ps.inventory = [Item("Small Potion","Heals 20 HP"), Item("Dagger","A small blade")]
        ps.gold = 12
        self.player_state = ps
        self.message = f"Welcome, {ps.name} the {ps.pclass}! Use arrow keys/WASD to move. Press I for inventory. Press H to toggle help."
        return ps

    def world_to_scene(self, new_index):
        self.scene_index = new_index
        self.scene = self.scenes[self.scene_index]
        # reposition player near top-left for new map
        self.player_obj.x = 80
        self.player_obj.y = 80

    def handle_item_pickup(self, go_obj, item: Item):
        # add item to inventory and remove it from scene
        self.player_state.inventory.append(item)
        self.scene.items = [(g,i) for (g,i) in self.scene.items if g != go_obj]
        self.message = f"Picked up {item.name}!"

    def handle_npc_interaction(self, npc: GameObject):
        # Branch on scene and npc name
        if self.scene.name == "Village" and npc.name == "Elder":
            # simple dialog: offer small gold or advice
            self.message = "Elder: 'Training helps. Rest at the inn or buy potions.' (Press N to continue exploring.)"
        elif self.scene.name == "Forest" and npc.name == "Trapped Spirit":
            # choice: help or ignore
            chosen = self.ask_choice("A trapped spirit begs for help. Help it? (Y/N)")
            if chosen == 'Y':
                self.player_state.helped_spirit = True
                self.player_state.inventory.append(Item("Spirit Charm", "A protective charm"))
                self.player_state.has_charm = True
                self.message = "You freed the spirit. It grants you a Spirit Charm."
            else:
                # ignore -> get Lucky Charm later via an item already placed
                self.message = "You ignored the spirit. You feel uneasy."
        elif self.scene.name == "Castle" and npc.name == "Ancient Guardian":
            # final branching choice - handled elsewhere when reaching central area
            self.message = "The Ancient Guardian watches you. Press N to interact with Guardian."
        else:
            self.message = f"You talk to {npc.name}. They nod."

    def ask_choice(self, prompt_text) -> str:
        """Helper: display prompt and wait for Y or N press. Returns 'Y' or 'N'."""
        asking = True
        result = 'N'
        while asking:
            self.screen.fill((30, 30, 30))
            draw_text(self.screen, prompt_text, SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 20, size=28, color=WHITE, center=True)
            draw_text(self.screen, "Press Y or N", SCREEN_WIDTH//2, SCREEN_HEIGHT//2 + 30, size=20, color=WHITE, center=True)
            pygame.display.flip()
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit(); sys.exit(0)
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_y:
                        result = 'Y'; asking = False
                    elif ev.key == pygame.K_n:
                        result = 'N'; asking = False
            self.clock.tick(FPS)
        return result

    def transition_to_combat(self, enemy_obj: GameObject):
        # create and run combat screen, using enemy_obj.name
        cs = CombatScreen(self.screen, self.clock, self.player_state, enemy_obj.name)
        result = cs.run()
        # if victory, remove enemy from scene
        if result['victory']:
            self.scene.enemies = [e for e in self.scene.enemies if e != enemy_obj]
            self.message = f"Defeated {enemy_obj.name}."
        else:
            if result.get("fled", False):
                self.message = "You fled the combat."
            else:
                # player was defeated: end game
                self.message = "You were defeated..."
        # check for player death (hp <= 0)
        if self.player_state.hp <= 0:
            self.end_game("BAD", "You have fallen in battle.")
        return result

    def end_game(self, ending_type: str, detail: str):
        # show final message and stop running main loop
        self.message = f"=== Ending: {ending_type} === {detail}"
        # display an ending screen then stop
        self.display_ending_screen(ending_type, detail)
        self.running = False

    def display_ending_screen(self, typ, text):
        showing = True
        while showing:
            self.screen.fill((10, 10, 10))
            draw_text(self.screen, f"Ending: {typ}", SCREEN_WIDTH//2, 120, size=44, color=WHITE, center=True)
            draw_text(self.screen, text, SCREEN_WIDTH//2, 200, size=22, color=WHITE, center=True)
            draw_text(self.screen, "Press ESC to quit or R to restart.", SCREEN_WIDTH//2, 420, size=20, color=WHITE, center=True)
            pygame.display.flip()
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit(); sys.exit(0)
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        pygame.quit(); sys.exit(0)
                    if ev.key == pygame.K_r:
                        # restart whole app by re-running main game loop
                        showing = False
                        main()
            self.clock.tick(FPS)

    def final_guardian_event(self, guardian_obj: GameObject):
        # Player stands before Guardian; provide three options: Befriend / Fight / Trick
        # Show on-screen menu
        chosen = None
        while chosen is None:
            self.screen.fill((30,30,40))
            draw_text(self.screen, "The Ancient Guardian stands before you.", SCREEN_WIDTH//2, 80, size=28, color=WHITE, center=True)
            draw_text(self.screen, "[B]efriend   [F]ight   [T]rick", SCREEN_WIDTH//2, 160, size=24, color=WHITE, center=True)
            draw_text(self.screen, "Press the corresponding key to choose.", SCREEN_WIDTH//2, 220, size=18, color=WHITE, center=True)
            pygame.display.flip()
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit(); sys.exit(0)
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_b:
                        chosen = 'B'
                    elif ev.key == pygame.K_f:
                        chosen = 'F'
                    elif ev.key == pygame.K_t:
                        chosen = 'T'
            self.clock.tick(FPS)
        # Resolve choices
        if chosen == 'B':
            # require spirit charm or high magic
            if self.player_state.has_charm or self.player_state.magic >= 8:
                self.end_game("GOOD", "You spoke truly; the guardian accepts peace.")
            else:
                # fail, force combat
                self.message = "Your words fail. The Guardian attacks!"
                res = self.transition_to_combat(guardian_obj)
                if not res['victory']:
                    self.end_game("BAD", "You failed to subdue the Guardian.")
                else:
                    # if helped spirit earlier -> good, else neutral
                    if self.player_state.helped_spirit:
                        self.end_game("GOOD", "You defeated it and the land heals faster (you helped spirit earlier).")
                    else:
                        self.end_game("NEUTRAL", "You defeated it, but the cost was heavy.")
        elif chosen == 'F':
            res = self.transition_to_combat(guardian_obj)
            if not res['victory']:
                self.end_game("BAD", "The Guardian defeated you.")
            else:
                if self.player_state.helped_spirit:
                    self.end_game("GOOD", "You defeated the Guardian; the spirits aid recovery.")
                else:
                    self.end_game("NEUTRAL", "You won, but peace will take time.")
        elif chosen == 'T':
            chance = 0.25 + (self.player_state.agility * 0.03) + (self.player_state.magic * 0.02)
            if random.random() < chance:
                self.end_game("GOOD", "Your trick works and the Guardian steps aside.")
            else:
                self.message = "Trick failed; Guardian attacks!"
                res = self.transition_to_combat(guardian_obj)
                if not res['victory']:
                    self.end_game("BAD", "You were defeated while attempting a trick.")
                else:
                    self.end_game("NEUTRAL", "You prevailed but the victory feels hollow.")
        else:
            self.message = "You hesitated and the moment passed."

    # ---- Main game loop ----
    def run(self):
        # Create player first
        if not self.player_state:
            self.create_player()
        dt = 0
        while self.running:
            # handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_i:
                        self.show_inventory = not self.show_inventory
                    elif event.key == pygame.K_h:
                        self.show_help = not self.show_help
                    elif event.key == pygame.K_n:
                        # advance to next scene when on edges or interact with Guardian
                        # if at castle and near guardian, run final event
                        # check if near guardian in castle
                        if self.scene.name == "Castle":
                            # find guardian npc
                            for npc in self.scene.npcs:
                                if npc.name == "Ancient Guardian":
                                    if self.player_obj.rect().colliderect(npc.rect()):
                                        self.final_guardian_event(npc)
                                        break
                        # else advance scene
                        if self.scene_index < len(self.scenes) - 1:
                            self.world_to_scene(self.scene_index + 1)
                            self.message = f"Traveled to {self.scene.name}."
                    elif event.key == pygame.K_r:
                        # quick heal/test
                        self.player_state.hp = self.player_state.max_hp
                        self.player_state.mp = self.player_state.max_mp
                    elif event.key == pygame.K_ESCAPE:
                        self.running = False

            # movement handling
            keys = pygame.key.get_pressed()
            vx = vy = 0
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                vx = -1
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                vx = 1
            if keys[pygame.K_UP] or keys[pygame.K_w]:
                vy = -1
            if keys[pygame.K_DOWN] or keys[pygame.K_s]:
                vy = 1
            # normalize diagonal
            if vx != 0 and vy != 0:
                vx *= 0.7071; vy *= 0.7071
            # move with delta
            move_x = vx * PLAYER_SPEED * (self.clock.get_time() / 1000.0)
            move_y = vy * PLAYER_SPEED * (self.clock.get_time() / 1000.0)
            # tentative move and collision with scene obstacles
            next_rect = self.player_obj.rect().move(move_x, 0)
            blocked = False
            for obs in self.scene.obstacles:
                if next_rect.colliderect(obs):
                    blocked = True; break
            if not blocked:
                self.player_obj.x += move_x
            next_rect = self.player_obj.rect().move(0, move_y)
            blocked = False
            for obs in self.scene.obstacles:
                if next_rect.colliderect(obs):
                    blocked = True; break
            if not blocked:
                self.player_obj.y += move_y

            # check item pickups
            for go, item in list(self.scene.items):
                if self.player_obj.rect().colliderect(go.rect()):
                    self.handle_item_pickup(go, item)

            # check NPC interactions proximity (press N to interact)
            # But we also handle if player walks directly onto NPC -> auto-interact
            for npc in self.scene.npcs:
                if self.player_obj.rect().colliderect(npc.rect()):
                    self.handle_npc_interaction(npc)

            # check enemy collision -> start combat
            for en in list(self.scene.enemies):
                if self.player_obj.rect().colliderect(en.rect()):
                    # start combat
                    res = self.transition_to_combat(en)
                    if not self.player_state.hp > 0:
                        self.running = False
                        break

            # drawing scene
            self.scene.draw(self.screen)
            # draw player
            pygame.draw.rect(self.screen, PLAYER_COLOR, self.player_obj.rect())
            draw_text(self.screen, self.player_state.name if self.player_state else "NoName", self.player_obj.x, self.player_obj.y - 16, size=14)
            # UI HUD
            draw_text(self.screen, f"Location: {self.scene.name}", 12, 8, size=18)
            draw_text(self.screen, f"HP: {self.player_state.hp}/{self.player_state.max_hp}  MP: {self.player_state.mp}/{self.player_state.max_mp}  Gold: {self.player_state.gold}", 12, 30, size=16)
            if self.show_help:
                draw_text(self.screen, "Move: Arrows/WASD  Inventory: I  Next Scene / Interact: N  Help: H  Restart: R", 12, SCREEN_HEIGHT - 28, size=16)
            # message box
            pygame.draw.rect(self.screen, (230, 230, 230), (10, SCREEN_HEIGHT - 90, SCREEN_WIDTH - 20, 60))
            draw_text(self.screen, f"{self.message}", 18, SCREEN_HEIGHT - 82, size=18)

            # inventory overlay
            if self.show_inventory:
                pygame.draw.rect(self.screen, (30,30,30), (220, 100, 520, 420))
                draw_text(self.screen, "Inventory (press I to close)", SCREEN_WIDTH//2, 120, size=22, color=WHITE, center=True)
                for i, it in enumerate(self.player_state.inventory):
                    draw_text(self.screen, f"{i+1}. {it.name} - {it.description}", 260, 160 + i*28, size=18, color=WHITE)
            pygame.display.flip()
            self.clock.tick(FPS)
        pygame.quit()

# ---- Entry point ----

def main():
    g = Game()
    g.run()

if __name__ == "__main__":
    main()
