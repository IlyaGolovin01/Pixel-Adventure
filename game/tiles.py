"""Объекты уровня: террейн (с автотайлингом), фрукты, пилы, финишный флаг."""

import math

import pygame

from . import settings as S
from . import assets
from .assets import Animation

GUIDE_COLOR = (91, 96, 122)
GUIDE_EDGE = (174, 181, 205)


def _dashed_line(surf, start, end, color=GUIDE_COLOR, width=3, dash=10, gap=7):
    """Пунктирная линия диапазона движения."""
    a = pygame.Vector2(start)
    b = pygame.Vector2(end)
    delta = b - a
    length = delta.length()
    if length <= 0:
        return
    direction = delta / length
    pos = 0.0
    while pos < length:
        p1 = a + direction * pos
        p2 = a + direction * min(length, pos + dash)
        pygame.draw.line(surf, color, p1, p2, width)
        pos += dash + gap


def _guide_ends(surf, start, end):
    for point in (start, end):
        pygame.draw.circle(surf, GUIDE_COLOR, point, 6)
        pygame.draw.circle(surf, GUIDE_EDGE, point, 6, 2)

# Левый верхний угол каждой полноценной области 3x3 в Terrain (16x16).
# Строки области: верх, середина, низ; колонки: левый край, центр, правый край.
TERRAIN_STYLES = {
    "X": (6, 0),    # зелёная трава
    "I": (0, 0),    # серый камень
    "J": (0, 4),    # дерево
    "K": (0, 8),    # бирюзовый камень
    "L": (6, 4),    # оранжевая трава
    "Q": (6, 8),    # розовая трава
    "U": (12, 0),   # коричневые панели
    "V": (12, 4),   # светлый металл
    "W": (12, 8),   # оранжевые панели
    "Y": (17, 4),   # красный кирпич
    "Z": (17, 8),   # жёлтые блоки
}
TERRAIN_SOLIDS = set(TERRAIN_STYLES)

# Эти четыре набора занимают область 4x3: правая стенка вынесена в четвёртую
# колонку, а нижние углы лежат под центральной частью большого блока.
PANEL_TILES = {
    "U": (12, 1),  # отдельный коричневый блок
    "V": (12, 5),  # отдельный металлический блок
    "W": (12, 9),  # отдельный оранжевый блок
    "Z": (17, 9),  # отдельный жёлтый блок
}

PANEL_COLORS = {
    "U": ((151, 63, 69), (101, 42, 57), (218, 157, 103)),
    "V": ((166, 181, 194), (77, 91, 108), (219, 228, 234)),
    "W": ((220, 91, 39), (150, 48, 37), (255, 169, 66)),
    "Z": ((225, 203, 37), (160, 103, 20), (255, 239, 91)),
}

_PANEL_CACHE = {}

GRASS = {
    "top_l": (6, 0), "top_m": (7, 0), "top_r": (8, 0),
    "mid_l": (6, 1), "mid_m": (7, 1), "mid_r": (8, 1),
    "bottom_l": (6, 2), "bottom_m": (7, 2), "bottom_r": (8, 2),
}


class Tile:
    """Статичный тайл террейна. image подбирается автотайлингом."""

    __slots__ = ("rect", "image")

    def __init__(self, col, row, image, angle=0):
        self.rect = pygame.Rect(col * S.TILE, row * S.TILE, S.TILE, S.TILE)
        self.image = pygame.transform.rotate(image, angle) if angle else image


class Lamp:
    """Декоративная лампа и источник локального света."""

    def __init__(self, col, row, frames):
        self.anim = Animation(frames[1:] or frames, fps=8)
        self.col, self.row = col, row
        frame = self.anim.frame()
        self.pos = (col * S.TILE + S.TILE // 2 - frame.get_width() // 2,
                    row * S.TILE)
        self.light_pos = pygame.Vector2(col * S.TILE + S.TILE // 2,
                                        row * S.TILE + S.TILE * 1.25)
        self.radius = S.TILE * 7

    def update(self, dt):
        self.anim.update(dt)

    def draw(self, surf, cam):
        surf.blit(self.anim.frame(), (self.pos[0] - cam.x, self.pos[1] - cam.y))


def terrain_key(solid_set, col, row):
    """Вернуть позицию тайла в области 3x3 по соседям того же материала."""
    above = (col, row - 1) in solid_set
    below = (col, row + 1) in solid_set
    left = (col - 1, row) in solid_set
    right = (col + 1, row) in solid_set
    tile_row = 0 if not above else (2 if not below else 1)
    tile_col = 0 if not left else (2 if not right else 1)
    return tile_col, tile_row


