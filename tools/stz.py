"""Team Sonic Racing .stz reader/writer.
.stz = 6 x (u32 offset, u32 raw size, u32 zlib size) header, zlib sections.
Section 3 = data chunks (PTEX KFRM OBJS SCNE FONT TEXT), section 4 = one RELO chunk per data chunk.
Chunk = tag, u32 size (0x40-aligned), u32 used size, 0x44332211, data. Pointers are offsets from chunk+0x10."""
import struct, zlib

def read_stz(p):
    d = open(p, 'rb').read()
    secs = []
    for k in range(6):
        off, raw, comp = struct.unpack_from('<3I', d, k * 12)
        secs.append(zlib.decompress(d[off:off + comp]) if comp else None)
    return d, secs

def chunks(b):
    out = []; i = 0
    while i + 16 <= len(b):
        tag = b[i:i + 4].decode(); sz, used, mg = struct.unpack_from('<3I', b, i + 4)
        assert mg == 0x44332211
        out.append((tag, i, sz, used)); i += sz
    return out

def fonts(sec3):
    """yield (font_index, header_off, {codepoint: record_off}) for every font in the FONT chunk"""
    c = {t: (o, s, u) for t, o, s, u in chunks(sec3)}
    o = c['FONT'][0]; D = o + 0x10
    n, = struct.unpack_from('<I', sec3, D + 0x10)
    plist, = struct.unpack_from('<Q', sec3, D + 0x20)
    for k in range(n):
        fo, = struct.unpack_from('<Q', sec3, D + plist + k * 8)
        h, cnt, ptab, pg1, pg2, pend = struct.unpack_from('<IIQQQQ', sec3, D + fo)
        glyphs = {}
        for i in range(cnt):
            r = D + pg1 + i * 40
            glyphs[struct.unpack_from('<I', sec3, r + 28)[0] & 0xffff] = r
        yield k, D + fo, glyphs

def texts(sec3):
    c = {t: (o, s, u) for t, o, s, u in chunks(sec3)}
    o = c['TEXT'][0]; T = o + 0x10
    n, = struct.unpack_from('<I', sec3, T + 0x10)
    pent, = struct.unpack_from('<Q', sec3, T + 0x20)
    out = []
    for i in range(n):
        h, _, p = struct.unpack_from('<IIQ', sec3, T + pent + i * 16)
        e = sec3.find(b'\0', T + p)
        out.append((h, p, sec3[T + p:e].decode('utf8')))
    return out


def chunk_data(sec3, tag):
    for t, o, sz, used in chunks(sec3):
        if t == tag:
            return sec3[o + 0x10:o + 0x10 + used]

def make_chunk(tag, data):
    size = (0x10 + len(data) + 0x3f) & ~0x3f
    return tag.encode() + struct.pack('<3I', size, len(data), 0x44332211) + data + b'\0' * (size - 0x10 - len(data))

def relo_offsets(sec4, tag):
    for t, o, sz, used in chunks(sec4):
        if sec4[o + 0x10:o + 0x14] == tag.encode():
            i = o + 0x14; out = []
            while True:
                f, off = struct.unpack_from('<II', sec4, i); i += 8
                if f == 0:
                    return out
                assert f == 1
                out.append(off)

def make_relo(tag, offs):
    data = tag.encode() + b''.join(struct.pack('<II', 1, o) for o in offs) + b'\0' * 8
    return make_chunk('RELO', data)

def rebuild_sections(sec3, sec4, replace):
    """replace = {tag: (data, relo_offsets)}; other chunks copied verbatim"""
    out3 = bytearray(); out4 = bytearray()
    rl = chunks(sec4)
    for (t, o, sz, used), (rt, ro, rsz, rused) in zip(chunks(sec3), rl):
        assert sec4[ro + 0x10:ro + 0x14] == t.encode()
        if t in replace:
            data, offs = replace[t]
            out3 += make_chunk(t, data); out4 += make_relo(t, offs)
        else:
            out3 += sec3[o:o + sz]; out4 += sec4[ro:ro + rsz]
    return bytes(out3), bytes(out4)

def write_stz(secs):
    hdr = bytearray(); body = bytearray(); off = 0x48
    for s in secs:
        if s is None:
            hdr += struct.pack('<3I', off, 0, 0); continue
        c = zlib.compress(s, 9)
        hdr += struct.pack('<3I', off, len(s), len(c))
        pad = (len(c) + 0x3f) & ~0x3f
        body += c + b'\0' * (pad - len(c)); off += pad
    return bytes(hdr) + bytes(body) + b'\0' * 24

def text_parse(data):
    n, = struct.unpack_from('<I', data, 0x10)
    pent, = struct.unpack_from('<Q', data, 0x20)
    ents = [struct.unpack_from('<IIQ', data, pent + 16 * i) for i in range(n)]
    pool = min(p for _, _, p in ents)
    assert pool >= pent + 16 * n
    strs = []
    for h, z, p in ents:
        e = data.index(b'\0', p)
        strs.append(data[p:e].decode('utf8'))
    return dict(prefix=data[:pool], pent=pent, ents=ents, strs=strs, order=sorted(range(n), key=lambda i: ents[i][2]), tail=data)

def text_build(T, strs):
    out = bytearray(T['prefix'])
    ptr = {}   # entries that shared a string in the original keep sharing it
    for i in T['order']:
        p = T['ents'][i][2]
        if p in ptr:
            assert strs[i] == strs[ptr[p][1]]
            continue
        ptr[p] = (len(out), i); out += strs[i].encode('utf8') + b'\0'
    for i, (h, z, p) in enumerate(T['ents']):
        struct.pack_into('<IIQ', out, T['pent'] + 16 * i, h, z, ptr[p][0])
    return bytes(out)
