"""Pixel Adventure — 2D-платформер на pygame.

Стартовое меню:
  ↑ / ↓           — выбор пункта
  Enter / Space   — подтвердить

Управление в игре:
  ← / → или A / D — движение
  Space / W / ↑   — прыжок (в воздухе — двойной прыжок)
  R               — начать заново с первого уровня
  Esc             — вернуться в меню

Цель: собрать все фрукты и дойти до флага, не задев пилы.
После прохождения открывается следующий уровень по порядку.
"""

import sys
import math
import os
import subprocess
import json

import pygame

from game import settings as S
from game import assets
from game.level import Level
from game.player import Player
from game.levels_data import LEVELS
from game.audio import Audio
from game.effects import Effects
try:
    from game.levels_data import LEVEL_ROTATIONS
except ImportError:
    LEVEL_ROTATIONS = [{} for _ in LEVELS]
try:
    from game.levels_data import LEVEL_ROUTES
except ImportError:
    LEVEL_ROUTES = [{} for _ in LEVELS]
try:
    from game.levels_data import LEVEL_TILE_OVERRIDES
except ImportError:
    LEVEL_TILE_OVERRIDES = [{} for _ in LEVELS]


class Camera:
    """Камера следит за игроком и не выходит за границы уровня."""

    def __init__(self, level):
        self.x = 0.0
        self.y = 0.0
        self.level = level

    def follow(self, target_rect):
        # Центрируем игрока на экране
        self.x = target_rect.centerx - S.SCREEN_W / 2
        self.y = target_rect.centery - S.SCREEN_H / 2
        # Клампим к границам мира
        self.x = max(0.0, min(self.x, self.level.width - S.SCREEN_W))
        self.y = max(0.0, min(self.y, self.level.height - S.SCREEN_H))


