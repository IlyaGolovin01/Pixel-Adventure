"""Сборка уровня из текстовой карты (карту даёт генератор).

Легенда карты:
  'X','I','J','K','L','Q','U','V','W','Y','Z' — стили блоков террейна
  'P' — точка появления игрока
  'f' — фрукт (тип циклически меняется)
  'S' — пила-ловушка          '^' — шип
  'T' — трамплин              'F' — огонь
  'N' — вентилятор            'O' — шипованный шар
  'R' — Rock Head (давилка)   'H' — Spike Head (давилка)
  'A' — стрела-шип            'B' — ящик (с фруктом)
  'M' — движущаяся платформа  'D' — падающая платформа
  'C' — чекпоинт              'E' — финишный флаг
  ' ' — пусто
"""

import pygame

from . import settings as S
from . import assets
from .generator import generate
from .tiles import (Tile, Lamp, Fruit, Saw, Spike, Flag, pick_terrain_image, TERRAIN_SOLIDS,
                    Trampoline, Fire, Fan, SpikedBall, Smasher, Arrow, Box,
                    MovingPlatform, FallingPlatform, Checkpoint)

FRUIT_TYPES = ["Apple", "Bananas", "Cherries", "Kiwi",
               "Melon", "Orange", "Pineapple", "Strawberry"]


