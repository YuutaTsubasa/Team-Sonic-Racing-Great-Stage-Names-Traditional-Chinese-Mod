"""Draw new glyphs in the style of an existing TSR font.

1. Fit Noto Sans TC (size, weight, offset) to the font's own CJK glyphs in pen coordinates
   (image left = pen x + xoff, image top = baseline - yoff).
2. Learn the style as a table: (signed distance to the stroke, signed distance to the stroke
   shifted by the shadow vector, height in the em box) -> mean RGBA, from the font's CJK glyphs.
3. New glyph = Noto mask -> features -> table lookup.
"""
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import distance_transform_edt

NOTO = 'C:/Windows/Fonts/NotoSansTC-VF.ttf'
SS = 4          # supersampling
_fonts = {}


def noto(size, weight):
    k = (size, weight)
    if k not in _fonts:
        f = ImageFont.truetype(NOTO, size)
        f.set_variation_by_axes([weight])
        _fonts[k] = f
    return _fonts[k]


def is_cjk(c):
    return 0x4E00 <= c <= 0x9FFF


class Canvas:
    """pen coords (x right, y down, baseline y=0) <-> canvas pixels: cx = x + px, cy = y + py"""
    def __init__(self, px, py, w, h):
        self.px, self.py, self.w, self.h = px, py, w, h


def place(img, g, cv):
    out = np.zeros((cv.h, cv.w, 4), np.float64)
    x0, y0 = g.xoff + cv.px, cv.py - g.yoff
    h, w = img.shape[:2]
    xs, ys = max(0, -x0), max(0, -y0)
    xe, ye = min(w, cv.w - x0), min(h, cv.h - y0)
    out[y0 + ys:y0 + ye, x0 + xs:x0 + xe] = img[ys:ye, xs:xe]
    return out


def render_hi(ch, size, weight, cv, dx, dy):
    """coverage mask at SS x resolution, pen origin shifted by (dx, dy) in hi-res pixels"""
    im = Image.new('L', (cv.w * SS, cv.h * SS), 0)
    ImageDraw.Draw(im).text((cv.px * SS + dx, cv.py * SS + dy), ch, font=noto(size * SS, weight),
                            fill=255, anchor='ls')
    return np.asarray(im, np.float64) / 255