def terrain_coord(style, tile_col, tile_row):
    """Преобразовать логическую позицию 3x3 в координату исходного листа."""
    base_c, base_r = TERRAIN_STYLES.get(style, TERRAIN_STYLES["X"])
    if style not in PANEL_TILES:
        return base_c + tile_col, base_r + tile_row
    # Остальные изображения в этих областях — готовые многоклеточные детали,
    # а не части автотайла. Для клеточной карты используем одиночный блок.
    return PANEL_TILES[style]


def terrain_image(tileset, style, tile_col, tile_row):
    """Вернуть тайл материала; панели рисуются как связная поверхность."""
    if style not in PANEL_COLORS:
        return tileset[terrain_coord(style, tile_col, tile_row)]

    key = (style, tile_col, tile_row)
    cached = _PANEL_CACHE.get(key)
    if cached is not None:
        return cached

    base, dark, light = PANEL_COLORS[style]
    tile = pygame.Surface((S.NATIVE_TILE, S.NATIVE_TILE), pygame.SRCALPHA)
    tile.fill(base)

    # Неброская внутренняя фактура без отдельных рамок вокруг каждой клетки.
    pygame.draw.line(tile, tuple(max(0, c - 10) for c in base), (0, 8), (15, 8))
    pygame.draw.rect(tile, tuple(min(255, c + 8) for c in base), (4, 4, 3, 3))

    if tile_row == 0:
        pygame.draw.rect(tile, light, (0, 0, 16, 3))
        pygame.draw.line(tile, dark, (0, 3), (15, 3), 1)
    if tile_row == 2:
        pygame.draw.rect(tile, dark, (0, 13, 16, 3))
        pygame.draw.line(tile, light, (0, 12), (15, 12), 1)
    if tile_col == 0:
        pygame.draw.rect(tile, dark, (0, 0, 3, 16))
        pygame.draw.line(tile, light, (3, 0), (3, 15), 1)
    if tile_col == 2:
        pygame.draw.rect(tile, dark, (13, 0, 3, 16))
        pygame.draw.line(tile, light, (12, 0), (12, 15), 1)

    cached = pygame.transform.scale(tile, (S.TILE, S.TILE))
    _PANEL_CACHE[key] = cached
    return cached


def pick_terrain_image(tileset, solid_set, col, row, style="X"):
    """Выбрать правильный край/центр материала из его области 3x3."""
    dc, dr = terrain_key(solid_set, col, row)
    return terrain_image(tileset, style, dc, dr)


class Fruit:
    """Анимированный собираемый фрукт."""

    def __init__(self, col, row, name, collected_frames):
        self.anim = Animation(assets.load_fruit(name))
        self.collect_anim = Animation(collected_frames, loop=False)
        # Центр клетки
        cx = col * S.TILE + S.TILE // 2
        cy = row * S.TILE + S.TILE // 2
        self.center = (cx, cy)
        # Небольшой хитбокс вокруг центра
        size = int(S.TILE * 0.7)
        self.rect = pygame.Rect(0, 0, size, size)
        self.rect.center = (cx, cy)
        self.collected = False
        self.done = False

    def collect(self):
        if not self.collected:
            self.collected = True
            self.collect_anim.reset()

    def update(self, dt):
        if self.collected:
            self.collect_anim.update(dt)
            if self.collect_anim.done:
                self.done = True
        else:
            self.anim.update(dt)

    def draw(self, surf, cam):
        anim = self.collect_anim if self.collected else self.anim
        frame = anim.frame()
        r = frame.get_rect(center=(self.center[0] - cam.x, self.center[1] - cam.y))
        surf.blit(frame, r)


