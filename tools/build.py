"""Build the Team Sonic Racing zh-TW track-name mod.

For every ui/frontend/*_CH_T.stz that contains a transliterated track name:
  - TEXT: replace the old names with the new ones (names_src.NEW)
  - FONT: every font that could draw an old name gets glyphs for the new name's missing
          characters, drawn in that font's own style (glyphgen) on a new texture page
  - PTEX: append that page (DXT5) and a sprite for it
Writes out/data/ui/frontend/<dir>/<file>. The game files are only read.
"""
import json
import os
import struct
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import dds  # noqa: E402
import fontlib  # noqa: E402
import glyphgen  # noqa: E402
import ptex  # noqa: E402
from atlas import Atlas  # noqa: E402
from names_src import EN, NEW  # noqa: E402
from stz import (chunk_data, chunks, read_stz, rebuild_sections, relo_offsets, text_build,  # noqa: E402
                 text_parse, write_stz)

GAME = os.environ.get('TSR_DATA', r"C:/Program Files (x86)/Steam/steamapps/common/Team Sonic Racing/data")
# once the mod is installed the game folder holds modded files; build from the backed-up originals
_BACKUP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backup', 'data')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, 'work', 'glyphs')
PAGE_W = 512
PAD = 2


def find_files():
    out = []
    fe = os.path.join(GAME, 'ui', 'frontend')
    for dn in sorted(os.listdir(fe)):
        for fn in sorted(os.listdir(os.path.join(fe, dn))):
            if fn.endswith('_CH_T.stz'):
                out.append(f'ui/frontend/{dn}/{fn}')
    return out


def font_needs(f):
    """new-name characters missing from a font that can draw at least one old name"""
    have = {g.code for g in f.glyphs}
    need = []
    for o in NEW:
        if all(ord(c) in have for c in o):
            need += [c for c in NEW[o] if ord(c) not in have and c not in need]
    return need


def replace_names(t):
    body = t.rstrip('\n')
    if body in NEW:                      # the whole string is a name: add the English name
        return f'{NEW[body]} {EN[body]}' + t[len(body):]
    return replace_in_sentence(t)


def replace_in_sentence(t):
    for old in sorted(NEW, key=len, reverse=True):
        t = t.replace(old, NEW[old])
    return t


REF_CHARS = '的一是了我不人在他有這個上們來到時大地為子中你說生國年著就那和要她出也得裡後自以會家可下而過天去能對小多然於心學麼之都好看起發當沒成只如事把還用第樣道想作種開美總從無情己面最女但現前些所同日手又行意動方期它頭經長兒回位分愛老因很給名法間斯知世什兩次使身者被高已親其進此話常與活正感'


STYLES = os.path.join(ROOT, 'work', 'styles.npz')
_registry = None


def _refs(font, atlas):
    out = {}
    for c in REF_CHARS:
        g = fontlib.lookup(font, ord(c))
        if g is not None:
            out[c] = (g.xoff, g.yoff, g.adv, g.w, g.h, atlas.glyph_img(g).astype(np.int16))
        if len(out) == 6:
            break
    return out


def style_sig(font, atlas):
    """The same font is copied into many .stz files, each DXT-compressed a little differently.
    Fonts with the same glyph metrics and nearly the same pixels share one style fit."""
    import hashlib
    import pickle
    global _registry
    if _registry is None:
        _registry = pickle.load(open(STYLES, 'rb')) if os.path.exists(STYLES) else []
    refs = _refs(font, atlas)
    for sig, other in _registry:
        common = [c for c in refs if c in other]
        if len(common) < 4:
            continue
        if all(refs[c][:5] == other[c][:5] for c in common) and                 max(np.abs(refs[c][5] - other[c][5]).mean() for c in common) < 6:
            return sig
    h = hashlib.sha1()
    for c, v in refs.items():
        h.update(struct.pack('<hhhHH', *v[:5])); h.update(v[5].tobytes())
    sig = h.hexdigest()[:12]
    _registry.append((sig, refs))
    pickle.dump(_registry, open(STYLES, 'wb'))
    return sig


