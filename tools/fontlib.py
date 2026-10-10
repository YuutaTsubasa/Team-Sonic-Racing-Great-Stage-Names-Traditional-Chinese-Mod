"""Parse / rebuild the FONT chunk. Lookup: index = (table[c % N] ^ c) % N."""
import struct

class Glyph:
    __slots__ = ('page', 'x', 'y', 'w', 'h', 'dw', 'dh', 'code', 'xoff', 'adv', 'yoff', 'flags', 'raw')
    def __init__(self, raw):
        self.raw = raw
        (self.page, _, self.x, self.y, self.w, self.h, self.dw, self.dh, self.code, self.xoff,
         self.adv, self.yoff, self.flags) = struct.unpack('<6I2HHhhhI', raw)
    def pack(self):
        return struct.pack('<6I2HHhhhI', self.page, 0, self.x, self.y, self.w, self.h, self.dw, self.dh,
                           self.code, self.xoff, self.adv, self.yoff, self.flags)

class Font:
    pass

def parse(chunkdata):
    """chunkdata = FONT chunk data (after the 16-byte chunk header)"""
    b = chunkdata
    head = b[:0x18]
    n, = struct.unpack_from('<I', b, 0x10)
    p1, p2 = struct.unpack_from('<QQ', b, 0x18)
    flist = [struct.unpack_from('<Q', b, p2 + 8 * k)[0] for k in range(n)]
    fonts = {}
    for fo in sorted(set(flist)):
        f = Font()
        f.hash, N, pt, g1, g2, ge = struct.unpack_from('<IIQQQQ', b, fo)
        assert pt == fo + 0x38 and g1 == g2 == pt + 4 * N and ge == g1 + 40 * N
        f.extra = b[fo + 0x28:fo + 0x38]
        f.table = list(struct.unpack_from(f'<{N}I', b, pt))
        f.glyphs = [Glyph(b[g1 + 40 * i:g1 + 40 * i + 40]) for i in range(N)]
        f.off = fo
        fonts[fo] = f
    return dict(head=head, n=n, p1data=b[p1:p2], flist=flist, fonts=fonts, size=len(b))

def lookup(f, c):
    N = len(f.glyphs)
    i = (f.table[c % N] ^ c) % N
    return f.glyphs[i] if f.glyphs[i].code == c else None

def build_table(glyphs):
    """order glyphs and make the table so that (T[c % N] ^ c) % N finds each one"""
    if len(glyphs) % 2 == 0:
        # keys of a bucket share c % N; with N = 2^k * m, XOR keeps their low k bits equal, so they
        # compete for only m slots (none at all when N is a power of two). The game's own fonts
        # all have odd N: pad with an unreachable duplicate like the dead newline they carry.
        glyphs = list(glyphs) + [Glyph(glyphs[0].pack())]
    N = len(glyphs)
    buckets = {}
    seen = set(); dead = []          # the originals carry an unreachable duplicate '\n'; keep it unreachable
    for g in glyphs:
        if g.code in seen:
            dead.append(g); continue
        seen.add(g.code)
        buckets.setdefault(g.code % N, []).append(g)
    slots = [None] * N
    table = [0] * N
    multi = sorted((k for k in buckets if len(buckets[k]) > 1), key=lambda k: -len(buckets[k]))
    for k in multi:
        keys = buckets[k]
        for v in range(1, 1 << 24):
            idx = [(v ^ g.code) % N for g in keys]
            if len(set(idx)) == len(idx) and all(slots[i] is None for i in idx):
                break
        else:
            raise RuntimeError(f'no seed for bucket {k} of {N}')
        table[k] = v
        for i, g in zip(idx, keys):
            slots[i] = g
    free = [i for i in range(N) if slots[i] is None]
    for k in buckets:
        if len(buckets[k]) == 1:
            i = free.pop()
            g = buckets[k][0]
            slots[i] = g
            table[k] = i ^ g.code
    for g in dead:
        slots[free.pop()] = g
    assert not free and None not in slots
    return slots, table

def serialize(F):
    """returns (data bytes, relo offsets)"""
    out = bytearray(F['head']) + b'\0' * 0x10
    relo = [0x18, 0x20]
    newoff = {}
    for fo in sorted(F['fonts']):
        f = F['fonts'][fo]
        N = len(f.glyphs)
        o = len(out); newoff[fo] = o
        pt = o + 0x38; g1 = pt + 4 * N; ge = g1 + 40 * N
        out += struct.pack('<IIQQQQ', f.hash, N, pt, g1, g1, ge) + f.extra
        out += struct.pack(f'<{N}I', *f.table)
        for g in f.glyphs:
            out += g.pack()
        relo += [o + 8, o + 0x10, o + 0x18, o + 0x20]
    p1 = len(out); out += F['p1data']; p2 = len(out)
    for k, fo in enumerate(F['flist']):
        relo.append(len(out)); out += struct.pack('<Q', newoff[fo])
    struct.pack_into('<QQ', out, 0x18, p1, p2)
    return bytes(out), relo