class Level:
    def __init__(self, level_num=0, grid=None, rotations=None, routes=None, tile_overrides=None):
        rows = grid if grid is not None else generate(level_num)
        self.cols = max(len(r) for r in rows)
        self.rows = len(rows)
        self.width = self.cols * S.TILE
        self.height = self.rows * S.TILE

        self.tiles = []
        self.solids = []          # список pygame.Rect для коллизий (статичные)
        self.fruits = []
        self.saws = []
        self.spikes = []
        self.hazards = []         # опасности с методом hits(): огонь, шар, давилки, стрелы
        self.boosters = []        # трамплины и вентиляторы (действуют на игрока)
        self.movers = []          # твёрдые движущиеся: платформы (есть .rect и .solid)
        self.boxes = []           # ломкие ящики (твёрдые пока целы)
        self.checkpoints = []
        self.lamps = []
        self.flag = None
        self.player_spawn = (S.TILE, S.TILE)

        # Общие анимационные ресурсы, чтобы не грузить по многу раз
        tileset = assets.load_terrain_tiles()
        collected_frames = assets.load_fruit_collected()
        saw_frames = assets.load_saw()
        spike_img = assets.load_spike()
        flag_frames = assets.load_checkpoint_flag()
        tramp_frames = assets.load_trampoline()
        fire_frames = assets.load_fire()
        fan_frames = assets.load_fan()
        ball_frames = assets.load_spiked_ball()
        rock_frames = assets.load_smasher("Rock Head")
        spikehead_frames = assets.load_smasher("Spike Head")
        arrow_frames = assets.load_arrow()
        box_frames = assets.load_box(1)
        mplat_frames = assets.load_moving_platform("Brown")
        fplat_frames = assets.load_falling_platform()
        checkpoint_frames = assets.load_checkpoint()
        lamp_frames = assets.load_lamp()

        # 1) множество твёрдых клеток — нужно для автотайлинга
        solid_set = set()
        terrain_sets = {style: set() for style in TERRAIN_SOLIDS}
        for r, line in enumerate(rows):
            for c, ch in enumerate(line):
                if ch in TERRAIN_SOLIDS:
                    solid_set.add((c, r))
                    terrain_sets[ch].add((c, r))

        fruit_i = 0
        for r, line in enumerate(rows):
            for c, ch in enumerate(line):
                if ch in TERRAIN_SOLIDS:
                    override = (tile_overrides or {}).get((c, r))
                    img = assets.load_preview_tile(*override) if override and len(override) == 2 and override[0] >= 0 else (tileset.get(tuple(override), pick_terrain_image(tileset, terrain_sets[ch], c, r, ch)) if override else pick_terrain_image(tileset, terrain_sets[ch], c, r, ch))
                    angle = (rotations or {}).get((c, r), (rotations or {}).get(f"{c},{r}", 0))
                    tile = Tile(c, r, img, angle)
                    self.tiles.append(tile)
                    self.solids.append(tile.rect)
                elif ch == "P":
                    self.player_spawn = (c * S.TILE, r * S.TILE)
                elif ch == "f":
                    name = FRUIT_TYPES[fruit_i % len(FRUIT_TYPES)]
                    fruit_i += 1
                    self.fruits.append(Fruit(c, r, name, collected_frames))
                elif ch == "S":
                    self.saws.append(Saw(c, r, saw_frames, route=(routes or {}).get((c, r))))
                elif ch == "^":
                    self.spikes.append(Spike(c, r, spike_img))
                elif ch == "T":
                    self.boosters.append(Trampoline(c, r, tramp_frames))
                elif ch == "F":
                    self.hazards.append(Fire(c, r, fire_frames))
                elif ch == "N":
                    self.boosters.append(Fan(c, r, fan_frames))
                elif ch == "O":
                    self.hazards.append(SpikedBall(c, r, ball_frames, (routes or {}).get((c, r))))
                elif ch == "R":
                    self.movers.append(Smasher(c, r, rock_frames, (routes or {}).get((c, r)), solid=True))
                elif ch == "H":
                    self.hazards.append(Smasher(c, r, spikehead_frames, (routes or {}).get((c, r))))
                elif ch == "A":
                    self.hazards.append(Arrow(c, r, arrow_frames))
                elif ch == "B":
                    name = FRUIT_TYPES[fruit_i % len(FRUIT_TYPES)]
                    fruit_i += 1
                    self.boxes.append(Box(c, r, box_frames, name, collected_frames))
                elif ch == "M":
                    self.movers.append(MovingPlatform(c, r, mplat_frames, (routes or {}).get((c, r))))
                elif ch == "D":
                    self.movers.append(FallingPlatform(c, r, fplat_frames, (routes or {}).get((c, r))))
                elif ch == "C":
                    self.checkpoints.append(Checkpoint(c, r, checkpoint_frames))
                elif ch == "g":
                    self.lamps.append(Lamp(c, r, lamp_frames))
                elif ch == "E":
                    self.flag = Flag(c, r, flag_frames)

        self.total_fruits = len(self.fruits) + len(self.boxes)

    def dynamic_solids(self):
        """Твёрдые прямоугольники этого кадра: тайлы + активные платформы + целые ящики."""
        rects = list(self.solids)
        for m in self.movers:
            if m.solid:
                rects.append(m.rect)
        for b in self.boxes:
            if b.solid:
                rects.append(b.rect)
        return rects

    def spawn_fruit(self, fruit):
        """Добавить выпавший из ящика фрукт в общий список (учтён в total_fruits)."""
        if fruit is not None:
            self.fruits.append(fruit)

    def update(self, dt):
        for f in self.fruits:
            f.update(dt)
        self.fruits = [f for f in self.fruits if not f.done]
        for s in self.saws:
            s.update(dt)
        for h in self.hazards:
            h.update(dt)
        for b in self.boosters:
            b.update(dt)
        for m in self.movers:
            m.update(dt)
        for bx in self.boxes:
            bx.update(dt)
        self.boxes = [bx for bx in self.boxes if not bx.gone]
        for cp in self.checkpoints:
            cp.update(dt)
        for lamp in self.lamps:
            lamp.update(dt)
        if self.flag:
            self.flag.update(dt)

    def draw(self, surf, cam):
        # Тайлы (только видимые)
        view = pygame.Rect(int(cam.x), int(cam.y), S.SCREEN_W, S.SCREEN_H)
        for t in self.tiles:
            if view.colliderect(t.rect):
                surf.blit(t.image, (t.rect.x - cam.x, t.rect.y - cam.y))
        # Траектории идут позади объектов, но поверх фона и террейна.
        for obj in (*self.saws, *self.hazards, *self.movers):
            draw_guide = getattr(obj, "draw_guide", None)
            if draw_guide is not None:
                draw_guide(surf, cam)
        for sp in self.spikes:
            if view.colliderect(sp.rect):
                sp.draw(surf, cam)
        for lamp in self.lamps:
            lamp.draw(surf, cam)
        for cp in self.checkpoints:
            cp.draw(surf, cam)
        for b in self.boosters:
            b.draw(surf, cam)
        for m in self.movers:
            m.draw(surf, cam)
        for bx in self.boxes:
            bx.draw(surf, cam)
        if self.flag:
            self.flag.draw(surf, cam)
        for f in self.fruits:
            f.draw(surf, cam)
        for s in self.saws:
            s.draw(surf, cam)
        for h in self.hazards:
            h.draw(surf, cam)
