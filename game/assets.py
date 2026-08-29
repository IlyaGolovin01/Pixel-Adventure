"""Загрузка и подготовка графических ассетов Pixel Adventure.

Все спрайт-листы разложены горизонтально: N кадров одинакового размера
в один ряд. Тайлсет террейна — сетка 16x16. Здесь мы нарезаем листы на
кадры, увеличиваем их в SCALE раз (nearest-neighbour, чтобы сохранить
чёткий пиксель-арт) и отдаём удобные структуры для анимаций.
"""

import os
import pygame

from . import settings as S

# Корень с ассетами относительно этого файла (game/ -> проект -> assets)
ASSETS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
PREVIEW_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "_tileset_preview.png")

def load_preview_tile(col, row, cols=21, rows=10):
    """Вырезать крупную ячейку из пользовательского атласа-превью."""
    sheet = pygame.image.load(PREVIEW_PATH).convert_alpha()
    cw, ch = sheet.get_width() / cols, sheet.get_height() / rows
    x, y = int(col * cw), int(row * ch)
    w, h = max(1, int((col + 1) * cw) - x), max(1, int((row + 1) * ch) - y)
    tile = sheet.subsurface((x, y, w, h)).copy()
    return pygame.transform.scale(tile, (S.TILE, S.TILE))


def path(*parts):
    return os.path.join(ASSETS, *parts)


def load_image(*parts):
    """Загрузить png с альфа-каналом."""
    return pygame.image.load(path(*parts)).convert_alpha()


def scale(surf, factor=S.SCALE):
    """Увеличить поверхность без сглаживания."""
    w, h = surf.get_size()
    return pygame.transform.scale(surf, (int(w * factor), int(h * factor)))


def slice_strip(surf, frame_w, frame_h, count=None, do_scale=True):
    """Нарезать горизонтальный спрайт-лист на список кадров.

    count=None -> определить число кадров по ширине листа.
    """
    if count is None:
        count = surf.get_width() // frame_w
    frames = []
    for i in range(count):
        frame = surf.subsurface((i * frame_w, 0, frame_w, frame_h)).copy()
        if do_scale:
            frame = scale(frame)
        frames.append(frame)
    return frames


def load_character(name):
    """Загрузить все анимации персонажа из Main Characters/<name>.

    Возвращает dict: имя_состояния -> список кадров (уже увеличенных).
    Кадры персонажей 32x32.
    """
    base = ("Main Characters", name)
    fw = fh = 32
    files = {
        "idle": "Idle (32x32).png",
        "run": "Run (32x32).png",
        "jump": "Jump (32x32).png",
        "fall": "Fall (32x32).png",
        "double_jump": "Double Jump (32x32).png",
        "hit": "Hit (32x32).png",
        "wall_jump": "Wall Jump (32x32).png",
    }
    anims = {}
    for state, fname in files.items():
        sheet = load_image(*base, fname)
        anims[state] = slice_strip(sheet, fw, fh)
    return anims


def load_appear_disappear():
    """Эффекты появления/исчезновения (96x96)."""
    appear = slice_strip(load_image("Main Characters", "Appearing (96x96).png"), 96, 96)
    disappear = slice_strip(
        load_image("Main Characters", "Desappearing (96x96).png"), 96, 96
    )
    return appear, disappear


def load_spawn_effects(factor=2):
    """Кадры появления/исчезновения (96x96), уменьшенные до factor× (×3 слишком велик).

    Возвращает (appear_frames, disappear_frames) — списки кадров одинакового размера.
    """
    appear = slice_strip(
        load_image("Main Characters", "Appearing (96x96).png"), 96, 96, do_scale=False
    )
    disappear = slice_strip(
        load_image("Main Characters", "Desappearing (96x96).png"), 96, 96, do_scale=False
    )
    size = (96 * factor, 96 * factor)
    resize = lambda frames: [pygame.transform.scale(f, size) for f in frames]
    return resize(appear), resize(disappear)


def load_dust():
    """Одиночный кадр пылевого клуба (Other/Dust Particle.png)."""
    return scale(load_image("Other", "Dust Particle.png"), 2)


def load_confetti():
    """Кусочки конфетти — набор цветных кадров из ленты 16x16."""
    frames = slice_strip(
        load_image("Other", "Confetti (16x16).png"), 16, 16, do_scale=False
    )
    return [scale(f, 2) for f in frames]


def load_transition():
    """Ромб перехода (Other/Transition.png); используется как растущая диафрагма."""
    return load_image("Other", "Transition.png")


def load_menu_button(name):
    """Иконка кнопки меню из Menu/Buttons/<name>.png."""
    return scale(load_image("Menu", "Buttons", f"{name}.png"), 2)


def load_level_icon(n):
    """Номерная плашка уровня из Menu/Levels/NN.png (n — номер уровня, с 1)."""
    return scale(load_image("Menu", "Levels", f"{n:02d}.png"), 2)


def load_terrain_tiles():
    """Нарезать тайлсет террейна на словарь (col,row) -> увеличенный тайл."""
    sheet = load_image("Terrain", "Terrain (16x16).png")
    ts = S.NATIVE_TILE
    cols = sheet.get_width() // ts
    rows = sheet.get_height() // ts
    tiles = {}
    for r in range(rows):
        for c in range(cols):
            tile = sheet.subsurface((c * ts, r * ts, ts, ts)).copy()
            tiles[(c, r)] = scale(tile)
    return tiles


def load_fruit(name):
    """Анимация фрукта (17 кадров 32x32)."""
    sheet = load_image("Items", "Fruits", f"{name}.png")
    return slice_strip(sheet, 32, 32)


