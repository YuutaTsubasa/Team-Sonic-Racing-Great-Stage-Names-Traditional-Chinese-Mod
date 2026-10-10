"""Glyph images from a stz: Atlas(sec3).glyph_img(g) -> RGBA array; textures decoded on demand."""
import struct
import numpy as np
from ptex import Ptex

class Atlas:
    def __init__(self, sec3):
        self.P = Ptex(sec3); self.cache = {}
    def tex(self, ti):
        if ti not in self.cache:
            self.cache[ti] = self.P.decode(ti)
        return self.cache[ti]
    def origin(self, page):
        return self.P.sprite_rect(page)
    def glyph_img(self, g):
        ti, ox, oy = self.origin(g.page)
        return self.tex(ti)[oy + g.y:oy + g.y + g.h, ox + g.x:ox + g.x + g.w]
