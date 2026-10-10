"""PTEX chunk: sprites (hash, UV quad, texture index) and DXT3/DXT5 textures without mipmaps."""
import struct
import numpy as np
import dds

def ddsheader(w, h, four):
    hd = bytearray(128); hd[:4] = b'DDS '
    struct.pack_into('<7I', hd, 4, 124, 0x81007, h, w, (w * h) if four == b'DXT5' or four == b'DXT3' else 0, 0, 1)
    struct.pack_into('<II4s', hd, 76, 32, 4, four)
    struct.pack_into('<I', hd, 108, 0x1000)
    return bytes(hd)

class Ptex:
    def __init__(self, sec3):
        self.b = sec3; D = self.D = 0x10
        self.nspr, self.ntex = struct.unpack_from('<II', sec3, D)
        ptab, = struct.unpack_from('<Q', sec3, D + 8)
        self.sprites = {}
        for i in range(self.nspr):
            o = D + 0x10 + i * 0x30
            h = struct.unpack_from('<I', sec3, o)[0]
            uv = struct.unpack_from('<8f', sec3, o + 4)
            ti = struct.unpack_from('<I', sec3, o + 0x28)[0]
            self.sprites[h] = (uv, ti)
        self.tex = []
        for k in range(self.ntex):
            p, = struct.unpack_from('<Q', sec3, D + ptab + k * 16)
            w, h, size = struct.unpack_from('<3I', sec3, D + p)
            four = sec3[D + p + 12:D + p + 16]
            self.tex.append((D + p + 16, w, h, size, four))

    def decode(self, k):
        o, w, h, size, four = self.tex[k]
        if four == b'ARGB':                 # uncompressed, B G R A bytes
            a = np.frombuffer(self.b, np.uint8, w * h * 4, o).reshape(h, w, 4)
            return a[..., [2, 1, 0, 3]].copy()
        return dds.decode(ddsheader(w, h, four) + self.b[o:o + size])

    def sprite_rect(self, h):
        uv, ti = self.sprites[h]
        _, w, hh, _, _ = self.tex[ti]
        return ti, round(min(uv[0::2]) * w), round(min(uv[1::2]) * hh)


def parse_raw(data):
    """PTEX chunk data -> (sprites [raw 0x30 bytes], textures [(header16, body)])"""
    nspr, ntex, ptab = struct.unpack_from('<IIQ', data, 0)
    assert ptab == 0x10 + 0x30 * nspr
    sprites = [data[0x10 + 0x30 * i:0x40 + 0x30 * i] for i in range(nspr)]
    texs = []
    for k in range(ntex):
        p, z = struct.unpack_from('<QQ', data, ptab + 16 * k)
        assert z == 0
        w, h, size = struct.unpack_from('<3I', data, p)
        texs.append((data[p:p + 16], data[p + 16:p + 16 + size]))
    return sprites, texs


def serialize_raw(sprites, texs):
    nspr, ntex = len(sprites), len(texs)
    ptab = 0x10 + 0x30 * nspr
    out = bytearray(struct.pack('<IIQ', nspr, ntex, ptab)) + b''.join(sprites)
    out += b'\0' * (16 * ntex)
    relo = [8]
    for k, (hd, body) in enumerate(texs):
        struct.pack_into('<QQ', out, ptab + 16 * k, len(out), 0)
        relo.append(ptab + 16 * k)
        out += hd + body
    return bytes(out), relo


def sprite_entry(h, x0, y0, x1, y1, w, hh, ti):
    u0, v0, u1, v1 = x0 / w, y0 / hh, x1 / w, y1 / hh
    return struct.pack('<I8fIII', h, u0, v0, u1, v0, u1, v1, u0, v1, 0, ti, 0)