def down(a):
    h, w = a.shape
    return a.reshape(h // SS, SS, w // SS, SS).mean((1, 3))


def sdf_hi(mask_hi):
    m = mask_hi >= 0.5
    if not m.any():
        return np.full(m.shape, 99.0)
    return (distance_transform_edt(~m) - distance_transform_edt(m)) / SS


class Style:
    def __init__(self, font, atlas, log=print):
        self.f = font
        cjk = [g for g in font.glyphs if is_cjk(g.code) and g.w > 4 and g.h > 4]
        random.Random(1).shuffle(cjk)
        self.ref = cjk[:300]
        g0 = max(self.ref[:50], key=lambda g: g.adv)
        self.adv = g0.adv
        self.xoff = int(np.median([g.xoff for g in self.ref]))
        pad = 4 + self.adv // 3
        top = max(g.yoff for g in self.ref)
        bot = max(g.h - g.yoff for g in self.ref)
        wid = max(g.xoff + g.w for g in self.ref)
        self.cv = Canvas(pad, top + pad, wid + 2 * pad, top + bot + 2 * pad)
        self.imgs = {g.code: place(atlas.glyph_img(g).astype(np.float64) / 255, g, self.cv) for g in self.ref}
        self.flags = g0.flags
        self.log = log
        al = np.concatenate([im[..., 3].ravel() for im in self.imgs.values()])
        lu = np.concatenate([(im[..., :3] @ np.array([0.3, 0.59, 0.11])).ravel() for im in self.imgs.values()])
        self.dark = lu[al > 0.5].mean() < 0.45 if (al > 0.5).any() else True
        self.fit()
        self.learn()

    # ---------------------------------------------------------------- alignment
    def light(self, a):
        luma = a[..., :3] @ np.array([0.3, 0.59, 0.11])
        if self.dark:                       # dark/translucent fonts (shadow layers): align on alpha
            return a[..., 3]
        return a[..., 3] * np.clip((luma - 0.35) / 0.4, 0, 1)

    def fit(self):
        chars = self.ref[:10]
        L = [self.light(self.imgs[g.code]) for g in chars]
        best = (-1,)
        base = self.adv
        k = max(1, round(base / 22))          # big fonts: coarser first pass
        for weight in (400, 600, 900):
            for size in range(round(base * 0.8), round(base * 1.25) + 1, k):
                hi = [render_hi(chr(g.code), int(size), weight, self.cv, 0, 0) for g in chars]
                for dy in range(-4 * k * SS, 4 * k * SS + 1, k * SS):
                    for dx in range(-4 * k * SS, 4 * k * SS + 1, k * SS):
                        s = self.score(hi, L, dx, dy)
                        if s > best[0]:
                            best = (s, weight, int(size), dx, dy)
        s, weight, size, dx0, dy0 = best
        for sz in range(size - k + 1, size + k):
            hi = [render_hi(chr(g.code), sz, weight, self.cv, 0, 0) for g in chars]
            for dy in range(dy0 - k * SS, dy0 + k * SS + 1, max(1, k)):
                for dx in range(dx0 - k * SS, dx0 + k * SS + 1, max(1, k)):
                    sc = self.score(hi, L, dx, dy)
                    if sc > best[0]:
                        best = (sc, weight, sz, dx, dy)
        self.score_, self.weight, self.size, self.dx, self.dy = best
        self.log(f'  fit: corr={self.score_:.3f} weight={self.weight} size={self.size} '
                 f'dx={self.dx / SS:+.2f} dy={self.dy / SS:+.2f}')

    @staticmethod
    def score(hi, L, dx, dy):
        tot = 0
        for h, l in zip(hi, L):
            c = down(np.roll(np.roll(h, dy, 0), dx, 1))
            a, b = c - c.mean(), l - l.mean()
            tot += (a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum() + 1e-9)
        return tot / len(hi)

    # ---------------------------------------------------------------- style table
    def features(self, ch, shadow):
        hi = render_hi(ch, self.size, self.weight, self.cv, self.dx, self.dy)
        d0 = down(sdf_hi(hi))
        sx, sy = shadow
        sh = np.roll(np.roll(hi, sy * SS // 2, 0), sx * SS // 2, 1)
        d1 = down(sdf_hi(sh))
        yy = np.arange(self.cv.h)[:, None] - self.cv.py          # pen y
        ybin = np.clip(((yy + self.size * 0.9) / (self.size * 1.1) * 6).astype(int), 0, 5)
        return d0, d1, np.broadcast_to(ybin, d0.shape)

    def keys(self, d0, d1, yb):
        q0 = np.clip(np.round(d0 * 2), -8, self.R2).astype(int) + 8
        q1 = np.clip(np.round(d1 * 2), -8, self.R2).astype(int) + 8
        return q0, q1, yb

    def build(self, shadow, chars):
        """per cell (d0, d1, y), (d0, d1) and (d0): median alpha, median colour of opaque pixels"""
        n0 = self.R2 + 9
        K, X = [], []
        for g in chars:
            d0, d1, yb = self.features(chr(g.code), shadow)
            q0, q1, yb = self.keys(d0, d1, yb)
            K.append(((q0 * n0 + q1) * 6 + yb).ravel()); X.append(self.imgs[g.code].reshape(-1, 4))
        K = np.concatenate(K); X = np.concatenate(X)
        tabs = []
        for div in (1, 6, 6 * n0):
            k = K // div
            order = np.argsort(k, kind='stable'); ks = k[order]; xs = X[order]
            keys, start = np.unique(ks, return_index=True)
            size = (n0 * n0 * 6) // div + 1
            val = np.zeros((size, 4)); cnt = np.zeros(size)
            for key, a, b in zip(keys, start, list(start[1:]) + [len(ks)]):
                grp = xs[a:b]
                al = np.median(grp[:, 3])
                op = grp[grp[:, 3] > 0.5]
                col = np.median(op[:, :3], 0) if len(op) else np.median(grp[:, :3], 0)
                val[key] = (*col, al); cnt[key] = b - a
            tabs.append((div, val, cnt))
        return tabs

    def predict(self, tabs, d0, d1, yb):
        n0 = self.R2 + 9
        q0, q1, yb = self.keys(d0, d1, yb)
        key = (q0 * n0 + q1) * 6 + yb
        out = None
        for div, val, cnt in reversed(tabs):          # coarse first, finer overrides
            k = key // div
            v = val[k]; ok = (cnt[k] >= 3)[..., None]
            out = v if out is None else np.where(ok, v, out)
        return np.clip(out, 0, 1)

    def learn(self):
        # outline reach: how far ink extends beyond the light fill
        self.R2 = int(min(48, 4 + self.adv * 0.6))
        train, test = self.ref[:120], self.ref[120:150]
        best = None
        k = max(1, round(self.adv / 22))
        cands = [(0, 0)] + [(sx * k, sy * k) for sx in range(0, 7, 1 if k == 1 else 2)
                            for sy in range(1, 9, 1 if k == 1 else 2) if sx <= sy]
        for sh in cands:
            acc = self.build(sh, train[:30])
            err = 0
            for g in test[:8]:
                p = self.predict(acc, *self.features(chr(g.code), sh))
                err += np.abs(p * p[..., 3:] - self.imgs[g.code] * self.imgs[g.code][..., 3:]).mean()
            if best is None or err < best[0]:
                best = (err, sh)
        self.shadow = best[1]
        self.acc = self.build(self.shadow, train)
        err = 0
        for g in test:
            p = self.predict(self.acc, *self.features(chr(g.code), self.shadow))
            err += np.abs(p * p[..., 3:] - self.imgs[g.code] * self.imgs[g.code][..., 3:]).mean()
        self.err = err / len(test)
        # ink matching: the averaged table blurs thin strokes; boost alpha until total ink matches
        po = sum(self.imgs[g.code][..., 3].sum() for g in test)
        pa = [self.predict(self.acc, *self.features(chr(g.code), self.shadow))[..., 3] for g in test]
        lo, hi = 0.5, 4.0
        for _ in range(30):
            k = (lo + hi) / 2
            if sum((1 - (1 - a) ** k).sum() for a in pa) < po:
                lo = k
            else:
                hi = k
        self.gamma = (lo + hi) / 2
        self.log(f'  style: shadow={self.shadow} reach={self.R2 / 2} err={self.err:.4f} ink-gamma={self.gamma:.2f}')

    # ---------------------------------------------------------------- output
    def draw(self, ch):
        """returns (rgba uint8 image cropped to ink, xoff, yoff)"""
        p = self.predict(self.acc, *self.features(ch, self.shadow))
        p[..., 3] = 1 - (1 - p[..., 3]) ** self.gamma
        p[p[..., 3] < 1.5 / 255] = 0
        ys, xs = np.nonzero(p[..., 3])
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        img = (p[y0:y1, x0:x1] * 255 + 0.5).astype(np.uint8)
        return img, x0 - self.cv.px, self.cv.py - y0

    def reconstruct(self, g):
        p = self.predict(self.acc, *self.features(chr(g.code), self.shadow))
        p[..., 3] = 1 - (1 - p[..., 3]) ** self.gamma
        return p
