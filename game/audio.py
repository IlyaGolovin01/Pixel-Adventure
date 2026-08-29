import math
import os
import struct
import wave
import pygame


class Audio:
    def __init__(self):
        self.enabled = False
        self.sounds = {}
        try:
            pygame.mixer.init()
            self.enabled = True
            for name, seq in {
                "jump": (660, 0.10), "step": (180, 0.035), "hazard": (90, 0.18),
                "checkpoint": (880, 0.16), "win": (1040, 0.35),
            }.items():
                self.sounds[name] = self._tone(*seq)
        except pygame.error:
            pass

    def _tone(self, freq, duration):
        rate = 22050
        data = bytearray()
        for i in range(int(rate * duration)):
            v = int(8000 * math.sin(2 * math.pi * freq * i / rate))
            data += struct.pack("<h", v)
        return pygame.mixer.Sound(buffer=bytes(data))

    def play(self, name):
        if self.enabled and name in self.sounds:
            self.sounds[name].play()

    def set_volume(self, value):
        value = max(0.0, min(1.0, float(value)))
        if self.enabled:
            pygame.mixer.music.set_volume(value)
            for sound in self.sounds.values(): sound.set_volume(value)

    def music_for(self, theme):
        if not self.enabled:
            return
        root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "Music")
        path = os.path.join(root, f"{theme}.ogg")
        if os.path.exists(path):
            try:
                pygame.mixer.music.load(path)
                pygame.mixer.music.play(-1)
            except pygame.error:
                pass

    def stop_music(self):
        if self.enabled:
            pygame.mixer.music.stop()
