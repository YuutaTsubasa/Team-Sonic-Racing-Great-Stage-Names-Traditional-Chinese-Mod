"""DDS textures as used in SA2 PC .pak files: DXT1/DXT3/DXT5 or 32-bit A8R8G8B8, with or
without mipmaps. decode() returns the top level as RGBA; replace() re-encodes a new top
level (and regenerates every mipmap) keeping the original header, format and size.
DXT encoder from Free Riders (sfr_texture.py): principal-axis endpoints + least squares."""
import io
import struct

import numpy as np
from PIL import Image

HEADER = 128


def info(d):
    assert d[:4] == b'DDS ', 'not a DDS'
    h, w = struct.unpack_from('<II', d, 12)
    mips = max(struct.unpack_from('<I', d, 28)[0], 1)
    four = d[84:88]
    if four in (b'DXT1', b'DXT3', b'DXT5'):
        fmt = four.decode()
    else:
        bits, rm, gm, bm, am = struct.unpack_from('<IIIII', d, 88)
        assert bits == 32 and rm == 0xFF0000 and am == 0xFF000000, 'unsupported DDS pixel format'
        fmt = 'ARGB'
    return w, h, mips, fmt


def level_size(w, h, fmt):
    if fmt == 'ARGB':
        return w * h * 4
    blocks = ((w + 3) // 4) * ((h + 3) // 4)
    return blocks * (8 if fmt == 'DXT1' else 16)


def decode(d):
    w, h, _, fmt = info(d)
    if fmt == 'ARGB':
        a = np.frombuffer(d, np.uint8, w * h * 4, HEADER).reshape(h, w, 4)
        return a[..., [2, 1, 0, 3]].copy()
    im = Image.open(io.BytesIO(d))
    im.load()
    return np.asarray(im.convert('RGBA')).copy()


# ---------------------------------------------------------------- DXT encoder
def to_565(rgb):
    r, g, b = (rgb[..., 0] * 31 + 127) // 255, (rgb[..., 1] * 63 + 127) // 255, (rgb[..., 2] * 31 + 127) // 255
    return (r << 11) | (g << 5) | b


def from_565(c):
    r, g, b = (c >> 11) & 31, (c >> 5) & 63, c & 31
    return np.stack([(r * 255 + 15) // 31, (g * 255 + 31) // 63, (b * 255 + 15) // 31], -1)


def blocks_of(rgba):
    h, w, _ = rgba.shape
    ph, pw = (-h) % 4, (-w) % 4
    if ph or pw:
        rgba = np.pad(rgba, ((0, ph), (0, pw), (0, 0)), mode='edge')
        h, w = rgba.shape[:2]
    b = rgba.reshape(h // 4, 4, w // 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(-1, 16, 4)
    return b.astype(np.int64)


def palette_of(c0, c1):
    p0, p1 = from_565(c0), from_565(c1)
    return np.stack([p0, p1, (2 * p0 + p1) // 3, (p0 + 2 * p1) // 3], 1)


def encode_colour(blocks, opaque_only):
    rgb, alpha = blocks[..., :3].astype(np.float64), blocks[..., 3]
    weight = (alpha > 0 if opaque_only else np.ones(alpha.shape, bool)).astype(np.float64)
    empty = weight.sum(1) == 0
    weight[empty] = 1
    total = weight.sum(1, keepdims=True)
    mean = (rgb * weight[..., None]).sum(1) / total
    centred = (rgb - mean[:, None]) * weight[..., None]
    cov = np.einsum('npi,npj->nij', centred, rgb - mean[:, None])
    axis = np.ones((len(blocks), 3)) / np.sqrt(3)
    for _ in range(8):
        axis = np.einsum('nij,nj->ni', cov, axis)
        axis /= np.maximum(np.linalg.norm(axis, axis=1, keepdims=True), 1e-9)
    proj = np.einsum('npi,ni->np', rgb - mean[:, None], axis)
    big = np.where(weight > 0, proj, -np.inf).max(1)
    small = np.where(weight > 0, proj, np.inf).min(1)
    hi = np.clip(mean + axis * big[:, None], 0, 255)
    lo = np.clip(mean + axis * small[:, None], 0, 255)
    for _ in range(2):
        c0, c1 = to_565(hi.round().astype(np.int64)), to_565(lo.round().astype(np.int64))
        palette = palette_of(c0, c1)
        index = ((rgb[:, :, None, :] - palette[:, None, :, :]) ** 2).sum(-1).argmin(-1)
        t = np.array([0.0, 1.0, 1 / 3, 2 / 3])[index]
        a, b = (1 - t) * weight, t * weight
        aa, bb, ab = (a * (1 - t)).sum(1), (b * t).sum(1), (a * t).sum(1)
        ax = (a[..., None] * rgb).sum(1)
        bx = (b[..., None] * rgb).sum(1)
        det = aa * bb - ab * ab
        ok = np.abs(det) > 1e-6
        new_hi = (bb[:, None] * ax - ab[:, None] * bx) / np.where(ok, det, 1)[:, None]
        new_lo = (aa[:, None] * bx - ab[:, None] * ax) / np.where(ok, det, 1)[:, None]
        hi = np.where(ok[:, None], np.clip(new_hi, 0, 255), hi)
        lo = np.where(ok[:, None], np.clip(new_lo, 0, 255), lo)
    c0, c1 = to_565(hi.round().astype(np.int64)), to_565(lo.round().astype(np.int64))
    swap = c0 < c1
    c0, c1 = np.where(swap, c1, c0), np.where(swap, c0, c1)
    palette = palette_of(c0, c1)
    index = ((rgb[:, :, None, :] - palette[:, None, :, :]) ** 2).sum(-1).argmin(-1)
    index[c0 == c1] = 0
    bits = (index << (2 * np.arange(16))).sum(1)
    return c0.astype('<u2'), c1.astype('<u2'), bits.astype('<u4')


def encode_dxt(rgba, fmt):
    blocks = blocks_of(rgba)
    c0, c1, bits = encode_colour(blocks, fmt != 'DXT1')
    colour = np.zeros(len(blocks), dtype=[('c0', '<u2'), ('c1', '<u2'), ('bits', '<u4')])
    colour['c0'], colour['c1'], colour['bits'] = c0, c1, bits
    if fmt == 'DXT1':
        # blocks with transparent pixels: 3-colour mode (c0 <= c1, index 3 = transparent)
        alpha = blocks[..., 3]
        tr = (alpha < 128).any(1)
        if tr.any():
            k = np.nonzero(tr)[0]
            lo, hi = np.minimum(c0[k], c1[k]), np.maximum(c0[k], c1[k])
            p0, p1 = from_565(lo.astype(np.int64)), from_565(hi.astype(np.int64))
            pal = np.stack([p0, p1, (p0 + p1) // 2], 1)
            rgb = blocks[k, :, :3]
            idx = ((rgb[:, :, None, :] - pal[:, None, :, :]) ** 2).sum(-1).argmin(-1)
            idx[alpha[k] < 128] = 3
            colour['c0'][k], colour['c1'][k] = lo, hi
            colour['bits'][k] = (idx << (2 * np.arange(16))).sum(1).astype('<u4')
        return colour.tobytes()
    alpha = blocks[..., 3]
    if fmt == 'DXT3':
        a4 = (alpha * 15 + 127) // 255
        packed = (a4.astype(np.uint64) << (4 * np.arange(16, dtype=np.uint64))).sum(1).astype('<u8')
        out = np.zeros(len(blocks), dtype=[('a', '<u8'), ('c', colour.dtype)])
        out['a'], out['c'] = packed, colour
        return out.tobytes()
    a0, a1 = alpha.max(1), alpha.min(1)
    levels = np.stack([a0, a1] + [((7 - k) * a0 + k * a1) // 7 for k in range(1, 7)], 1)
    index = np.abs(alpha[:, :, None] - levels[:, None, :]).argmin(-1)
    index[a0 == a1] = 0
    packed = (index.astype(np.uint64) << (3 * np.arange(16, dtype=np.uint64))).sum(1)
    head = np.zeros(len(blocks), dtype=[('a0', 'u1'), ('a1', 'u1'), ('bits', '<u2', 3), ('c', colour.dtype)])
    head['a0'], head['a1'] = a0, a1
    head['bits'] = np.stack([(packed >> np.uint64(16 * k)) & np.uint64(0xFFFF) for k in range(3)], 1)
    head['c'] = colour
    return head.tobytes()


def encode_level(rgba, fmt):
    if fmt == 'ARGB':
        return np.ascontiguousarray(rgba[..., [2, 1, 0, 3]]).tobytes()
    return encode_dxt(rgba, fmt)


def replace(d, rgba):
    """New DDS bytes: same header/format/size/mip count, top level = rgba."""
    w, h, mips, fmt = info(d)
    assert rgba.shape[:2] == (h, w), f'image {rgba.shape[1]}x{rgba.shape[0]} != texture {w}x{h}'
    body = bytearray()
    im = Image.fromarray(np.asarray(rgba, np.uint8), 'RGBA')
    lw, lh = w, h
    for lvl in range(mips):
        a = np.asarray(im if lvl == 0 else im.resize((lw, lh), Image.BOX))
        body += encode_level(a, fmt)
        lw, lh = max(lw // 2, 1), max(lh // 2, 1)
    total = sum(level_size(max(w >> k, 1), max(h >> k, 1), fmt) for k in range(mips))
    assert len(body) == total, (len(body), total)
    out = d[:HEADER] + bytes(body) + d[HEADER + total:]
    assert len(out) == len(d)
    return out