class Saw:
    """Пила-ловушка: патрулирует по горизонтали и вращается."""

    def __init__(self, col, row, frames, span_tiles=3, route=None):
        self.anim = Animation(frames, fps=24)
        cx = col * S.TILE + S.TILE // 2
        cy = row * S.TILE + S.TILE // 2
        self.center = pygame.Vector2(cx, cy)
        self.origin_x = float(cx)
        self.span = span_tiles * S.TILE
        self.speed = 90.0
        self.dir = 1
        self.origin = self.center.copy()
        self.path = [(pygame.Vector2(x, y) * S.TILE) for x, y in (route or {}).get("path", [])]
        self.path_i = 0
        self.speed = float((route or {}).get("speed", self.speed))
        # Урон-зона — вписанный круг, приближаем прямоугольником поменьше спрайта
        self.radius = int(S.TILE * 0.55)

    def update(self, dt):
        self.anim.update(dt)
        if len(self.path) > 1:
            target = self.origin + self.path[self.path_i]
            delta = target - self.center
            if delta.length() <= self.speed * dt:
                self.center.update(target)
                self.path_i = (self.path_i + 1) % len(self.path)
            elif delta.length_squared():
                self.center += delta.normalize() * self.speed * dt
            return
        self.center.x += self.dir * self.speed * dt
        if self.center.x > self.origin_x + self.span:
            self.center.x = self.origin_x + self.span
            self.dir = -1
        elif self.center.x < self.origin_x - self.span:
            self.center.x = self.origin_x - self.span
            self.dir = 1

    def hits(self, rect):
        """Пересекается ли круг пилы с прямоугольником игрока."""
        cx, cy = self.center
        nx = max(rect.left, min(cx, rect.right))
        ny = max(rect.top, min(cy, rect.bottom))
        return (nx - cx) ** 2 + (ny - cy) ** 2 <= self.radius ** 2

    def draw(self, surf, cam):
        frame = self.anim.frame()
        r = frame.get_rect(center=(self.center.x - cam.x, self.center.y - cam.y))
        surf.blit(frame, r)

    def draw_guide(self, surf, cam):
        if len(self.path) > 1:
            points = [(round(self.origin.x + p.x - cam.x), round(self.origin.y + p.y - cam.y)) for p in self.path]
            pygame.draw.lines(surf, GUIDE_COLOR, False, points + [points[0]], 3)
            return
        y = round(self.center.y - cam.y)
        start = (round(self.origin_x - self.span - cam.x), y)
        end = (round(self.origin_x + self.span - cam.x), y)
        _dashed_line(surf, start, end)


