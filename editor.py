"""Редактор уровней Pixel Adventure.

Запуск:
    python editor.py

Возможности:
  * Выбор любого из готовых уровней (game/levels_data.py) и правка «на месте».
  * Кисти: блок, фрукт, пила, шип, старт, флаг, ластик, трамплин, огонь,
    вентилятор, шип. шар, Rock/Spike Head, стрела, ящик, платформы, чекпоинт.
    Первым десяти назначены цифры 1–9,0; остальные выбираются кликом по палитре.
  * Ставим ЛКМ (можно с зажатием — рисуем линию), удаляем ПКМ.
  * Панорама: средняя кнопка мыши (перетаскивание) или стрелки/WASD.
  * Зум: колесо мыши (относительно курсора).
  * Отмена: Ctrl+Z.
  * Сохранение всех уровней обратно в game/levels_data.py: Ctrl+S.

Легенда карты (совместима с игрой):
  'X','I','J','K','L','Q','U','V','W','Y','Z' блоки  'P' старт  'f' фрукт
  'S' пила  '^' шип  'E' флаг
  'T' трамплин  'F' огонь  'N' вентилятор  'O' шип. шар  'R'/'H' давилки
  'A' стрела  'B' ящик  'M' платформа  'D' пад. платформа  'C' чекпоинт  ' ' пусто
"""

import os
import copy
import sys
import subprocess

import pygame

from game import settings as S
from game import assets
from game.tiles import (TERRAIN_STYLES, TERRAIN_SOLIDS, terrain_key,
                        terrain_coord, terrain_image)
from game import levels_data


# --- Кисти -----------------------------------------------------------
# (символ, подпись, горячая клавиша | None). Первым десяти назначены цифры
# 1–9,0; остальные выбираются кликом по палитре.
BRUSHES = [
    ("X", "Блок", pygame.K_1),
    ("I", "Серый", None),
    ("J", "Дерево", None),
    ("K", "Бирюз.", None),
    ("L", "Оранж.тр.", None),
    ("Q", "Розов.тр.", None),
    ("U", "Коричн.", None),
    ("V", "Металл", None),
    ("W", "Оранж.", None),
    ("Y", "Кирпич", None),
    ("Z", "Жёлтый", None),
    ("f", "Фрукт", pygame.K_2),
    ("S", "Пила", pygame.K_3),
    ("^", "Шип", pygame.K_4),
    ("P", "Старт", pygame.K_5),
    ("E", "Флаг", pygame.K_6),
    (" ", "Ластик", pygame.K_7),
    ("T", "Трамплин", pygame.K_8),
    ("F", "Огонь", pygame.K_9),
    ("N", "Вентил.", pygame.K_0),
    ("O", "Шар", None),
    ("R", "Rock", None),
    ("H", "Spike", None),
    ("A", "Стрела", None),
    ("B", "Ящик", None),
    ("M", "Платф.", None),
    ("D", "Пад.пл.", None),
    ("C", "Чекпоинт", None),
    ("g", "Лампа", None),
]
UNIQUE = {"P", "E"}          # таких объектов может быть только один на уровне

# Палитра кистей: сеточные кнопки с переносом по ширине окна.
BTN_W, BTN_H = 122, 46
PAL_X0, PAL_Y0 = 12, 34       # левый край и верх палитры (под строкой заголовка)
PAL_GAP = 6
BOTTOM_H = 34                 # высота нижней строки-статуса

CANVAS_BG = (26, 28, 40)
GRID_COL = (44, 48, 66)
GRID_COL2 = (58, 62, 84)     # линии каждые 5 клеток
BAR_BG = (18, 20, 30)
BAR_HI = (255, 204, 0)
TXT = (235, 238, 245)
TXT_DIM = (150, 156, 176)
BOUND_COL = (90, 150, 255)