def glyph_for(style_cache, font, atlas, sig, ch, log=print):
    """cached (rgba, xoff, yoff, adv, flags) for ch in the style of font"""
    os.makedirs(CACHE, exist_ok=True)
    key = f'{sig}_{ord(ch):04x}'
    png, meta = os.path.join(CACHE, key + '.png'), os.path.join(CACHE, key + '.json')
    legacy = os.path.join(CACHE, f'{font.hash:08x}_{len(font.glyphs)}_{ord(ch):04x}')
    if not os.path.exists(png) and os.path.exists(legacy + '.png'):
        png, meta = legacy + '.png', legacy + '.json'
    if os.path.exists(png) and os.path.exists(meta):
        m = json.load(open(meta))
        return np.asarray(Image.open(png).convert('RGBA')), m['xoff'], m['yoff'], m['adv'], m['flags']
    if sig not in style_cache:
        log(f'  fitting style {sig} (font {font.hash:08x}, {len(font.glyphs)} glyphs)')
        style_cache[sig] = glyphgen.Style(font, atlas, log=log)
    st = style_cache[sig]
    img, xoff, yoff = st.draw(ch)
    cjk = [g for g in font.glyphs if glyphgen.is_cjk(g.code)]
    adv = int(np.bincount([g.adv for g in cjk]).argmax())
    flags = max(set(g.flags for g in cjk), key=[g.flags for g in cjk].count)
    Image.fromarray(img).save(png)
    json.dump(dict(xoff=int(xoff), yoff=int(yoff), adv=adv, flags=flags), open(meta, 'w'))
    return img, xoff, yoff, adv, flags


def pack(sizes):
    """shelf packing into PAGE_W columns; returns positions and page height"""
    pos = {}; x = y = shelf = 0
    for k, (w, h) in sorted(sizes.items(), key=lambda kv: -kv[1][1]):
        if x + w + PAD > PAGE_W:
            x, y, shelf = 0, y + shelf, 0
        pos[k] = (x + PAD, y + PAD)
        x += w + 2 * PAD; shelf = max(shelf, h + 2 * PAD)
    return pos, (y + shelf + 3) // 4 * 4


def build_file(rel, style_cache, report):
    src = os.path.join(_BACKUP, rel) if os.path.exists(os.path.join(_BACKUP, rel)) else os.path.join(GAME, rel)
    d, s = read_stz(src)
    tags = [c[0] for c in chunks(s[3])]
    if 'FONT' not in tags:
        return False
    T = text_parse(chunk_data(s[3], 'TEXT')) if 'TEXT' in tags else None
    new_strs = [replace_names(t) for t in T['strs']] if T else []
    changed = [i for i, (a, b) in enumerate(zip(T['strs'], new_strs)) if a != b] if T else []
    # the track names live in CommonProjects but are drawn with whichever screen's own copy of
    # the font, so every font that can draw an old name gets the new name's glyphs
    present = list(NEW)
    try:
        F = fontlib.parse(chunk_data(s[3], 'FONT'))
    except (AssertionError, TypeError):
        assert not changed, rel          # kerned digit fonts (FinishGP, Leaderboard): no names
        return False
    atlas = Atlas(s[3])
    sprites, texs = ptex.parse_raw(chunk_data(s[3], 'PTEX'))

    # which glyphs each font needs
    todo = {fo: font_needs(f) for fo, f in F['fonts'].items()}   # font offset -> [chars]
    todo = {fo: v for fo, v in todo.items() if v}
    if not changed and not todo:
        return False
    report[rel] = dict(strings=len(changed), names=present,
                       fonts={f'{F["fonts"][fo].hash:08x}': ''.join(v) for fo, v in todo.items()})
    print(f'{rel}: {len(changed)} strings, {len(todo)} fonts need {sum(map(len, todo.values()))} glyphs', flush=True)

    s3_ptex = None
    if todo:
        imgs = {}
        for fo, chars in todo.items():
            f = F['fonts'][fo]
            sig = style_sig(f, atlas)
            for c in chars:
                imgs[(fo, c)] = glyph_for(style_cache, f, atlas, sig, c)
        pos, ph = pack({k: (v[0].shape[1], v[0].shape[0]) for k, v in imgs.items()})
        page = np.zeros((ph, PAGE_W, 4), np.uint8)
        for k, (x, y) in pos.items():
            im = imgs[k][0]
            page[y:y + im.shape[0], x:x + im.shape[1]] = im
        Image.fromarray(page).save(os.path.join(ROOT, 'work', 'page_' + os.path.basename(rel) + '.png'))
        hashes = [struct.unpack_from('<I', sp)[0] for sp in sprites]
        newhash = max(hashes) + 1
        assert newhash < 1 << 32
        ti = len(texs)
        texs.append((struct.pack('<3I4s', PAGE_W, ph, PAGE_W * ph, b'DXT5'), dds.encode_dxt(page, 'DXT5')))
        sprites.append(ptex.sprite_entry(newhash, 0, 0, PAGE_W, ph, PAGE_W, ph, ti))
        for (fo, c), (im, xoff, yoff, adv, flags) in imgs.items():
            f = F['fonts'][fo]
            x, y = pos[(fo, c)]
            h, w = im.shape[:2]
            raw = struct.pack('<6I2HHhhhI', newhash, 0, x, y, w, h, w, h, ord(c), xoff, adv, yoff, flags)
            f.glyphs.append(fontlib.Glyph(raw))
        for fo in todo:
            f = F['fonts'][fo]
            f.glyphs, f.table = fontlib.build_table(f.glyphs)
        s3_ptex = ptex.serialize_raw(sprites, texs)

    rep = {'TEXT': (text_build(T, new_strs), relo_offsets(s[4], 'TEXT'))} if changed else {}
    if todo:
        rep['FONT'] = fontlib.serialize(F)
        rep['PTEX'] = s3_ptex
    s3, s4 = rebuild_sections(s[3], s[4], rep)
    out = os.path.join(ROOT, 'out', 'data', rel)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'wb').write(write_stz([None, None, None, s3, s4, None]))
    return True


