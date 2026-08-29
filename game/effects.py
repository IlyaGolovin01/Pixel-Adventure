"""Визуальные эффекты: пыль под ногами, поф появления/смерти, конфетти победы.

Все ассеты уже есть в наборе — здесь они просто оживают. Пыль и пофы живут
в мировых координатах (рисуются со смещением камеры), конфетти — в экранных
(сыплется поверх экрана победы).
"""

import math
import random

import pygame

from . import settings as S
from . import assets
from .assets import Animation


class _Puff:
    """Затухающий пылевой клуб: летит, чуть расширяется и растворяется."""

    __slots__ = ("x", "y", "vx", "vy", "life", "age", "image", "flip")

    def __init__(self, x, y, vx, vy, life, image, flip=False):
        self.x = float(x)
        self.y = float(y)
        self.vx = vx
        self.vy = vy
        self.life = life
        self.age = 0.0
        self.image = image
        self.flip = flip

    def update(self, dt):
        self.age += dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vx *= 0.90          # трение о воздух
        self.vy += 140 * dt      # лёгкое оседание

    @property
    def done(self):
        return self.age >= self.life

    def draw(self, surf, cam):
        t = max(0.0, 1.0 - self.age / self.life)     # 1 → 0
        img = self.image
        k = 0.6 + 0.7 * (1.0 - t)                    # клуб слегка раздувается
        w = max(1, int(img.get_width() * k))
        h = max(1, int(img.get_height() * k))
        frame = pygame.transform.scale(img, (w, h))
        if self.flip:
            frame = pygame.transform.flip(frame, True, False)
        # Надёжное затухание для поверхностей с попиксельной альфой.
        frame.fill((255, 255, 255, int(220 * t)), special_flags=pygame.BLEND_RGBA_MULT)
        surf.blit(frame, (self.x - w / 2 - cam.x, self.y - h / 2 - cam.y))


class _Poof:
    """Одноразовая анимация появления/исчезновения персонажа."""

    __slots__ = ("anim", "cx", "cy")

    def __init__(self, cx, cy, frames, fps=20):
        self.anim = Animation(frames, fps=fps, loop=False)
        self.cx = cx
        self.cy = cy

    def update(self, dt):
        self.anim.update(dt)

    @property
    def done(self):
        return self.anim.done

    def draw(self, surf, cam):
        frame = self.anim.frame()
        r = frame.get_rect(center=(self.cx - cam.x, self.cy - cam.y))
        surf.blit(frame, r)


class _Confetti:
    """Кусочек конфетти в экранных координатах: падает, качается и вращается."""

    __slots__ = ("x", "y", "vx", "vy", "spin", "angle", "image", "life", "age")

    def __init__(self, x, y, image):
        self.x = x
        self.y = y
        self.vx = random.uniform(-70, 70)
        self.vy = random.uniform(40, 170)
        self.spin = random.uniform(-360, 360)
        self.angle = random.uniform(0, 360)
        self.image = image
        self.life = random.uniform(2.2, 3.8)
        self.age = 0.0

    def update(self, dt):
        self.age += dt
        self.vy += 200 * dt
        self.x += self.vx * dt + math.sin(self.age * 5.0) * 22 * dt
        self.y += self.vy * dt
        self.angle += self.spin * dt

    @property
    def done(self):
        return self.age >= self.life or self.y > S.SCREEN_H + 48

    def draw(self, surf):
        img = pygame.transform.rotate(self.image, self.angle)
        surf.blit(img, img.get_rect(center=(self.x, self.y)))


class Effects:
    """Хранилище и менеджер всех визуальных эффектов игры."""

    def __init__(self):
        self.dust_img = assets.load_dust()
        self.appear, self.disappear = assets.load_spawn_effects(2)
        self.confetti_frames = assets.load_confetti()
        self.world = []        # пыль и пофы (мировые координаты)
        self.confetti = []     # конфетти (экранные координаты)
        self._run_t = 0.0

    def reset(self):
        """Очистить эффекты при старте нового уровня."""
        self.world.clear()
        self.confetti.clear()
        self._run_t = 0.0

    # -- Появление / исчезновение ------------------------------------
    def spawn_appear(self, cx, cy):
        self.world.append(_Poof(cx, cy, self.appear))

    def spawn_disappear(self, cx, cy):
        self.world.append(_Poof(cx, cy, self.disappear))

    # -- Пыль ---------------------------------------------------------
    def land_dust(self, player):
        """Всплеск пыли при приземлении — разлетается в обе стороны от ног."""
        cx = player.rect.centerx
        by = player.rect.bottom
        for i in range(5):
            side = -1 if i < 2.5 else 1
            self.world.append(_Puff(
                cx + random.uniform(-6, 6), by,
                side * random.uniform(80, 200), -random.uniform(20, 70),
                random.uniform(0.25, 0.42), self.dust_img, flip=side < 0))

    def run_dust(self, player, dt):
        """Пыль из-под ног во время бега по земле (с интервалом)."""
        if not player.on_ground or abs(player.vel.x) < 40:
            self._run_t = 0.0
            return
        self._run_t -= dt
        if self._run_t <= 0:
            self._run_t = 0.09
            back = -1 if player.vel.x > 0 else 1     # клуб остаётся позади
            self.world.append(_Puff(
                player.rect.centerx + back * 10, player.rect.bottom,
                back * random.uniform(30, 90), -random.uniform(20, 55),
                random.uniform(0.25, 0.4), self.dust_img, flip=back < 0))

    # -- Конфетти -----------------------------------------------------
    def burst_confetti(self, count=90):
        if not self.confetti_frames:
            return
        for _ in range(count):
            img = random.choice(self.confetti_frames)
            self.confetti.append(_Confetti(
                random.uniform(0, S.SCREEN_W),
                random.uniform(-S.SCREEN_H * 0.4, 0), img))

    def clear_confetti(self):
        self.confetti.clear()

    # -- Общий цикл ---------------------------------------------------
    def update(self, dt):
        for p in self.world:
            p.update(dt)
        self.world = [p for p in self.world if not p.done]
        for c in self.confetti:
            c.update(dt)
        self.confetti = [c for c in self.confetti if not c.done]

    def draw_world(self, surf, cam):
        for p in self.world:
            p.draw(surf, cam)

    def draw_screen(self, surf):
        for c in self.confetti:
            c.draw(surf)
