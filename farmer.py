#!/usr/bin/env python3
"""
rpg_gui_pyqt.py

A short single-file PyQt5 GUI for a small text-RPG:
- Character creation (Warrior, Mage, Rogue)
- Village -> Haunted Forest -> Enchanted Castle progression
- Turn-based combat with buttons (Attack, Defend, Magic, Item, Flee)
- Inventory dialog, loot, and branching decisions with 3 endings (Good / Neutral / Bad)
- Input and states validated, robust to edge cases.

Dependencies:
    pip install pyqt5

Run:
    python rpg_gui_pyqt.py
"""

import sys
import random
from dataclasses import dataclass, field
from typing import List, Callable, Optional

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QGroupBox, QTextEdit, QListWidget, QMessageBox, QDialog, QLineEdit, QComboBox
)
from PyQt5.QtCore import Qt

# ---------------------------
# Data models (dataclasses)
# ---------------------------

@dataclass
class Player:
    name: str
    pclass: str
    strength: int = 5
    agility: int = 5
    magic: int = 5
    max_hp: int = 30
    max_mp: int = 15
    hp: int = 30
    mp: int = 15
    inventory: List[str] = field(default_factory=list)
    gold: int = 10
    defending: bool = False
    helped_spirit: bool = False
    has_charm: bool = False

    def is_alive(self) -> bool:
        return self.hp > 0

    def show_short(self) -> str:
        inv = ", ".join(self.inventory) if self.inventory else "Empty"
        return f"HP: {self.hp}/{self.max_hp}  MP: {self.mp}/{self.max_mp}  Gold: {self.gold}\nSTR:{self.strength} AGI:{self.agility} MAG:{self.magic}\nInventory: {inv}"

@dataclass
class Enemy:
    name: str
    hp: int
    strength: int
    agility: int
    magic: int
    level: int = 1
    loot: List[str] = field(default_factory=list)
    special: Optional[Callable[['Player', 'Enemy', 'MainWindow'], None]] = None

    def is_alive(self) -> bool:
        return self.hp > 0

# ---------------------------
# Utility functions
# ---------------------------

def clamp(n, a, b): return max(a, min(b, n))

def calc_damage(att_str, base=3, variance=3, magic=False, att_mag=0):
    if magic:
        raw = base + att_mag + random.randint(0, variance)
    else:
        raw = base + att_str + random.randint(0, variance)
    return max(0, raw)

def make_enemy(name: str, difficulty: int = 1) -> Enemy:
    if name == "Goblin":
        return Enemy("Goblin", hp=8 + difficulty*2, strength=3 + difficulty, agility=3 + difficulty, magic=0, level=difficulty, loot=["Small Potion"] if random.random() < 0.6 else [])
    if name == "ForestWraith":
        return Enemy("Forest Wraith", hp=14 + difficulty*3, strength=4 + difficulty, agility=4 + difficulty, magic=3 + difficulty, level=difficulty, loot=["Mana Potion"])
    if name == "Bandit":
        return Enemy("Bandit Leader", hp=18 + difficulty*4, strength=6 + difficulty, agility=5 + difficulty, magic=0, level=difficulty, loot=["Lucky Charm"], special=goblin_special)
    if name == "Dragon":
        def breath(player, enemy, mw):
            mw.append_text("The Ancient Guardian breathes fire!")
            dmg = 12 + enemy.level * 2
            if player.defending:
                dmg //= 2
            player.hp -= dmg
            player.hp = clamp(player.hp, 0, player.max_hp)
            mw.append_text(f"You take {dmg} fire damage.")
        return Enemy("Ancient Guardian", hp=45 + difficulty*10, strength=8 + difficulty*2, agility=4 + difficulty, magic=8 + difficulty, level=difficulty+3, loot=["Ancient Artifact"], special=breath)
    return Enemy("Wolf", hp=10 + difficulty*2, strength=4 + difficulty, agility=5 + difficulty, magic=0, level=difficulty)

def goblin_special(player: Player, enemy: Enemy, mw):
    if player.inventory and random.random() < 0.2:
        stolen = player.inventory.pop(0)
        mw.append_text(f"{enemy.name} snatches your {stolen}!")
    else:
        mw.append_text(f"{enemy.name} tries a dirty trick but fails.")

# ---------------------------
# Dialogs
# ---------------------------