class Game:
    STATE_MENU, STATE_PLAY, STATE_WIN, STATE_LEVELS, STATE_SETTINGS, STATE_PAUSE, STATE_ACHIEVEMENTS = "menu", "play", "win", "levels", "settings", "pause", "achievements"

    def __init__(self, start_level=0):
        pygame.init()
        self.audio = Audio()
        self.settings_path = os.path.join(os.path.dirname(__file__), "settings.json")
        try:
            with open(self.settings_path, encoding="utf-8") as f: self.user_settings = json.load(f)
        except (OSError, ValueError, TypeError): self.user_settings = {"volume": 0.7, "fullscreen": True, "resolution": [1920, 1080]}
        self.audio.set_volume(self.user_settings.get("volume", 0.7))
        if S.FULLSCREEN:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode((S.SCREEN_W, S.SCREEN_H))
        # Синхронизируем настройки с фактическим размером окна:
        # от него зависят размер карты в генераторе и клампинг камеры.
        w, h = self.screen.get_size()
        if w >= 320 and h >= 240:      # игнорируем вырожденный размер (headless)
            S.set_screen_size(w, h)
        pygame.mouse.set_visible(False)
        pygame.display.set_caption(S.TITLE)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 28, bold=True)
        self.big_font = pygame.font.SysFont("consolas", 72, bold=True)
        self.title_font = pygame.font.SysFont("consolas", 110, bold=True)

        self.bg = assets.load_background(S.BG_NAME)
        self.theme = "Blue"
        self.theme_light = (5, 7, 16, 215)
        self.theme_lamp_radius = 7.0
        self.bg_offset = 0.0
        self.characters = ["Mask Dude", "Ninja Frog", "Pink Man", "Virtual Guy"]
        self.character_index = 1
        self.character_name = self.characters[self.character_index]
        self.character_previews = {
            name: assets.load_character(name)["idle"] for name in self.characters
        }
        self._glow_cache = {}
        self.effects = Effects()
        self.transition_img = assets.load_transition()
        self.transition_t = 0.0        # таймер «диафрагмы» появления уровня
        self._death_poofed = False     # поф смерти уже выпущен в этот раз
        self.best_times_path = os.path.join(os.path.dirname(__file__), "best_times.json")
        try:
            with open(self.best_times_path, encoding="utf-8") as f:
                self.best_times = {int(k): float(v) for k, v in json.load(f).items()}
        except (OSError, ValueError, TypeError):
            self.best_times = {}
        self.progress_path = os.path.join(os.path.dirname(__file__), "progress.json")
        try:
            with open(self.progress_path, encoding="utf-8") as f: self.progress = json.load(f)
        except (OSError, ValueError, TypeError): self.progress = {}
        self.completed_levels = set(self.progress.get("completed", [])) if isinstance(self.progress, dict) else set()
        self.max_fruits = dict(self.progress.get("fruits", {})) if isinstance(self.progress, dict) else {}
        self.achievements = set(self.progress.get("achievements", [])) if isinstance(self.progress, dict) else set()
        self.medals = dict(self.progress.get("medals", {})) if isinstance(self.progress, dict) else {}
        self.ghosts = dict(self.progress.get("ghosts", {})) if isinstance(self.progress, dict) else {}
        self.level_deaths = 0
        saved_last = self.progress.get("last_level") if isinstance(self.progress, dict) else None
        if start_level == 0 and isinstance(saved_last, int):
            start_level = saved_last

        self.level_num = int(start_level) % len(LEVELS)
        self._start_level(self._next_grid())

        # Начинаем со стартового меню (уровень уже сгенерирован — виден как фон).
        self.state = self.STATE_MENU
        self.audio.music_for("Menu")
        self.menu_items = ["Играть", "Выбор уровня", "Достижения", "Персонаж", "Настройки", "Редактор карт", "Выход"]
        self.settings_index = 0
        self.pause_index = 0
        self.level_select_index = 0
        self.menu_index = 0
        self.menu_time = 0.0

        # Иконки-акценты меню и номерные плашки уровней. Не критичны для игры —
        # если файла нет, просто рисуем без иконки (мягкая загрузка).
        self.menu_icons = {}
        for item, icon in {
            "Играть": "Play",
            "Выбор уровня": "Levels",
            "Достижения": "Achievements",
            "Настройки": "Settings",
            "Выход": "Close",
        }.items():
            try:
                self.menu_icons[item] = assets.load_menu_button(icon)
            except (pygame.error, FileNotFoundError, OSError):
                pass
        self.level_icons = {}
        for n in range(1, len(LEVELS) + 1):
            try:
                self.level_icons[n] = assets.load_level_icon(n)
            except (pygame.error, FileNotFoundError, OSError):
                pass

    def _next_grid(self):
        """Взять текущую карту; после пятнадцатой начать с первой."""
        return LEVELS[self.level_num % len(LEVELS)]

    def _start_level(self, grid):
        self._set_theme(grid)
        self.level = Level(grid=grid, rotations=LEVEL_ROTATIONS[self.level_num % len(LEVEL_ROTATIONS)],
                           routes=LEVEL_ROUTES[self.level_num % len(LEVEL_ROUTES)],
                           tile_overrides=LEVEL_TILE_OVERRIDES[self.level_num % len(LEVEL_TILE_OVERRIDES)])
        self.camera = Camera(self.level)
        sx, sy = self.level.player_spawn
        self.player = Player(sx, sy, self.character_name)
        self.camera.follow(self.player.rect)
        self.effects.reset()
        self.effects.spawn_appear(self.player.rect.centerx, self.player.rect.centery)
        self.transition_t = S.TRANSITION_TIME
        self._death_poofed = False
        self.score = 0
        self.state = self.STATE_PLAY
        self.death_timer = 0.0
        self.win_timer = 0.0
        self.level_time = 0.0
        self.level_finished_time = None
        self.level_deaths = 0
        self.run_trace = []
        self._save_progress(last_level=self.level_num)

    def _save_progress(self, last_level=None):
        data = {"completed": sorted(self.completed_levels), "fruits": self.max_fruits,
                "achievements": sorted(self.achievements),
                "medals": self.medals,
                "ghosts": self.ghosts,
                "last_level": self.level_num if last_level is None else int(last_level)}
        try:
            with open(self.progress_path, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)
        except OSError:
            pass

    def _set_theme(self, grid):
        themes = {
            "X": ("Blue", (5, 7, 16, 215), 7.0),
            "I": ("Gray", (10, 11, 15, 220), 6.0),
            "J": ("Brown", (24, 14, 8, 220), 5.5),
            "K": ("Green", (5, 18, 12, 215), 7.5),
            "L": ("Purple", (16, 7, 25, 220), 6.0),
            "Q": ("Pink", (25, 8, 18, 220), 6.0),
            "U": ("Brown", (25, 15, 8, 225), 5.5),
            "V": ("Gray", (12, 14, 18, 225), 5.0),
            "W": ("Yellow", (28, 20, 5, 220), 7.0),
            "Y": ("Purple", (14, 8, 22, 220), 6.0),
            "Z": ("Yellow", (24, 18, 4, 220), 7.0),
        }
        material = next((ch for row in grid for ch in row if ch in themes), "X")
        self.theme, self.theme_light, self.theme_lamp_radius = themes[material]
        self.bg = assets.load_background(self.theme)
        self.audio.music_for(self.theme)

    def _next_level(self):
        """Финиш уровня → следующий уровень по порядку."""
        self.level_num += 1
        self._start_level(self._next_grid())

    def _restart_run(self):
        """Начать заново с первого уровня (по кнопке R)."""
        self.level_num = 0
        self._start_level(self._next_grid())

    def _start_game(self):
        """Запуск из меню: свежий забег с первого уровня."""
        self.level_num = 0
        self._start_level(self._next_grid())
        self.state = self.STATE_PLAY

    def _to_menu(self):
        """Вернуться в стартовое меню (Esc во время игры)."""
        self.state = self.STATE_MENU
        self.menu_index = 0
        self.menu_time = 0.0

    def _launch_editor(self):
        """Закрыть игру и открыть редактор отдельным окном."""
        editor = os.path.join(os.path.dirname(__file__), "editor.py")
        pygame.quit()
        subprocess.Popen([sys.executable, editor], cwd=os.path.dirname(editor))

    # -- Обновление ---------------------------------------------------
    def update(self, dt, auto=None, auto_jump=False):
        # Фон прокручивается во всех состояниях — так меню «живое».
        self.bg_offset = (self.bg_offset + S.BG_SCROLL * dt) % self.bg.get_height()

        # «Диафрагма» появления уровня тикает независимо от состояния.
        if self.transition_t > 0:
            self.transition_t = max(0.0, self.transition_t - dt)

        if self.state == self.STATE_MENU:
            self.menu_time += dt
            self.level.update(dt)                 # анимации фруктов/пил/флага
            self.player.anims["idle"].update(dt)  # герой на заставке дышит
            return

        if self.state == self.STATE_PAUSE:
            return

        if self.state == self.STATE_WIN:
            self.level.update(dt)
            self.effects.update(dt)
            self.win_timer += dt
            if self.win_timer > 2.0:      # пауза-поздравление, затем новый уровень
                self._next_level()
            return

        self.level_time += dt
        if self.state == self.STATE_PLAY and not self.player.dead:
            self.run_trace.append([round(self.level_time, 3), round(self.player.rect.x, 1), round(self.player.rect.y, 1)])

        if auto_jump:
            self.player.handle_jump_pressed()

        # Платформы двигаются до игрока, чтобы коллизия шла по свежим позициям.
        prev_on_ground = self.player.on_ground
        self.level.update(dt)
        self.player.update(dt, self.level.dynamic_solids(), auto=auto)
        self._carry_on_platforms()
        self.camera.follow(self.player.rect)
        self.effects.update(dt)

        if self.player.dead:
            if not self._death_poofed:      # облачко на месте гибели — один раз
                self.effects.spawn_disappear(self.player.rect.centerx,
                                             self.player.rect.centery)
                self._death_poofed = True
            self.death_timer += dt
            if self.death_timer > 1.1:
                self.player.respawn()
                self.effects.spawn_appear(self.player.rect.centerx,
                                          self.player.rect.centery)
                self.level_deaths += 1
                self.death_timer = 0.0
                self._death_poofed = False
            return

        # Пыль: всплеск при приземлении и клубы из-под ног при беге.
        if not prev_on_ground and self.player.on_ground:
            self.effects.land_dust(self.player)
        self.effects.run_dust(self.player, dt)

        # Падение в пропасть
        if self.player.rect.top > self.level.height + S.TILE * 2:
            self.player.kill_player()
            return

        self._check_hazards()
        self._check_boosters(dt)
        self._check_boxes()
        self._check_checkpoints()
        self._check_fruits()
        self._check_flag()

    def _carry_on_platforms(self):
        """Игрок на движущейся платформе едет с ней; падающая — начинает падать."""
        pr = self.player.rect
        for m in self.level.movers:
            if not getattr(m, "solid", True):
                continue
            on_top = abs(pr.bottom - m.rect.top) <= 4
            over = pr.right > m.rect.left and pr.left < m.rect.right
            if on_top and over:
                if m.dx:
                    pr.x += m.dx          # горизонтальный перенос
                if hasattr(m, "trigger"):
                    m.trigger()           # падающая платформа — запуск обвала

    def _check_hazards(self):
        pr = pygame.Rect(int(self.player.rect.x), int(self.player.rect.y),
                         int(self.player.rect.width), int(self.player.rect.height))
        for saw in self.level.saws:
            if saw.hits(pr):
                self.player.kill_player()
                self.audio.play("hazard")
                return
        for spike in self.level.spikes:
            if spike.hits(pr):
                self.player.kill_player()
                self.audio.play("hazard")
                return
        for hz in self.level.hazards:
            if hz.hits(pr):
                self.player.kill_player()
                self.audio.play("hazard")
                return

    def _check_boosters(self, dt):
        """Трамплины подбрасывают, вентиляторы держат в воздухе."""
        if self.player.dead:
            return
        for b in self.level.boosters:
            if hasattr(b, "bounce"):
                b.bounce(self.player)
            elif hasattr(b, "affects"):
                b.affects(self.player, dt)

    def _check_boxes(self):
        """Касание целого ящика ломает его и роняет фрукт.

        Ящик — твёрдый, поэтому после коллизии игрок стоит вплотную к его краю
        (без перекрытия). Ловим касание, слегка расширяя рамку ящика.
        """
        pr = pygame.Rect(int(self.player.rect.x), int(self.player.rect.y),
                         int(self.player.rect.width), int(self.player.rect.height))
        for bx in self.level.boxes:
            if bx.solid and bx.rect.inflate(4, 4).colliderect(pr):
                self.level.spawn_fruit(bx.break_open())

    def _check_checkpoints(self):
        pr = self.player.rect
        for cp in self.level.checkpoints:
            if not cp.active and pr.colliderect(cp.rect):
                cp.activate(self.player)
                self.audio.play("checkpoint")

    def _check_fruits(self):
        pr = self.player.rect
        for fruit in self.level.fruits:
            if not fruit.collected and pr.colliderect(fruit.rect):
                fruit.collect()
                self.score += 1

    def _check_flag(self):
        flag = self.level.flag
        if flag and self.player.rect.colliderect(flag.rect):
            if self.score >= self.level.total_fruits:
                self.state = self.STATE_WIN
                self.audio.play("win")
                self.effects.burst_confetti()
                self.level_finished_time = self.level_time
                old = self.best_times.get(self.level_num)
                if old is None or self.level_finished_time < old:
                    self.best_times[self.level_num] = self.level_finished_time
                    self.ghosts[str(self.level_num)] = self.run_trace[-12000:]
                    try:
                        with open(self.best_times_path, "w", encoding="utf-8") as f:
                            json.dump(self.best_times, f, indent=2)
                    except OSError:
                        pass
                self.completed_levels.add(self.level_num)
                key = str(self.level_num)
                self.max_fruits[key] = max(int(self.max_fruits.get(key, 0)), self.score)
                self._save_progress()
                self.achievements.update(("all_fruits",))
                if self.level_deaths == 0:
                    self.achievements.add("no_death")
                if self.level_finished_time <= 60.0:
                    self.achievements.add("speedrun")
                medal = self._medal_for_time(self.level_finished_time)
                old_medal = self.medals.get(str(self.level_num), "")
                order = {"": 0, "bronze": 1, "silver": 2, "gold": 3}
                if order[medal] > order.get(old_medal, 0):
                    self.medals[str(self.level_num)] = medal
                self._save_progress()

    @staticmethod
    def _medal_for_time(seconds):
        if seconds <= 40: return "gold"
        if seconds <= 60: return "silver"
        if seconds <= 90: return "bronze"
        return ""

    # -- Отрисовка ----------------------------------------------------
    def draw(self):
        if self.state == self.STATE_ACHIEVEMENTS:
            self._draw_achievements()
            return
        if self.state == self.STATE_PAUSE:
            self._draw_background(); self.level.draw(self.screen, self.camera)
            frame = self.player.current_frame(); dx, dy = self.player.draw_pos
            self.screen.blit(frame, (dx - self.camera.x, dy - self.camera.y))
            self._draw_lighting(); self._draw_pause(); return
        if self.state == self.STATE_SETTINGS:
            self._draw_settings()
            return
        if self.state == self.STATE_LEVELS:
            self._draw_levels()
            return
        self._draw_background()
        self.level.draw(self.screen, self.camera)
        self._draw_ghost()
        # Игрок
        frame = self.player.current_frame()
        dx, dy = self.player.draw_pos
        self.screen.blit(frame, (dx - self.camera.x, dy - self.camera.y))
        self._draw_lighting()

        if self.state == self.STATE_MENU:
            self._draw_menu()
            return

        # Пыль и облачка появления/смерти — поверх сцены (только в игре).
        self.effects.draw_world(self.screen, self.camera)
        self._draw_hud()
        if self.state == self.STATE_WIN:
            medal = {"bronze": "БРОНЗА", "silver": "СЕРЕБРО", "gold": "ЗОЛОТО"}.get(self.medals.get(str(self.level_num)), "")
            self._draw_center_banner("УРОВЕНЬ ПРОЙДЕН!", f"{medal}   Готовим следующий уровень…")
            self.effects.draw_screen(self.screen)      # конфетти поверх баннера
        self._draw_transition()

    def _draw_ghost(self):
        trace = self.ghosts.get(str(self.level_num), [])
        if not trace or self.state not in (self.STATE_PLAY, self.STATE_WIN):
            return
        t = self.level_finished_time if self.state == self.STATE_WIN and self.level_finished_time is not None else self.level_time
        sample = trace[0]
        for item in trace:
            if item[0] > t:
                break
            sample = item
        ghost = self.player.current_frame().copy()
        ghost.set_alpha(85)
        x = sample[1] + self.player.rect.width / 2 - ghost.get_width() / 2 - self.camera.x
        y = sample[2] - ghost.get_height() + self.player.rect.height - self.camera.y
        self.screen.blit(ghost, (round(x), round(y)))

    def _glow(self, radius):
        radius = int(radius)
        glow = self._glow_cache.get(radius)
        if glow is None:
            glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            center = (radius, radius)
            for r in range(radius, 0, -8):
                strength = int(225 * (1 - r / radius) ** 0.65)
                pygame.draw.circle(glow, (0, 0, 0, strength), center, r)
            self._glow_cache[radius] = glow
        return glow

    def _cut_light(self, darkness, x, y, radius):
        glow = self._glow(radius)
        darkness.blit(glow, (int(x - radius), int(y - radius)),
                      special_flags=pygame.BLEND_RGBA_SUB)

    def _draw_lighting(self):
        darkness = pygame.Surface((S.SCREEN_W, S.SCREEN_H), pygame.SRCALPHA)
        darkness.fill(self.theme_light)
        for lamp in self.level.lamps:
            self._cut_light(darkness,
                            lamp.light_pos.x - self.camera.x,
                            lamp.light_pos.y - self.camera.y,
                            lamp.radius * self.theme_lamp_radius / 7.0)
        self._cut_light(darkness,
                        self.player.rect.centerx - self.camera.x,
                        self.player.rect.centery - self.camera.y,
                        S.TILE * 2.5)
        self.screen.blit(darkness, (0, 0))

    def _draw_menu(self):
        cx = S.SCREEN_W // 2
        # Затемняющая подложка, чтобы текст читался поверх игры.
        overlay = pygame.Surface((S.SCREEN_W, S.SCREEN_H), pygame.SRCALPHA)
        overlay.fill((10, 12, 28, 170))
        self.screen.blit(overlay, (0, 0))

        # Заголовок с лёгким «покачиванием».
        bob = int(math.sin(self.menu_time * 2.0) * 8)
        title = self.title_font.render("PIXEL ADVENTURE", True, S.UI_ACCENT)
        tshadow = self.title_font.render("PIXEL ADVENTURE", True, S.SHADOW)
        ty = S.SCREEN_H // 4 + bob
        self.screen.blit(tshadow, tshadow.get_rect(center=(cx + 4, ty + 4)))
        self.screen.blit(title, title.get_rect(center=(cx, ty)))

        # Пункты меню.
        base_y = S.SCREEN_H // 2 + 20
        for i, item in enumerate(self.menu_items):
            selected = i == self.menu_index
            color = S.UI_ACCENT if selected else S.WHITE
            icon = self.menu_icons.get(item)          # ищем по исходному имени пункта
            text = f"Персонаж: {self.character_name}" if item == "Персонаж" else item
            label = f"> {text} <" if selected else text
            surf = self.big_font.render(label, True, color)
            shadow = self.big_font.render(label, True, S.SHADOW)
            y = base_y + i * 80
            sr = surf.get_rect(center=(cx, y))
            self.screen.blit(shadow, shadow.get_rect(center=(cx + 3, y + 3)))
            self.screen.blit(surf, sr)
            if icon is not None:                      # иконка-акцент слева от текста
                h = sr.height
                ic = pygame.transform.scale(icon, (h, h))
                self.screen.blit(ic, (sr.left - h - 16, y - h // 2))

        # Крупный анимированный предпросмотр выбранного героя справа от меню.
        frames = self.character_previews[self.character_name]
        frame = frames[int(self.menu_time * 10) % len(frames)]
        preview_size = S.TILE * 4
        preview = pygame.transform.scale(frame, (preview_size, preview_size))
        px = min(S.SCREEN_W - preview_size - 60, cx + 430)
        py = base_y + 80 - preview_size // 2
        panel = pygame.Rect(px - 22, py - 22, preview_size + 44, preview_size + 72)
        pygame.draw.rect(self.screen, (18, 20, 38, 220), panel, border_radius=18)
        pygame.draw.rect(self.screen, S.UI_ACCENT, panel, 3, border_radius=18)
        self.screen.blit(preview, (px, py))
        name = self.font.render(self.character_name, True, S.WHITE)
        self.screen.blit(name, name.get_rect(center=(panel.centerx, panel.bottom - 23)))

    def _draw_levels(self):
        self.screen.fill((12, 15, 30))
        title = self.big_font.render("ВЫБОР УРОВНЯ", True, S.UI_ACCENT)
        self.screen.blit(title, title.get_rect(center=(S.SCREEN_W // 2, 70)))
        cols = 5; cw, ch = 300, 130
        ox = (S.SCREEN_W - cols * cw) // 2
        for i in range(len(LEVELS)):
            x = ox + (i % cols) * cw; y = 140 + (i // cols) * ch
            rect = pygame.Rect(x + 8, y, cw - 16, ch - 12)
            selected = i == self.level_select_index
            pygame.draw.rect(self.screen, (45, 50, 78) if selected else (25, 29, 50), rect, border_radius=10)
            pygame.draw.rect(self.screen, S.UI_ACCENT if selected else (80, 85, 115), rect, 3, border_radius=10)
            icon = self.level_icons.get(i + 1)        # номерная плашка в углу карточки
            if icon is not None:
                size = 56
                pic = pygame.transform.scale(icon, (size, size))
                self.screen.blit(pic, (rect.right - size - 12, rect.y + 10))
            done = i in self.completed_levels
            lines = [f"Уровень {i + 1}  {'✓' if done else '…'}", f"Фрукты: {self.max_fruits.get(str(i), 0)}/{Level(grid=LEVELS[i]).total_fruits}"]
            if i in self.best_times: lines.append(f"Рекорд: {self.best_times[i]:.2f} с")
            else: lines.append("Рекорд: —")
            lines.append({"bronze": "Bronze", "silver": "Silver", "gold": "Gold"}.get(self.medals.get(str(i)), "Medal: -"))
            for j, line in enumerate(lines):
                self.screen.blit(self.font.render(line, True, S.WHITE), (rect.x + 14, rect.y + 12 + j * 27))
        hint = self.font.render("←/→/↑/↓ выбор · Enter играть · Esc назад", True, S.WHITE)
        self.screen.blit(hint, hint.get_rect(center=(S.SCREEN_W // 2, S.SCREEN_H - 35)))

    def _draw_settings(self):
        self.screen.fill((12, 15, 30))
        title = self.big_font.render("НАСТРОЙКИ", True, S.UI_ACCENT)
        self.screen.blit(title, title.get_rect(center=(S.SCREEN_W // 2, 100)))
        items = [f"Громкость: {int(self.user_settings.get('volume', .7) * 100)}%",
                 f"Разрешение: {S.SCREEN_W}x{S.SCREEN_H}",
                 f"Полный экран: {'Да' if self.user_settings.get('fullscreen') else 'Нет'}",
                 "Управление: A/D или стрелки — движение; Space — прыжок; Shift — рывок",
                 "Esc — назад"]
        for i, text in enumerate(items):
            color = S.UI_ACCENT if i == self.settings_index else S.WHITE
            self.screen.blit(self.font.render(("> " if i == self.settings_index else "") + text, True, color),
                             (S.SCREEN_W // 2 - 420, 220 + i * 70))

    def _draw_achievements(self):
        self.screen.fill((12, 15, 30))
        title = self.big_font.render("ДОСТИЖЕНИЯ", True, S.UI_ACCENT)
        self.screen.blit(title, title.get_rect(center=(S.SCREEN_W // 2, 110)))
        items = [("all_fruits", "Садовник — собрать все фрукты"),
                 ("no_death", "Безупречно — пройти уровень без смерти"),
                 ("speedrun", "Молния — уложиться в 60 секунд")]
        for i, (key, label) in enumerate(items):
            status = "✓" if key in self.achievements else "—"
            color = S.UI_ACCENT if key in self.achievements else S.WHITE
            self.screen.blit(self.font.render(f"{status}  {label}", True, color), (S.SCREEN_W // 2 - 400, 250 + i * 75))
        hint = self.font.render("Esc — назад", True, S.WHITE)
        self.screen.blit(hint, hint.get_rect(center=(S.SCREEN_W // 2, S.SCREEN_H - 50)))

    def _draw_pause(self):
        overlay = pygame.Surface((S.SCREEN_W, S.SCREEN_H), pygame.SRCALPHA); overlay.fill((5, 8, 18, 205)); self.screen.blit(overlay, (0, 0))
        title = self.big_font.render("ПАУЗА", True, S.UI_ACCENT); self.screen.blit(title, title.get_rect(center=(S.SCREEN_W // 2, 230)))
        for i, text in enumerate(("Продолжить", "Заново", "В меню")):
            color = S.UI_ACCENT if i == self.pause_index else S.WHITE
            surf = self.font.render(("> " if i == self.pause_index else "") + text, True, color)
            self.screen.blit(surf, surf.get_rect(center=(S.SCREEN_W // 2, 360 + i * 60)))

    def _save_settings(self):
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f: json.dump(self.user_settings, f, indent=2)
        except OSError: pass

        # Подсказка по управлению.
        hint = self.font.render(
            "↑/↓ — выбор   Enter — ок   ←→/AD — идти, Space — прыжок",
            True, S.WHITE)
        self.screen.blit(hint, hint.get_rect(center=(S.SCREEN_W // 2, S.SCREEN_H - 50)))

    def _draw_background(self):
        bg = self.bg
        bw, bh = bg.get_size()
        off = int(self.bg_offset)
        for x in range(0, S.SCREEN_W, bw):
            for y in range(-bh, S.SCREEN_H + bh, bh):
                self.screen.blit(bg, (x, y + off))

    def _draw_hud(self):
        txt = f"Фрукты: {self.score}/{self.level.total_fruits}"
        surf = self.font.render(txt, True, S.WHITE)
        shadow = self.font.render(txt, True, S.SHADOW)
        self.screen.blit(shadow, (14, 12))
        self.screen.blit(surf, (12, 10))

        lvl = f"Уровень {self.level_num + 1}"
        lsurf = self.font.render(lvl, True, S.WHITE)
        lshadow = self.font.render(lvl, True, S.SHADOW)
        lx = S.SCREEN_W - lsurf.get_width() - 12
        self.screen.blit(lshadow, (lx + 2, 12))
        self.screen.blit(lsurf, (lx, 10))
        current = self.level_finished_time if self.state == self.STATE_WIN and self.level_finished_time is not None else self.level_time
        timer = self.font.render(f"Время: {current:06.2f} с", True, S.WHITE)
        self.screen.blit(timer, (12, 78))
        best = self.best_times.get(self.level_num)
        if best is not None:
            btxt = self.font.render(f"Лучшее: {best:06.2f} с", True, S.UI_ACCENT)
            self.screen.blit(btxt, (12, 110))

        if self.score >= self.level.total_fruits and self.state == self.STATE_PLAY:
            hint = self.font.render("К флагу!", True, S.UI_ACCENT)
            self.screen.blit(hint, (12, 44))

    def _draw_center_banner(self, title, subtitle):
        overlay = pygame.Surface((S.SCREEN_W, S.SCREEN_H), pygame.SRCALPHA)
        overlay.fill((10, 10, 20, 150))
        self.screen.blit(overlay, (0, 0))
        t = self.big_font.render(title, True, S.UI_ACCENT)
        s = self.font.render(subtitle, True, S.WHITE)
        self.screen.blit(t, t.get_rect(center=(S.SCREEN_W // 2, S.SCREEN_H // 2 - 20)))
        self.screen.blit(s, s.get_rect(center=(S.SCREEN_W // 2, S.SCREEN_H // 2 + 30)))

    def _draw_transition(self):
        """«Диафрагма» старта уровня: тёмный слой с растущим ромбом-дырой."""
        if self.transition_t <= 0:
            return
        p = 1.0 - self.transition_t / S.TRANSITION_TIME     # 0 → 1 по ходу
        p = max(0.0, min(1.0, p))
        overlay = pygame.Surface((S.SCREEN_W, S.SCREEN_H), pygame.SRCALPHA)
        overlay.fill((8, 8, 16, 255))
        max_size = int((S.SCREEN_W + S.SCREEN_H) * 1.15)
        size = max(1, int(max_size * p))
        diamond = pygame.transform.scale(self.transition_img, (size, size))
        rect = diamond.get_rect(center=(S.SCREEN_W // 2, S.SCREEN_H // 2))
        overlay.blit(diamond, rect, special_flags=pygame.BLEND_RGBA_SUB)
        self.screen.blit(overlay, (0, 0))

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(S.FPS) / 1000.0
            dt = min(dt, 1 / 30)  # защита от скачков при лагах
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if self.state == self.STATE_MENU:
                        if event.key in (pygame.K_UP, pygame.K_w):
                            self.menu_index = (self.menu_index - 1) % len(self.menu_items)
                        elif event.key in (pygame.K_DOWN, pygame.K_s):
                            self.menu_index = (self.menu_index + 1) % len(self.menu_items)
                        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER,
                                           pygame.K_SPACE):
                            item = self.menu_items[self.menu_index]
                            if item == "Выход":
                                running = False
                            elif item == "Редактор карт":
                                self._launch_editor()
                                running = False
                            elif item == "Играть":
                                self._start_game()
                            elif item == "Выбор уровня":
                                self.state = self.STATE_LEVELS
                                self.level_select_index = self.level_num
                            elif item == "Достижения":
                                self.state = self.STATE_ACHIEVEMENTS
                            elif item == "Настройки":
                                self.state = self.STATE_SETTINGS
                                self.settings_index = 0
                        elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                            if self.menu_items[self.menu_index] == "Персонаж":
                                delta = -1 if event.key in (pygame.K_LEFT, pygame.K_a) else 1
                                self.character_index = (self.character_index + delta) % len(self.characters)
                                self.character_name = self.characters[self.character_index]
                        elif event.key == pygame.K_ESCAPE:
                            running = False
                    elif self.state == self.STATE_ACHIEVEMENTS:
                        if event.key == pygame.K_ESCAPE:
                            self.state = self.STATE_MENU
                    elif self.state == self.STATE_SETTINGS:
                        if event.key == pygame.K_ESCAPE:
                            self.state = self.STATE_MENU
                        elif event.key in (pygame.K_UP, pygame.K_w):
                            self.settings_index = (self.settings_index - 1) % 5
                        elif event.key in (pygame.K_DOWN, pygame.K_s):
                            self.settings_index = (self.settings_index + 1) % 5
                        elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                            step = -1 if event.key in (pygame.K_LEFT, pygame.K_a) else 1
                            if self.settings_index == 0:
                                self.user_settings["volume"] = max(0.0, min(1.0, self.user_settings.get("volume", .7) + step * .1))
                                self.audio.set_volume(self.user_settings["volume"])
                            elif self.settings_index == 1:
                                sizes = [(1280, 720), (1600, 900), (1920, 1080)]
                                cur = tuple(self.user_settings.get("resolution", [1920, 1080])); i = sizes.index(cur) if cur in sizes else 2
                                w, h = sizes[(i + step) % len(sizes)]; self.user_settings["resolution"] = [w, h]; self.screen = pygame.display.set_mode((w, h), pygame.FULLSCREEN if self.user_settings.get("fullscreen") else 0); S.set_screen_size(w, h)
                            elif self.settings_index == 2:
                                self.user_settings["fullscreen"] = not self.user_settings.get("fullscreen", True)
                                w, h = self.user_settings.get("resolution", [1920, 1080]); flags = pygame.FULLSCREEN if self.user_settings["fullscreen"] else 0; self.screen = pygame.display.set_mode((w, h), flags); S.set_screen_size(w, h)
                            self._save_settings()
                    elif self.state == self.STATE_LEVELS:
                        if event.key == pygame.K_ESCAPE:
                            self.state = self.STATE_MENU
                        elif event.key in (pygame.K_LEFT, pygame.K_a):
                            self.level_select_index = (self.level_select_index - 1) % len(LEVELS)
                        elif event.key in (pygame.K_RIGHT, pygame.K_d):
                            self.level_select_index = (self.level_select_index + 1) % len(LEVELS)
                        elif event.key == pygame.K_UP:
                            self.level_select_index = (self.level_select_index - 5) % len(LEVELS)
                        elif event.key == pygame.K_DOWN:
                            self.level_select_index = (self.level_select_index + 5) % len(LEVELS)
                        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                            self.level_num = self.level_select_index
                            self._start_level(self._next_grid())
                    elif self.state == self.STATE_PAUSE:
                        if event.key == pygame.K_ESCAPE:
                            self.state = self.STATE_PLAY
                        elif event.key in (pygame.K_UP, pygame.K_w):
                            self.pause_index = (self.pause_index - 1) % 3
                        elif event.key in (pygame.K_DOWN, pygame.K_s):
                            self.pause_index = (self.pause_index + 1) % 3
                        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                            if self.pause_index == 0:
                                self.state = self.STATE_PLAY
                            elif self.pause_index == 1:
                                self._start_level(self._next_grid())
                            else:
                                self._to_menu()
                    else:
                        if event.key == pygame.K_ESCAPE:
                            self.pause_index = 0
                            self.state = self.STATE_PAUSE
                        elif event.key == pygame.K_r:
                            self._restart_run()
                        elif event.key == pygame.K_LSHIFT or event.key == pygame.K_RSHIFT:
                            if self.state == self.STATE_PLAY:
                                self.player.handle_dash_pressed()
                        elif event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                            if self.state == self.STATE_PLAY and not self.player.dead:
                                self.player.handle_jump_pressed()
                                self.audio.play("jump")
            self.update(dt)
            self.draw()
            pygame.display.flip()
        pygame.quit()

    # -- Режим скриншота (отладка) -----------------------------------
    def screenshot(self, out_path, frames=60, menu=False):
        """Прогнать N кадров и сохранить. menu=True — снимок стартового меню."""
        if not menu:
            self._start_game()          # выходим из меню в игру
        for i in range(frames):
            pygame.event.pump()
            jump = i % 40 == 20
            auto = None if menu else 1
            self.update(1 / 60, auto=auto, auto_jump=(jump and not menu))
            self.draw()
            pygame.display.flip()
        pygame.image.save(self.screen, out_path)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--level":
        level = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        game = Game(start_level=level)
        game.state = game.STATE_PLAY
        game.run()
        return
    if len(sys.argv) > 1 and sys.argv[1] == "--shot":
        out = sys.argv[2] if len(sys.argv) > 2 else "_shot.png"
        frames = int(sys.argv[3]) if len(sys.argv) > 3 else 60
        game = Game()
        game.screenshot(out, frames)
        pygame.quit()
        print("saved", out)
    else:
        Game().run()


if __name__ == "__main__":
    main()