def _fit_job(job):
    """worker: fit one style and draw its characters into the cache"""
    sig, rel, fo, chars = job
    src = os.path.join(_BACKUP, rel) if os.path.exists(os.path.join(_BACKUP, rel)) else os.path.join(GAME, rel)
    _, s = read_stz(src)
    F = fontlib.parse(chunk_data(s[3], 'FONT'))
    atlas = Atlas(s[3]); cache = {}
    logs = []
    for c in sorted(chars):
        glyph_for(cache, F['fonts'][fo], atlas, sig, c, log=logs.append)
    return sig, rel, logs


def _build_job(rel):
    report = {}
    build_file(rel, {}, report)
    return report


def plan(files):
    """sig -> (rel, font offset, chars) for every style that still needs drawing"""
    jobs = {}
    for rel in files:
        src = os.path.join(_BACKUP, rel) if os.path.exists(os.path.join(_BACKUP, rel)) else os.path.join(GAME, rel)
        _, s = read_stz(src)
        if 'FONT' not in [c[0] for c in chunks(s[3])]:
            continue
        try:
            F = fontlib.parse(chunk_data(s[3], 'FONT'))
        except (AssertionError, TypeError):
            continue
        atlas = None
        for fo, f in F['fonts'].items():
            need = font_needs(f)
            if not need:
                continue
            atlas = atlas or Atlas(s[3])
            sig = style_sig(f, atlas)
            todo = {c for c in need if not os.path.exists(os.path.join(CACHE, f'{sig}_{ord(c):04x}.json'))}
            if todo:
                j = jobs.setdefault(sig, [rel, fo, set()])
                j[2] |= todo
    return jobs


def main():
    from multiprocessing import Pool
    t = time.time()
    files = find_files()
    jobs = plan(files)
    print(f'plan: {len(jobs)} styles to fit ({time.time() - t:.0f}s)', flush=True)
    if jobs:
        with Pool(min(len(jobs), 14)) as pool:
            for k, (sig, rel, logs) in enumerate(pool.imap_unordered(
                    _fit_job, [(sig, *v) for sig, v in jobs.items()]), 1):
                print(f'[{k}/{len(jobs)}] style {sig} from {rel}', *logs, sep='\n', flush=True)
    report = {}
    with Pool(12) as pool:
        for part in pool.imap_unordered(_build_job, files):
            report.update(part)
    json.dump(report, open(os.path.join(ROOT, 'work', 'build_report.json'), 'w', encoding='utf8'),
              ensure_ascii=False, indent=1)
    print(f'done in {time.time() - t:.0f}s')


if __name__ == '__main__':
    main()