class CharacterDialog(QDialog):
    """Character creation modal"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Character")
        self.resize(320, 160)
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter name (default: Hero)")
        layout.addWidget(QLabel("Name:"))
        layout.addWidget(self.name_input)

        layout.addWidget(QLabel("Choose Class:"))
        self.class_select = QComboBox()
        self.class_select.addItems(["Warrior", "Mage", "Rogue"])
        layout.addWidget(self.class_select)

        btn = QPushButton("Create")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

    def get_values(self):
        name = self.name_input.text().strip() or "Hero"
        pclass = self.class_select.currentText()
        return name, pclass

# ---------------------------
# Inventory Dialog
# ---------------------------

class InventoryDialog(QDialog):
    def __init__(self, player: Player, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Inventory")
        self.resize(360, 300)
        self.player = player
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        self.use_btn = QPushButton("Use")
        self.discard_btn = QPushButton("Discard")
        self.close_btn = QPushButton("Close")
        btn_layout.addWidget(self.use_btn)
        btn_layout.addWidget(self.discard_btn)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

        self.close_btn.clicked.connect(self.accept)
        self.use_btn.clicked.connect(self.use_item)
        self.discard_btn.clicked.connect(self.discard_item)
        self.refresh()

    def refresh(self):
        self.list_widget.clear()
        for it in self.player.inventory:
            self.list_widget.addItem(it)

    def use_item(self):
        idx = self.list_widget.currentRow()
        if idx < 0:
            QMessageBox.information(self, "Select", "Select an item to use.")
            return
        item = self.player.inventory.pop(idx)
        # apply effects
        if item == "Small Potion":
            heal = min(self.player.max_hp - self.player.hp, 20)
            self.player.hp += heal
            QMessageBox.information(self, "Healed", f"You heal {heal} HP.")
        elif item == "Mana Potion":
            restore = min(self.player.max_mp - self.player.mp, 12)
            self.player.mp += restore
            QMessageBox.information(self, "MP", f"You recover {restore} MP.")
        elif item == "Lucky Charm":
            self.player.hp = min(self.player.max_hp, self.player.hp + 8)
            self.player.gold += 5
            QMessageBox.information(self, "Lucky Charm", "HP +8, Gold +5.")
        elif item == "Spirit Charm":
            self.player.has_charm = True
            QMessageBox.information(self, "Spirit Charm", "You feel protected.")
        else:
            QMessageBox.information(self, "Used", f"You used {item}.")
        self.refresh()

    def discard_item(self):
        idx = self.list_widget.currentRow()
        if idx < 0:
            QMessageBox.information(self, "Select", "Select an item to discard.")
            return
        item = self.player.inventory.pop(idx)
        QMessageBox.information(self, "Discarded", f"You discarded {item}.")
        self.refresh()

# ---------------------------
# Main Window (Game)
# ---------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Short RPG - PyQt GUI")
        self.resize(800, 520)

        self.player: Optional[Player] = None
        self.current_enemy: Optional[Enemy] = None
        self.stage = "start"  # start -> village -> forest -> castle -> done

        # central layout
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout()
        central.setLayout(main_layout)

        # Left: story / logs
        left_box = QVBoxLayout()
        main_layout.addLayout(left_box, 3)

        self.story = QTextEdit()
        self.story.setReadOnly(True)
        left_box.addWidget(QLabel("Story / Log"))
        left_box.addWidget(self.story)

        # action buttons area
        self.action_group = QGroupBox("Actions")
        ag_layout = QHBoxLayout()
        self.action_group.setLayout(ag_layout)
        left_box.addWidget(self.action_group)

        self.btn_attack = QPushButton("Attack")
        self.btn_defend = QPushButton("Defend")
        self.btn_magic = QPushButton("Magic")
        self.btn_item = QPushButton("Inventory")
        self.btn_flee = QPushButton("Flee")

        for b in (self.btn_attack, self.btn_defend, self.btn_magic, self.btn_item, self.btn_flee):
            ag_layout.addWidget(b)

        # Right: player panel
        right_box = QVBoxLayout()
        main_layout.addLayout(right_box, 1)

        self.stat_label = QLabel("No character yet")
        self.stat_label.setAlignment(Qt.AlignTop)
        self.stat_label.setWordWrap(True)
        right_box.addWidget(QLabel("Player"))
        right_box.addWidget(self.stat_label)

        # control buttons
        right_box.addWidget(QLabel("Game Controls"))
        self.btn_new = QPushButton("New Game")
        self.btn_next = QPushButton("Next (Progress)")
        right_box.addWidget(self.btn_new)
        right_box.addWidget(self.btn_next)

        # bind signals
        self.btn_new.clicked.connect(self.start_new_game)
        self.btn_next.clicked.connect(self.progress)
        self.btn_attack.clicked.connect(self.player_attack)
        self.btn_defend.clicked.connect(self.player_defend)
        self.btn_magic.clicked.connect(self.player_magic)
        self.btn_item.clicked.connect(self.open_inventory)
        self.btn_flee.clicked.connect(self.player_flee)

        # disable action buttons until in battle
        self.set_battle_mode(False)

        # start message
        self.append_text("Welcome — click New Game to begin.")

    # ---------------------------
    # UI helpers
    # ---------------------------
    def append_text(self, text: str):
        self.story.append(text)
        self.story.ensureCursorVisible()

    def set_battle_mode(self, in_battle: bool):
        for b in (self.btn_attack, self.btn_defend, self.btn_magic, self.btn_item, self.btn_flee):
            b.setEnabled(in_battle)
        # Next shouldn't be used mid-battle
        self.btn_next.setEnabled(not in_battle)

    def refresh_stats(self):
        if not self.player:
            self.stat_label.setText("No character yet")
        else:
            self.stat_label.setText(self.player.show_short())

    # ---------------------------
    # Lifecycle
    # ---------------------------
    def start_new_game(self):
        dlg = CharacterDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        name, pclass = dlg.get_values()
        self.player = self.create_player(name, pclass)
        self.stage = "village"
        self.append_text(f"Created {self.player.name} the {self.player.pclass}.")
        self.refresh_stats()
        self.append_text("You are in the Village. Use Next to explore.")
        self.set_battle_mode(False)

    def create_player(self, name: str, pclass: str) -> Player:
        p = Player(name=name, pclass=pclass)
        if pclass == "Warrior":
            p.strength = 8; p.agility = 5; p.magic = 2; p.max_hp = 40; p.max_mp = 10
            p.hp = p.max_hp; p.mp = p.max_mp; p.inventory = ["Small Potion", "Lucky Charm"]
        elif pclass == "Mage":
            p.strength = 2; p.agility = 4; p.magic = 9; p.max_hp = 26; p.max_mp = 30
            p.hp = p.max_hp; p.mp = p.max_mp; p.inventory = ["Mana Potion", "Mana Potion"]
        elif pclass == "Rogue":
            p.strength = 6; p.agility = 8; p.magic = 4; p.max_hp = 32; p.max_mp = 15
            p.hp = p.max_hp; p.mp = p.max_mp; p.inventory = ["Small Potion", "Dagger"]
        else:
            p.hp = p.max_hp; p.mp = p.max_mp
        return p

    # ---------------------------
    # Game progression (village, forest, castle)
    # ---------------------------

    def progress(self):
        if not self.player:
            QMessageBox.information(self, "No character", "Create a character first.")
            return

        if self.stage == "village":
            self.enter_village()
        elif self.stage == "forest":
            self.enter_forest()
        elif self.stage == "castle":
            self.enter_castle()
        else:
            QMessageBox.information(self, "Done", "The game is over. Start a new game.")
        self.refresh_stats()

    def enter_village(self):
        self.append_text("You arrive at the quiet village. A small shop offers potions.")
        btns = QMessageBox()
        btns.setWindowTitle("Village Options")
        btns.setText("Choose an action in the Village:")
        buy = btns.addButton("Buy Potion (5 gold)", QMessageBox.AcceptRole)
        rest = btns.addButton("Rest (8 gold)", QMessageBox.AcceptRole)
        leave = btns.addButton("Leave Village", QMessageBox.RejectRole)
        btns.exec_()
        clicked = btns.clickedButton()
        if clicked == buy:
            if self.player.gold >= 5:
                self.player.gold -= 5
                self.player.inventory.append("Small Potion")
                self.append_text("You bought a Small Potion.")
            else:
                self.append_text("Not enough gold to buy.")
        elif clicked == rest:
            if self.player.gold >= 8:
                self.player.gold -= 8
                self.player.hp = self.player.max_hp
                self.player.mp = self.player.max_mp
                self.append_text("You rested and restored HP/MP.")
            else:
                self.append_text("Not enough gold to rest.")
        else:
            self.append_text("You leave the village and head toward the Haunted Forest.")
            self.stage = "forest"

        self.refresh_stats()

    def enter_forest(self):
        self.append_text("The Haunted Forest greets you with chilly mist.")
        # spirit event
        choice = QMessageBox.question(self, "Forest Spirit", "A trapped forest spirit pleads for help. Help it?", QMessageBox.Yes | QMessageBox.No)
        if choice == QMessageBox.Yes:
            self.append_text("You free the spirit. It gives you a Spirit Charm.")
            self.player.helped_spirit = True
            self.player.inventory.append("Spirit Charm")
            self.player.has_charm = True
        else:
            self.append_text("You ignore the spirit and move on. Later you find a Lucky Charm.")
            self.player.inventory.append("Lucky Charm")

        # two random encounters
        for i in range(2):
            et = random.choice(["Goblin", "ForestWraith", "Bandit"])
            enemy = make_enemy(et, difficulty=1 + (i // 1))
            self.append_text(f"A {enemy.name} appears!")
            self.start_battle(enemy)
            if not self.player.is_alive():
                self.game_over("BAD", "You were defeated in the forest.")
                return
        self.append_text("You made it through the forest and head toward the Enchanted Castle.")
        self.stage = "castle"
        self.refresh_stats()

    def enter_castle(self):
        self.append_text("You arrive at the Enchanted Castle. A Bandit blocks the gate.")
        minor = make_enemy("Bandit", difficulty=2)
        self.start_battle(minor)
        if not self.player.is_alive():
            self.game_over("BAD", "You fell before the castle gate.")
            return
        # final branching decision
        self.append_text("At the inner gate stands the Ancient Guardian.")
        # present options via dialog
        btns = QMessageBox()
        btns.setWindowTitle("Final Choice")
        btns.setText("What will you do before the Guardian?")
        bef = btns.addButton("Befriend", QMessageBox.AcceptRole)
        fig = btns.addButton("Fight", QMessageBox.DestructiveRole)
        tri = btns.addButton("Trick", QMessageBox.ActionRole)
        btns.exec_()
        clicked = btns.clickedButton()
        guardian = make_enemy("Dragon", difficulty=2)

        if clicked == bef:
            if self.player.has_charm or self.player.magic >= 8:
                self.append_text("You speak with calm. The Guardian lowers its stance and accepts you. (Good Ending)")
                self.game_over("GOOD", "You restored peace to the land.")
                return
            else:
                self.append_text("Your words fail. The Guardian attacks!")
                self.start_battle(guardian)
                if not self.player.is_alive():
                    self.game_over("BAD", "You were slain by the Guardian.")
                    return
                if self.player.helped_spirit:
                    self.game_over("GOOD", "You defeated the Guardian and the land heals faster.")
                else:
                    self.game_over("NEUTRAL", "You defeated it, but the cost weighs on you.")
                return

        elif clicked == fig:
            self.append_text("You decide to fight the Guardian.")
            self.start_battle(guardian)
            if not self.player.is_alive():
                self.game_over("BAD", "You were broken by the Guardian.")
                return
            if self.player.helped_spirit:
                self.game_over("GOOD", "Because you helped earlier, the land heals quickly.")
            else:
                self.game_over("NEUTRAL", "You won, but the aftermath is heavy.")
            return

        elif clicked == tri:
            chance = 0.25 + (self.player.agility * 0.03) + (self.player.magic * 0.02)
            if random.random() < chance:
                self.append_text("Your ruse works and the Guardian lets you pass. (Good Ending)")
                self.game_over("GOOD", "You slipped by and resolved things without bloodshed.")
                return
            else:
                self.append_text("Trick failed. The Guardian attacks!")
                self.start_battle(guardian)
                if not self.player.is_alive():
                    self.game_over("BAD", "You were defeated by the Guardian.")
                    return
                self.game_over("NEUTRAL", "You overcame the Guardian but at cost.")
                return

    # ---------------------------
    # Battle management
    # ---------------------------
    def start_battle(self, enemy: Enemy):
        """Initializes a battle. Control switches to battle mode."""
        self.current_enemy = enemy
        self.player.defending = False
        self.append_text(f"Battle start: {self.player.name} vs {enemy.name}")
        self.set_battle_mode(True)
        self.refresh_stats()
        # battle loop proceeds by user clicking actions. Enemy actions are executed after player's action.

    def end_battle_if_needed(self):
        e = self.current_enemy
        p = self.player
        if e and not e.is_alive():
            self.append_text(f"You defeated {e.name}!")
            if e.loot:
                self.append_text(f"You found: {', '.join(e.loot)}")
                p.inventory.extend(e.loot)
            p.gold += e.level * 5
            self.current_enemy = None
            self.set_battle_mode(False)
            self.refresh_stats()
        elif not p.is_alive():
            self.current_enemy = None
            self.set_battle_mode(False)
            # player death handled by caller (progress/enter_x)
        # else battle continues

    def player_attack(self):
        if not self._battle_ok(): return
        e = self.current_enemy; p = self.player
        crit_chance = min(30, 5 + p.agility * 2)
        crit = random.randint(1, 100) <= crit_chance
        dmg = calc_damage(p.strength, base=2, variance=4)
        if crit:
            dmg = int(dmg * 1.6)
            self.append_text("Critical hit!")
        e.hp -= dmg
        e.hp = clamp(e.hp, 0, 9999)
        self.append_text(f"You attack {e.name} for {dmg} damage.")
        self.post_player_action()

    def player_defend(self):
        if not self._battle_ok(): return
        self.player.defending = True
        self.append_text("You brace yourself. Incoming damage will be reduced this turn.")
        self.post_player_action()

    def player_magic(self):
        if not self._battle_ok(): return
        cost = 6
        p = self.player; e = self.current_enemy
        if p.mp < cost:
            self.append_text("Not enough MP!")
            return
        p.mp -= cost
        dmg = calc_damage(0, base=4, variance=6, magic=True, att_mag=p.magic)
        burn = False
        if p.pclass == "Mage" and random.random() < 0.25:
            burn = True
        e.hp -= dmg
        e.hp = clamp(e.hp, 0, 9999)
        self.append_text(f"You cast a spell dealing {dmg} magic damage.")
        if burn:
            self.append_text(f"The {e.name} is burned for 3 extra damage!")
            e.hp -= 3
            e.hp = clamp(e.hp, 0, 9999)
        self.post_player_action()

    def player_flee(self):
        if not self._battle_ok(): return
        chance = 0.4 + self.player.agility * 0.03
        if random.random() < chance:
            self.append_text("You successfully fled the battle!")
            # fleeing ends battle without victory
            self.current_enemy = None
            self.set_battle_mode(False)
            self.refresh_stats()
        else:
            self.append_text("You failed to flee!")
            self.post_player_action()

    def open_inventory(self):
        if not self.player:
            QMessageBox.information(self, "No character", "Create a character first.")
            return
        dlg = InventoryDialog(self.player, self)
        dlg.exec_()
        self.refresh_stats()

    def post_player_action(self):
        """Called after player took an action: check if enemy dead, else run enemy turn."""
        self.end_battle_if_needed()
        if self.current_enemy:  # enemy gets a turn
            self.enemy_turn()
            self.refresh_stats()
            if not self.player.is_alive():
                self.append_text("You have fallen in battle...")
                # caller (progress) will check player life and show endings accordingly
                self.set_battle_mode(False)
            else:
                self.end_battle_if_needed()

    def enemy_turn(self):
        e = self.current_enemy; p = self.player
        if not e or not e.is_alive(): return
        # special move sometimes
        if e.special and random.random() < 0.2:
            e.special(p, e, self)
            return
        base_hit = 75
        dodge = min(50, p.agility * 3)
        hit_roll = random.randint(1, 100)
        if hit_roll <= base_hit - dodge:
            dmg = calc_damage(e.strength, base=2, variance=3)
            if p.defending:
                dmg = dmg // 2
            p.hp -= dmg
            p.hp = clamp(p.hp, 0, p.max_hp)
            self.append_text(f"{e.name} hits you for {dmg} damage.")
        else:
            self.append_text(f"{e.name} tries to hit but you dodge!")

    def _battle_ok(self) -> bool:
        if not self.player or not self.current_enemy:
            QMessageBox.information(self, "No battle", "There is no ongoing battle.")
            return False
        return True

    # ---------------------------
    # Ending and game over
    # ---------------------------
    def game_over(self, result: str, message: str):
        # disable actions and display ending
        self.append_text(f"\n=== Ending: {result} ===\n{message}")
        if result == "GOOD":
            self.append_text("Good Ending: The land heals and you are celebrated.")
        elif result == "NEUTRAL":
            self.append_text("Neutral Ending: You prevailed but at a price.")
        else:
            self.append_text("Bad Ending: Darkness claims the land...")
        QMessageBox.information(self, f"Game Over - {result}", message)
        self.stage = "done"
        self.set_battle_mode(False)
        self.refresh_stats()

# ---------------------------
# Entry point
# ---------------------------

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    random.seed()
    main()
