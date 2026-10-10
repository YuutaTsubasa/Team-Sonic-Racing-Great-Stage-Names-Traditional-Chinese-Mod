"""Read back out/ stz files: no old names left, every original glyph still found by the
(T[c % N] ^ c) % N lookup, every new name drawable, and a preview of each name per font."""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(__file__))
import fontlib  # noqa: E402
from atlas import Atlas  # noqa: E402
from names_src import EN, NEW  # noqa: E402
from stz import chunk_data, read_stz, text_parse  # noqa: E402

GAME = os.environ.get('TSR_DATA', r"C:/Program Files (x86)/Steam/steamapps/common/Team Sonic Racing/data")
# once the mod is installed the game folder holds modded files; build from the backed-up originals
_BACKUP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backup', 'data')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def draw_line(font, atlas, text):
    gs = [fontlib.lookup(font, ord(c)) for c in text]
    if any(g is None for g in gs):
        return None
    top = max(g.yoff for g in gs); bot = max(g.h - g.yoff for g in gs)
    W = sum(g.adv for g in gs) + 40
    im = Image.new('RGBA', (W, top + bot + 8), (40, 50, 120, 255))
    x = 4
    for g in gs:
        gi = atlas.glyph_img(g)
        if gi.size:
            im.alpha_composite(Image.fromarray(np.ascontiguousarray(gi)), (x + g.xoff, 4 + top - g.yoff))
        x += g.adv
    return im


def main():
    ok = True
    rows = []
    by_font = {}
    for dp, _, fs in os.walk(os.path.join(ROOT, 'out', 'data')):
        for fn in sorted(fs):
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, os.path.join(ROOT, 'out', 'data')).replace('\\', '/')
            _, s = read_stz(p)
            _, so = read_stz(os.path.join(_BACKUP, rel) if os.path.exists(os.path.join(_BACKUP, rel)) else os.path.join(GAME, rel))
            if chunk_data(s[3], 'TEXT') is None:
                T = To = dict(strs=[])
            else:
                T = text_parse(chunk_data(s[3], 'TEXT'))
                To = text_parse(chunk_data(so[3], 'TEXT'))
            left = [o for o in NEW if NEW[o] != o and any(o in t for t in T['strs'])]
            names = list(NEW.values())   # text from CommonProjects is drawn with every screen's fonts
            diff = sum(a != b for a, b in zip(T['strs'], To['strs']))
            print(f'{rel}: {diff} strings changed, old names left: {left or "none"}')
            ok &= not left and len(T['strs']) == len(To['strs'])
            F = fontlib.parse(chunk_data(s[3], 'FONT'))
            Fo = fontlib.parse(chunk_data(so[3], 'FONT'))
            A = Atlas(s[3])
            for (fo, f), (_, fo_) in zip(sorted(F['fonts'].items()), sorted(Fo['fonts'].items())):
                lost = sum(1 for g in fo_.glyphs if fontlib.lookup(f, g.code) is None)
                if lost:
                    print(f'  font {f.hash:08x}: {lost} original glyphs lost'); ok = False
                old_ok = [o for o in NEW if all(fontlib.lookup(fo_, ord(c)) for c in o)]
                for o in old_ok:
                    if NEW[o] not in names:
                        continue
                    im = draw_line(f, A, f'{NEW[o]} {EN[o]}')
                    if im is None:
                        print(f'  font {f.hash:08x}: cannot draw {NEW[o]} {EN[o]}'); ok = False
                    elif len(by_font.setdefault(f.hash, [])) < 8:
                        by_font[f.hash].append(1)
                        rows.append((f'{fn[:-9]} {f.hash:08x}', im))
    # preview sheet: names per font
    by = {}
    for k, im in rows:
        by.setdefault(k, []).append(im)
    sheets = []
    for k, ims in by.items():
        W = sum(i.width for i in ims[:8]) + 260
        H = max(i.height for i in ims[:8])
        row = Image.new('RGBA', (max(W, 300), H), (40, 50, 120, 255))
        ImageDraw.Draw(row).text((4, 4), k, fill='white')
        x = 260
        for i in ims[:8]:
            row.alpha_composite(i, (x, 0)); x += i.width
        sheets.append(row)
    if sheets:
        W = max(r.width for r in sheets); H = sum(r.height for r in sheets)
        out = Image.new('RGBA', (W, H), (40, 50, 120, 255)); y = 0
        for r in sheets:
            out.alpha_composite(r, (0, y)); y += r.height
        out.save(os.path.join(ROOT, 'work', 'verify.png'))
    print('OK' if ok else 'FAILED')


if __name__ == '__main__':
    main()