class Editor:
    def __init__(self):
        pygame.init()
        self.W, self.H = 1600, 900
        self.screen = pygame.display.set_mode((self.W, self.H), pygame.RESIZABLE)
        pygame.display.set_caption("Pixel Adventure — редактор уровней")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 20, bold=True)
        self.small = pygame.font.SysFont("consolas", 16, bold=True)

        # Все уровни как редактируемые списки списков символов.
        self.levels = [self._to_grid(g) for g in levels_data.LEVELS]
        saved_rotations = getattr(levels_data, "LEVEL_ROTATIONS", [{} for _ in self.levels])
        self.level_rotations = [dict(r) for r in saved_rotations]
        while len(self.level_rotations) < len(self.levels):
            self.level_rotations.append({})
        saved_routes = getattr(levels_data, "LEVEL_ROUTES", [{} for _ in self.levels])
        self.level_routes = [dict(r) for r in saved_routes]
        while len(self.level_routes) < len(self.levels):
            self.level_routes.append({})
        saved_tiles = getattr(levels_data, "LEVEL_TILE_OVERRIDES", [{} for _ in self.levels])
        self.tile_overrides = [dict(r) for r in saved_tiles]
        while len(self.tile_overrides) < len(self.levels): self.tile_overrides.append({})
        if not self.levels:                       # на случай пустого набора
            self.levels = [self._blank_grid(80, 24)]
        self.idx = 0

        # Ассеты для предпросмотра.
        self.tileset = assets.load_terrain_tiles()
        self.icons = {
            "f": assets.load_fruit("Apple")[0],
            "S": assets.load_saw()[0],
            "^": assets.load_spike(),
            "E": assets.load_checkpoint_flag()[0],
            "P": assets.load_character("Ninja Frog")["idle"][0],
            "T": assets.load_trampoline()["idle"][0],
            "F": assets.load_fire()["off"][0],
            "N": assets.load_fan()["on"][0],
            "O": assets.load_spiked_ball()["ball"],
            "R": assets.load_smasher("Rock Head")["idle"][0],
            "H": assets.load_smasher("Spike Head")["idle"][0],
            "A": assets.load_arrow()[0],
            "B": assets.load_box(1)["idle"][0],
            "M": assets.load_moving_platform("Brown")["on"][0],
            "D": assets.load_falling_platform()["off"][0],
            "C": assets.load_checkpoint()["no_flag"][0],
            "g": assets.load_lamp()[2],
        }
        self._scaled = {}                          # кэш масштабированных спрайтов

        self.brush = 0
        self.rotations = [0] * len(BRUSHES)
        # Прямоугольники стрелок «пред./след. уровень» (пересчитываются в _draw_toolbar).
        self._prev_rect = pygame.Rect(self.W - 100, 4, 36, 36)
        self._next_rect = pygame.Rect(self.W - 56, 4, 36, 36)
        self._game_rect = pygame.Rect(self.W - 220, 4, 100, 36)
        self.cam_x = 0.0
        self.cam_y = 0.0
        self.zoom = 1.0
        self.undo_stack = []
        self.painting = None                       # None | "paint" | "erase"
        self.panning = False
        self.pan_from = (0, 0)
        self.status = "Готово. ЛКМ — поставить, ПКМ — стереть, Ctrl+S — сохранить."
        self.status_time = 0.0
        self.dirty = False
        self.selection = None
        self.clipboard = None
        self.route_mode = False
        self.route_anchor = None
        self.route_path = None
        self.tile_palette = False
        self.tile_page = 0
        self.tile_brush = "X"
        self.tileset_preview = pygame.image.load(os.path.join(os.path.dirname(__file__), "_tileset_preview.png")).convert()
        self.preview_rect = pygame.Rect(0, 0, 520, 420)
        self.preview_cols, self.preview_rows = 21, 10
        self.preview_tile = (0, 0)

        self._fit_view()

    # -- Модель уровня ------------------------------------------------
    @staticmethod
    def _to_grid(rows):
        w = max(len(r) for r in rows)
        return [list(r.ljust(w)) for r in rows]

    @staticmethod
    def _blank_grid(w, h):
        return [[" "] * w for _ in range(h)]

    @property
    def grid(self):
        return self.levels[self.idx]

    @property
    def cols(self):
        return len(self.grid[0])

    @property
    def rows(self):
        return len(self.grid)

    @property
    def etile(self):
        return max(10, int(round(S.TILE * self.zoom)))

    # -- Палитра кистей (сетка с переносом) ---------------------------
    def _palette_cols(self):
        """Сколько кнопок помещается в ряд при текущей ширине (место справа под
        переключатель уровня)."""
        avail = self.W - PAL_X0 - 200
        return max(1, avail // (BTN_W + PAL_GAP))

    def _brush_rects(self):
        """Прямоугольники кнопок кистей, разложенные по сетке с переносом."""
        per_row = self._palette_cols()
        rects = []
        for i in range(len(BRUSHES)):
            r, c = divmod(i, per_row)
            x = PAL_X0 + c * (BTN_W + PAL_GAP)
            y = PAL_Y0 + r * (BTN_H + PAL_GAP)
            rects.append(pygame.Rect(x, y, BTN_W, BTN_H))
        return rects

    @property
    def top_h(self):
        """Высота панели инструментов: зависит от числа рядов палитры."""
        per_row = self._palette_cols()
        if self.tile_palette and self.tile_page:
            rows = 10
            return PAL_Y0 + rows * 58 + 8
        rows = (len(BRUSHES) + per_row - 1) // per_row
        return PAL_Y0 + rows * (BTN_H + PAL_GAP) + 8

    def _fit_view(self):
        """Подобрать зум так, чтобы уровень целиком помещался по высоте."""
        avail_h = self.H - self.top_h - BOTTOM_H
        self.zoom = max(0.2, min(1.5, (avail_h / self.rows) / S.TILE))
        self.cam_x = 0.0
        self.cam_y = 0.0

    # -- Масштабирование спрайтов (с кэшем) ---------------------------
    def _fit(self, base, box):
        """Вписать спрайт в квадрат box px, вернуть (surf, ox, oy) для центровки."""
        key = (id(base), box)
        cached = self._scaled.get(key)
        if cached is None:
            bw, bh = base.get_size()
            k = min(box / bw, box / bh)
            sw, sh = max(1, int(bw * k)), max(1, int(bh * k))
            surf = pygame.transform.smoothscale(base, (sw, sh))
            cached = (surf, (box - sw) // 2, (box - sh) // 2)
            self._scaled[key] = cached
        return cached

    def _block_surf(self, style, key):
        """Тайл блока нужного вида, масштабированный под etile (с кэшем)."""
        et = self.etile
        ck = (style, key, et)
        surf = self._scaled.get(ck)
        if surf is None:
            dc, dr = key
            surf = pygame.transform.scale(terrain_image(self.tileset, style, dc, dr),
                                          (et, et))
            self._scaled[ck] = surf
        return surf

    # -- Геометрия камеры ---------------------------------------------
    def canvas_rect(self):
        return pygame.Rect(0, self.top_h, self.W, self.H - self.top_h - BOTTOM_H)

    def screen_to_cell(self, mx, my):
        et = self.etile
        cx = int((mx + self.cam_x) // et)
        cy = int((my - self.top_h + self.cam_y) // et)
        if 0 <= cx < self.cols and 0 <= cy < self.rows:
            return cx, cy
        return None

    def clamp_cam(self):
        et = self.etile
        world_w = self.cols * et
        world_h = self.rows * et
        cv = self.canvas_rect()
        # Разрешаем небольшой отступ, чтобы край было удобно рисовать.
        self.cam_x = max(-40, min(self.cam_x, max(-40.0, world_w - cv.width + 40)))
        self.cam_y = max(-40, min(self.cam_y, max(-40.0, world_h - cv.height + 40)))

    # -- Редактирование -----------------------------------------------
    def push_undo(self):
        self.undo_stack.append((self.idx, copy.deepcopy(self.grid),
                                copy.deepcopy(self.level_rotations[self.idx]),
                                copy.deepcopy(self.level_routes[self.idx])))
        if len(self.undo_stack) > 60:
            self.undo_stack.pop(0)

    def undo(self):
        if self.undo_stack:
            idx, snap, rotations, routes = self.undo_stack.pop()
            self.levels[idx] = snap
            self.level_rotations[idx] = rotations
            self.level_routes[idx] = routes
            self.idx = idx
            self.dirty = True
            self._set_status("Отмена")

    def set_cell(self, cx, cy, ch):
        if self.grid[cy][cx] == ch:
            return
        if ch in UNIQUE:                           # старт/флаг — только один
            for r in range(self.rows):
                for c in range(self.cols):
                    if self.grid[r][c] == ch:
                        self.grid[r][c] = " "
        self.grid[cy][cx] = ch
        if ch in TERRAIN_SOLIDS and self.tile_palette:
            self.tile_overrides[self.idx][(cx, cy)] = tuple(self.preview_tile)
        else:
            self.tile_overrides[self.idx].pop((cx, cy), None)
        key = (cx, cy)
        if ch in TERRAIN_SOLIDS:
            angle = self.rotations[self.brush]
            if angle:
                self.level_rotations[self.idx][key] = angle
            else:
                self.level_rotations[self.idx].pop(key, None)
        else:
            self.level_rotations[self.idx].pop(key, None)
        self.dirty = True

    def apply_brush(self, cx, cy, erase=False):
        ch = " " if erase else BRUSHES[self.brush][0]
        self.set_cell(cx, cy, ch)

    def switch_level(self, delta):
        self.idx = (self.idx + delta) % len(self.levels)
        self._fit_view()
        self._set_status(f"Уровень {self.idx + 1}/{len(self.levels)}")

    # -- Сохранение ---------------------------------------------------
    def save(self):
        out = os.path.join(os.path.dirname(__file__), "game", "levels_data.py")
        lines = [
            '"""Готовые уровни (запечены заранее). Показываются в случайном порядке.',
            "",
            "Отредактированы в editor.py. Каждый элемент LEVELS — карта уровня",
            "(список строк одинаковой длины).",
            "Легенда: X/I/J/K/L/Q/U/V/W/Y/Z блоки  P старт  f фрукт  S пила  ^ шип  E флаг",
            "  T трамплин  F огонь  N вентилятор  O шип.шар  R/H давилки",
            "  A стрела  B ящик  M платформа  D пад.платформа  C чекпоинт  g лампа",
            '"""',
            "",
            "LEVELS = [",
        ]
        for grid in self.levels:
            lines.append("    [")
            for row in grid:
                lines.append("        %r," % "".join(row))
            lines.append("    ],")
        lines.append("]")
        lines.extend(["", "LEVEL_ROUTES = ["])
        for routes in self.level_routes:
            lines.append("    %r," % routes)
        lines.append("]")
        lines.extend(["", "LEVEL_TILE_OVERRIDES = ["])
        for overrides in self.tile_overrides:
            lines.append("    %r," % overrides)
        lines.append("]")
        lines.extend(["", "LEVEL_ROTATIONS = ["])
        for rotations in self.level_rotations:
            lines.append("    %r," % rotations)
        lines.append("]")
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        self.dirty = False
        self._set_status(f"Сохранено {len(self.levels)} уровней → game/levels_data.py")

    def _set_status(self, msg):
        self.status = msg
        self.status_time = 3.0

    # -- Ввод ---------------------------------------------------------
    def handle_wheel(self, y, mx, my):
        if self.route_mode or pygame.key.get_mods() & pygame.KMOD_ALT:
            cell = self.route_anchor or self.screen_to_cell(mx, my)
            if cell and self.grid[cell[1]][cell[0]] in ("M", "D"):
                self.push_undo()
                route = self.level_routes[self.idx].setdefault(cell, {})
                if self.grid[cell[1]][cell[0]] == "M":
                    route["span"] = max(1, min(20, route.get("span", S.PLATFORM_SPAN) + y))
                    self._set_status(f"Маршрут платформы: {route['span']} клеток")
                else:
                    route["delay"] = max(0.1, min(3.0, route.get("delay", S.FALL_DELAY) + y * 0.1))
                    self._set_status(f"Задержка падения: {route['delay']:.1f} с")
                self.dirty = True
                return
        old = self.etile
        self.zoom = max(0.25, min(2.5, self.zoom * (1.1 if y > 0 else 1 / 1.1)))
        new = self.etile
        if new != old:
            # Держим точку под курсором на месте.
            self.cam_x = (self.cam_x + mx) * new / old - mx
            self.cam_y = (self.cam_y + (my - self.top_h)) * new / old - (my - self.top_h)
            self.clamp_cam()

    def toolbar_click(self, mx, my):
        """Клик по верхней панели: кисти и переключатели уровня."""
        if self.tile_palette and self.tile_page:
            cell_w, cell_h = 72, 58
            for i in range(210):
                c, r = i % 21, i // 21
                if pygame.Rect(8 + c * cell_w, 34 + r * cell_h, cell_w - 4, cell_h - 4).collidepoint(mx, my):
                    self.preview_tile = (c, r)
                    self._set_status(f"Выбран блок tileset: {c},{r}")
                    return True
            return my < self.top_h
        for i, rect in enumerate(self._brush_rects()):
            if rect.collidepoint(mx, my):
                self.brush = i
                return True
        if self._prev_rect.collidepoint(mx, my):
            self.switch_level(-1)
            return True
        if self._next_rect.collidepoint(mx, my):
            self.switch_level(1)
            return True
        if self._game_rect.collidepoint(mx, my):
            self.launch_game()
            return True
        return my < self.top_h                      # клик по панели не рисует по карте

    def launch_game(self):
        """Сохранить карты, закрыть редактор и открыть игру в меню."""
        if self.dirty:
            self.save()
        game = os.path.join(os.path.dirname(__file__), "main.py")
        pygame.quit()
        subprocess.Popen([sys.executable, game, "--level", str(self.idx)], cwd=os.path.dirname(game))
        self._quit_requested = True

    def handle_event(self, e):
        if e.type == pygame.QUIT:
            return False
        if e.type == pygame.VIDEORESIZE:
            self.W, self.H = e.w, e.h
            self.screen = pygame.display.set_mode((self.W, self.H), pygame.RESIZABLE)
        elif e.type == pygame.KEYDOWN:
            self._on_key(e)
        elif e.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            self.handle_wheel(e.y, mx, my)
        elif e.type == pygame.MOUSEBUTTONDOWN:
            self._on_mouse_down(e)
        elif e.type == pygame.MOUSEBUTTONUP:
            if e.button in (1, 3):
                self.painting = None
            elif e.button == 2:
                self.panning = False
        elif e.type == pygame.MOUSEMOTION:
            self._on_mouse_move(e)
        return True

    def _on_key(self, e):
        mods = pygame.key.get_mods()
        ctrl = mods & pygame.KMOD_CTRL
        if ctrl and e.key == pygame.K_s:
            self.save()
        elif ctrl and e.key == pygame.K_z:
            self.undo()
        elif ctrl and e.key == pygame.K_c and self.selection:
            x0, y0, x1, y1 = self.selection
            self.clipboard = [row[x0:x1 + 1] for row in self.grid[y0:y1 + 1]]
            self._set_status("Область скопирована")
        elif ctrl and e.key == pygame.K_v and self.clipboard:
            cell = self.screen_to_cell(*pygame.mouse.get_pos())
            if cell:
                self.push_undo()
                for yy, row in enumerate(self.clipboard):
                    for xx, ch in enumerate(row):
                        if cell[1] + yy < self.rows and cell[0] + xx < self.cols:
                            self.grid[cell[1] + yy][cell[0] + xx] = ch
                self.dirty = True
                self._set_status("Область вставлена")
        elif e.key in (pygame.K_LEFTBRACKET, pygame.K_PAGEUP):
            if self.route_mode and self.route_anchor:
                self._adjust_route(-1)
            else:
                self.switch_level(-1)
        elif e.key in (pygame.K_RIGHTBRACKET, pygame.K_PAGEDOWN):
            if self.route_mode and self.route_anchor:
                self._adjust_route(1)
            else:
                self.switch_level(1)
        elif e.key == pygame.K_HOME:
            self._fit_view()
        elif e.key == pygame.K_ESCAPE:
            pygame.event.post(pygame.event.Event(pygame.QUIT))
        elif e.key == pygame.K_F3:
            self.route_mode = not self.route_mode
            self.route_anchor = None
            self.route_path = None
            self.painting = None
            self._set_status("Режим маршрутов включён" if self.route_mode else "Режим маршрутов выключен")
        elif e.key == pygame.K_t:
            self.tile_palette = not self.tile_palette
            self._set_status("Тайлсет: средняя кнопка выбирает материал" if self.tile_palette else "Обычная палитра")
        elif e.key in (pygame.K_TAB, pygame.K_2):
            self.tile_palette = True
            self.tile_page = 1 - self.tile_page
            self._set_status("Страница 2: блоки из tileset_preview.png" if self.tile_page else "Страница 1: игровые кисти")
        elif e.key == pygame.K_F6:
            self.launch_game()
        elif e.key == pygame.K_F2:
            self.selection = None
            self._set_status("Выделение: Shift+ЛКМ по углам")
        elif e.key == pygame.K_n and ctrl:
            self.push_undo()
            self.levels[self.idx] = [row + [" "] * 4 for row in self.grid]
            self.dirty = True
            self._fit_view()
            self._set_status(f"Размер карты: {self.cols}x{self.rows}")
        elif ctrl and e.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
            self.resize_map(e.key)
        elif self.route_mode and self.route_anchor and e.key in (pygame.K_MINUS, pygame.K_KP_MINUS,
                                                                  pygame.K_EQUALS, pygame.K_KP_PLUS):
            cell = self.route_anchor
            if self.grid[cell[1]][cell[0]] == "M":
                self.push_undo()
                route = self.level_routes[self.idx].setdefault(cell, {})
                delta = 10 if e.key in (pygame.K_EQUALS, pygame.K_KP_PLUS) else -10
                route["speed"] = max(20, min(500, route.get("speed", S.PLATFORM_SPEED) + delta))
                self.dirty = True
                self._set_status(f"Скорость: {route['speed']:.0f} px/с")
        elif e.key == pygame.K_r:
            self.rotations[self.brush] = (self.rotations[self.brush] + 90) % 360
            self._set_status(f"Поворот кисти: {self.rotations[self.brush]}°")
        else:
            for i, (_, _, hk) in enumerate(BRUSHES):
                if e.key == hk:
                    self.brush = i

    def resize_map(self, key):
        self.push_undo()
        if key == pygame.K_RIGHT:
            for row in self.grid:
                row.append(" ")
        elif key == pygame.K_LEFT and self.cols > 8:
            for row in self.grid:
                row.pop()
        elif key == pygame.K_DOWN:
            self.grid.append([" "] * self.cols)
        elif key == pygame.K_UP and self.rows > 8:
            self.grid.pop()
        self.level_rotations[self.idx] = {
            p: a for p, a in self.level_rotations[self.idx].items()
            if p[0] < self.cols and p[1] < self.rows
        }
        self.level_routes[self.idx] = {
            p: route for p, route in self.level_routes[self.idx].items()
            if p[0] < self.cols and p[1] < self.rows
        }
        self.dirty = True
        self.clamp_cam()
        self._set_status(f"Размер карты: {self.cols}x{self.rows}")

    def _adjust_route(self, delta):
        c, r = self.route_anchor
        if self.grid[r][c] != "M":
            return
        self.push_undo()
        route = self.level_routes[self.idx].setdefault((c, r), {})
        route["span"] = max(1, min(20, route.get("span", S.PLATFORM_SPAN) + delta))
        self.dirty = True
        self._set_status(f"Маршрут: {route['span']} клеток; +/- скорость")

    def _on_mouse_down(self, e):
        mx, my = e.pos
        if self.tile_palette and e.button == 1 and self.preview_rect.collidepoint(mx, my):
            pw, ph = self.preview_rect.size
            tx = min(self.preview_cols - 1, max(0, int((mx - self.preview_rect.x) * self.preview_cols / pw)))
            ty = min(self.preview_rows - 1, max(0, int((my - self.preview_rect.y) * self.preview_rows / ph)))
            self.preview_tile = (tx, ty)
            self.brush = next((i for i, b in enumerate(BRUSHES) if b[0] == self.tile_brush), self.brush)
            self._set_status(f"Выбран тайл: {tx},{ty}. ЛКМ рисует его")
            return
        if my < self.top_h:
            self.toolbar_click(mx, my)
            return
        if e.button == 2:                          # средняя — панорама
            if self.tile_palette:
                cell = self.screen_to_cell(*e.pos)
                if cell and self.grid[cell[1]][cell[0]] in TERRAIN_SOLIDS:
                    self.tile_brush = self.grid[cell[1]][cell[0]]
                    self.brush = next((i for i, b in enumerate(BRUSHES) if b[0] == self.tile_brush), self.brush)
                    self._set_status(f"Выбран тайл {self.tile_brush}: рисуйте ЛКМ")
                return
            self.panning = True
            self.pan_from = (mx, my)
            return
        if e.button in (1, 3):
            if self.route_mode and e.button == 1:
                cell = self.screen_to_cell(*e.pos)
                if cell and self.grid[cell[1]][cell[0]] in ("M", "D", "S", "O", "R", "H"):
                    self.route_anchor = cell
                    self.route_path = list(self.level_routes[self.idx].get(cell, {}).get("path", [(0, 0)]))
                    self._set_status("Колесо: длина/задержка; +/-: скорость")
                elif self.route_anchor and self.route_path is not None and cell:
                    self.route_path.append((cell[0] - self.route_anchor[0], cell[1] - self.route_anchor[1]))
                    self.level_routes[self.idx].setdefault(self.route_anchor, {})["path"] = self.route_path
                    self.dirty = True
                    self._set_status(f"Точка {len(self.route_path)} добавлена; ПКМ завершить")
                return
            if self.route_mode and e.button == 3 and self.route_anchor and self.route_path:
                self.level_routes[self.idx].setdefault(self.route_anchor, {})["path"] = self.route_path
                self.dirty = True
                self.route_path = None
                self._set_status("Маршрут сохранён")
                return
            if e.button == 1 and pygame.key.get_mods() & pygame.KMOD_SHIFT:
                cell = self.screen_to_cell(*e.pos)
                if cell:
                    if self.selection is None:
                        self.selection = (cell[0], cell[1], cell[0], cell[1])
                    else:
                        x0, y0, _, _ = self.selection
                        self.selection = (min(x0, cell[0]), min(y0, cell[1]), max(x0, cell[0]), max(y0, cell[1]))
                    self._set_status("Область выделена")
                return
            self.push_undo()
            self.painting = "paint" if e.button == 1 else "erase"
            cell = self.screen_to_cell(mx, my)
            if cell:
                self.apply_brush(*cell, erase=(e.button == 3))

    def _on_mouse_move(self, e):
        mx, my = e.pos
        if self.panning:
            dx, dy = mx - self.pan_from[0], my - self.pan_from[1]
            self.cam_x -= dx
            self.cam_y -= dy
            self.pan_from = (mx, my)
            self.clamp_cam()
            return
        if self.painting and my >= self.top_h:
            cell = self.screen_to_cell(mx, my)
            if cell:
                self.apply_brush(*cell, erase=(self.painting == "erase"))

    def _pan_keys(self, dt):
        keys = pygame.key.get_pressed()
        speed = 700 * dt
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.cam_x -= speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.cam_x += speed
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            self.cam_y -= speed
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            self.cam_y += speed
        if any((keys[pygame.K_LEFT], keys[pygame.K_RIGHT], keys[pygame.K_UP],
                keys[pygame.K_DOWN], keys[pygame.K_a], keys[pygame.K_d],
                keys[pygame.K_w])):
            self.clamp_cam()

    # -- Отрисовка ----------------------------------------------------
    def draw(self):
        self.screen.fill(CANVAS_BG)
        self._draw_canvas()
        self._draw_toolbar()
        self._draw_status()

    def _draw_canvas(self):
        et = self.etile
        cv = self.canvas_rect()
        prev = self.screen.get_clip()
        self.screen.set_clip(cv)

        # Множество твёрдых клеток для автотайлинга блоков.
        solid = set()
        terrain_sets = {style: set() for style in TERRAIN_SOLIDS}
        for r in range(self.rows):
            row = self.grid[r]
            for c in range(self.cols):
                if row[c] in TERRAIN_SOLIDS:
                    solid.add((c, r))
                    terrain_sets[row[c]].add((c, r))

        # Видимый диапазон клеток.
        c0 = max(0, int(self.cam_x // et))
        c1 = min(self.cols, int((self.cam_x + cv.width) // et) + 1)
        r0 = max(0, int(self.cam_y // et))
        r1 = min(self.rows, int((self.cam_y + cv.height) // et) + 1)

        # Фон уровня (чуть светлее канвы) + рамка границ.
        wx = -self.cam_x
        wy = self.top_h - self.cam_y
        pygame.draw.rect(self.screen, (32, 35, 50),
                         (wx, wy, self.cols * et, self.rows * et))

        # Сетка.
        for c in range(c0, c1 + 1):
            x = int(wx + c * et)
            col = GRID_COL2 if c % 5 == 0 else GRID_COL
            pygame.draw.line(self.screen, col, (x, wy),
                             (x, wy + self.rows * et))
        for r in range(r0, r1 + 1):
            y = int(wy + r * et)
            col = GRID_COL2 if r % 5 == 0 else GRID_COL
            pygame.draw.line(self.screen, col, (wx, y),
                             (wx + self.cols * et, y))

        # Объекты.
        for r in range(r0, r1):
            row = self.grid[r]
            for c in range(c0, c1):
                ch = row[c]
                if ch == " ":
                    continue
                x = int(wx + c * et)
                y = int(wy + r * et)
                if ch in TERRAIN_SOLIDS:
                    key = terrain_key(terrain_sets[ch], c, r)
                    surf = self._block_surf(ch, key)
                    angle = self.level_rotations[self.idx].get((c, r), 0)
                    if angle:
                        surf = pygame.transform.rotate(surf, angle)
                    self.screen.blit(surf, (x, y))
                else:
                    base = self.icons.get(ch)
                    if base is not None:
                        surf, ox, oy = self._fit(base, et)
                        self.screen.blit(surf, (x + ox, y + oy))

        # Граница уровня.
        pygame.draw.rect(self.screen, BOUND_COL,
                         (wx, wy, self.cols * et, self.rows * et), 2)
        if self.route_mode:
            for rr in range(self.rows):
                for rc in range(self.cols):
                    if self.grid[rr][rc] not in ("M", "S", "O", "R", "H"):
                        continue
                    route = self.level_routes[self.idx].get((rc, rr), {})
                    path = route.get("path")
                    if path and len(path) > 1:
                        points = [(int(wx + (rc + 0.5 + px) * et), int(wy + (rr + 0.5 + py) * et)) for px, py in path]
                        # Игровой объект после последней точки возвращается к первой,
                        # поэтому редактор тоже рисует замыкающий сегмент.
                        pygame.draw.lines(self.screen, (80, 210, 255), True, points, 3)
                        for n, point in enumerate(points):
                            pygame.draw.circle(self.screen, (255, 220, 80), point, 6)
                            label = self.small.render(str(n + 1), True, (20, 20, 30))
                            self.screen.blit(label, label.get_rect(center=point))
                        continue
                    span = route.get("span", S.PLATFORM_SPAN)
                    y = int(wy + (rr + 0.5) * et)
                    x0 = int(wx + (rc + 0.5 - span) * et)
                    x1 = int(wx + (rc + 0.5 + span) * et)
                    pygame.draw.line(self.screen, (80, 210, 255), (x0, y), (x1, y), 3)
                    pygame.draw.circle(self.screen, (80, 210, 255), (x0, y), 5)
                    pygame.draw.circle(self.screen, (80, 210, 255), (x1, y), 5)
        if self.selection:
            x0, y0, x1, y1 = self.selection
            pygame.draw.rect(self.screen, BAR_HI,
                             (wx + x0 * et, wy + y0 * et,
                              (x1 - x0 + 1) * et, (y1 - y0 + 1) * et), 3)

        # Подсветка клетки под курсором.
        mx, my = pygame.mouse.get_pos()
        if cv.collidepoint(mx, my):
            cell = self.screen_to_cell(mx, my)
            if cell:
                hx = int(wx + cell[0] * et)
                hy = int(wy + cell[1] * et)
                hl = pygame.Surface((et, et), pygame.SRCALPHA)
                hl.fill((255, 204, 0, 60))
                self.screen.blit(hl, (hx, hy))
                pygame.draw.rect(self.screen, BAR_HI, (hx, hy, et, et), 2)

        self.screen.set_clip(prev)
    def _draw_toolbar(self):
        top_h = self.top_h
        pygame.draw.rect(self.screen, BAR_BG, (0, 0, self.W, top_h))
        pygame.draw.line(self.screen, (60, 64, 88), (0, top_h), (self.W, top_h), 2)

        title = self.small.render("Кисть (клик или 1–9,0):", True, TXT_DIM)
        self.screen.blit(title, (PAL_X0, 10))
        if self.tile_palette and self.tile_page:
            self.screen.blit(self.font.render("Страница 2 — tileset_preview.png (TAB — назад)", True, BAR_HI), (PAL_X0, 10))
            info = self.small.render("Клик по блоку справа выбирает его; ЛКМ по карте рисует", True, TXT_DIM)
            self.screen.blit(info, (PAL_X0, 62))
        if self.tile_palette:
            label = self.font.render("TАЙЛСЕТ: T выключить | MMB взять тайл с карты", True, BAR_HI)
            self.screen.blit(label, (PAL_X0 + 330, 10))

        if self.tile_palette and self.tile_page:
            cell_w = max(48, (self.W - 20) // 21)
            for i in range(210):
                c, r = i % 21, i // 21
                rect = pygame.Rect(8 + c * cell_w, 34 + r * 58, cell_w - 3, 55)
                sx, sy = int(c * self.tileset_preview.get_width() / 21), int(r * self.tileset_preview.get_height() / 10)
                ex, ey = int((c + 1) * self.tileset_preview.get_width() / 21), int((r + 1) * self.tileset_preview.get_height() / 10)
                tile = pygame.transform.scale(self.tileset_preview.subsurface((sx, sy, ex - sx, ey - sy)), rect.size)
                self.screen.blit(tile, rect)
                pygame.draw.rect(self.screen, BAR_HI if self.preview_tile == (c, r) else (70, 74, 96), rect, 2)
            return
        for i, ((ch, label, hk), rect) in enumerate(zip(BRUSHES, self._brush_rects())):
            active = i == self.brush
            pygame.draw.rect(self.screen, (44, 48, 66) if active else (30, 33, 48),
                             rect, border_radius=6)
            pygame.draw.rect(self.screen, BAR_HI if active else (70, 74, 96),
                             rect, 2, border_radius=6)
            # Иконка кисти слева.
            box = rect.height - 10
            ix, iy = rect.x + 5, rect.y + 5
            if ch in TERRAIN_SOLIDS:
                icon = pygame.transform.scale(
                    terrain_image(self.tileset, ch, 1, 0), (box, box))
                self.screen.blit(icon, (ix, iy))
            elif ch == " ":
                pygame.draw.rect(self.screen, (60, 40, 44),
                                 (ix, iy, box, box), border_radius=4)
                pygame.draw.line(self.screen, (220, 90, 90),
                                 (ix + 5, iy + 5), (ix + box - 5, iy + box - 5), 3)
                pygame.draw.line(self.screen, (220, 90, 90),
                                 (ix + box - 5, iy + 5), (ix + 5, iy + box - 5), 3)
            else:
                surf, ox, oy = self._fit(self.icons[ch], box)
                self.screen.blit(surf, (ix + ox, iy + oy))
            # Подпись + (если есть) горячая клавиша под ней.
            tx = rect.x + box + 10
            lbl = self.small.render(label, True, TXT if active else TXT_DIM)
            if hk is not None:
                self.screen.blit(lbl, (tx, rect.y + 5))
                kk = self.small.render(f"[{pygame.key.name(hk).upper()}]", True, TXT_DIM)
                self.screen.blit(kk, (tx, rect.y + 24))
            else:
                self.screen.blit(lbl, (tx, rect.centery - lbl.get_height() // 2))

        # Переключатель уровня справа.
        star = "*" if self.dirty else ""
        lvl = self.font.render(f"Уровень {self.idx + 1}/{len(self.levels)}{star}",
                               True, TXT)
        lr = lvl.get_rect(midright=(self.W - 120, 22))
        self.screen.blit(lvl, lr)
        self._game_rect = pygame.Rect(self.W - 220, 4, 100, 36)
        pygame.draw.rect(self.screen, (44, 48, 66), self._game_rect, border_radius=6)
        pygame.draw.rect(self.screen, (90, 94, 120), self._game_rect, 2, border_radius=6)
        game_label = self.small.render("Игра", True, TXT)
        self.screen.blit(game_label, game_label.get_rect(center=self._game_rect.center))
        self._prev_rect = pygame.Rect(self.W - 100, 4, 36, 36)
        self._next_rect = pygame.Rect(self.W - 56, 4, 36, 36)
        for rect, ch in ((self._prev_rect, "<"), (self._next_rect, ">")):
            pygame.draw.rect(self.screen, (44, 48, 66), rect, border_radius=6)
            pygame.draw.rect(self.screen, (90, 94, 120), rect, 2, border_radius=6)
            g = self.font.render(ch, True, TXT)
            self.screen.blit(g, g.get_rect(center=rect.center))

    def _draw_status(self):
        y = self.H - BOTTOM_H
        pygame.draw.rect(self.screen, BAR_BG, (0, y, self.W, BOTTOM_H))
        pygame.draw.line(self.screen, (60, 64, 88), (0, y), (self.W, y), 1)
        left = self.small.render(self.status, True,
                                 BAR_HI if self.status_time > 0 else TXT_DIM)
        self.screen.blit(left, (12, y + 8))
        hint = ("ЛКМ ставить · ПКМ стереть · колесо зум · сред.кнопка/стрелки "
                "панорама · [ ] уровень · Ctrl+Z отмена · Ctrl+S сохранить")
        if self.route_mode:
            hint = "F3 маршруты: ЛКМ M выбрать, ЛКМ точки, ПКМ завершить | [ ] длина | +/- скорость | Ctrl+S"
        hs = self.small.render(hint, True, TXT_DIM)
        self.screen.blit(hs, hs.get_rect(midright=(self.W - 12, y + BOTTOM_H // 2)))

    # -- Главный цикл -------------------------------------------------
    def run(self):
        running = True
        self._quit_requested = False
        while running:
            dt = self.clock.tick(60) / 1000.0
            for e in pygame.event.get():
                if not self.handle_event(e):
                    running = False
            if self._quit_requested:
                running = False
            self._pan_keys(dt)
            if self.status_time > 0:
                self.status_time -= dt
            self.draw()
            pygame.display.flip()
        pygame.quit()


if __name__ == "__main__":
    Editor().run()
