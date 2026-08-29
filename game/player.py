"""Игрок: физика платформера и анимации.

Хитбокс (self.rect) меньше спрайта: в кадре 32x32 сам персонаж занимает
центр ~18x24 px. Спрайт рисуется со смещением относительно хитбокса.
Коллизии решаются раздельно по осям X и Y (классический подход).
"""

import pygame

from . import settings as S
from . import assets
from .assets import Animation

# Хитбокс в исходных пикселях спрайта (до масштаба)
HITBOX_W = 14
HITBOX_H = 16
# Смещение спрайта относительно левого-верхнего угла хитбокса (в исходных px)
SPRITE_OFF_X = -(32 - HITBOX_W) // 2       # -7
SPRITE_OFF_Y = -(32 - HITBOX_H)           # -6 (ноги к низу)


class Player(pygame.sprite.Sprite):
    def __init__(self, x, y, character="Ninja Frog"):
        super().__init__()
        raw = assets.load_character(character)
        self.anims = {
            "idle": Animation(raw["idle"]),
            "run": Animation(raw["run"]),
            "jump": Animation(raw["jump"], loop=False),
            "fall": Animation(raw["fall"]),
            "double_jump": Animation(raw["double_jump"], loop=False),
            "wall_jump": Animation(raw["wall_jump"], loop=False),
            "hit": Animation(raw["hit"], loop=False),
        }
        self.state = "idle"
        self.facing_left = False

        # Хитбокс в экранных пикселях
        self.rect = pygame.FRect(
            x, y, HITBOX_W * S.SCALE, HITBOX_H * S.SCALE
        )
        self.vel = pygame.Vector2(0, 0)
        self.on_ground = False
        self.jumps_left = 2
        # Сторона стены: -1 слева, 1 справа, 0 — стены нет.
        self.wall_dir = 0
        self.dash_available = True
        self.dash_timer = 0.0

        # Таймеры "прощающей" физики
        self.coyote = 0.0
        self.buffer = 0.0

        # Состояние жизни
        self.dead = False
        self.spawn = pygame.Vector2(x, y)

        self.image = self.anims["idle"].frame()

    # -- Ввод ---------------------------------------------------------
    def handle_jump_pressed(self):
        """Игрок нажал прыжок — запоминаем в буфер."""
        self.buffer = S.JUMP_BUFFER

    def handle_dash_pressed(self):
        if self.dead or self.on_ground or not self.dash_available:
            return
        keys = pygame.key.get_pressed()
        direction = -1 if keys[pygame.K_LEFT] or keys[pygame.K_a] else 1 if keys[pygame.K_RIGHT] or keys[pygame.K_d] else (-1 if self.facing_left else 1)
        self.dash_available = False
        self.dash_timer = S.DASH_TIME
        self.vel.update(direction * S.DASH_SPEED, 0)
        self.facing_left = direction < 0
        self._set_state("run", restart=True)

    def _try_jump(self):
        """Прыжок с земли, от стены или двойной в воздухе."""
        if self.on_ground or self.coyote > 0:
            self.vel.y = -S.JUMP_SPEED
            self.jumps_left = 1
            self.on_ground = False
            self.coyote = 0
            self.buffer = 0
            self._set_state("jump", restart=True)
        elif self.wall_dir:
            self.vel.y = -S.WALL_JUMP_SPEED
            self.vel.x = -self.wall_dir * S.WALL_JUMP_PUSH
            self.facing_left = self.vel.x < 0
            self.jumps_left = 1
            self.wall_dir = 0
            self.buffer = 0
            self._set_state("wall_jump", restart=True)
        elif self.jumps_left > 0:
            self.vel.y = -S.DOUBLE_JUMP_SPEED
            self.jumps_left = 0
            self.buffer = 0
            self._set_state("double_jump", restart=True)

    # -- Обновление ---------------------------------------------------
    def update(self, dt, solids, auto=None):
        if self.dead:
            self._update_dead(dt)
            return

        if self.dash_timer > 0:
            self.dash_timer = max(0.0, self.dash_timer - dt)
            self.rect.x += self.vel.x * dt
            self._collide_axis(solids, axis="x")
            self._update_animation(dt, -1 if self.facing_left else 1)
            return

        if auto is not None:
            # Автопилот для режима скриншота: -1 влево, 1 вправо
            move = auto
        else:
            keys = pygame.key.get_pressed()
            move = 0
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                move -= 1
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                move += 1

        # Горизонтальная скорость с разгоном/торможением
        target = move * S.PLAYER_SPEED
        if move != 0:
            self.facing_left = move < 0
            if self.vel.x < target:
                self.vel.x = min(self.vel.x + S.PLAYER_ACCEL * dt, target)
            elif self.vel.x > target:
                self.vel.x = max(self.vel.x - S.PLAYER_ACCEL * dt, target)
        else:
            # трение до нуля
            if self.vel.x > 0:
                self.vel.x = max(0.0, self.vel.x - S.PLAYER_FRICTION * dt)
            else:
                self.vel.x = min(0.0, self.vel.x + S.PLAYER_FRICTION * dt)

        # Таймеры
        self.coyote = max(0.0, self.coyote - dt)
        self.buffer = max(0.0, self.buffer - dt)
        if self.buffer > 0:
            self._try_jump()

        # Гравитация
        self.vel.y = min(self.vel.y + S.GRAVITY * dt, S.MAX_FALL)

        # Движение + коллизии по осям
        was_on_ground = self.on_ground
        self.rect.x += self.vel.x * dt
        self._collide_axis(solids, axis="x")
        self.rect.y += self.vel.y * dt
        self.on_ground = False
        self._collide_axis(solids, axis="y")

        if was_on_ground and not self.on_ground and self.vel.y >= 0:
            # только что сошли с края — включаем coyote
            self.coyote = S.COYOTE_TIME
        if self.on_ground:
            self.jumps_left = 2
            self.wall_dir = 0
            self.dash_available = True

        self._update_animation(dt, move)

    def _collide_axis(self, solids, axis):
        r = self.rect
        hit = pygame.Rect(int(r.x), int(r.y), int(r.width), int(r.height))
        for s in solids:
            if hit.colliderect(s):
                if axis == "x":
                    if self.vel.x > 0:
                        r.right = s.left
                        self.wall_dir = 1
                    elif self.vel.x < 0:
                        r.left = s.right
                        self.wall_dir = -1
                    self.vel.x = 0
                    hit.x = int(r.x)
                else:  # y
                    if self.vel.y > 0:
                        r.bottom = s.top
                        self.on_ground = True
                    elif self.vel.y < 0:
                        r.top = s.bottom
                    self.vel.y = 0
                    hit.y = int(r.y)

    # -- Смерть / респаун --------------------------------------------
    def kill_player(self):
        if self.dead:
            return
        self.dead = True
        self.vel.x = 0
        self.vel.y = -S.JUMP_SPEED * 0.6  # подпрыгивание при смерти
        self._set_state("hit", restart=True)

    def _update_dead(self, dt):
        # Падаем вниз, проигрывая анимацию удара
        self.vel.y = min(self.vel.y + S.GRAVITY * dt, S.MAX_FALL)
        self.rect.y += self.vel.y * dt
        self.anims["hit"].update(dt)

    def respawn(self):
        self.dead = False
        self.rect.topleft = (self.spawn.x, self.spawn.y)
        self.vel.update(0, 0)
        self.jumps_left = 2
        self.wall_dir = 0
        self.dash_available = True
        self.dash_timer = 0.0
        self._set_state("idle", restart=True)

    # -- Анимация -----------------------------------------------------
    def _set_state(self, state, restart=False):
        if state != self.state:
            self.state = state
            self.anims[state].reset()
        elif restart:
            self.anims[state].reset()

    def _update_animation(self, dt, move):
        if self.state not in ("jump", "double_jump", "wall_jump") or self.anims[self.state].done:
            if not self.on_ground:
                if self.vel.y < 0:
                    self._set_state("jump")
                else:
                    self._set_state("fall")
            elif abs(self.vel.x) > 10:
                self._set_state("run")
            else:
                self._set_state("idle")
        self.anims[self.state].update(dt)

    @property
    def draw_pos(self):
        """Левый-верхний угол спрайта в мировых координатах."""
        return (
            self.rect.x + SPRITE_OFF_X * S.SCALE,
            self.rect.y + SPRITE_OFF_Y * S.SCALE,
        )

    def current_frame(self):
        return self.anims[self.state].frame(flip=self.facing_left)