class Spike:
    """Статичный шип-ловушка (стоит на тайле, урон при касании сверху/сбоку)."""

    __slots__ = ("image", "pos", "rect")

    def __init__(self, col, row, image):
        self.image = image
        self.pos = (col * S.TILE, row * S.TILE)
        # Урон-зона чуть уже клетки и прижата книзу (сами шипы невысокие).
        w = int(S.TILE * 0.8)
        h = int(S.TILE * 0.5)
        self.rect = pygame.Rect(0, 0, w, h)
        self.rect.midbottom = (col * S.TILE + S.TILE // 2, (row + 1) * S.TILE)

    def hits(self, rect):
        return self.rect.colliderect(rect)

    def draw(self, surf, cam):
        surf.blit(self.image, (self.pos[0] - cam.x, self.pos[1] - cam.y))


class Flag:
    """Финишный флаг (анимированный)."""

    def __init__(self, col, row, frames, route=None):
        self.anim = Animation(frames)
        # Флаг 64x64 -> ставим основанием на клетку
        fw = frames[0].get_width()
        fh = frames[0].get_height()
        self.pos = (col * S.TILE + S.TILE // 2 - fw // 2,
                    (row + 1) * S.TILE - fh)
        self.rect = pygame.Rect(col * S.TILE, row * S.TILE - S.TILE,
                                S.TILE, S.TILE * 2)

    def update(self, dt):
        self.anim.update(dt)

    def draw(self, surf, cam):
        surf.blit(self.anim.frame(), (self.pos[0] - cam.x, self.pos[1] - cam.y))


# --- Помощник: спрайт на клетке, прижатый основанием к её низу --------
def _grounded_pos(col, row, frame):
    """Левый-верхний угол кадра так, чтобы он стоял по центру клетки на её полу."""
    fw, fh = frame.get_size()
    x = col * S.TILE + S.TILE // 2 - fw // 2
    y = (row + 1) * S.TILE - fh
    return x, y


class Trampoline:
    """Трамплин: стоит на клетке, подбрасывает игрока при приземлении сверху."""

    def __init__(self, col, row, frames, route=None):
        self.idle = Animation(frames["idle"])
        self.jump = Animation(frames["jump"], loop=False)
        self.anim = self.idle
        self.col, self.row = col, row
        # Плоская зона-«батут» в верхней части клетки.
        self.rect = pygame.Rect(col * S.TILE + 4, (row + 1) * S.TILE - S.TILE // 2,
                                S.TILE - 8, S.TILE // 2)

    def bounce(self, player):
        """Если игрок падает на трамплин сверху — подбросить и проиграть анимацию."""
        pr = player.rect
        if player.vel.y < 0:
            return False
        if pr.right <= self.rect.left or pr.left >= self.rect.right:
            return False
        if pr.bottom < self.rect.top or pr.bottom > self.rect.bottom + 12:
            return False
        player.vel.y = -S.TRAMPOLINE_SPEED
        player.on_ground = False
        player.jumps_left = 2
        self.jump.reset()
        self.anim = self.jump
        return True

    def update(self, dt):
        self.anim.update(dt)
        if self.anim is self.jump and self.jump.done:
            self.anim = self.idle

    def draw(self, surf, cam):
        frame = self.anim.frame()
        x, y = _grounded_pos(self.col, self.row, frame)
        surf.blit(frame, (x - cam.x, y - cam.y))


class Fire:
    """Огонь: циклично вспыхивает и гаснет; урон только пока горит."""

    def __init__(self, col, row, frames, route=None):
        self.off = Animation(frames["off"])
        self.on = Animation(frames["on"])
        self.col, self.row = col, row
        self.on_state = False
        self.timer = S.FIRE_OFF_TIME
        # Урон-зона — язык пламени над клеткой (узкая, прижата книзу).
        w = int(S.TILE * 0.5)
        h = S.TILE
        self.rect = pygame.Rect(0, 0, w, h)
        self.rect.midbottom = (col * S.TILE + S.TILE // 2, (row + 1) * S.TILE)

    def update(self, dt):
        self.timer -= dt
        if self.timer <= 0:
            self.on_state = not self.on_state
            self.timer = S.FIRE_ON_TIME if self.on_state else S.FIRE_OFF_TIME
            (self.on if self.on_state else self.off).reset()
        (self.on if self.on_state else self.off).update(dt)

    def hits(self, rect):
        return self.on_state and self.rect.colliderect(rect)

    def draw(self, surf, cam):
        frame = (self.on if self.on_state else self.off).frame()
        x, y = _grounded_pos(self.col, self.row, frame)
        surf.blit(frame, (x - cam.x, y - cam.y))


class Fan:
    """Вентилятор: поток воздуха вверх держит и поднимает игрока над собой."""

    def __init__(self, col, row, frames):
        self.anim = Animation(frames["on"], fps=24)
        self.col, self.row = col, row
        # Столб потока над вентилятором.
        top = (row + 1) * S.TILE
        self.stream = pygame.Rect(col * S.TILE + 2, top - S.FAN_RANGE * S.TILE,
                                  S.TILE - 4, S.FAN_RANGE * S.TILE)

    def affects(self, player, dt):
        if not self.stream.colliderect(player.rect):
            return
        if player.vel.y > -S.FAN_MAX_UP:
            player.vel.y = max(-S.FAN_MAX_UP, player.vel.y - S.FAN_FORCE * dt)
        player.on_ground = False

    def update(self, dt):
        self.anim.update(dt)

    def draw(self, surf, cam):
        frame = self.anim.frame()
        x, y = _grounded_pos(self.col, self.row, frame)
        surf.blit(frame, (x - cam.x, y - cam.y))


class SpikedBall:
    """Шипованный шар на цепи: маятник вокруг точки крепления; урон касанием."""

    def __init__(self, col, row, frames, route=None):
        self.ball = frames["ball"]
        self.chain = frames["chain"]
        self.anchor = pygame.Vector2(col * S.TILE + S.TILE // 2,
                                     row * S.TILE + S.TILE // 2)
        self.length = S.SPIKEBALL_LEN * S.TILE
        self.amp = 1.15                     # размах отклонения, рад
        self.t = 0.0
        self.pos = pygame.Vector2(self.anchor.x, self.anchor.y + self.length)
        self.radius = int(self.ball.get_width() * 0.4)
        self.path = [(pygame.Vector2(x, y) * S.TILE) for x, y in (route or {}).get("path", [])]
        self.path_i = 0
        self.route_speed = float((route or {}).get("speed", 90.0))

    def update(self, dt):
        if len(self.path) > 1:
            target = self.anchor + self.path[self.path_i]
            delta = target - self.anchor
            if delta.length() <= self.route_speed * dt:
                self.anchor.update(target)
                self.path_i = (self.path_i + 1) % len(self.path)
            elif delta.length_squared():
                self.anchor += delta.normalize() * self.route_speed * dt
            self.pos.update(self.anchor)
            return
        self.t += dt * S.SPIKEBALL_SPEED
        angle = self.amp * math.sin(self.t)
        self.pos.x = self.anchor.x + self.length * math.sin(angle)
        self.pos.y = self.anchor.y + self.length * math.cos(angle)

    def hits(self, rect):
        nx = max(rect.left, min(self.pos.x, rect.right))
        ny = max(rect.top, min(self.pos.y, rect.bottom))
        return (nx - self.pos.x) ** 2 + (ny - self.pos.y) ** 2 <= self.radius ** 2

    def draw(self, surf, cam):
        # Цепь: тайлим звено от крепления к шару.
        seg = self.chain.get_height()
        d = self.pos - self.anchor
        dist = max(1.0, d.length())
        steps = int(dist // seg)
        for i in range(steps):
            p = self.anchor + d * (i * seg / dist)
            r = self.chain.get_rect(center=(p.x - cam.x, p.y - cam.y))
            surf.blit(self.chain, r)
        r = self.ball.get_rect(center=(self.pos.x - cam.x, self.pos.y - cam.y))
        surf.blit(self.ball, r)

    def draw_guide(self, surf, cam):
        if len(self.path) > 1:
            points = [(round(self.anchor.x + p.x - cam.x), round(self.anchor.y + p.y - cam.y)) for p in self.path]
            pygame.draw.lines(surf, GUIDE_COLOR, False, points + [points[0]], 3)
            return
        points = []
        for i in range(25):
            angle = -self.amp + 2 * self.amp * i / 24
            x = self.anchor.x + self.length * math.sin(angle) - cam.x
            y = self.anchor.y + self.length * math.cos(angle) - cam.y
            points.append((round(x), round(y)))
        pygame.draw.lines(surf, GUIDE_COLOR, False, points, 3)
        anchor = (round(self.anchor.x - cam.x), round(self.anchor.y - cam.y))
        pygame.draw.circle(surf, GUIDE_EDGE, anchor, 6, 2)


class Smasher:
    """Давилка (Rock Head / Spike Head): рывками ходит вниз-вверх; урон касанием."""

    def __init__(self, col, row, frames, route=None, solid=False):
        self.anim = Animation(frames["idle"])
        self.cx = col * S.TILE + S.TILE // 2
        self.top_y = row * S.TILE + S.TILE // 2   # исходный центр (верх хода)
        self.y = float(self.top_y)
        self.bottom_y = self.top_y + S.SMASHER_RANGE * S.TILE
        self.going_down = True
        img = frames["idle"][0]
        w, h = img.get_size()
        self.half = (int(w * 0.4), int(h * 0.4))
        self.origin = pygame.Vector2(self.cx, self.y)
        self.path = [(pygame.Vector2(x, y) * S.TILE) for x, y in (route or {}).get("path", [])]
        self.path_i = 0
        self.route_speed = float((route or {}).get("speed", S.SMASHER_SPEED))
        self.solid = solid
        self.dx = 0
        self.dy = 0

    def update(self, dt):
        self.anim.update(dt)
        old_x, old_y = self.cx, self.y
        if len(self.path) > 1:
            pos = pygame.Vector2(self.cx, self.y)
            target = self.origin + self.path[self.path_i]
            delta = target - pos
            if delta.length() <= self.route_speed * dt:
                pos.update(target)
                self.path_i = (self.path_i + 1) % len(self.path)
            elif delta.length_squared():
                pos += delta.normalize() * self.route_speed * dt
            self.cx, self.y = pos.x, pos.y
            self.dx = round(self.cx - old_x)
            self.dy = round(self.y - old_y)
            return
        if self.going_down:
            self.y += S.SMASHER_SPEED * dt
            if self.y >= self.bottom_y:
                self.y = self.bottom_y
                self.going_down = False
        else:
            self.y -= S.SMASHER_RETURN * dt
            if self.y <= self.top_y:
                self.y = self.top_y
                self.going_down = True
        self.dx = round(self.cx - old_x)
        self.dy = round(self.y - old_y)

    @property
    def rect(self):
        hw, hh = self.half
        return pygame.Rect(self.cx - hw, int(self.y) - hh, hw * 2, hh * 2)

    def hits(self, rect):
        return self.rect.colliderect(rect)

    def draw(self, surf, cam):
        frame = self.anim.frame()
        r = frame.get_rect(center=(self.cx - cam.x, self.y - cam.y))
        surf.blit(frame, r)

    def draw_guide(self, surf, cam):
        if len(self.path) > 1:
            points = [(round(self.origin.x + p.x - cam.x), round(self.origin.y + p.y - cam.y)) for p in self.path]
            pygame.draw.lines(surf, GUIDE_COLOR, False, points + [points[0]], 3)
            return
        x = round(self.cx - cam.x)
        start = (x, round(self.top_y - cam.y))
        end = (x, round(self.bottom_y - cam.y))
        _dashed_line(surf, start, end)


class Arrow:
    """Статичная стрела-шип: опасность при касании (как шип, но анимированная)."""

    def __init__(self, col, row, frames):
        self.anim = Animation(frames, fps=12)
        self.col, self.row = col, row
        w = int(S.TILE * 0.7)
        h = int(S.TILE * 0.7)
        self.rect = pygame.Rect(0, 0, w, h)
        self.rect.center = (col * S.TILE + S.TILE // 2, row * S.TILE + S.TILE // 2)

    def update(self, dt):
        self.anim.update(dt)

    def hits(self, rect):
        return self.rect.colliderect(rect)

    def draw(self, surf, cam):
        frame = self.anim.frame()
        r = frame.get_rect(center=(self.rect.centerx - cam.x,
                                   self.rect.centery - cam.y))
        surf.blit(frame, r)


class Box:
    """Ящик: твёрдый, пока цел; ломается при касании и роняет фрукт."""

    def __init__(self, col, row, frames, fruit_name, collected_frames):
        self.idle = Animation(frames["idle"])
        self.break_anim = Animation(frames["break"], loop=False)
        self.col, self.row = col, row
        self.fruit_name = fruit_name
        self.collected_frames = collected_frames
        # Коллизия/касание — ровно клетка (сетка чистая, спрайт чуть нависает).
        self.rect = pygame.Rect(col * S.TILE, row * S.TILE, S.TILE, S.TILE)
        self.broken = False
        self.gone = False

    @property
    def solid(self):
        return not self.broken

    def break_open(self):
        """Сломать ящик, вернуть выпавший фрукт (или None, если уже сломан)."""
        if self.broken:
            return None
        self.broken = True
        self.break_anim.reset()
        return Fruit(self.col, self.row, self.fruit_name, self.collected_frames)

    def update(self, dt):
        if self.broken:
            self.break_anim.update(dt)
            if self.break_anim.done:
                self.gone = True
        else:
            self.idle.update(dt)

    def draw(self, surf, cam):
        anim = self.break_anim if self.broken else self.idle
        frame = anim.frame()
        x, y = _grounded_pos(self.col, self.row, frame)
        surf.blit(frame, (x - cam.x, y - cam.y))


class MovingPlatform:
    """Движущаяся платформа: твёрдая, ездит по горизонтали и везёт игрока."""

    def __init__(self, col, row, frames, route=None):
        self.anim = Animation(frames["on"], fps=18)
        img = frames["on"][0]
        w, h = img.get_size()
        self.rect = pygame.Rect(col * S.TILE, row * S.TILE, w, h)
        self.fx = float(self.rect.x)
        self.origin_x = float(self.rect.x)
        self.origin_y = float(self.rect.y)
        raw_path = (route or {}).get("path")
        self.path = [(float(x) * S.TILE, float(y) * S.TILE) for x, y in raw_path] if raw_path else None
        self.path_i = 0
        self.fx = float(self.rect.x)
        self.fy = float(self.rect.y)
        self.span = float((route or {}).get("span", S.PLATFORM_SPAN)) * S.TILE
        self.speed = float((route or {}).get("speed", S.PLATFORM_SPEED))
        self.dir = 1
        self.dx = 0
        self.solid = True

    def update(self, dt):
        self.anim.update(dt)
        old_pos = pygame.Vector2(self.rect.x, self.rect.y)
        if self.path and len(self.path) > 1:
            target = pygame.Vector2(self.rect.x, self.rect.y)
            ox, oy = self.path[self.path_i]
            target.update(self.origin_x + ox, self.origin_y + oy)
            delta = target - pygame.Vector2(self.rect.x, self.rect.y)
            if delta.length() <= self.speed * dt:
                self.rect.topleft = (round(target.x), round(target.y))
                self.path_i = (self.path_i + 1) % len(self.path)
            elif delta.length_squared():
                self.rect.x += round(delta.normalize().x * self.speed * dt)
                self.rect.y += round(delta.normalize().y * self.speed * dt)
            self.dx = self.rect.x - round(old_pos.x)
            return
        self.fx += self.dir * self.speed * dt
        if self.fx > self.origin_x + self.span:
            self.fx = self.origin_x + self.span
            self.dir = -1
        elif self.fx < self.origin_x - self.span:
            self.fx = self.origin_x - self.span
            self.dir = 1
        self.rect.x = round(self.fx)
        self.dx = self.rect.x - round(old_pos.x)

    def draw(self, surf, cam):
        surf.blit(self.anim.frame(), (self.rect.x - cam.x, self.rect.y - cam.y))

    def draw_guide(self, surf, cam):
        if self.path and len(self.path) > 1:
            points = [(round(self.origin_x + x + self.rect.width / 2 - cam.x),
                       round(self.origin_y + y + self.rect.height / 2 - cam.y))
                      for x, y in self.path]
            pygame.draw.lines(surf, GUIDE_COLOR, False, points + [points[0]], 3)
            return
        y = round(self.rect.centery - cam.y)
        half_w = self.rect.width // 2
        start = (round(self.origin_x - self.span + half_w - cam.x), y)
        end = (round(self.origin_x + self.span + half_w - cam.x), y)
        _dashed_line(surf, start, end)


class FallingPlatform:
    """Падающая платформа: твёрдая, но проваливается вскоре после наступа."""

    def __init__(self, col, row, frames, route=None):
        self.off = Animation(frames["off"])
        self.shake = Animation(frames["on"], fps=24)
        img = frames["off"][0]
        w, h = img.get_size()
        self.origin = pygame.Vector2(col * S.TILE, row * S.TILE)
        self.rect = pygame.Rect(col * S.TILE, row * S.TILE, w, h)
        self.dx = 0                        # платформа не ездит — для единого API movers
        self.state = "idle"                # idle → shake → fall → wait
        self.timer = 0.0
        self.vy = 0.0
        self.fall_delay = float((route or {}).get("delay", S.FALL_DELAY))

    @property
    def solid(self):
        return self.state in ("idle", "shake")

    def trigger(self):
        if self.state == "idle":
            self.state = "shake"
            self.timer = self.fall_delay
            self.shake.reset()

    def update(self, dt):
        if self.state == "shake":
            self.shake.update(dt)
            self.timer -= dt
            if self.timer <= 0:
                self.state = "fall"
                self.vy = 0.0
        elif self.state == "fall":
            self.vy = min(self.vy + S.GRAVITY * dt, S.MAX_FALL)
            self.rect.y += int(self.vy * dt)
            self.timer += dt
            if self.timer >= S.FALL_RESPAWN:
                self.state = "wait"
                self.timer = S.FALL_RESPAWN
        elif self.state == "wait":
            self.timer -= dt
            if self.timer <= 0:
                self.rect.topleft = (int(self.origin.x), int(self.origin.y))
                self.state = "idle"
        else:
            self.off.update(dt)

    def draw(self, surf, cam):
        if self.state == "wait":
            return                          # исчезла, ждёт возврата
        anim = self.shake if self.state == "shake" else self.off
        surf.blit(anim.frame(), (self.rect.x - cam.x, self.rect.y - cam.y))


class Checkpoint:
    """Чекпоинт: касание активирует и переносит точку возрождения игрока."""

    def __init__(self, col, row, frames):
        self.no_flag = Animation(frames["no_flag"])
        self.flag = Animation(frames["flag"])
        self.col, self.row = col, row
        self.active = False
        self.spawn = (col * S.TILE, row * S.TILE)
        # Зона касания — колонна в рост флага.
        self.rect = pygame.Rect(col * S.TILE, (row - 1) * S.TILE,
                                S.TILE, S.TILE * 2)

    def activate(self, player):
        if self.active:
            return False
        self.active = True
        self.flag.reset()
        player.spawn.update(self.spawn[0], self.spawn[1])
        return True

    def update(self, dt):
        (self.flag if self.active else self.no_flag).update(dt)

    def draw(self, surf, cam):
        frame = (self.flag if self.active else self.no_flag).frame()
        x, y = _grounded_pos(self.col, self.row, frame)
        surf.blit(frame, (x - cam.x, y - cam.y))