def load_fruit_collected():
    """Эффект сбора фрукта (Collected.png, 6 кадров 32x32)."""
    sheet = load_image("Items", "Fruits", "Collected.png")
    return slice_strip(sheet, 32, 32)


def load_saw():
    """Анимация вращающейся пилы (On (38x38).png, 8 кадров)."""
    sheet = load_image("Traps", "Saw", "On (38x38).png")
    return slice_strip(sheet, 38, 38)


def load_spike():
    """Статичный шип (Spikes/Idle.png, 16x16) — один увеличенный тайл."""
    return scale(load_image("Traps", "Spikes", "Idle.png"))


def load_checkpoint_flag():
    """Флаг чекпоинта в состоянии Idle (64x64)."""
    sheet = load_image(
        "Items", "Checkpoints", "Checkpoint", "Checkpoint (Flag Idle)(64x64).png"
    )
    return slice_strip(sheet, 64, 64)


def load_background(name):
    """Тайл фона 64x64 (не увеличиваем — тайлим как есть)."""
    return load_image("Background", f"{name}.png")


# --- Новые предметы и ловушки ---------------------------------------
# Соглашение набора Pixel Adventure: имя с «(WxH)» — горизонтальный спрайт-лист,
# обычное имя — одиночный кадр. Все листы — один ряд, поэтому высота кадра равна
# высоте листа; нам достаточно знать ширину кадра из имени файла.

def _row(*parts, fw):
    """Нарезать одноряд­ный лист по ширине кадра fw (высота = высота листа)."""
    sheet = load_image(*parts)
    return slice_strip(sheet, fw, sheet.get_height())


def load_trampoline():
    """Трамплин: покой (Idle) и отскок (Jump 28x28, анимация)."""
    return {
        "idle": [scale(load_image("Traps", "Trampoline", "Idle.png"))],
        "jump": _row("Traps", "Trampoline", "Jump (28x28).png", fw=28),
    }


def load_fire():
    """Огонь: потушен (Off), горит (On 16x32) и вспышка появления (Hit 16x32)."""
    return {
        "off": [scale(load_image("Traps", "Fire", "Off.png"))],
        "on": _row("Traps", "Fire", "On (16x32).png", fw=16),
        "hit": _row("Traps", "Fire", "Hit (16x32).png", fw=16),
    }


def load_fan():
    """Вентилятор: выключен (Off) и крутится (On 24x8)."""
    return {
        "off": [scale(load_image("Traps", "Fan", "Off.png"))],
        "on": _row("Traps", "Fan", "On (24x8).png", fw=24),
    }


def load_moving_platform(color="Brown"):
    """Движущаяся платформа Brown/Grey: покой (Off) и работа (On 32x8)."""
    return {
        "off": [scale(load_image("Traps", "Platforms", f"{color} Off.png"))],
        "on": _row("Traps", "Platforms", f"{color} On (32x8).png", fw=32),
    }


def load_falling_platform():
    """Падающая платформа: покой (Off) и тряска (On 32x10)."""
    return {
        "off": [scale(load_image("Traps", "Falling Platforms", "Off.png"))],
        "on": _row("Traps", "Falling Platforms", "On (32x10).png", fw=32),
    }


def load_smasher(kind="Rock Head"):
    """Давилка Rock Head / Spike Head: покой (Idle) и «моргание» (Blink)."""
    fw = {"Rock Head": 42, "Spike Head": 54}[kind]
    fh = {"Rock Head": 42, "Spike Head": 52}[kind]
    return {
        "idle": [scale(load_image("Traps", kind, "Idle.png"))],
        "blink": _row("Traps", kind, f"Blink ({fw}x{fh}).png", fw=fw),
    }


def load_spiked_ball():
    """Шипованный шар и звено цепи (оба — одиночные кадры)."""
    return {
        "ball": scale(load_image("Traps", "Spiked Ball", "Spiked Ball.png")),
        "chain": scale(load_image("Traps", "Spiked Ball", "Chain.png")),
    }


def load_arrow():
    """Стрела-шип (Arrow Idle 18x18, анимация покоя)."""
    return _row("Traps", "Arrow", "Idle (18x18).png", fw=18)


def load_box(n=1):
    """Ящик Box{n}: покой (Idle) и разрушение (Break, кадр 28x24)."""
    base = ("Items", "Boxes", f"Box{n}")
    return {
        "idle": [scale(load_image(*base, "Idle.png"))],
        "break": _row(*base, "Break.png", fw=28),
    }


def load_checkpoint():
    """Чекпоинт: неактивный (No Flag) и поднятый флаг (Flag Idle 64x64)."""
    base = ("Items", "Checkpoints", "Checkpoint")
    return {
        "no_flag": [scale(load_image(*base, "Checkpoint (No Flag).png"))],
        "flag": _row(*base, "Checkpoint (Flag Idle)(64x64).png", fw=64),
    }


def load_lamp():
    """Подвесная лампа: 6 кадров 16x32 (выключена + тёплое мерцание)."""
    return _row("Items", "Lamp", "Lamp (16x32).png", fw=16)


class Animation:
    """Проигрыватель кадровой анимации.

    Хранит список кадров и текущее время; отдаёт нужный кадр.
    """

    def __init__(self, frames, fps=S.ANIM_FPS, loop=True):
        self.frames = frames
        self.fps = fps
        self.loop = loop
        self.time = 0.0
        self.done = False

    def reset(self):
        self.time = 0.0
        self.done = False

    def update(self, dt):
        self.time += dt * self.fps
        if not self.loop and self.time >= len(self.frames):
            self.time = len(self.frames) - 1
            self.done = True

    def frame(self, flip=False):
        idx = int(self.time) % len(self.frames)
        img = self.frames[idx]
        if flip:
            img = pygame.transform.flip(img, True, False)
        return img
