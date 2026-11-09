#!/usr/bin/env python3
"""alt2: independent synthetic personal-injury case-file generator.

Run from the provider-match folder:  python records/altgen2/generate_alt2.py
Writes records/data/alt2/alt2-<n>/records.pdf and truth.json for n = 1..10.
Everything (patients, clinicians, providers, insurers, firms) is fictional.
See README.md in this folder for the model.
"""
import datetime as dt
import json
import os
import random
import sys

import fitz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from specs import CASES, CPT, DX  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUTROOT = os.path.normpath(os.path.join(HERE, '..', 'data', 'alt2'))
PW, PH = 612.0, 792.0
TD = dt.timedelta

# ------------------------------------------------------------------ name pools (fictional)
FIRST_F = ['Marisol', 'Dagny', 'Ruthanne', 'Ilse', 'Coralee', 'Theodora', 'Wren', 'Annika', 'Bettina', 'Lucinda', 'Odalys', 'Phaedra', 'Junie', 'Rosalind', 'Saoirse', 'Yolanda', 'Mirela', 'Tamsin', 'Eudora', 'Nell']
FIRST_M = ['Desmond', 'Anselm', 'Teodoro', 'Brice', 'Lowell', 'Ambrose', 'Caspian', 'Rudy', 'Emeric', 'Fitzgerald', 'Isidro', 'Jasper', 'Leopold', 'Milo', 'Osric', 'Thaddeus', 'Wendell', 'Cyrus', 'Gideon', 'Rafferty']
LASTS = ['Quillfeather', 'Abernathy', 'Okonjo', 'Vasquez-Lind', 'Thibodeaux', 'Marchetti', 'Haverkamp', 'Lindqvist', 'Oyelaran', 'Prentiss', 'Szymanski', 'Kowalczyk', 'Delacroix', 'Nakashima', 'Ferreira', 'Galloway', 'Brannigan', 'Holloway', 'Ibarra', 'Jankowski',
         'Kettleborough', 'Mbeki-Ross', 'Nordgren', 'Pellerin', 'Ruskova', 'Satterfield', 'Tremblay', 'Underhill', 'Valcourt', 'Whitlock', 'Yarborough', 'Zelenko', 'Achterberg', 'Bramwell', 'Castellanos', 'Dunleavy', 'Esterhazy', 'Fairweather', 'Greaves', 'Hightower']
CLIN_F = ['Priya', 'Helena', 'Constance', 'Keiko', 'Moira', 'Adaeze', 'Signe', 'Paloma', 'Renata', 'Gwen', 'Ines', 'Larissa', 'Mercy', 'Noor', 'Tova', 'Ursula', 'Vera', 'Willa', 'Zofia', 'Beatrix']
CLIN_M = ['Arjun', 'Bastian', 'Conrad', 'Dmitri', 'Ezra', 'Florian', 'Gareth', 'Hamish', 'Ignatius', 'Jonas', 'Kofi', 'Laszlo', 'Matthias', 'Nikhil', 'Orrin', 'Pieter', 'Quentin', 'Rowan', 'Soren', 'Tobias']
TOWNS = ['Marrowfield', 'Quillon Falls', 'Tessaly', 'Brennock', 'Ashgrove Bend', 'Wexmoor', 'Larkhaven', 'Dunmere', 'Pellridge', 'Saltmarsh Point', 'Varrow', 'Kestrel Bay', 'Oxleigh', 'Corvane', 'Hollin Gap']
COUNTIES = ['Harlow', 'Brisco', 'Tamsin', 'Ruddle', 'Okerlund', 'Fenwick', 'Galt']
SAINTS = ['St. Aldric', 'St. Wenna', 'St. Ivo', 'St. Cuthwin', 'Our Lady of the Lindens']
STREETS = ['Tannery Row', 'Quarry Hill Rd', 'Lantern Way', 'Osprey Ave', 'Millrace Ct', 'Juniper Pkwy', 'Foundry St', 'Bellwether Ln', 'Harrow Dr', 'Cobble Mill Rd', 'Signal Ave', 'Weaver St']
STATES = [('OH', '43'), ('PA', '15'), ('NC', '27'), ('WI', '53'), ('OR', '97'), ('MO', '63'), ('KY', '40'), ('NM', '87'), ('IA', '50'), ('VT', '05')]
AREAS = ['330', '412', '919', '608', '503', '314', '859', '505', '515', '802']
LAW = ['Okonkwo & Dahl, PLLC', 'Vasquez Brandt Injury Law', 'Haverford-Imani Trial Lawyers', 'Brightwater & Sole, LLP', 'Lindgren Achebe Law Group']
INS_AUTO = ['Granite Shoal Mutual Insurance Co.', 'Bluewater Casualty Company', 'Northgate Indemnity Group']
INS_GL = ['Pillarstone Assurance Company', 'Harbor Ledger Casualty', 'Copperfield General Insurance']
INS_WC = ['Keystone Hollow Workers Compensation Fund', 'Ironbridge Employers Mutual', 'Tallgrass Comp Insurance Co.']
DEF = ['Pemberton Vance Ruiz LLP', 'Calloway & Strand', 'Mercer Ostrowski LLP', 'Halberd Quaye & Lin']

DATEFMTS = ['dash', 'mondot', 'dmy_long', 'short', 'iso', 'weekday', 'dots', 'dmonY', 'slash', 'BdY']


def fmt_date(d, style):
    if style == 'dash':
        return d.strftime('%m-%d-%Y')
    if style == 'mondot':
        return (f"May {d.day} {d.year}" if d.month == 5 else f"{d.strftime('%b')}. {d.day} {d.year}")
    if style == 'dmy_long':
        return f"{d.day} {d.strftime('%B')} {d.year}"
    if style == 'short':
        return f"{d.month}/{d.day}/{d.strftime('%y')}"
    if style == 'iso':
        return d.isoformat()
    if style == 'weekday':
        return f"{d.strftime('%A')}, {d.strftime('%B')} {d.day}, {d.year}"
    if style == 'dots':
        return d.strftime('%Y.%m.%d')
    if style == 'dmonY':
        return f"{d.day:02d}-{d.strftime('%b').upper()}-{d.year}"
    if style == 'slash':
        return d.strftime('%m/%d/%Y')
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def mdY(d):
    return d.strftime('%m/%d/%Y')


def addm(t, mins):
    h, m = map(int, t.split(':'))
    x = (h * 60 + m + mins) % 1440
    return f"{x // 60:02d}:{x % 60:02d}"


def subseq(codes):
    out = []
    for c in codes:
        if c[0] in 'VWXY':
            continue
        if c.startswith('S') and c.endswith('A'):
            c = c[:-1] + 'D'
        if c not in out:
            out.append(c)
    return out


def weekday_after(d, n):
    d = d + TD(days=n)
    while d.weekday() >= 5:
        d += TD(days=1)
    return d


# ------------------------------------------------------------------ provider / style
class Prov:
    def __init__(self, case, ptype, name, dfmt, specialty=''):
        r = case.r
        self.case, self.ptype, self.name, self.dfmt, self.specialty = case, ptype, name, dfmt, specialty
        fam = r.choice(['helv', 'tiro', 'cour', 'helv', 'tiro'])
        size = r.choice([8.5, 9, 9.5, 10, 10.5]) if fam != 'cour' else r.choice([8, 8.5, 9])
        self.st = dict(body=fam, bold={'helv': 'hebo', 'tiro': 'tibo', 'cour': 'cobo'}[fam], ital={'helv': 'heit', 'tiro': 'tiit', 'cour': 'coit'}[fam],
                       size=size, hsize=size + r.choice([0, 0.5, 1]), halign=r.choice(['left', 'center', 'center', 'right']), talign=r.choice(['left', 'center']),
                       rule=r.random() < 0.6, margin=r.choice([48, 54, 60, 66, 72]), top=r.choice([46, 52, 58]), tfont=r.choice(['cour', fam]),
                       lead=r.choice([1.22, 1.3, 1.38]))
        self.caps = r.random() < 0.5
        self.hcaps = r.random() < 0.6
        self.sfx = r.choice(['', ':', ':', ' --'])
        self.kvsep = r.choice([': ', ':  ', ' - ', ' = ', ': '])
        self.tbl = r.choice(['pipe', 'pipe', 'space', 'pipe2'])
        self.hdrmode = r.randrange(3)
        self.tstyle = r.choice(['mil', 'colon', 'ampm'])
        self.pagefmt = r.choice(['Page {i} of {n}', 'Pg {i}/{n}', '- {i} -', '{i} of {n}', 'Page {i}', 'p. {i}/{n}'])
        self.always_pg = r.random() < 0.5
        town = case.town if r.random() < 0.75 else r.choice(TOWNS)
        self.town = town
        st_, z = case.state
        self.addr = f"{r.randint(100, 9899)} {r.choice(STREETS)}{r.choice(['', ', Suite ' + str(r.randint(100, 450)), ', Bldg ' + r.choice('ABC')])}, {town}, {st_} {z}{r.randint(100, 999)}"
        self.phone = f"({case.area}) 555-01{r.randint(10, 99)}"
        self.fax = f"({case.area}) 555-01{r.randint(10, 99)}"
        self.npi = '1' + ''.join(str(r.randint(0, 9)) for _ in range(9))
        self.tin = f"{r.randint(10, 99)}-{r.randint(1000000, 9999999)}"
        self.ehr = r.random() < 0.65
        self.faxes = r.random() < 0.5
        self.mrn = r.choice(['', 'E', 'MR', 'H']) + str(r.randint(100000, 9999999))
        self.acct = str(r.randint(10000000, 99999999))
        self.fee = r.uniform(0.85, 1.35)
        self.staff = {}
        self.services = []   # (date, procs, codes, kind)
        self.docs = []
        self.first = None

    # formatting
    def d(self, d):
        return fmt_date(d, self.dfmt)

    def t(self, t):
        h, m = map(int, t.split(':'))
        if self.tstyle == 'mil':
            return f"{h:02d}{m:02d}"
        if self.tstyle == 'colon':
            return t
        return f"{(h % 12) or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"

    def dt(self, d, t):
        if self.dfmt == 'iso':
            return f"{d.isoformat()}T{t}"
        return f"{self.d(d)} {self.t(t)}"

    def cap(self, s):
        return s.upper() if self.caps else s

    def sec(self, s):
        return ('S', self.cap(s) + self.sfx)

    def kv(self, k, v):
        return ('K', f"{k}{self.kvsep}{v}")

    def table(self, heads, rows):
        rows = [[str(c) for c in row] for row in rows]
        if self.tbl == 'space':
            w = [max(len(str(x[i])) for x in [heads] + rows) for i in range(len(heads))]
            fmt = lambda row: '  '.join(str(c).ljust(w[i]) for i, c in enumerate(row)).rstrip()
            return [('R', fmt(heads))] + [('R', fmt(r_)) for r_ in rows]
        if self.tbl == 'pipe2':
            return [('R', '| ' + ' | '.join(heads) + ' |')] + [('R', '| ' + ' | '.join(r_) + ' |') for r_ in rows]
        return [('R', ' | '.join(heads))] + [('R', ' | '.join(r_)) for r_ in rows]

    def person(self, role, idx=0):
        key = (role, idx)
        if key not in self.staff:
            self.staff[key] = self.case.clinician(role)
        return self.staff[key]

    def header(self):
        c = self.case
        pt = c.pt
        nm = self.name.upper() if self.hcaps else self.name
        L = [('H', nm)]
        if self.specialty:
            L.append(('H', self.specialty))
        L += [('H', self.addr), ('H', f"Tel {self.phone}   Fax {self.fax}")]
        if self.hdrmode == 0:
            L.append(('H', f"PATIENT: {pt['last'].upper()}, {pt['first'].upper()}    MRN: {self.mrn}    DOB: {self.d(pt['dob'])}"))
        elif self.hdrmode == 1:
            L.append(('H', f"Name: {pt['first']} {pt['last']} | DOB: {self.d(pt['dob'])} | Acct: {self.acct}"))
        else:
            L += [('H', f"Patient Name: {pt['last']}, {pt['first']} {pt['mi']}."), ('H', f"Date of Birth: {self.d(pt['dob'])}    Chart #: {self.mrn}")]
        return L

    def letterhead(self):
        L = [('H', self.name.upper() if self.hcaps else self.name)]
        if self.specialty:
            L.append(('H', self.specialty))
        L += [('H', self.addr), ('H', f"Telephone {self.phone}  /  Facsimile {self.fax}")]
        return L


# ------------------------------------------------------------------ rendering
def wrap(text, font, size, width):
    out = []
    for para in text.split('\n'):
        words = para.split(' ')
        cur = ''
        for w in words:
            t = w if not cur else cur + ' ' + w
            if fitz.get_text_length(t, fontname=font, fontsize=size) <= width or not cur:
                cur = t
            else:
                out.append(cur)
                cur = w
        out.append(cur)
    return out


def build_lines(items, st, sc, width):
    lines = []
    size = st['size'] * sc
    lead = st['lead']
    first_h = True
    had_h = False
    for role, text in items:
        if role == 'F':
            continue
        if role == 'H':
            f = st['bold'] if first_h else st['body']
            sz = (st['hsize'] + (2 if first_h else 0)) * sc
            for ln in wrap(text, f, sz, width):
                lines.append((ln, f, sz, st['halign'], sz * lead, 'H'))
            first_h = False
            had_h = True
            continue
        if had_h:
            lines.append((None, None, 0, None, size * 0.6, 'rule' if st['rule'] else 'gap'))
            had_h = False
        if role == 'T':
            sz = size + 2.5 * sc
            for ln in wrap(text, st['bold'], sz, width):
                lines.append((ln, st['bold'], sz, st['talign'], sz * 1.45, 'T'))
        elif role == 'S':
            sz = size + 0.5 * sc
            lines.append((None, None, 0, None, size * 0.35, 'gap'))
            for ln in wrap(text, st['bold'], sz, width):
                lines.append((ln, st['bold'], sz, 'left', sz * lead, 'S'))
        elif role == 'R':
            f = st['tfont']
            sz = size - 0.5 * sc
            while fitz.get_text_length(text, fontname=f, fontsize=sz) > width and sz > 4.5:
                sz -= 0.25
            lines.append((text, f, sz, 'left', sz * lead, 'R'))
        elif role == 'B':
            lines.append((None, None, 0, None, size * 0.7, 'gap'))
        elif role == 'X':
            for ln in wrap(text, st['ital'], size, width):
                lines.append((ln, st['ital'], size, 'left', size * lead, 'X'))
        else:  # P, K, L
            for ln in wrap(text, st['body'], size, width):
                lines.append((ln, st['body'], size, 'left', size * lead, role))
    return lines


def put(page, x, y, text, font, size, crop=None, color=(0, 0, 0), rotate=0, morph=None):
    if not text:
        return
    if crop:
        if y < crop.get('top', 0) or y > PH - crop.get('bottom', 0):
            return
        limit = PW - crop.get('right', 0)
        if x + fitz.get_text_length(text, fontname=font, fontsize=size) > limit:
            while text and x + fitz.get_text_length(text, fontname=font, fontsize=size) > limit:
                text = text[:-1]
            if not text.strip():
                return
    kw = dict(fontname=font, fontsize=size, color=color)
    if rotate:
        kw['rotate'] = rotate
    if morph is not None:
        kw['morph'] = morph
    page.insert_text((x, y), text, **kw)


def draw_body(page, items, st, crop=None):
    m = st['margin']
    width = PW - 2 * m
    top = st['top']
    sc = 1.0
    for _ in range(25):
        lines = build_lines(items, st, sc, width)
        if top + sum(l[4] for l in lines) <= PH - 58:
            break
        sc *= 0.94
    y = top
    for text, f, sz, align, lh, kind in lines:
        y += lh
        if kind == 'rule':
            if not crop or y - lh * 0.5 > crop.get('top', 0):
                page.draw_line((m, y - lh * 0.5), (PW - m, y - lh * 0.5), color=(0.3, 0.3, 0.3), width=0.6)
            continue
        if text is None:
            continue
        w = fitz.get_text_length(text, fontname=f, fontsize=sz)
        x = m if align == 'left' else (PW - w) / 2 if align == 'center' else PW - m - w
        put(page, x, y, text, f, sz, crop)
    foots = [t for r_, t in items if r_ == 'F']
    for i, ft in enumerate(foots):
        sz = st['size'] - 1
        w = fitz.get_text_length(ft, fontname=st['body'], fontsize=sz)
        x = (PW - w) / 2 if st['talign'] == 'center' else PW - m - w
        put(page, x, PH - 42 + i * 10, ft, st['body'], sz, crop)


def draw_overlay(page, ov, crop=None):
    k = ov[0]
    if k == 'fax_top':
        put(page, 22, 12, ov[1], 'cour', 7, crop)
    elif k == 'fax_bot':
        put(page, 22, PH - 6, ov[1], 'cour', 7, crop)
    elif k == 'foot':
        put(page, 30, PH - 17, ov[1], 'helv', 6.5, crop)
    elif k == 'bates':
        text, pos = ov[1], ov[2]
        f, sz = ov[3] if len(ov) > 3 else ('hebo', 8)
        w = fitz.get_text_length(text, fontname=f, fontsize=sz)
        if pos == 'br':
            x, y = PW - 26 - w, PH - 27
        elif pos == 'bc':
            x, y = (PW - w) / 2, PH - 27
        elif pos == 'bl':
            x, y = 26, PH - 27
        else:
            x, y = PW - 26 - w, 26
        put(page, x, y, text, f, sz, crop)
    elif k == 'side':
        put(page, 16, 560, ov[1], 'hebo', 7.5, crop, rotate=90)
    elif k == 'stamp':
        lines, x, y, ang, col = ov[1], ov[2], ov[3], ov[4], ov[5]
        mat = fitz.Matrix(ang)
        h = 11 * len(lines) + 6
        w = max(fitz.get_text_length(s, fontname='hebo', fontsize=8.5) for s in lines) + 12
        rect = fitz.Rect(x, y, x + w, y + h)
        if not crop or y > crop.get('top', 0):
            page.draw_rect(rect, color=col, width=1.1, morph=(fitz.Point(x, y), mat))
        for i, s in enumerate(lines):
            put(page, x + 6, y + 12 + 11 * i, s, 'hebo', 8.5, crop, color=col, morph=(fitz.Point(x, y), mat))
    elif k == 'sticky':
        lines, x, y = ov[1], ov[2], ov[3]
        w = max(fitz.get_text_length(s, fontname='tiit', fontsize=10) for s in lines) + 14
        h = 13 * len(lines) + 12
        page.draw_rect(fitz.Rect(x, y, x + w, y + h), color=(0.85, 0.75, 0.2), fill=(1, 0.95, 0.55), width=0.5)
        for i, s in enumerate(lines):
            put(page, x + 7, y + 15 + 13 * i, s, 'tiit', 10, None, color=(0.15, 0.15, 0.5))
    elif k == 'hand':
        text, x, y, ang = ov[1], ov[2], ov[3], ov[4]
        put(page, x, y, text, 'coit', 10, None, color=(0.1, 0.2, 0.7), morph=(fitz.Point(x, y), fitz.Matrix(ang)))
    elif k == 'sticker':
        lines, x, y = ov[1], ov[2], ov[3]
        page.draw_rect(fitz.Rect(x, y, x + 78, y + 13 * len(lines) + 8), color=(0, 0, 0), fill=(0.93, 0.97, 1), width=0.8)
        for i, s in enumerate(lines):
            w = fitz.get_text_length(s, fontname='hebo', fontsize=8.5)
            put(page, x + 39 - w / 2, y + 13 + 13 * i, s, 'hebo', 8.5)


def render_rec(pdf, rec):
    page = pdf.new_page(width=PW, height=PH)
    draw_body(page, rec['items'], rec['st'], rec['crop'])
    for ov in rec['inh']:
        draw_overlay(page, ov, rec['crop'])
    for ov in rec['own']:
        draw_overlay(page, ov, None)
    return page


# ------------------------------------------------------------------ copy damage
CONF = {'0': 'O', 'O': '0', '1': 'l', 'l': '1', 'I': 'l', '5': 'S', 'S': '5', '8': 'B', 'B': '8', '3': '8', '6': 'b', 'e': 'c', 'c': 'e',
        'a': 'o', 'o': 'a', 'h': 'b', 'n': 'h', 'u': 'v', 't': 'f', 'g': 'q', ',': '.', '.': ',', ':': ';', 'i': 'j', 'E': 'F', 'D': '0', '7': '1'}
DIGR = {'rn': 'm', 'cl': 'd', 'li': 'h', 'vv': 'w', 'ri': 'n', 'm': 'rn', 'fi': 'h'}
STRAY = ["'", '`', '.', ',', '~', '^', '|', ';', '_', '\xb0']


def ocr_text(s, r, p):
    out = []
    i = 0
    while i < len(s):
        two = s[i:i + 2]
        if two in DIGR and r.random() < p * 2.5:
            out.append(DIGR[two]); i += 2; continue
        c = s[i]
        if c == 'm' and r.random() < p * 1.5:
            out.append('rn'); i += 1; continue
        if c == ' ' and r.random() < p * 0.9:
            i += 1; continue                         # merged words
        if c.isalpha() and i > 0 and s[i - 1].isalpha() and r.random() < p * 0.35:
            out.append(' ')                         # split word
        if c in CONF and r.random() < p:
            out.append(CONF[c]); i += 1; continue
        if r.random() < p * 0.18:
            out.append(r.choice(STRAY))
        out.append(c)
        i += 1
    return ''.join(out)


def ocr_items(items, r, p):
    out = []
    for role, text in items:
        if role in ('B',):
            out.append((role, text)); continue
        t = ocr_text(text, r, p)
        if role in ('P', 'K', 'L') and len(t) > 30 and r.random() < 0.3:   # broken line
            sp = [i for i, ch in enumerate(t) if ch == ' ']
            if sp:
                j = r.choice(sp)
                t = t[:j] + '\n' + t[j + 1:]
        out.append((role, t))
    return out


def reflow(items, st, r):
    fams = [f for f in ('helv', 'tiro', 'cour') if f != st['body']]
    fam = r.choice(fams)
    size = st['size'] + r.choice([-1, -0.5, 0.5, 1]) if fam != 'cour' else min(st['size'], 9) - 0.5
    st2 = dict(st, body=fam, bold={'helv': 'hebo', 'tiro': 'tibo', 'cour': 'cobo'}[fam], ital={'helv': 'heit', 'tiro': 'tiit', 'cour': 'coit'}[fam], size=size,
               hsize=size, margin=r.choice([40, 50, 76, 84]), halign='left', talign='left', lead=r.choice([1.15, 1.25, 1.45]), rule=False)
    out = []
    i = 0
    while i < len(items):
        role, text = items[i]
        if role == 'K' and i + 1 < len(items) and items[i + 1][0] == 'K':
            out.append(('K', text + '     ' + items[i + 1][1]))
            i += 2
            continue
        out.append((role, text))
        i += 1
    return out, st2


# ------------------------------------------------------------------ case builder
class Case:
    def __init__(self, n, spec):
        self.n, self.spec, self.id = n, spec, f"alt2-{n}"
        self.r = random.Random(7919 * n + 13)
        self.m = random.Random(104729 * n + 5)
        r = self.r
        self.content, self.docs, self.events, self.out = {}, [], [], []
        self.seen = set()
        self.used = set()
        self.town = r.choice(TOWNS)
        self.state = r.choice(STATES)
        self.area = AREAS[STATES.index(self.state)]
        self.county = r.choice(COUNTIES)
        sex = spec['sex'] or r.choice('FM')
        age = r.randint(*spec['age'])
        self.acc = dt.date(2024, 2, 1) + TD(days=r.randint(0, 520))
        dob = self.acc - TD(days=age * 365 + r.randint(20, 340))
        first = r.choice(FIRST_F if sex == 'F' else FIRST_M)
        self.pt = dict(first=first, last=r.choice(LASTS), mi=r.choice('ABCDEFGHJKLMNPRSTW'), dob=dob, sex=sex, age=age,
                       addr=f"{r.randint(10, 9999)} {r.choice(STREETS)}, {self.town}", phone=f"({self.area}) 555-01{r.randint(10, 99)}",
                       member=f"{r.choice(['XJQ', 'WPN', 'HRT', 'MBC'])}{r.randint(100000000, 999999999)}")
        self.he = 'he' if sex == 'M' else 'she'
        self.his = 'his' if sex == 'M' else 'her'
        self.sexw = 'male' if sex == 'M' else 'female'
        self.acc_time = f"{r.choice([7, 9, 10, 11, 13, 14, 15, 16, 17, 21, 22]):02d}:{r.randint(0, 59):02d}"
        self.dfmts = DATEFMTS[:]
        r.shuffle(self.dfmts)
        self.provs = []
        self.embeds = {}   # holder name -> list of (after_doc_id, [cids], src prov, date)
        # third parties
        self.law = self._party('law', r.choice(LAW))
        ins = {'auto': INS_AUTO, 'gl': INS_GL, 'wc': INS_WC}[spec['insurer']]
        self.ins = self._party('ins', r.choice(ins))
        self.dfn = self._party('def', r.choice(DEF))
        self.claimno = f"{r.randint(10, 99)}-{r.randint(10000, 99999)}-{r.choice('ABCDK')}"
        self.fileno = f"{r.randint(2024, 2025)}-{r.randint(100, 999)}"

    def _party(self, kind, name):
        p = Prov(self, kind, name, self.r.choice(DATEFMTS))
        return p

    def clinician(self, role):
        r = self.r
        cred = {'md': r.choice(['MD', 'DO', 'MD']), 'pa': 'PA-C', 'np': 'APRN, FNP-C', 'rn': 'RN', 'pt': 'PT, DPT', 'pta': 'PTA', 'ot': 'OTR/L, CHT', 'cota': 'COTA/L',
                'dc': 'DC', 'medic': 'NRP', 'emt': 'EMT', 'crna': 'CRNA', 'rad': 'MD', 'clerk': '', 'para': '', 'atty': 'Esq.', 'adj': '', 'lpn': 'LPN', 'tech': 'MLS(ASCP)'}[role]
        while True:
            fn = r.choice(CLIN_F + CLIN_M)
            ln = r.choice(LASTS)
            if (fn, ln) not in self.used and ln != self.pt['last']:
                self.used.add((fn, ln))
                break
        nm = f"{fn} {r.choice('ABCDEFGHJKLMNPRSTW')}. {ln}"
        return f"{nm}, {cred}" if cred else nm

    def prov(self, ptype, name, specialty=''):
        p = Prov(self, ptype, name, self.dfmts[len(self.provs) % len(self.dfmts)], specialty)
        self.provs.append(p)
        return p

    # ---------------- documents / events
    def doc(self, p, kind, bodies, date, hdr='patient', label=''):
        did = f"d{len(self.docs) + 1:03d}"
        cids = []
        n = len(bodies)
        for i, b in enumerate(bodies):
            cid = f"c{len(self.content) + 1:04d}"
            items = []
            if hdr == 'patient':
                items += p.header()
            elif hdr == 'letter':
                items += p.letterhead()
            items += b
            if n > 1 or p.always_pg:
                items.append(('F', p.pagefmt.format(i=i + 1, n=n)))
            self.content[cid] = dict(items=items, st=p.st, prov=p, kind=kind, doc=did, label=label)
            cids.append(cid)
        D = dict(id=did, prov=p, kind=kind, cids=cids, date=date, label=label)
        self.docs.append(D)
        p.docs.append(D)
        if p.first is None or date < p.first:
            p.first = date
        return D

    def event(self, date, p, kind, summary, codes, procs, docs, bill=True):
        self.events.append(dict(date=date, provider=p.name, kind=kind, summary=summary, codes=list(codes), procedures=list(procs),
                                doc_id=docs[0]['id'], pages=[c for D in docs for c in D['cids']]))
        if bill:
            p.services.append((date, list(procs), list(codes), kind))

    def embed(self, holder, after_doc, src_docs, date):
        self.embeds.setdefault(holder.name, []).append((after_doc['id'], [c for D in src_docs for c in D['cids']], src_docs[0]['prov'], date))

    def vitals(self, base=None):
        r = self.r
        return dict(bp=f"{r.randint(112, 158)}/{r.randint(64, 96)}", hr=r.randint(62, 112), rr=r.randint(12, 22), spo2=r.randint(94, 100),
                    temp=f"{r.uniform(97.4, 99.6):.1f}", pain=r.randint(2, 9))

    def fill(self, s):
        return s.replace('{part}', self.spec['part']).replace('{injury}', self.spec['injury']).replace('{proc}', self.spec['proc_short'])

    # ================================================================= builders
    def b_prior(self, p):
        s, r, pt = self.spec, self.r, self.pt
        pr = s['prior']
        d = weekday_after(self.acc, -r.randint(90, 340))
        md = p.person('md')
        v = self.vitals()
        cpt = pr['cpt']
        if cpt in ('99395', '99396'):
            cpt = '99395' if pt['age'] < 40 else '99396'
        b1 = [('T', p.cap(r.choice(['Office Visit Note', 'Clinic Progress Note', 'Encounter Summary']))), p.kv('Date of Service', p.d(d)), p.kv('Provider', md), p.kv('Visit Type', pr['type']),
              p.sec('Chief Complaint'), ('P', pr['cc']), p.sec('History of Present Illness'), ('P', f"{pt['age']}-year-old {self.sexw} {s['occupation']}. " + pr['hpi']),
              p.sec('Vital Signs')] + p.table(['BP', 'Pulse', 'Resp', 'Temp', 'SpO2', 'Wt (lb)'], [[v['bp'], v['hr'], v['rr'], v['temp'], f"{v['spo2']}%", r.randint(118, 236)]]) + [
              p.sec('Review of Systems'), ('P', 'Constitutional: negative for fever, chills or weight change. ' + pr['ros'] + ' Neurological: negative for numbness or weakness.'),
              p.sec('Current Medications')] + [('L', f"- {m}") for m in pr['meds']] + [p.kv('Allergies', s['allergies'])]
        b2 = [p.sec('Physical Examination'), ('P', 'General: well appearing, in no distress.'), ('P', pr['exam']), ('P', pr['region']), p.sec('Assessment and Plan')] + \
             [('L', f"{i + 1}. {DX[c]} ({c})") for i, c in enumerate(pr['codes'])] + [('P', pr['plan']), p.kv('Return', pr['fu']),
                                                                                      ('X', f"Electronically signed by {md} on {p.dt(d, addm('16:10', r.randint(0, 90)))}")]
        D = self.doc(p, 'clinical', [b1, b2], d)
        self.event(d, p, 'prior_visit', f"Pre-incident {pr['type'].lower()}: {pr['cc'].lower()}; {s['part']} documented normal.", pr['codes'], [cpt], [D])

    def b_ems(self, p, hosp):
        s, r, pt, d = self.spec, self.r, self.pt, self.acc
        t0 = self.acc_time
        times = [('Call received', t0)]
        for lab, dm in [('Dispatched', 1), ('En route', 1), ('On scene', r.randint(6, 12)), ('Patient contact', 1), ('Depart scene', r.randint(14, 24)), ('Arrive destination', r.randint(9, 18)), ('Transfer of care', r.randint(4, 9))]:
            times.append((lab, addm(times[-1][1], dm)))
        medic, emt = p.person('medic'), p.person('emt')
        unit = f"{r.choice(['Medic', 'Rescue', 'Ambulance', 'ALS'])} {r.randint(2, 41)}"
        inc = f"{d.year % 100}-{r.randint(10000, 99999)}"
        vit = []
        for k in range(3):
            v = self.vitals()
            vit.append([p.t(addm(times[4][1], 2 + k * 8)), v['bp'], v['hr'], v['rr'], f"{v['spo2']}%", 15 if s['key'] != 'nursing_home_fall' else 13, max(v['pain'], 7 - k)])
        b1 = [('T', p.cap(r.choice(['Patient Care Report', 'Prehospital Care Record', 'EMS Run Report']))), p.kv('Incident #', inc), p.kv('Unit', unit), p.kv('Date of Service', p.d(d)),
              p.kv('Crew', f"{medic}; {emt}"), p.kv('Response', 'Emergent, lights and siren'), p.kv('Location type', s['setting']), p.kv('Patient', f"{pt['first']} {pt['last']}, {pt['age']} y/o {self.sexw}"),
              p.sec('Times')] + p.table(['Event', 'Time'], [[a, p.t(b)] for a, b in times]) + [
              p.sec('Chief Complaint'), ('P', s['cc']), p.sec('Vital Signs')] + p.table(['Time', 'BP', 'HR', 'RR', 'SpO2', 'GCS', 'Pain'], vit)
        fent = r.choice([50, 75, 100])
        b2 = [p.sec('Narrative'),
              ('P', f"C: {s['cc']}."),
              ('P', f"H: Pt is a {pt['age']} y/o {self.sexw} who {s['mech']}. Denies neck pain unless noted. PMH: {', '.join(s['pmh'])}. Allergies: {s['allergies']}."),
              ('P', f"A: On arrival pt found {s['ems_found']}. Airway patent, breathing unlabored, radial pulses present. {s['nv'].capitalize()}."),
              ('P', f"R: Medical control not contacted; standing orders followed."),
              ('P', f"T: {s['ems_tx']}. Pt tolerated transport, reassessed every 8 minutes, transferred to {hosp.name} ED staff with verbal report."),
              p.sec('Treatment')] + p.table(['Time', 'Intervention', 'Dose/Detail', 'By'], [
                  [p.t(addm(times[4][1], 3)), 'Splint/immobilization', 'as narrative', emt.split(',')[0]],
                  [p.t(addm(times[4][1], 6)), 'IV access', '18 g L AC, NS TKO', medic.split(',')[0]],
                  [p.t(addm(times[4][1], 8)), 'Fentanyl IV', f"{fent} mcg", medic.split(',')[0]],
                  [p.t(addm(times[5][1], 5)), 'Ondansetron IV', '4 mg', medic.split(',')[0]]]) + [
              p.sec('Field Impression'), ('P', f"Traumatic injury: suspected {s['injury']}."),
              p.kv('Disposition', 'Transported, no lights or siren to destination'), p.kv('Destination', hosp.name), p.kv('Mileage', f"{r.uniform(3.1, 14.8):.1f} mi"),
              ('X', f"Report completed by {medic} {p.dt(d, addm(times[-1][1], r.randint(20, 70)))}")]
        D = self.doc(p, 'clinical', [b1, b2], d)
        self.event(d, p, 'er_visit', f"EMS response and transport to {hosp.name} after {s['title'].lower()}.", s['icd'] + s['ext'], ['A0427', 'A0425'], [D])
        return times[6][1]

    def b_er(self, p, arrive, urgent=False):
        s, r, pt, d = self.spec, self.r, self.pt, self.acc
        md, rn = p.person('md' if not urgent else r.choice(['pa', 'np'])), p.person('rn')
        v = self.vitals()
        esi = r.choice([2, 3])
        b1 = [('T', p.cap('Urgent Care Visit - Triage and Intake' if urgent else r.choice(['Emergency Department Triage Record', 'ED Nursing Triage']))),
              p.kv('Arrival', p.dt(d, arrive)), p.kv('Mode of arrival', 'EMS' if s['ems'] else 'Private vehicle'), p.kv('Acuity (ESI)', str(esi)) if not urgent else p.kv('Acuity', 'Level 2 of 4'),
              p.kv('Triage RN', rn), p.sec('Triage Vitals')] + p.table(['BP', 'HR', 'RR', 'Temp F', 'SpO2', 'Pain 0-10'], [[v['bp'], v['hr'], v['rr'], v['temp'], f"{v['spo2']}%", max(v['pain'], 6)]]) + [
              p.sec('Triage Note'), ('P', f"Pt states {self.he} {s['mech']}. Complains of {s['cc'].lower()}. {s['nv'].capitalize()}."),
              p.kv('Allergies', s['allergies']), p.kv('Medical history', ', '.join(s['pmh'])), p.kv('Tetanus', r.choice(['Within 5 years', 'Unknown - Tdap given', 'Within 10 years'])),
              p.kv('Fall risk screen', r.choice(['Positive', 'Negative'])), p.kv('Interpreter needed', 'No')]
        b2 = [('T', p.cap('Provider Note')), p.kv('Seen by', md), p.kv('Time seen', p.t(addm(arrive, r.randint(12, 45)))), p.sec('History of Present Illness'),
              ('P', f"{pt['age']}-year-old {self.sexw} {s['occupation']} who {s['mech']}. Reports immediate pain and inability to use the {s['part']}. "
                    f"No other complaints. Last oral intake about {r.randint(2, 6)} hours prior."),
              p.sec('Review of Systems'), ('P', 'All other systems reviewed and negative except as noted in HPI.'),
              p.sec('Past History'), ('P', f"Medical: {', '.join(s['pmh'])}. Surgical: {r.choice(['appendectomy', 'none', 'tonsillectomy', 'cholecystectomy'])}. Social: {r.choice(['never smoker', 'former smoker, quit 10 years ago', 'occasional alcohol, no tobacco'])}."),
              p.sec('Physical Examination'), ('P', f"Vitals reviewed. Alert, {'oriented' if s['key'] != 'nursing_home_fall' else 'confused at baseline'}, in moderate distress due to pain."),
              ('P', s['er_exam']), ('P', 'Head atraumatic unless noted, chest wall nontender, abdomen soft, pelvis stable to compression.' if s['key'] not in ('assault_face', 'nursing_home_fall') else 'Chest wall nontender, abdomen soft, pelvis stable.')]
        studies = [s['studies'][k]['name'] for k in s['er_imaging']]
        b3 = [p.sec('Results and Medical Decision Making'), ('P', f"Imaging ordered: {'; '.join(studies)}. Preliminary reads reviewed by me, see final radiology reports."),
              ('P', 'Labs: CBC and basic metabolic panel within acceptable limits; see laboratory report.' if not urgent else 'No laboratory studies indicated.'),
              ('P', 'Differential included fracture, dislocation, ligamentous injury and neurovascular compromise; neurovascular status remained intact on serial checks.'),
              p.sec('ED Course' if not urgent else 'Clinic Course'), ('P', s['er_course'])] + p.table(['Time', 'Medication', 'Dose', 'Route'], [
                  [p.t(addm(arrive, 25)), r.choice(['Morphine', 'Hydromorphone', 'Fentanyl']), r.choice(['4 mg', '0.5 mg', '50 mcg']), 'IV'],
                  [p.t(addm(arrive, 70)), 'Ondansetron', '4 mg', 'IV'], [p.t(addm(arrive, 140)), 'Acetaminophen', '1000 mg', 'PO']]) + [
              p.sec('Diagnoses')] + [('L', f"{c}  {DX[c]}") for c in s['icd'] + s['ext']]
        dispo = 'Admitted' if s['admit'] else 'Discharged home' if s['key'] != 'nursing_home_fall' else 'Returned to facility'
        b4 = [p.sec('Disposition'), p.kv('Disposition', dispo), p.kv('Condition', 'Stable'), p.kv('Departure', p.t(addm(arrive, r.randint(190, 330)))),
              ('P', f"Plan discussed with patient{' and facility nurse by phone' if s['key'] == 'nursing_home_fall' else ''}. " +
               ('Admitted for definitive management.' if s['admit'] else f"Follow up with specialist within 3-7 days. Keep splint or sling dry; elevate; return for numbness, color change or uncontrolled pain.")),
              p.sec('Discharge Prescriptions' if not s['admit'] else 'Handoff'),
              ('L', 'Oxycodone-acetaminophen 5/325 mg, 1 tab q6h PRN, #12' if not s['admit'] else f"Report given to inpatient RN at {p.t(addm(arrive, 300))}."),
              ('L', 'Ibuprofen 600 mg q6h with food PRN' if not s['admit'] else 'Inpatient orders entered by admitting team.'),
              ('X', f"Electronically signed: {md} {p.dt(d, addm(arrive, r.randint(330, 420)))}")]
        pages = [b1, b2, b3, b4] if not urgent else [b1, b2, b3 + b4[:6] + b4[-1:]]
        D = self.doc(p, 'clinical', pages, d)
        self.er_note = D
        procs = list(s['er_procs'])
        self.event(d, p, 'er_visit', f"{'Urgent care' if urgent else 'Emergency department'} evaluation of {s['injury']} after {s['title'].split(' with ')[0].lower()}; {dispo.lower()}.",
                   s['icd'] + s['ext'], procs, [D])
        return D

    def b_lab(self, p, arrive):
        r, d = self.r, self.acc
        tech = p.person('tech')
        coll = addm(arrive, r.randint(15, 40))
        rows = [['WBC', f"{r.uniform(7.2, 13.9):.1f}", '4.0-11.0', 'K/uL'], ['Hemoglobin', f"{r.uniform(11.4, 15.6):.1f}", '12.0-17.5', 'g/dL'], ['Hematocrit', f"{r.uniform(34, 46):.1f}", '36-52', '%'],
                ['Platelets', str(r.randint(160, 390)), '150-400', 'K/uL'], ['Sodium', str(r.randint(134, 144)), '135-145', 'mmol/L'], ['Potassium', f"{r.uniform(3.4, 4.9):.1f}", '3.5-5.1', 'mmol/L'],
                ['Chloride', str(r.randint(98, 108)), '98-107', 'mmol/L'], ['CO2', str(r.randint(21, 29)), '22-29', 'mmol/L'], ['BUN', str(r.randint(9, 24)), '7-20', 'mg/dL'],
                ['Creatinine', f"{r.uniform(0.6, 1.2):.2f}", '0.6-1.3', 'mg/dL'], ['Glucose', str(r.randint(86, 168)), '70-99', 'mg/dL'], ['Calcium', f"{r.uniform(8.6, 10.1):.1f}", '8.5-10.5', 'mg/dL']]
        for row in rows:
            lo, hi = row[2].split('-')
            val = float(row[1])
            row.insert(2, 'H' if val > float(hi) else 'L' if val < float(lo) else '')
        b = [('T', p.cap('Laboratory Report')), p.kv('Collected', p.dt(d, coll)), p.kv('Received', p.dt(d, addm(coll, 9))), p.kv('Accession', f"L{r.randint(1000000, 9999999)}"),
             p.kv('Ordering', self.er_note['prov'].person('md')), p.sec('Hematology and Chemistry')] + p.table(['Test', 'Result', 'Flag', 'Reference', 'Units'], rows) + [
             ('P', 'Specimen: venous blood. Hemolysis index normal.'), ('X', f"Verified by {tech} {p.dt(d, addm(coll, 52))}")]
        D = self.doc(p, 'clinical', [b], d)
        self.event(d, p, 'lab', 'CBC and basic metabolic panel drawn in the emergency department.', self.spec['icd'], ['85025', '80048'], [D])

    def b_imaging(self, p, key, d, t, where, codes, corrected=False):
        s, r = self.spec, self.r
        st = s['studies'][key]
        rad = p.person('rad', 0 if key in s['er_imaging'] else 1)
        fnd = list(st['findings'])
        acc_no = f"{r.choice(['RAD', 'IMG', 'A'])}{r.randint(100000, 999999)}"
        def body(fs, status, signed):
            return [('T', p.cap(r_title)), p.kv('Exam', st['name']), p.kv('Exam date', p.dt(d, t)), p.kv('Accession', acc_no), p.kv('Location', where),
                    p.kv('Ordering provider', ordering), p.kv('Report status', status), p.sec('Clinical History'), ('P', st['hx']), p.sec('Comparison'), ('P', comparison),
                    p.sec('Technique'), ('P', st['technique']), p.sec('Findings')] + [('P', f) for f in fs] + [p.sec('Impression')] + \
                   [('L', f"{i + 1}. {x}") for i, x in enumerate(st['impression'])] + [('X', f"Interpreted by {rad}. {signed}")]
        r_title = r.choice(['Diagnostic Imaging Report', 'Radiology Report', 'Imaging Consultation'])
        ordering = self.er_note['prov'].person('md') if key in s['er_imaging'] else (self.ortho.person('md') if self.ortho else 'Referring physician')
        comparison = r.choice(['None available.', 'None.', 'No prior studies of this region.'])
        D = self.doc(p, 'clinical', [body(fnd, 'FINAL', f"Electronically signed {p.dt(d, addm(t, r.randint(40, 200)))}")], d)
        docs = [D]
        if corrected:
            idx, new = st['alt']
            fnd2 = list(fnd)
            fnd2[idx] = new
            D2 = self.doc(p, 'clinical', [body(fnd2, 'CORRECTED', f"Corrected report signed {p.dt(d + TD(days=r.randint(1, 3)), addm(t, r.randint(10, 300)))}")], d, label='corrected')
            docs.append(D2)
        self.event(d, p, 'imaging', f"{st['name'].title()}: {st['impression'][0]}", codes, [st['cpt']], docs)
        return docs

    # ---------- inpatient
    def b_admission(self, p, los, surg_day, surg_prov):
        s, r, pt = self.spec, self.r, self.pt
        hosp_md = p.person('md', 1)
        days = [self.acc + TD(days=k) for k in range(los)]
        notes_docs = {}
        # H&P
        v = self.vitals()
        hp1 = [('T', p.cap('History and Physical - Admission')), p.kv('Admit date', p.d(days[0])), p.kv('Attending', hosp_md), p.kv('Service', r.choice(['Orthopaedic Surgery', 'Hospital Medicine']) if s['spec'][0] == 'ortho' else r.choice(['Trauma Surgery', 'Hospital Medicine'])),
               p.sec('Chief Complaint'), ('P', s['cc']), p.sec('History of Present Illness'),
               ('P', f"{pt['first']} {pt['last']} is a {pt['age']}-year-old {self.sexw} who {s['mech']}. Evaluated in the emergency department where imaging demonstrated {s['injury']}. Admitted for pain control and definitive management."),
               p.sec('Past Medical History')] + [('L', f"- {x}") for x in s['pmh']] + [p.sec('Medications'), ('P', '; '.join(s['prior']['meds'])), p.kv('Allergies', s['allergies']),
               p.sec('Social History'), ('P', f"Works as a {s['occupation']}. Lives {r.choice(['with spouse', 'alone', 'with adult daughter', 'with partner'])} in a {r.choice(['two-story home', 'first-floor apartment', 'ranch home with 3 entry steps'])}.")]
        hp2 = [p.sec('Physical Examination'), ('P', f"BP {v['bp']}, HR {v['hr']}, RR {v['rr']}, T {v['temp']}, SpO2 {v['spo2']}%."), ('P', s['er_exam']),
               p.sec('Data Reviewed'), ('P', 'Emergency department laboratory results and imaging reviewed.'), p.sec('Assessment and Plan')] + \
              [('L', f"{i + 1}. {DX[c]}") for i, c in enumerate(s['icd'])] + [
               ('P', f"Plan: {s['surg']['name'].lower()} on hospital day {surg_day}. NPO after midnight. Multimodal analgesia. VTE prophylaxis. PT/OT after surgery."),
               ('X', f"Signed {hosp_md} {p.dt(days[0], addm(self.acc_time, 300 + r.randint(0, 120)))}")]
        shifts = [('Day', ['08:00', '10:00', '12:00', '14:00', '16:00', '18:00']), ('Night', ['20:00', '22:00', '00:00', '02:00', '04:00', '06:00'])]
        prev_pain = 8
        for k, d in enumerate(days):
            day_docs = []
            if k == 0:
                day_docs.append(self.doc(p, 'clinical', [hp1, hp2], d))
            else:
                pod = k - surg_day
                vv = self.vitals()
                pain = max(2, prev_pain - r.randint(0, 2))
                prev_pain = pain
                subj = r.choice(['Slept intermittently overnight.', 'Reports pain better controlled.', 'Ambulated with therapy yesterday.', 'Mild nausea this morning, resolved.', 'Asking about discharge timing.', 'Pain worse with dependency of the limb.'])
                status = (f"POD #{pod} s/p {s['proc_short']}." if pod > 0 else ('Day of surgery.' if pod == 0 else f"Preoperative, awaiting {s['proc_short']}."))
                pn = [('T', p.cap('Daily Progress Note')), p.kv('Date', p.d(d)), p.kv('Hospital day', str(k + 1)), p.kv('Author', hosp_md),
                      p.sec('Subjective'), ('P', f"{subj} Pain {pain}/10 at rest. {status}"),
                      p.sec('Objective'), ('P', f"T {vv['temp']}  HR {vv['hr']}  BP {vv['bp']}  RR {vv['rr']}  SpO2 {vv['spo2']}% RA. I/O {r.randint(1200, 2600)}/{r.randint(900, 2400)} mL."),
                      ('P', f"{s['part'].capitalize()}: {r.choice(['dressing clean, dry and intact', 'splint intact, mild strike-through', 'incision without erythema', 'swelling decreased from yesterday'])}. {s['nv'].capitalize()}."),
                      ('P', f"Labs: Hgb {r.uniform(9.1, 13.8):.1f}, WBC {r.uniform(6.0, 12.8):.1f}, Cr {r.uniform(0.6, 1.2):.2f}."),
                      p.sec('Assessment and Plan'),
                      ('L', f"1. {s['injury'].capitalize()} - {status}"),
                      ('L', f"2. Pain - continue scheduled acetaminophen, oxycodone PRN; used {r.randint(1, 5)} PRN doses in 24 h."),
                      ('L', f"3. VTE prophylaxis - enoxaparin, SCDs."),
                      ('L', f"4. Disposition - {r.choice(['PT/OT evaluation pending', 'case management following', 'anticipate discharge in 1-2 days', 'home health referral placed'])}.")]
                if k == len(days) - 1:
                    pn.append(('L', '5. Discharge today; see discharge summary.'))
                pn.append(('X', f"{hosp_md} {p.dt(d, f'{r.randint(7, 11):02d}:{r.randint(0, 59):02d}')}"))
                day_docs.append(self.doc(p, 'clinical', [pn], d))
            # flowsheets
            for sname, times in shifts:
                if k == 0 and sname == 'Day' and int(self.acc_time[:2]) >= 14:
                    continue
                rn = p.person('rn', r.randint(0, 3))
                rows = []
                for tt in times:
                    vv = self.vitals()
                    rows.append([p.t(tt), vv['bp'], vv['hr'], vv['rr'], vv['spo2'], vv['temp'], r.randint(1, 8), r.choice(['repositioned', 'ice applied', 'PRN given', 'asleep', 'ambulated', 'elevated', 'none'])])
                fs = [('T', p.cap('Nursing Flowsheet')), p.kv('Date', p.d(d)), p.kv('Shift', f"{sname} {'07:00-19:00' if sname == 'Day' else '19:00-07:00'}"), p.kv('Primary RN', rn),
                      p.sec('Vital Signs and Pain')] + p.table(['Time', 'BP', 'HR', 'RR', 'SpO2', 'Temp', 'Pain', 'Intervention'], rows) + [
                      p.sec('Assessment'), p.kv('Neuro', r.choice(['A&O x4', 'A&O x3', 'alert, follows commands'])), p.kv('Neurovascular', s['nv']),
                      p.kv('Skin', r.choice(['intact, Braden 18', 'intact, Braden 16', 'abrasions healing, Braden 17'])),
                      p.kv('Intake/Output', f"{r.randint(600, 1400)} mL / {r.randint(400, 1300)} mL"), p.kv('Activity', r.choice(['bedrest', 'OOB to chair x1', 'ambulated 40 ft with walker', 'dangled at bedside'])),
                      p.kv('Safety', r.choice(['bed low, call light in reach, bed alarm on', 'fall precautions in place', 'SCDs on, side rails x2']))]
                day_docs.append(self.doc(p, 'clinical', [fs], d))
            # MAR
            meds = s['meds'] or ['Acetaminophen 1000 mg PO q8h', 'Oxycodone 5 mg PO q4h PRN pain']
            rows = []
            for med in meds:
                sched = 'PRN' if 'PRN' in med else r.choice(['0900', '0900 2100', '0600 1400 2200', '0000 0600 1200 1800'])
                if 'PRN' in med:
                    given = ' '.join(f"{r.randint(0, 23):02d}{r.choice(['05', '20', '35', '50'])}" for _ in range(r.randint(0, 4))) or 'not given'
                else:
                    given = ' '.join(x + ' ' + r.choice(['KT', 'JR', 'MB', 'AL', 'SO']) for x in sched.split())
                rows.append([med, sched, given])
            mar = [('T', p.cap('Medication Administration Record')), p.kv('MAR date', p.d(d)), p.kv('Weight', f"{r.randint(55, 104)} kg"), p.kv('Allergies', s['allergies'])] + \
                  p.table(['Medication / Dose / Route / Freq', 'Scheduled', 'Given (time + initials)'], rows) + [
                  ('P', f"Pharmacist verification: {p.person('rn', 9).split(',')[0]} PharmD. Initials key: KT, JR, MB, AL, SO = assigned nurses for this date.")]
            day_docs.append(self.doc(p, 'clinical', [mar], d))
            if k == len(days) - 1:
                ds1 = [('T', p.cap('Discharge Summary')), p.kv('Admission date', p.d(days[0])), p.kv('Discharge date', p.d(d)), p.kv('Attending', hosp_md), p.kv('Length of stay', f"{los - 1} days"),
                       p.sec('Principal Diagnosis'), ('P', f"{DX[s['icd'][0]]} ({s['icd'][0]})"), p.sec('Procedures'), ('P', f"{s['surg']['name']} on {p.d(days[surg_day])}."),
                       p.sec('Hospital Course'), ('P', f"Admitted from the emergency department after {s['title'].split(' with ')[0].lower()}. Underwent {s['proc_short']} on hospital day {surg_day + 1} without complication. Pain controlled on oral regimen. Worked with physical therapy."),
                       ('P', 'No transfusion required. Vital signs stable at discharge.')]
                ds2 = [p.sec('Discharge Medications')] + [('L', f"- {x}") for x in r.sample(meds, min(4, len(meds)))] + [
                       p.sec('Follow-up'), ('P', f"{self.ortho.name if self.ortho else 'Surgeon'} in 10-14 days. Home health and outpatient therapy referrals placed."),
                       p.sec('Activity'), ('P', r.choice(['Non-weight-bearing on the operative limb.', 'Weight bearing as tolerated with walker.', 'Sling at all times except hygiene.', 'Activity as tolerated.'])),
                       ('X', f"Dictated by {hosp_md} {p.dt(d, '13:15')}; transcribed {p.d(d + TD(days=1))}")]
                day_docs.append(self.doc(p, 'clinical', [ds1, ds2], d))
            notes_docs[d] = day_docs
            if k == 0:
                self.event(d, p, 'office_visit', 'Hospital admission history and physical with nursing flowsheets and MAR.', s['icd'], ['99223'], day_docs)
            else:
                self.event(d, p, 'office_visit', f"Inpatient hospital day {k + 1}: progress note, nursing flowsheets and MAR" + (' and discharge summary.' if k == los - 1 else '.'),
                           s['icd'], ['99238' if k == los - 1 else '99232'], day_docs)
        self.discharge = notes_docs[days[-1]][-1]
        self.discharge_date = days[-1]
        return days

    def b_surgery(self, p, d, preop_page=False):
        s, r = self.spec, self.r
        sg = s['surg']
        surgeon = (self.surgeon_prov.person('md') if self.surgeon_prov else p.person('md'))
        asst = p.person('pa')
        anes = p.person('md', 5)
        start = f"{r.randint(7, 13):02d}:{r.choice(['05', '20', '35', '50'])}"
        end = addm(start, r.randint(55, 150))
        codes = [c for c in s['icd'] if c[0] not in 'VWXY']
        op1 = [('T', p.cap('Operative Report')), p.kv('Date of surgery', p.d(d)), p.kv('Surgeon', surgeon), p.kv('Assistant', asst), p.kv('Anesthesiologist', anes),
               p.kv('Preoperative diagnosis', s['injury'].capitalize()), p.kv('Postoperative diagnosis', 'Same'), p.kv('Procedure', sg['name']),
               p.kv('Anesthesia', sg['anesthesia']), p.kv('Estimated blood loss', sg['ebl']), p.kv('Implants', sg['implants']), p.kv('Complications', 'None apparent'),
               p.sec('Indications'), ('P', f"The patient sustained {s['injury']} when {self.he} {s['mech']}. Risks, benefits and alternatives including nonoperative care were discussed and informed consent obtained.")]
        op2 = [p.sec('Description of Procedure'), ('P', f"The patient was identified in the holding area, the {s['part']} marked, and brought to the operating room. Time-out performed. Preoperative antibiotics given.")] + \
              [('P', x) for x in sg['steps']] + [p.sec('Findings'), ('P', sg['findings']), p.kv('Disposition', 'To PACU in stable condition'),
                                                 ('X', f"{surgeon} dictated {p.dt(d, addm(end, 25))}")]
        rows = []
        tt = start
        for _ in range(r.randint(7, 9)):
            vv = self.vitals()
            rows.append([p.t(tt), vv['bp'], vv['hr'], vv['spo2'], r.randint(30, 38) if 'eneral' in sg['anesthesia'] else '-', r.choice(['', 'incision', 'fluoro', 'closure', ''])])
            tt = addm(tt, 15)
        an = [('T', p.cap('Anesthesia Record')), p.kv('Date', p.d(d)), p.kv('ASA class', r.choice(['I', 'II', 'II', 'III'])), p.kv('Anesthesia type', sg['anesthesia']),
              p.kv('Anesthesia start/stop', f"{p.t(addm(start, -20))} / {p.t(addm(end, 10))}"), p.kv('Provider', anes), p.kv('CRNA', p.person('crna')),
              p.sec('Intraoperative Vitals')] + p.table(['Time', 'BP', 'HR', 'SpO2', 'EtCO2', 'Event'], rows) + [
              p.kv('Fluids', f"LR {r.randint(6, 16) * 100} mL"), p.kv('Medications', r.choice(['propofol, fentanyl, rocuronium, dexamethasone, ondansetron', 'propofol infusion, midazolam 2 mg, fentanyl 100 mcg', 'midazolam, fentanyl, cefazolin 2 g'])),
              p.kv('Airway', r.choice(['ETT 7.5 grade I view', 'LMA size 4', 'Natural airway, nasal cannula', 'Nasotracheal 6.5'])), ('P', 'Uneventful anesthetic. Transferred to PACU with stable vitals.')]
        bodies = [op1, op2, an]
        if preop_page:
            v = self.vitals()
            pre = [('T', p.cap('Pre-Procedure History and Physical Update')), p.kv('Date', p.d(d)), p.kv('Procedure planned', sg['name']), ('P', f"Interval history: no change since office evaluation. NPO since midnight. Vitals BP {v['bp']}, HR {v['hr']}, SpO2 {v['spo2']}%."),
                   ('P', f"Exam: heart regular, lungs clear. {s['part'].capitalize()} skin intact, marked by surgeon."), p.kv('Consent', 'signed and witnessed'), ('X', surgeon)]
            pac = [('T', p.cap('PACU / Phase II Discharge Note')), p.kv('Date', p.d(d)), p.kv('Arrival PACU', p.t(addm(end, 5))), p.kv('Aldrete', '9 -> 10'),
                   ('P', f"Pain {r.randint(2, 5)}/10 after block. Tolerated liquids. Discharge instructions reviewed with {r.choice(['spouse', 'friend', 'facility transport nurse', 'sister'])}."),
                   p.kv('Discharged', p.t(addm(end, r.randint(70, 150)))), ('X', p.person('rn', 4))]
            bodies = [pre] + bodies + [pac]
        D = self.doc(p, 'clinical', bodies, d)
        procs = list(sg['cpt']) + ([sg['anes']] if sg.get('anes') else [])
        self.event(d, p, 'surgery', f"{sg['name']}.", codes, procs, [D])
        self.opnote = D
        return D

    # ---------- outpatient specialists
    def b_spec(self, p, kind, d, stage, n_of, xray=None):
        s, r, pt = self.spec, self.r, self.pt
        md = p.person('md') if stage in ('new', 'preop') or r.random() < 0.7 else p.person('pa')
        v = self.vitals()
        codes = subseq(s['icd']) if stage not in ('new', 'preop') else [c for c in s['icd'] if c[0] not in 'VWXY']
        if kind == 'ophtho':
            exam = f"Visual acuity 20/{r.choice([20, 25, 30])} OD, 20/20 OS. Pupils equal, no APD. {'Diplopia in extreme upgaze' if stage == 'new' else 'No diplopia in primary or reading gaze'}. Intraocular pressure {r.randint(13, 19)} OD. Dilated fundus normal."
            plan = 'No surgical orbital floor repair needed from an ophthalmic standpoint. Return in 6 weeks.' if stage == 'new' else 'Diplopia resolved. Release to follow up as needed.'
            codes = ['H53.2', 'S02.402D'] if stage != 'new' else ['H53.2', 'S02.402A']
            procs = ['99204' if stage == 'new' else '99213']
        elif kind == 'occmed':
            exam = f"Right hand: {r.choice(['incision healing', 'swelling moderate', 'swelling mild'])}, splint in place. Unable to grip with right hand."
            plan = r.choice(['Work status: no use of right hand, one-handed duty only.', 'Work status: modified duty, no lifting over 5 lb with right hand, no press operation.', 'Work status: modified duty, may use right hand for light assembly, no press work.'])
            procs = ['99213' if stage != 'new' else '99203']
        elif kind == 'wound':
            area = r.uniform(1.0, 9.0) if stage != 'final' else 0.0
            exam = f"Volar forearm wound {area:.1f} sq cm, {r.choice(['granulating', 'clean base', 'minimal slough'])}, periwound erythema {r.choice(['resolving', 'none', 'trace'])}. Rabies vaccine series dose given today (left deltoid)." if stage != 'final' else 'Wounds fully epithelialized. Scar hypertrophic at volar wound.'
            plan = 'Continue daily dressing changes with silver alginate. Complete rabies series.' if stage != 'final' else 'Discharge from wound clinic. Silicone scar sheeting.'
            procs = ['99213', '90675', '96372'] if stage != 'final' else ['99213']
        else:
            exam = None
            procs = None
        if exam is None:   # surgeon-type specialist (ortho / hand / omfs / plastics / spine)
            texts = {
                'new': (f"New patient consultation for {s['injury']} sustained when {self.he} {s['mech']}. Seen in the ED on {p.d(self.acc)}.",
                        f"{s['part'].capitalize()}: swelling and tenderness as expected, splint or sling removed for exam and reapplied. {s['nv'].capitalize()}.",
                        f"Discussed operative versus nonoperative treatment. Recommend {s['surg']['name'].lower()}. Surgery scheduled."),
                'preop': (f"Returns for preoperative visit. Pain {v['pain']}/10.", f"{s['part'].capitalize()}: findings unchanged. {s['nv'].capitalize()}.", "Consent reviewed; surgery date confirmed."),
                'post1': (f"First postoperative visit after {s['proc_short']}. Pain {v['pain']}/10, using {r.choice(['acetaminophen only', 'oxycodone twice daily', 'ibuprofen and acetaminophen'])}.",
                          f"Incision clean, dry and intact. Sutures removed. Mild swelling. {s['nv'].capitalize()}.", 'Begin therapy per protocol. Continue protection. Return in 4 weeks with x-rays.'),
                'post2': (f"Six weeks after {s['proc_short']}. Attending therapy {r.choice(['twice', 'three times'])} weekly. Pain {max(1, v['pain'] - 3)}/10.",
                          f"Incision healed. Motion improving. {s['nv'].capitalize()}.", 'Advance activity and therapy. Return in 6 weeks.'),
                'post3': (f"About three months after surgery. Reports {r.choice(['persistent ache with activity', 'good progress but stiffness', 'pain at end of day'])}.",
                          f"{s['part'].capitalize()}: mild residual swelling, motion short of opposite side.", 'Continue home program. Refer to pain management for persistent pain.' if s['pain'] else 'Continue home program and therapy.'),
                'final': (f"Follow-up about {r.choice([5, 6])} months after surgery. Pain {r.randint(1, 4)}/10 with prolonged activity.",
                          f"{s['part'].capitalize()}: motion near functional range, strength {r.choice(['4/5', '4+/5'])}.", 'Maximum medical improvement anticipated in 1-2 months. Return as needed.')}
            hpi, exam, plan = texts[stage]
            procs = {'new': ['99204'], 'preop': ['99213'], 'post1': ['99024'], 'post2': ['99024'], 'post3': ['99213'], 'final': ['99213']}[stage]
            if stage in ('post1', 'post2') and not self.surg_done_by_this(p):
                procs = ['99213']
        else:
            hpi = f"{'Initial' if stage == 'new' else 'Follow-up'} visit related to {s['injury']} from injury on {p.d(self.acc)}."
        if xray and stage not in ('new',):
            procs = procs + [xray]
        b1 = [('T', p.cap(r.choice(['Office Visit', 'Clinic Note', 'Progress Note']) if stage != 'new' else r.choice(['New Patient Consultation', 'Initial Evaluation']))),
              p.kv('Visit date', p.d(d)), p.kv('Clinician', md), p.kv('Referring', r.choice(['Emergency department', 'Self', 'Primary care'])) if stage == 'new' else p.kv('Visit', f"{n_of[0]} of series"),
              p.sec('History' if stage != 'new' else 'History of Present Illness'), ('P', hpi),
              p.sec('Vitals')] + p.table(['BP', 'HR', 'Pain'], [[v['bp'], v['hr'], f"{v['pain']}/10"]]) + [p.sec('Examination'), ('P', exam)]
        if xray and stage not in ('new',):
            b1 += [p.sec('Imaging'), ('P', f"In-office radiographs of the {s['part']} today: {r.choice(['hardware intact, alignment maintained', 'interval healing with bridging callus', 'no hardware failure, fracture lines less distinct', 'stable position of implants'])}.")]
        tail = [p.sec('Assessment')] + [('L', f"{c} - {DX[c]}") for c in codes] + [p.sec('Plan'), ('P', plan), ('X', f"{md} - signed {p.d(d)}")]
        bodies = [b1 + tail] if stage != 'new' else [b1 + [p.sec('Past History'), ('P', f"PMH: {', '.join(s['pmh'])}. Allergies: {s['allergies']}. Occupation: {s['occupation']}.")], tail]
        D = self.doc(p, 'clinical', bodies, d)
        self.event(d, p, 'office_visit', f"{p.specialty or 'Specialist'} {stage} visit: {plan.split('.')[0].lower()}.", codes, procs, [D])
        return D

    def surg_done_by_this(self, p):
        return self.surgeon_prov is p

    # ---------- therapy
    def b_therapy(self, p, start, nvis, disc):
        s, r, pt = self.spec, self.r, self.pt
        th = p.person('pt' if disc == 'PT' else 'ot')
        asst = p.person('pta' if disc == 'PT' else 'cota')
        meas = s['measures']
        fname, f0, f1 = s['func']
        dates = []
        d = start
        while len(dates) < nvis:
            dates.append(d)
            d = weekday_after(d, r.choice([2, 2, 3, 1, 4]))
        reeval_i = nvis // 2
        codes = subseq(s['icd']) + (['M62.81'] if disc == 'PT' else []) + (['R26.89'] if disc == 'PT' and s['part'] in ('right ankle', 'right hip', 'right knee') else [])
        def mval(k, frac):
            nm, a, b = meas[k]
            x = a + (b - a) * frac + r.uniform(-0.04, 0.04) * abs(b - a)
            return f"{x:.0f}" if 'MMT' not in nm else f"{max(1, min(5, round(x)))}{r.choice(['', '-', '+'])}/5"
        def fval(frac):
            return f"{f0 + (f1 - f0) * frac + r.uniform(-2, 2):.0f}"
        evcode = '97162' if disc == 'PT' else '97166'
        rcode = '97164' if disc == 'PT' else '97168'
        ex_pool = (['97110', '97140', '97112', '97116', '97530', '97035'] if disc == 'PT' else ['97110', '97140', '97530', '97760', '97018'])
        auth_n = r.choice([12, 16, 20, 24])
        acts = r.sample(['Walking a block', 'Climbing stairs', 'Lifting a grocery bag', 'Dressing', 'Sleeping through the night', 'Driving', 'Household chores', 'Gripping a cup', 'Reaching overhead', 'Standing 30 minutes'], 6)

        def intake(d, frac):
            sc = ['no difficulty', 'a little', 'moderate', 'quite a bit', 'unable']
            rows = []
            for a in acts:
                lvl = max(0, min(4, round(3.4 - 3.2 * frac + r.uniform(-0.8, 0.8))))
                rows.append(('L', f"{a:<28} " + '  '.join(f"[{'X' if j == lvl else ' '}] {sc[j]}" for j in range(5))))
            return [('T', p.cap('Patient Intake Questionnaire')), p.kv('Date', p.d(d)), ('L', 'Please mark how much difficulty you have today with each activity:')] + rows + [
                    ('L', f"Pain today (0-10): {max(0, round(7 - 5 * frac + r.uniform(-1, 1)))}    Pain at worst this week (0-10): {max(1, round(9 - 5 * frac + r.uniform(-1, 1)))}"),
                    ('L', f"Are you working?  [{'X' if frac > 0.4 else ' '}] yes  [{' ' if frac > 0.4 else 'X'}] no      Using a brace/splint/device?  [{'X' if frac < 0.5 else ' '}] yes"),
                    ('L', 'Have you had any new injury since your last visit?  [ ] yes  [X] no'), ('L', 'Patient signature: (signed)')]
        hep = r.choice(['HEP issued with 6 exercises, written and pictured.', 'Home program reviewed; patient demonstrates correctly.', 'HEP progressed; handout updated.'])
        for i, d in enumerate(dates):
            frac = min(1.0, (i + 1) / nvis) * r.uniform(0.82, 0.98)
            if i == 0:
                e1 = [('T', p.cap(f"{'Physical' if disc == 'PT' else 'Occupational'} Therapy Initial Evaluation")), p.kv('Date of service', p.d(d)), p.kv('Therapist', th),
                      p.kv('Referring physician', self.surgeon_prov.person('md') if self.surgeon_prov else 'n/a'), p.kv('Diagnosis', f"{s['icd'][0][:-1]}D {DX.get(s['icd'][0][:-1] + 'D', '')}"),
                      p.kv('Date of injury', p.d(self.acc)), p.kv('Date of surgery', p.d(self.surg_date)),
                      p.sec('Subjective'), ('P', f"Patient reports {self.he} {s['mech']}. Underwent {s['proc_short']} on {p.d(self.surg_date)}. Current pain {r.randint(4, 7)}/10, worst {r.randint(7, 9)}/10. "
                                                    f"Difficulty with {r.choice(['stairs and prolonged standing', 'dressing and reaching overhead', 'gripping and carrying', 'sleeping and sitting more than 20 minutes', 'chewing and talking for long periods'])}."),
                      p.sec('Prior Level of Function'), ('P', f"Independent without device; working full duty as {s['occupation']}." if s['key'] != 'nursing_home_fall' else 'Ambulated with rolling walker with standby assist; needed help with bathing.')]
                e2 = [p.sec('Objective')] + p.table(['Measure', 'Initial', 'Goal'], [[m[0], mval(k, 0.02), f"{m[2]}"] for k, m in enumerate(meas)] + [[fname, fval(0.0), str(f1)]]) + [
                      ('P', f"Palpation: {r.choice(['moderate tenderness about incision', 'tender at surgical site', 'diffuse tenderness'])}. Edema: {r.choice(['2+', '1+', 'moderate'])}. Scar: {r.choice(['adherent', 'mobile', 'mildly adherent'])}."),
                      p.sec('Assessment'), ('P', f"Patient presents with impairments of motion, strength and function following {s['proc_short']}, limiting work and daily activities. Good rehab potential."),
                      p.sec('Goals'), ('L', f"STG (4 wk): {meas[0][0]} to {(meas[0][1] + meas[0][2]) // 2}."), ('L', f"LTG (8-12 wk): {fname} to {f1}; return to prior level of function."),
                      p.sec('Plan'), ('P', f"{r.choice([2, 3])}x/week for {r.choice([8, 10, 12])} weeks: {', '.join(ex_pool[:4])}. {hep}")]
                e3 = [p.sec('Charges'), *p.table(['CPT', 'Description', 'Units'], [[evcode, CPT[evcode][0], 1], ['97110', CPT['97110'][0], 1]]),
                      p.sec('Certification of Plan of Care'), ('P', 'I have reviewed this plan of care and certify a need for these services.'),
                      ('L', 'Physician signature: ____________________   Date: __________'), ('X', f"{th}  {p.dt(d, '17:40')}")]
                D = self.doc(p, 'clinical', [e1, e2, e3], d)
                DQ = self.doc(p, 'clinical', [intake(d, 0.0)], d, label='intake')
                self.event(d, p, 'pt_eval', f"{disc} initial evaluation after {s['proc_short']}; {fname} {fval(0.0)}.", codes, [evcode, '97110'], [D, DQ])
                self.therapy_eval = D
            elif i == reeval_i:
                r1 = [('T', p.cap('Progress Report / Re-evaluation')), p.kv('Date of service', p.d(d)), p.kv('Visit number', str(i + 1)), p.kv('Therapist', th),
                      p.sec('Subjective'), ('P', f"Reports {r.choice(['steady improvement', 'improvement but flare after work trial', 'slower progress than expected'])}. Pain {r.randint(2, 6)}/10."),
                      p.sec('Objective')] + p.table(['Measure', 'Initial', 'Current', 'Goal'], [[m[0], mval(k, 0.02), mval(k, frac), str(m[2])] for k, m in enumerate(meas)] + [[fname, fval(0), fval(frac), str(f1)]])
                r2 = [p.sec('Assessment'), ('P', f"Goals: STG {r.choice(['met', 'partially met'])}; LTG not yet met. Continued skilled therapy is necessary to address remaining deficits."),
                      p.sec('Plan'), ('P', f"Continue {r.choice([2, 3])}x/week for {r.choice([4, 6])} more weeks."), *p.table(['CPT', 'Units'], [[rcode, 1], ['97110', 2], ['97140', 1]]),
                      ('X', f"{th}  {p.d(d)}")]
                D = self.doc(p, 'clinical', [r1, r2], d)
                DQ = self.doc(p, 'clinical', [intake(d, frac)], d, label='intake')
                self.event(d, p, 'pt_reeval', f"{disc} re-evaluation, visit {i + 1}; {fname} {fval(frac)}.", codes, [rcode, '97110', '97140'], [D, DQ])
            else:
                cpts = ['97110'] + r.sample(ex_pool[1:], r.randint(1, 3))
                rows = [[c, CPT[c][0][:34], r.choice([15, 15, 23, 30, 8]), 1 if c != '97110' else r.choice([1, 2])] for c in cpts]
                final = (i == nvis - 1)
                tin = f"{r.randint(7, 17):02d}:{r.choice(['00', '15', '30', '45'])}"
                who = th if final or r.random() < 0.4 else asst
                quote = r.choice(['"It feels looser today."', '"Sore after work yesterday."', '"I did all my exercises."', '"Pain woke me up twice."', '"Better than last week."',
                                  '"Still can\'t do the stairs normally."', '"The swelling goes down overnight."', '"Weather makes it ache."', '"I tried going without the brace."'])
                n_ = [('T', p.cap('Discharge Summary' if final else r.choice(['Daily Treatment Note', 'Treatment Encounter Note', 'Daily Note']))), p.kv('Date of service', p.d(d)),
                      p.kv('Visit', f"{i + 1} of {nvis if final else 'authorized ' + str(auth_n)}"), p.kv('Time in/out', f"{p.t(tin)} / {p.t(addm(tin, r.choice([45, 50, 55, 60])))}"),
                      p.sec('Subjective'), ('P', f"{quote} Pain {r.randint(1, 6)}/10."), p.sec('Interventions')] + p.table(['CPT', 'Description', 'Min', 'Units'], rows) + [
                      p.sec('Objective'), ('P', f"{meas[0][0]}: {mval(0, frac)}. {meas[1][0]}: {mval(1, frac)}."),
                      p.sec('Assessment'), ('P', r.choice(['Tolerated session well.', 'Required cues for form.', 'Mild increase in pain post session, resolved with ice.', 'Progressed resistance today.', 'Good carryover of HEP.'])),
                      p.sec('Plan'), ('P', 'Discharge to independent home program; goals met or plateaued.' if final else r.choice(['Continue per plan of care.', 'Progress closed-chain exercise next visit.', 'Advance strengthening.', 'Reassess next week.'])),
                      ('X', f"{who}  {p.d(d)}")]
                D = self.doc(p, 'clinical', [n_], d)
                self.event(d, p, 'pt_visit', f"{disc} {'discharge visit' if final else 'treatment visit'} {i + 1}.", codes, [c for c in cpts], [D])
        return dates

    def b_chiro(self, p, start, nvis):
        s, r = self.spec, self.r
        dc = p.person('dc')
        dates = []
        d = start
        while len(dates) < nvis:
            dates.append(d)
            d = weekday_after(d, r.choice([2, 3, 4, 7]))
        regions = r.choice([['cervical', 'thoracic'], ['cervical', 'thoracic', 'lumbar'], ['thoracic', 'lumbar', 'pelvic']])
        codes = subseq(s['icd'])
        for i, d in enumerate(dates):
            if i == 0:
                b1 = [('T', p.cap('Chiropractic Initial Examination')), p.kv('Exam date', p.d(d)), p.kv('Doctor', dc), p.kv('Date of injury', p.d(self.acc)),
                      p.sec('History'), ('P', f"Patient reports {self.he} {s['mech']}. Since then compensatory {', '.join(regions)} pain and stiffness, in addition to {s['part']} complaints treated by orthopaedics."),
                      p.sec('Pain Scale')] + p.table(['Region', 'Pain', 'Frequency'], [[x, f"{r.randint(3, 8)}/10", r.choice(['constant', 'frequent', 'intermittent'])] for x in regions]) + [
                      p.sec('Examination'), ('P', f"Palpation: hypertonicity and segmental restriction {', '.join(regions)}. Kemp's {r.choice(['positive', 'negative'])}, Foraminal compression {r.choice(['negative', 'positive left'])}."),
                      p.sec('Diagnosis')] + [('L', f"{c} {DX[c]}") for c in codes] + [p.sec('Treatment Plan'), ('P', f"{r.choice([2, 3])} visits per week for 4 weeks: CMT, myofascial release, EMS, traction as indicated."), ('X', dc)]
                D = self.doc(p, 'clinical', [b1], d)
                self.event(d, p, 'pt_eval', 'Chiropractic initial examination for compensatory spinal pain.', codes, ['99203', '98941'], [D])
            else:
                cmt = '98941' if len(regions) > 2 else '98940'
                extra = r.sample(['97140', '97014', '97012', '98943'], r.randint(1, 2))
                b = [('T', p.cap('SOAP Note')), p.kv('DOS', p.d(d)), p.kv('Visit #', str(i + 1)),
                     ('P', f"S: {r.choice(['Stiff in the morning.', 'Better after last treatment.', 'Flare after long drive.', 'Slept better.', 'Same as last visit.'])} Pain {r.randint(2, 7)}/10."),
                     ('P', f"O: Subluxation/restriction noted at {r.choice(['C5-C6', 'T4-T6', 'L4-L5', 'C2-C3', 'T8-T9', 'SI R'])} and {r.choice(['C7-T1', 'L5-S1', 'T2-T3', 'SI L'])}; muscle spasm {r.choice(['moderate', 'mild', 'decreased'])}."),
                     ('P', f"A: {r.choice(['Improving.', 'Slow improvement.', 'Plateau.', 'Responding to care.'])}"),
                     ('P', f"P: CMT {cmt} {', '.join(regions)}; {', '.join(extra)}. Return {r.choice(['in 2 days', 'next week', 'Monday'])}.")] + \
                    p.table(['Code', 'Units'], [[cmt, 1]] + [[x, 1] for x in extra]) + [('X', dc)]
                D = self.doc(p, 'clinical', [b], d)
                self.event(d, p, 'pt_visit', f"Chiropractic treatment visit {i + 1}.", codes, [cmt] + extra, [D])

    def b_home(self, p, start, nvis):
        s, r = self.spec, self.r
        th = p.person('pt')
        dates = []
        d = start
        while len(dates) < nvis:
            dates.append(d)
            d = d + TD(days=r.choice([2, 3, 4]))
        codes = subseq(s['icd']) + ['Z47.89']
        for i, d in enumerate(dates):
            if i == 0:
                b1 = [('T', p.cap('Home Health Start of Care - PT Evaluation')), p.kv('SOC date', p.d(d)), p.kv('Clinician', th), p.kv('Homebound status', 'Requires walker and assist of one; leaving home is a taxing effort'),
                      p.sec('Home Environment'), ('P', f"{r.choice(['Two-story home, bedroom upstairs, 12 steps with one rail', 'Single-level home with 3 entry steps', 'Apartment on second floor, elevator available'])}. {r.choice(['Throw rugs removed', 'Shower chair in place', 'Raised toilet seat recommended'])}."),
                      p.sec('Functional Status')] + p.table(['Activity', 'Level'], [['Bed mobility', r.choice(['min assist', 'CGA'])], ['Transfers', r.choice(['min assist', 'CGA', 'SBA'])], ['Gait', f"{r.randint(15, 60)} ft with walker"], ['Stairs', r.choice(['unable', '4 steps with rail, mod assist'])]]) + \
                     [p.sec('Plan'), ('P', f"PT 2w3, 1w2. Gait training, transfer training, HEP, fall prevention."), ('X', f"{th}  {p.d(d)}")]
                b2 = [p.sec('Medication Reconciliation'), ('P', '; '.join(s['prior']['meds']) + '; post-discharge analgesics.'), p.sec('Fall Risk'), p.kv('Timed Up and Go', f"{r.randint(18, 40)} sec"),
                      p.kv('Risk', 'High'), p.sec('Vital Signs'), ('P', f"BP {self.vitals()['bp']}, HR {r.randint(64, 98)}, SpO2 {r.randint(94, 99)}%."), ('P', f"Next visit {p.d(dates[1]) if len(dates) > 1 else 'TBD'}.")]
                D = self.doc(p, 'clinical', [b1, b2], d)
                self.event(d, p, 'pt_eval', 'Home health physical therapy start-of-care evaluation.', codes, ['G0151'], [D])
            else:
                tin = f"{r.randint(8, 16):02d}:{r.choice(['00', '10', '30', '45'])}"
                b = [('T', p.cap('Home Visit Note - Physical Therapy')), p.kv('Visit date', p.d(d)), p.kv('Visit', f"{i + 1}"), p.kv('Time in', p.t(tin)),
                     p.kv('Time out', p.t(addm(tin, r.choice([45, 50, 60])))),
                     ('P', f"Vitals: BP {self.vitals()['bp']}, HR {r.randint(62, 98)}. Pain {r.randint(2, 7)}/10."),
                     ('P', f"Gait: {r.randint(40, 300)} ft with {r.choice(['walker', 'walker', 'cane'])}, {r.choice(['CGA', 'SBA', 'supervision', 'mod I'])}. Stairs: {r.choice(['not attempted', '4 steps', '8 steps', 'full flight'])}."),
                     ('P', f"Treatment: {r.choice(['gait training, transfer training, LE strengthening', 'HEP review, balance activities, stair training', 'therapeutic exercise, safety education'])}."),
                     ('P', f"Response: {r.choice(['fatigued but tolerated', 'tolerated well', 'mild pain increase, resolved with rest'])}."), ('X', f"{th}  {p.d(d)}")]
                D = self.doc(p, 'clinical', [b], d)
                self.event(d, p, 'pt_visit', f"Home health PT visit {i + 1}.", codes, ['G0151'], [D])

    def b_facility(self, p):
        """Nursing facility: incident report and post-fall nursing notes (72 h)."""
        s, r, pt, d = self.spec, self.r, self.pt, self.acc
        rn = p.person('rn')
        b1 = [('T', p.cap('Resident Incident Report')), p.kv('Date of occurrence', p.d(d)), p.kv('Time found', p.t(self.acc_time)), p.kv('Location', 'Room 214, beside bed'),
              p.kv('Witnessed', 'No'), p.kv('Reported by', rn), p.sec('Description'),
              ('P', f"Resident found on floor on left side by CNA during rounds. Resident states she was going to the bathroom. Bed alarm noted to be OFF at time found. Call light not within reach. Non-skid socks not on."),
              p.sec('Immediate Actions'), ('P', 'Assessed for injury before moving. Right wrist deformity and occipital laceration noted. Pressure applied. 911 called. Family and physician notified.'),
              p.kv('Physician notified', p.dt(d, addm(self.acc_time, 14))), p.kv('Family notified', p.dt(d, addm(self.acc_time, 31))),
              p.sec('Root Cause (preliminary)'), ('P', 'Bed alarm not reactivated after evening care. Toileting schedule not followed on the 1900 round.'), ('X', f"{rn}; reviewed by Director of Nursing")]
        D0 = self.doc(p, 'clinical', [b1], d)
        self.event(d, p, 'office_visit', 'Facility incident report: unwitnessed fall in room, bed alarm off.', s['icd'] + s['ext'], [], [D0], bill=False)
        for k in range(1, 4):
            dd = d + TD(days=k)
            rows = [[p.t(t), self.vitals()['bp'], r.randint(60, 96), r.choice(['A&O x1', 'A&O x1-2', 'baseline']), r.choice(['equal', 'equal, reactive']), r.choice(['pink, warm', 'pink, mild swelling']), r.randint(0, 6)]
                    for t in ['06:00', '14:00', '22:00']]
            b = [('T', p.cap('Post-Fall Monitoring - 72 Hour')), p.kv('Date', p.d(dd)), p.kv('Day', f"{k} of 3"), p.kv('Nurse', p.person('lpn', k))] + \
                p.table(['Time', 'BP', 'HR', 'Mental status', 'Pupils', 'R hand circ.', 'Pain'], rows) + [
                ('P', f"Splint intact. Staples clean. {r.choice(['Ate 75% of meals.', 'Ate 50% of breakfast.', 'Refused lunch, ate supper.'])} {r.choice(['No further falls.', 'Bed alarm verified ON each shift.', 'Low bed and floor mat in place.'])}"),
                ('X', p.person('lpn', k))]
            D = self.doc(p, 'clinical', [b], dd)
            self.event(dd, p, 'office_visit', f"Post-fall nursing monitoring day {k}.", subseq(s['icd']), ['99309'] if k == 1 else [], [D], bill=(k == 1))

    def b_pain(self, p, d0):
        s, r = self.spec, self.r
        pm = s['pain']
        md = p.person('md')
        codes = pm['codes']
        def intake(d, pain_now, worst):
            return [('T', p.cap('Pain Questionnaire - Patient Completed')), p.kv('Date completed', p.d(d)),
                    ('L', f"Where is your pain?  [X] {s['part']}  [ ] neck  [{'X' if s['key'] in ('stairwell_lumbar',) else ' '}] low back  [ ] other"),
                    ('L', f"Pain right now (0-10): {pain_now}      Worst in past week: {worst}      Best: {max(0, pain_now - r.randint(1, 3))}"),
                    ('L', f"Pain is:  [{'X' if r.random() < .6 else ' '}] aching  [{'X' if r.random() < .4 else ' '}] burning  [{'X' if r.random() < .5 else ' '}] sharp  [{'X' if r.random() < .3 else ' '}] throbbing"),
                    ('L', f"Sleep interrupted by pain: [{'X' if pain_now > 4 else ' '}] yes  [{' ' if pain_now > 4 else 'X'}] no"),
                    ('L', f"Current medications for pain: {r.choice(['ibuprofen', 'acetaminophen and ibuprofen', 'tramadol 50 mg at night', 'none'])}"),
                    ('L', f"Work status: [{'X' if r.random() < .5 else ' '}] working  [ ] modified duty  [ ] off work"),
                    ('L', 'Interference with activities (0-10): ' + str(r.randint(3, 8))), ('L', 'Mood (PHQ-2): ' + str(r.randint(0, 3))),
                    ('L', 'Patient signature: (signed)     Staff initials: ' + r.choice(['TB', 'LG', 'MR']))]
        dI = d0
        b_in = intake(dI, r.randint(5, 8), r.randint(8, 10))
        c1 = [('T', p.cap('Interventional Pain Consultation')), p.kv('Date', p.d(dI)), p.kv('Physician', md), p.sec('History'),
              ('P', f"Referred for persistent {s['part']} pain after {s['injury']} and {s['proc_short']}. Pain has persisted despite therapy."),
              p.sec('Examination'), ('P', f"{s['part'].capitalize()}: tenderness {r.choice(['diffuse', 'focal'])}, motion painful at end range. Neurologic exam nonfocal unless noted.")]
        c2 = [p.sec('Assessment')] + [('L', f"{c}: {DX[c]}") for c in codes] + [p.sec('Plan'), ('P', f"Recommend {pm['name'].lower()}. Risks reviewed. Continue therapy. Avoid opioids."), ('X', md)]
        DI = self.doc(p, 'clinical', [b_in], dI, label='intake')
        DC = self.doc(p, 'clinical', [c1, c2], dI)
        self.event(dI, p, 'office_visit', 'Pain management consultation with completed pain questionnaire.', codes, ['99204'], [DC, DI])
        dP = weekday_after(dI, r.randint(10, 20))
        v = self.vitals()
        proc = [('T', p.cap('Procedure Note')), p.kv('Date', p.d(dP)), p.kv('Procedure', pm['name']), p.kv('Physician', md), p.kv('Pre-procedure pain', f"{r.randint(5, 8)}/10"),
                p.sec('Description'), ('P', f"Consent obtained. Time-out performed. Patient positioned and prepped with chlorhexidine. Under {'fluoroscopic' if '77002' in pm['cpt'] or '64483' in pm['cpt'] else 'landmark'} guidance the needle was advanced to the target; "
                                           f"{'contrast confirmed spread without vascular uptake; ' if '77002' in pm['cpt'] or '64483' in pm['cpt'] else ''}injected {pm['drug']}."),
                p.kv('Vitals', f"BP {v['bp']}, HR {v['hr']}"), p.kv('Post-procedure pain', f"{r.randint(0, 3)}/10"), p.kv('Complications', 'None'), ('X', md)]
        DP = self.doc(p, 'clinical', [proc], dP)
        self.event(dP, p, 'injection', f"{pm['name']}.", codes, pm['cpt'], [DP])
        dF = weekday_after(dP, r.randint(24, 35))
        b_in2 = intake(dF, r.randint(2, 5), r.randint(5, 8))
        f1 = [('T', p.cap('Follow-up Visit')), p.kv('Date', p.d(dF)), p.kv('Physician', md), ('P', f"Reports {r.randint(30, 70)} percent relief for {r.randint(2, 5)} weeks after injection. Pain now {r.randint(2, 5)}/10."),
              p.sec('Plan'), ('P', r.choice(['Repeat injection if pain returns to baseline.', 'Continue home exercise; follow up in 3 months.', 'Consider repeat procedure in 8-12 weeks.'])), ('X', md)]
        DI2 = self.doc(p, 'clinical', [b_in2], dF, label='intake')
        DF = self.doc(p, 'clinical', [f1], dF)
        self.event(dF, p, 'office_visit', 'Pain management follow-up after injection with repeat pain questionnaire.', codes, ['99213'], [DF, DI2])

    # ---------- billing
    def b_billing(self, p):
        s, r, pt = self.spec, self.r, self.pt
        lines = []
        for d, procs, codes, kind in sorted(p.services, key=lambda x: x[0]):
            for c in procs:
                if c not in CPT:
                    continue
                units = 1
                if c == 'A0425':
                    units = r.randint(4, 15)
                if c in ('97110', '97140') and r.random() < 0.3:
                    units = 2
                lines.append((d, c, CPT[c][0], units, round(CPT[c][1] * p.fee * units, 2)))
        if p.ptype == 'hospital' and self.admit_days:
            for d in self.admit_days[:-1]:
                lines.append((d, 'RC0120', 'Room and board, semi-private', 1, round(2850 * p.fee, 2)))
                lines.append((d, 'RC0250', 'Pharmacy', r.randint(4, 15), round(r.uniform(180, 900) * p.fee, 2)))
            lines.append((self.surg_date, 'RC0360', 'Operating room services', 1, round(9800 * p.fee, 2)))
            lines.append((self.surg_date, 'RC0278', 'Medical/surgical supplies - implants', 1, round(r.uniform(2400, 7800), 2)))
            lines.sort(key=lambda x: x[0])
        if not lines:
            return
        per = r.choice([14, 16, 18])
        chunks = [lines[i:i + per] for i in range(0, len(lines), per)]
        stmt_date = self.prod1_date - TD(days=r.randint(3, 12))
        bodies = []
        running = 0.0
        for ci, ch in enumerate(chunks):
            rows = []
            for d, c, desc, u, amt in ch:
                running += amt
                rows.append([p.d(d), c, desc[:36], u, f"{amt:,.2f}"])
            b = [('T', p.cap('Itemized Statement of Charges')), p.kv('Statement date', p.d(stmt_date)), p.kv('Account', p.acct), p.kv('Guarantor', f"{pt['first']} {pt['last']}"),
                 p.kv('Tax ID', p.tin)] + p.table(['DOS', 'Code', 'Description', 'Units', 'Charge'], rows) + [p.kv('Charges this page', f"{sum(x[4] for x in ch):,.2f}"),
                 p.kv('Running total', f"{running:,.2f}")]
            if ci == len(chunks) - 1:
                paid = round(running * r.uniform(0.0, 0.45), 2)
                b += [p.kv('Total charges', f"{running:,.2f}"), p.kv('Payments/adjustments', f"-{paid:,.2f}"), p.kv('Balance due', f"{running - paid:,.2f}"),
                      ('P', r.choice(['Balance under lien pending settlement.', 'Letter of protection on file.', 'Billed to carrier; patient responsibility pending.']))]
            bodies.append(b)
        self.doc(p, 'billing', bodies, stmt_date, label='statement')
        # claim forms
        if p.ptype == 'hospital':
            self._ub(p)
        groups = []
        svc = sorted(p.services, key=lambda x: x[0])
        cur = []
        for x in svc:
            if not [c for c in x[1] if c in CPT]:
                continue
            cur.append(x)
            if len(cur) >= r.choice([1, 2, 3, 4]):
                groups.append(cur); cur = []
        if cur:
            groups.append(cur)
        if p.ptype == 'hospital':
            groups = groups[:2]
        made_replacement = False
        for g in groups[:r.choice([3, 4, 5])]:
            self._claim(p, g, None)
            if not made_replacement and p.ptype in ('therapy', 'chiro', 'ortho', 'pain', 'spec') and r.random() < 0.7:
                self._claim(p, g[:1], 'replacement')
                made_replacement = True

    def _claim(self, p, group, variant):
        s, r, pt = self.spec, self.r, self.pt
        dx = []
        for _, _, codes, _ in group:
            for c in codes:
                if c not in dx and c[0] not in 'VWXY':
                    dx.append(c)
        dx = dx[:6]
        rows = []
        for d, procs, codes, kind in group:
            pr = [c for c in procs if c in CPT]
            if variant == 'replacement':
                if any(c.startswith('97') or c.startswith('98') for c in pr):
                    pr = pr + (['97140'] if '97140' not in pr else ['97112'])
                else:
                    swap = {'99204': '99203', '99203': '99204', '99213': '99214', '99214': '99213', '99024': '99213'}
                    pr = [swap.get(pr[0], pr[0])] + pr[1:]
            for c in pr:
                u = 2 if variant == 'replacement' and c == pr[0] and c.startswith('97') else 1
                rows.append([d.strftime('%m %d %y'), d.strftime('%m %d %y'), '11' if p.ptype != 'hospital' else '23', c, 'A', f"{CPT[c][1] * p.fee * u:,.2f}", u, p.npi])
        letters = 'ABCDEF'
        b = [('T', 'HEALTH INSURANCE CLAIM FORM' + (' - REPLACEMENT OF PRIOR CLAIM' if variant else '')), ('L', 'APPROVED OMB-STYLE LAYOUT 02/12 (facsimile)'),
             p.kv('1a INSURED ID', self.claimno if s['insurer'] == 'wc' else pt['member']), p.kv('2 PATIENT NAME', f"{pt['last'].upper()}, {pt['first'].upper()} {pt['mi']}"),
             p.kv('3 BIRTH DATE', pt['dob'].strftime('%m %d %Y') + f"   SEX {pt['sex']}"), p.kv('10 CONDITION RELATED TO', 'EMPLOYMENT: YES' if s['insurer'] == 'wc' else ('AUTO ACCIDENT: YES' if s['insurer'] == 'auto' else 'OTHER ACCIDENT: YES')),
             p.kv('11c INSURANCE PLAN', self.ins.name), p.kv('14 DATE OF CURRENT ILLNESS', self.acc.strftime('%m %d %Y') + '  QUAL 431'),
             ('L', '21 DIAGNOSIS: ' + '   '.join(f"{letters[i]}. {c.replace('.', '')}" for i, c in enumerate(dx)))]
        if variant:
            b.append(p.kv('22 RESUBMISSION CODE', f"7   ORIGINAL REF NO. {r.randint(10 ** 11, 10 ** 12 - 1)}"))
        b += [('L', '24 SERVICE LINES')] + p.table(['From', 'To', 'POS', 'CPT/HCPCS', 'Ptr', 'Charges', 'Units', 'Rendering NPI'], rows) + [
             p.kv('25 FEDERAL TAX ID', p.tin), p.kv('26 PATIENT ACCOUNT NO', p.acct), p.kv('28 TOTAL CHARGE', f"{sum(float(x[5].replace(',', '')) for x in rows):,.2f}"),
             p.kv('32 SERVICE FACILITY', p.name), p.kv('33 BILLING PROVIDER', f"{p.name}  {p.phone}  NPI {p.npi}"), p.kv('31 SIGNATURE', f"{p.person('md') if p.ptype not in ('therapy', 'chiro', 'home') else 'Billing office'}   DATE {group[-1][0].strftime('%m/%d/%y')}")]
        self.doc(p, 'billing', [b], group[0][0], hdr='none', label='claim')

    def _ub(self, p):
        s, r, pt = self.spec, self.r, self.pt
        rows = [['0450', 'Emergency room', '99285', '1', f"{2200 * p.fee:,.2f}"], ['0320', 'Radiology - diagnostic', '', str(len(s['er_imaging'])), f"{r.uniform(900, 3400):,.2f}"],
                ['0300', 'Laboratory', '', '2', f"{r.uniform(150, 420):,.2f}"]]
        if self.admit_days:
            rows += [['0120', 'Room & board semi', '', str(len(self.admit_days) - 1), f"{2850 * p.fee * (len(self.admit_days) - 1):,.2f}"], ['0360', 'Operating room', s['surg']['cpt'][0], '1', f"{9800 * p.fee:,.2f}"],
                     ['0420', 'Physical therapy', '97162', '1', f"{r.uniform(240, 600):,.2f}"]]
        b = [('T', 'UB-04 FACILITY CLAIM SUMMARY'), p.kv('1 PROVIDER', p.name), p.kv('3a PAT CNTL #', p.acct), p.kv('4 TYPE OF BILL', '0111' if self.admit_days else '0131'), p.kv('5 FED TAX NO', p.tin),
             p.kv('6 STATEMENT PERIOD', f"{self.acc.strftime('%m%d%y')} THROUGH {(self.admit_days[-1] if self.admit_days else self.acc).strftime('%m%d%y')}"),
             p.kv('8 PATIENT NAME', f"{pt['last'].upper()}, {pt['first'].upper()}"), p.kv('10 BIRTHDATE', pt['dob'].strftime('%m%d%Y')), p.kv('12 ADMISSION DATE', self.acc.strftime('%m%d%y'))] + \
            p.table(['42 REV', '43 DESCRIPTION', '44 HCPCS', '46 UNITS', '47 TOTAL CHARGES'], rows) + [
            p.kv('50 PAYER', self.ins.name), p.kv('67 PRIN DX', s['icd'][0].replace('.', '')), p.kv('72 ECI', ' '.join(c.replace('.', '') for c in s['ext'][:2])), p.kv('76 ATTENDING', p.person('md', 1))]
        self.doc(p, 'billing', [b], self.acc, hdr='none', label='ub04')

    # ---------- admin
    def b_request(self, p, date, reqno):
        law, pt = self.law, self.pt
        para = self.law.person('para')
        atty = self.law.person('atty')
        b = [('L', law.d(date)), ('B', ''), ('L', f"VIA FACSIMILE {p.fax} AND FIRST-CLASS MAIL"), ('B', ''), ('L', p.name), ('L', 'Attn: Health Information Management / Release of Information'), ('L', p.addr), ('B', ''),
             ('L', f"RE:  Our Client: {pt['first']} {pt['last']}"), ('L', f"       Date of Birth: {law.d(pt['dob'])}"), ('L', f"       Date of Incident: {law.d(self.acc)}"),
             ('L', f"       Our File No.: {self.fileno}"), ('L', f"       Request No.: {reqno}"), ('B', ''), ('L', 'Dear Records Custodian:'),
             ('P', f"This firm represents the above-named client for injuries sustained on the date of incident. Please provide complete certified copies of all medical records for dates of service from {law.d(self.acc - TD(days=365 * 3))} to present, "
                   'including office and progress notes, nursing notes, flowsheets, medication administration records, operative and procedure reports, diagnostic test results, imaging reports, therapy notes, correspondence and outside records, '
                   'together with an itemized statement of all charges, payments and adjustments.'),
             ('P', 'A HIPAA-compliant authorization signed by our client is enclosed. Please include a signed certification of records custodian. If there is a fee for copying, kindly send an invoice in advance.'),
             ('P', f"Please direct any questions to the undersigned at {law.phone}. Thank you for your prompt attention to this request."), ('B', ''), ('L', 'Very truly yours,'), ('B', ''),
             ('L', para), ('L', f"Paralegal to {atty}"), ('B', ''), ('L', 'Enclosure: Authorization')]
        return self.doc(law, 'admin', [b], date, hdr='letter', label=f"request{reqno}")

    def b_authorization(self):
        law, pt, r = self.law, self.pt, self.r
        d = self.acc + TD(days=r.randint(20, 60))
        b = [('T', 'AUTHORIZATION FOR RELEASE OF PROTECTED HEALTH INFORMATION'), ('L', '(45 CFR 164.508 compliant form)'),
             ('K', f"Patient name: {pt['first']} {pt['mi']}. {pt['last']}"), ('K', f"Date of birth: {pt['dob'].strftime('%m/%d/%Y')}"), ('K', f"Address: {pt['addr']}"),
             ('P', 'I authorize any physician, hospital, clinic, therapist, ambulance service, pharmacy or other health care provider that has treated me to release the information described below to:'),
             ('L', f"{law.name}, {law.addr}"), ('L', 'Information to be released:  [X] complete medical record  [X] billing records  [X] imaging reports  [ ] psychotherapy notes'),
             ('L', '[X] I specifically authorize release of records relating to alcohol/drug treatment, HIV and mental health if present in the general record.'),
             ('P', 'Purpose: legal representation. This authorization expires two years from the date signed. I may revoke it in writing at any time except to the extent action has been taken in reliance on it. '
                   'Treatment, payment and enrollment may not be conditioned on signing. Information disclosed may be redisclosed by the recipient and no longer protected by federal privacy rules.'),
             ('L', 'A photocopy of this authorization shall be as valid as the original.'), ('B', ''), ('L', f"Signature of patient: (signed) {pt['first']} {pt['last']}"), ('L', f"Date: {d.strftime('%m/%d/%Y')}"),
             ('L', 'Witness: ' + law.person('para'))]
        return self.doc(law, 'admin', [b], d, hdr='none', label='authorization')

    def b_cert(self, p, date, npages, prod):
        r = self.r
        cust = p.person('clerk', 7 + prod)
        b = [('T', r.choice(['CERTIFICATION OF CUSTODIAN OF RECORDS', 'AFFIDAVIT OF RECORDS CUSTODIAN', 'BUSINESS RECORDS CERTIFICATION'])), ('B', ''),
             ('P', f"I, {cust}, certify that I am the duly authorized custodian of the medical and billing records of {p.name}, and have authority to certify those records."),
             ('P', f"The attached {npages} pages are true and complete copies of the records of {self.pt['first']} {self.pt['last']} (date of birth {p.d(self.pt['dob'])}) for the dates of service requested, "
                   'made at or near the time of the acts and events recorded by, or from information transmitted by, persons with knowledge, and kept in the course of regularly conducted activity.'),
             ('P', 'A thorough search was made; records not attached do not exist in our files.' if prod == 1 else 'This production supplements and replaces our prior production in response to your follow-up request.'),
             ('B', ''), ('L', f"Date: {p.d(date)}"), ('L', f"Signature: (signed) {cust}"), ('L', 'Title: ' + r.choice(['Release of Information Specialist', 'HIM Supervisor', 'Office Manager', 'Billing and Records Coordinator'])),
             ('L', f"Request reference: {self.fileno}-{r.randint(100, 999)}")]
        return self.doc(p, 'admin', [b], date, hdr='letter', label=f"cert{prod}")

    def b_faxcover(self, p, date, npages):
        r = self.r
        b = [('T', r.choice(['FAX TRANSMITTAL', 'FACSIMILE COVER SHEET', 'Fax'])), p.kv('Date', p.d(date)), p.kv('To', self.law.name), p.kv('Fax', self.law.fax), p.kv('From', p.person('clerk', 7)),
             p.kv('Pages (incl. cover)', str(npages + 1)), p.kv('Re', f"Records - {self.pt['last']}, {self.pt['first']}"),
             ('P', r.choice(['Records sent in response to your second request. Please call if any pages are illegible.', 'Per your follow-up request, enclosed are the records. Original production was mailed earlier.',
                             'Re-sending complete chart as requested.'])),
             ('P', 'CONFIDENTIALITY NOTICE: This facsimile contains protected health information. If you received it in error, notify the sender and destroy all copies.')]
        return self.doc(p, 'admin', [b], date, hdr='letter', label='faxcover')

    # ================================================================= assemble case
    def build(self):
        s, r = self.spec, self.r
        town = self.town
        sp_names = {'ortho': (f"{r.choice([town, r.choice(LASTS)])} Orthopaedic & Sports Clinic", 'Orthopaedic Surgery'),
                    'hand': (f"{town} Hand and Upper Extremity Center", 'Hand Surgery'),
                    'omfs': (f"{town} Oral & Facial Surgery Group", 'Oral and Maxillofacial Surgery'),
                    'ophtho': (f"{r.choice(TOWNS)} Eye Associates", 'Ophthalmology'),
                    'plastics': (f"{r.choice(LASTS)} Plastic & Reconstructive Surgery", 'Plastic Surgery'),
                    'wound': (f"{town} Wound Care & Hyperbaric Clinic", 'Wound Care'),
                    'spine': (f"{r.choice(TOWNS)} Spine Institute", 'Spine Surgery'),
                    'occmed': (f"{self.county} Occupational Health Partners", 'Occupational Medicine')}
        pcp_name = {'nursing_home_fall': f"{r.choice(LASTS)} Geriatric Medical Group"}.get(s['key'], r.choice([f"{town} Family Health", f"{r.choice(LASTS)} & {r.choice(LASTS)} Family Medicine", f"{r.choice(TOWNS)} Primary Care Associates"]))
        pcp = self.prov('pcp', pcp_name, 'Family Medicine' if s['key'] != 'nursing_home_fall' else 'Geriatrics')
        hospital = self.prov('hospital', r.choice([f"{town} Regional Medical Center", f"{r.choice(SAINTS)} Memorial Hospital", f"{r.choice(TOWNS)} Valley General Hospital"]))
        if s['urgent']:
            hospital.ptype = 'urgent'
            hospital.name = f"{r.choice(['QuickMend', 'FirstStop', 'Clearwater'])} Urgent Care - {town}"
        ems = self.prov('ems', r.choice([f"{self.county} County Fire-Rescue", f"{town} Volunteer Ambulance Corps", f"Tri-{self.county} EMS Authority"])) if s['ems'] else None
        facility = self.prov('facility', f"{town} Pines Care and Rehabilitation Center", 'Skilled Nursing Facility') if s['extra'] == 'facility' else None
        rad = self.prov('radiology', r.choice([f"{town} Imaging Partners", f"{r.choice(LASTS)} Diagnostic Radiology", f"{self.county} Radiology Associates"]), 'Diagnostic Radiology')
        specs = []
        for k in s['spec']:
            nm, sp = sp_names[k]
            pp = self.prov('spec' if k not in ('ortho',) else 'ortho', nm, sp)
            pp.kind = k
            specs.append(pp)
        self.ortho = specs[0]
        self.surgeon_prov = specs[0]
        asc = self.prov('asc', f"{town} Ambulatory Surgery Center") if s['surg']['where'] == 'asc' else None
        ther = self.prov('therapy', r.choice([f"{town} Physical Therapy & Rehab", f"MotionWorks Rehabilitation of {town}", f"{r.choice(LASTS)} Therapy Group"]) if s['therapy'] == 'PT'
                         else r.choice([f"{town} Hand Therapy Specialists", f"Reach Occupational Therapy - {town}"]), 'Physical Therapy' if s['therapy'] == 'PT' else 'Occupational / Hand Therapy')
        extra = None
        if s['extra'] == 'home_health':
            extra = self.prov('home', f"{self.county} Home Health Services")
        elif s['extra'] == 'chiro':
            extra = self.prov('chiro', f"{r.choice(LASTS)} Chiropractic Center", 'Chiropractic')
        pain = self.prov('pain', f"{r.choice([town, r.choice(TOWNS)])} Interventional Pain Specialists", 'Pain Medicine') if s['pain'] else None
        self.after_er = True
        self.admit_days = []

        # --- clinical timeline
        self.b_prior(pcp)
        arrive = addm(self.acc_time, r.randint(35, 70))
        if facility:
            self.b_facility(facility)
        if ems:
            arrive = self.b_ems(ems, hospital)
        er = self.b_er(hospital, arrive, urgent=s['urgent'])
        if not s['urgent']:
            self.b_lab(hospital, arrive)
        imaging_docs = []
        for k in s['er_imaging']:
            imaging_docs += self.b_imaging(rad, k, self.acc, addm(arrive, r.randint(30, 120)), hospital.name, s['icd'], corrected=(k == s['corrected']))
        sg = s['surg']
        if s['admit']:
            los = r.randint(*s['admit'])
            sday = sg['day']
            if s['out_imaging'] and s['out_imaging'][0][1] <= 2:   # inpatient MRI
                k, off = s['out_imaging'][0]
                imaging_docs += self.b_imaging(rad, k, self.acc + TD(days=off), '10:40', hospital.name, s['icd'], corrected=(k == s['corrected']))
            self.surg_date = self.acc + TD(days=sday)
            self.admit_days = self.b_admission(hospital, max(los, sday + 2), sday, None)
            self.b_surgery(hospital, self.surg_date)
            dc = self.discharge_date
            o_dates = [('post1', weekday_after(self.surg_date, r.randint(12, 16))), ('post2', weekday_after(self.surg_date, r.randint(40, 48))),
                       ('post3', weekday_after(self.surg_date, r.randint(84, 100))), ('final', weekday_after(self.surg_date, r.randint(150, 175)))]
        else:
            dc = self.acc
            self.surg_date = weekday_after(self.acc, sg['day'])
            new_d = weekday_after(self.acc, r.randint(1, 3) if sg['day'] < 8 else r.randint(3, 6))
            o_dates = [('new', new_d)]
            for k, off in s['out_imaging']:
                imaging_docs += self.b_imaging(rad, k, weekday_after(self.acc, off), f"{r.randint(8, 17):02d}:{r.choice(['00', '30', '15'])}", rad.name + ' - outpatient center',
                                                [c for c in s['icd'] if c[0] not in 'VWXY'], corrected=(k == s['corrected']))
            if sg['day'] - (new_d - self.acc).days > 12:
                o_dates.append(('preop', weekday_after(self.surg_date, -r.randint(4, 8))))
            self.surg_date = max(self.surg_date, new_d + TD(days=1))
            o_dates += [('post1', weekday_after(self.surg_date, r.randint(10, 14))), ('post2', weekday_after(self.surg_date, r.randint(40, 48))),
                        ('post3', weekday_after(self.surg_date, r.randint(84, 100))), ('final', weekday_after(self.surg_date, r.randint(150, 175)))]
        # surgeon practice visits
        ortho = specs[0]
        o_docs = {}
        for i, (stage, d) in enumerate(o_dates):
            if stage == 'post3' and r.random() < 0.35:
                continue
            o_docs[stage] = self.b_spec(ortho, ortho.kind, d, stage, (i + 1, len(o_dates)), xray=('73610' if s['part'] == 'right ankle' else None))
            if stage == 'new' and asc:
                self.b_surgery(asc, self.surg_date, preop_page=True)
        if not s['admit'] and not asc:
            self.b_surgery(hospital, self.surg_date)
        first_o = o_docs.get('new') or o_docs.get('post1')
        self.embed(ortho, first_o, [er] + imaging_docs[:2], first_o['date'])
        if 'post1' in o_docs and s['admit']:
            self.embed(ortho, o_docs['post1'], [self.opnote], o_docs['post1']['date'])
        # second specialists
        for sp in specs[1:]:
            k = sp.kind
            if k == 'ophtho':
                for st_, off in [('new', 1 if not s['admit'] else 4), ('fu', 45)]:
                    self.b_spec(sp, k, weekday_after(self.acc, off), st_, (1, 2))
            elif k == 'occmed':
                for i_, off in enumerate([2, 16, 37, 65, 98]):
                    self.b_spec(sp, k, weekday_after(self.acc, off), 'new' if i_ == 0 else 'fu', (i_ + 1, 5))
            elif k == 'wound':
                dc_off = (dc - self.acc).days + 1
                for i_, off in enumerate([dc_off, 7, 14, 21, 28]):
                    dd = weekday_after(self.acc, max(off, dc_off))
                    self.b_spec(sp, k, dd, 'new' if i_ == 0 else ('final' if i_ == 4 else 'fu'), (i_ + 1, 5))
        # therapy
        th_start = weekday_after(self.surg_date, r.randint(10, 21) if s['part'] not in ('right hip',) else r.randint(30, 40))
        nvis = r.randint(11, 18)
        self.b_therapy(ther, th_start, nvis, s['therapy'])
        if 'post1' in o_docs:
            self.embed(ther, self.therapy_eval, [o_docs['post1']], th_start)
        if extra and extra.ptype == 'home':
            self.b_home(extra, dc + TD(days=r.randint(2, 4)), r.randint(6, 9))
            if self.admit_days:
                self.embed(extra, extra.docs[0], [self.discharge], dc + TD(days=2))
        elif extra and extra.ptype == 'chiro':
            self.b_chiro(extra, weekday_after(self.acc, r.randint(30, 60)), r.randint(7, 11))
        if pain:
            pd0 = weekday_after(self.surg_date, r.randint(85, 110))
            self.b_pain(pain, pd0)
            mri = [D for D in imaging_docs if D['label'] != 'corrected'][-1:]
            self.embed(pain, pain.docs[1], mri + [self.opnote], pd0)

        # production timeline
        last_clin = max(e['date'] for e in self.events)
        self.prod1_date = last_clin + TD(days=r.randint(20, 60))
        for p in self.provs:
            self.b_billing(p)
        self.clin_provs = sorted([p for p in self.provs if p.docs], key=lambda p: p.first)
        self.auth = self.b_authorization()

    # ================================================================= productions
    def emit(self, cid, producer, prod, mech, items=None, st=None, crop=None, inh=None, own=None):
        c = self.content[cid]
        seen = cid in self.seen
        self.seen.add(cid)
        rec = dict(cid=cid, items=items if items is not None else c['items'], st=st or c['st'], crop=crop, inh=list(inh or []), own=list(own or []),
                   producer=producer, prod=prod, mech='original' if (mech == 'provider_production' or (not seen and mech == 'authorization_attachment')) else mech, kind=c['kind'])
        self.out.append(rec)
        return rec

    def fax_fn(self, sender, recip_fax, recip_name, d, t, n):
        m = self.m
        job = m.randint(1000, 99999)
        style = m.randrange(4)
        sfax = sender.fax.replace('(', '').replace(') ', '').replace('-', '')
        rfax = recip_fax.replace('(', '').replace(') ', '').replace('-', '')
        h, mi = map(int, t.split(':'))
        ap = f"{(h % 12) or 12}:{mi:02d} {'AM' if h < 12 else 'PM'}"
        nm = sender.name.upper()[:18]
        def f(i):
            if style == 0:
                return ('fax_top', f"{d.strftime('%b').upper()}-{d.day:02d}-{d.year} {t}  FROM:{nm}  {sfax}   TO:{rfax}   P.{i:03d}/{n:03d}")
            if style == 1:
                return ('fax_top', f"{d.strftime('%m/%d/%Y')} {ap}  FAX  Job {job}  Page {i} of {n}  {sender.name[:28]}")
            if style == 2:
                return ('fax_bot', f"Received Fax : {d.strftime('%b')} {d.day} {d.year} {ap}   Fax Station : {recip_name.upper()[:20]}   p. {i}")
            return ('fax_top', f"{d.isoformat()} {t}:{m.randint(10, 59)} {sfax} >> {rfax}  [{job}]  {i}/{n}")
        return f

    def ehr_fn(self, p, d):
        m = self.m
        user = m.choice(['JTORRES', 'mreyes2', 'KPATEL', 'hims.rel01', 'S.OKAFOR', 'roi_batch', 'LNGUYEN', 'dfranks'])
        t = f"{m.randint(7, 17):02d}:{m.randint(0, 59):02d}"
        ws = f"{m.choice(['HIM', 'ROI', 'FD', 'BIZ'])}-{m.randint(1, 40):02d}"
        style = m.randrange(4)
        def f(i):
            if style == 0:
                return ('foot', f"Printed by: {user} on {d.strftime('%m/%d/%Y')} {t}   Workstation {ws}   Page {i}")
            if style == 1:
                return ('foot', f"PRINTED {d.strftime('%d%b%Y').upper()} {t} BY {user.upper()} -- CONFIDENTIAL PATIENT INFORMATION -- {i}")
            if style == 2:
                return ('foot', f"{p.name} | printed {d.isoformat()} {t} | user {user} | p {i}")
            return ('foot', f"Print date: {d.strftime('%B')} {d.day}, {d.year} {t}  Printed for release of information  ({i})")
        return f

    def stamp(self, words, who, d, x=None, y=None):
        m = self.m
        col = m.choice([(0.75, 0.1, 0.1), (0.1, 0.25, 0.65), (0.2, 0.45, 0.2)])
        lines = [words, f"{d.strftime('%b').upper()} {d.day:02d} {d.year}" if m.random() < 0.5 else d.strftime('%m.%d.%y'), who[:30]]
        x = x if x is not None else m.uniform(330, 440)
        y = y if y is not None else m.uniform(60, 140)
        return ('stamp', lines, x, y, m.uniform(-9, 9), col)

    def productions(self):
        m, r = self.m, self.r
        U = len(self.content)
        # ---- production 1: plaintiff counsel's collection, provider by provider
        P1 = self.prod1_date
        req1, cert1 = {}, {}
        for p in self.clin_provs:
            req1[p.name] = self.b_request(p, P1 - TD(days=m.randint(30, 45)), 1)
        for p in self.clin_provs:
            seq = [(req1[p.name]['cids'][0], 'provider_production'), (self.auth['cids'][0], 'authorization_attachment')]
            body = []
            emb = self.embeds.get(p.name, [])
            for D in sorted(p.docs, key=lambda D: (D['kind'] != 'clinical', D['date'])):
                for c in D['cids']:
                    body.append((c, 'provider_production'))
                for after, cids, src, d in emb:
                    if after == D['id']:
                        for c in cids:
                            body.append((c, 'copy_in_other_chart', src, d))
            cert = self.b_cert(p, P1 + TD(days=m.randint(0, 12)), len(body), 1)
            cert1[p.name] = cert
            seq.append((cert['cids'][0], 'provider_production'))
            seq += body
            n = len(seq)
            faxf = self.fax_fn(p, self.law.fax, self.law.name, P1 + TD(days=m.randint(3, 15)), f"{m.randint(8, 18):02d}:{m.randint(0, 59):02d}", n) if p.faxes else None
            ehrf = self.ehr_fn(p, P1 + TD(days=m.randint(0, 10))) if p.ehr else None
            emb_fax = {}
            for i, it in enumerate(seq):
                own = []
                inh = []
                if faxf:
                    own.append(faxf(i + 1))
                if ehrf and self.content[it[0]]['kind'] != 'admin':
                    own.append(ehrf(i + 1))
                mech = it[1]
                if mech == 'copy_in_other_chart':
                    src, d = it[2], it[3]
                    key = (src.name, d)
                    if key not in emb_fax:
                        cnt = sum(1 for x in seq if len(x) > 2 and x[2] is src and x[3] == d)
                        emb_fax[key] = [self.fax_fn(src, p.fax, p.name, d - TD(days=m.randint(0, 3)), f"{m.randint(8, 17):02d}:{m.randint(0, 59):02d}", cnt), 0,
                                        self.stamp(m.choice(['RECEIVED', "REC'D", 'OUTSIDE RECORDS', 'SCANNED']), p.name, d)]
                    ef = emb_fax[key]
                    ef[1] += 1
                    inh.append(ef[0](ef[1]))
                    if ef[1] == 1 or m.random() < 0.5:
                        own.append(ef[2])
                self.emit(it[0], p.name, 1, mech, inh=inh, own=own)
        cur = len(self.out)
        U = len(self.content) + 9      # + originals created by the later productions
        lo, hi = max(220, int(U * 2.3)), min(420, int(U * 3.7))
        T = m.randint(min(lo, hi), max(lo, hi))
        T = max(T, cur + 60)
        R = T - cur
        self.prod2(int(R * m.uniform(0.25, 0.33)))
        self.prod3(int((T - len(self.out)) * m.uniform(0.45, 0.55)))
        self.prod4(T - len(self.out))

    def prov_docs(self, p):
        return [D for D in sorted(p.docs, key=lambda D: (D['kind'] != 'clinical', D['date'])) if D['kind'] != 'admin']

    def prod2(self, quota):
        m = self.m
        start = len(self.out)
        provs = self.clin_provs[:]
        m.shuffle(provs)
        P2 = self.prod1_date + TD(days=m.randint(45, 80))
        for p in provs:
            used = len(self.out) - start
            if used >= quota - 4:
                break
            docs = self.prov_docs(p)
            if m.random() < 0.35 and len(docs) > 4:    # partial re-send
                k = m.randint(len(docs) // 2, len(docs) - 1)
                docs = docs[-k:] if m.random() < 0.5 else docs[:k]
            body = [c for D in docs for c in D['cids']]
            room = quota - used - 4
            if room < 3:
                break
            body = body[:room]
            req = self.b_request(p, P2 - TD(days=m.randint(20, 30)), 2)
            dsend = P2 + TD(days=m.randint(0, 9))
            fc = self.b_faxcover(p, dsend, len(body) + 2)
            cert = self.b_cert(p, dsend, len(body), 2)
            variant = m.choice(['plain', 'plain', 'reflow', 'headerless', 'reflow'])
            vst = None
            seq = [(fc['cids'][0], 'provider_production'), (req['cids'][0], 'provider_production'), (self.auth['cids'][0], 'authorization_attachment'), (cert['cids'][0], 'provider_production')] + \
                  [(c, 'rerequest_reprint') for c in body]
            n = len(seq)
            faxf = self.fax_fn(p, self.law.fax, self.law.name, dsend, f"{m.randint(8, 18):02d}:{m.randint(0, 59):02d}", n)
            ehrf = self.ehr_fn(p, dsend - TD(days=m.randint(0, 2)))
            for i, (cid, mech) in enumerate(seq):
                own = [faxf(i + 1)]
                items = st = None
                lab = mech
                if mech == 'rerequest_reprint':
                    own.append(ehrf(i + 1))
                    c = self.content[cid]
                    if variant == 'reflow':
                        items, st = reflow(c['items'], c['st'], random.Random(hash_seed(cid, p.name)))
                        lab += '+reflow'
                    elif variant == 'headerless' and any(x[0] == 'H' for x in c['items']):
                        items = [x for x in c['items'] if x[0] != 'H']
                        lab += '+header_missing'
                    if m.random() < 0.12:
                        own.append(self.stamp(m.choice(['COPY', 'DUPLICATE COPY', 'RE-SENT']), p.name, dsend))
                        lab += '+stamp'
                self.emit(cid, p.name, 2, lab, items=items, st=st, own=own)

    def pick_docs(self, quota, avoid_admin=True):
        m = self.m
        pool = [D for D in self.docs if D['kind'] != 'admin' and any(o['cid'] == D['cids'][0] for o in self.out)]
        weights = [3.0 if D['kind'] == 'clinical' else 1.5 for D in pool]
        chosen, total = [], 0
        used = set()
        while total < quota and pool:
            D = m.choices(pool, weights)[0]
            if D['id'] in used and len(used) < len(pool):
                continue
            used.add(D['id'])
            cids = D['cids']
            if len(cids) > 2 and m.random() < 0.15:
                cids = cids[:m.randint(1, len(cids) - 1)]
            cids = cids[:quota - total]
            chosen.append((D, cids))
            total += len(cids)
        chosen.sort(key=lambda x: (x[0]['date'], x[0]['id']))
        return chosen

    def source_rec(self, cid):
        recs = [o for o in self.out if o['cid'] == cid]
        return self.m.choice(recs)

    def prod3(self, quota):
        m = self.m
        ins = self.ins
        d3 = self.prod1_date + TD(days=m.randint(90, 140))
        adj = ins.person('adj')
        prefix = ''.join(w[0] for w in ins.name.split()[:3]).upper()
        b = [('L', ins.d(d3)), ('B', ''), ('L', self.law.name), ('L', self.law.addr), ('B', ''), ('L', f"RE: Claimant {self.pt['first']} {self.pt['last']}   Claim No. {self.claimno}   D/L {ins.d(self.acc)}"), ('B', ''),
             ('P', f"Enclosed please find copies of the medical and billing records contained in our claim file, Bates labeled {prefix}-CF 000001 forward, produced in response to your request. "
                   'These records were obtained from the providers and from your prior submissions; some pages are scanned copies.'),
             ('P', 'Please let me know if you are missing any records listed in your demand.'), ('B', ''), ('L', 'Sincerely,'), ('L', adj), ('L', 'Senior Bodily Injury Adjuster')]
        cover = self.doc(ins, 'admin', [b], d3, hdr='letter', label='ins_cover')
        bates = m.randint(1, 1)
        self.emit(cover['cids'][0], ins.name, 3, 'provider_production', own=[('bates', f"{prefix}-CF {bates:06d}", 'br')])
        chosen = self.pick_docs(quota - 1)
        for D, cids in chosen:
            ocr = m.random() < 0.4
            p_ocr = m.uniform(0.012, 0.045)
            inherit = m.random() < 0.65
            stamp_first = m.random() < 0.55
            direct_fax = None if inherit else (self.fax_fn(D['prov'], ins.fax, ins.name, d3 - TD(days=m.randint(20, 60)), f"{m.randint(8, 17):02d}:{m.randint(0, 59):02d}", len(cids)) if m.random() < 0.6 else None)
            orng = random.Random(hash_seed(D['id'], 'ins', len(self.out)))
            for j, cid in enumerate(cids):
                bates += 1
                lab = ['insurer_claim_file']
                src = self.source_rec(cid) if inherit else None
                items = src['items'] if src else None
                st = src['st'] if src else None
                crop = src['crop'] if src else None
                inh = (src['inh'] + src['own']) if src else []
                if src:
                    lab.append('copy_of_copy')
                if direct_fax:
                    inh.append(direct_fax(j + 1))
                    lab.append('fax')
                if ocr:
                    items = ocr_items(items if items is not None else self.content[cid]['items'], orng, p_ocr)
                    lab.append('ocr')
                own = [('bates', f"{prefix}-CF {bates:06d}", 'br')]
                if j == 0 and stamp_first:
                    own.append(self.stamp(m.choice(['RECEIVED', 'RECEIVED - CLAIMS', 'FILED', 'REVIEWED']), f"{ins.name.split()[0]} BI UNIT {m.randint(1, 6)}", d3 - TD(days=m.randint(5, 50))))
                    lab.append('stamp')
                self.emit(cid, ins.name, 3, '+'.join(lab), items=items, st=st, crop=crop, inh=inh, own=own)

    def prod4(self, quota):
        m = self.m
        dfn = self.dfn
        d4 = self.prod1_date + TD(days=m.randint(160, 230))
        chosen = self.pick_docs(max(1, quota - 2))
        prefix = ''.join(w[0] for w in dfn.name.replace('&', '').split()[:3]).upper()
        start = m.randint(1000, 8000)
        rows = []
        b_no = start
        for k, (D, cids) in enumerate(chosen):
            rows.append([f"Ex. {k + 1}", (D['label'] or D['kind'])[:12] + ' ' + D['prov'].name[:30], fmt_date(D['date'], 'slash'), f"{prefix}{b_no + 2:07d}-{prefix}{b_no + 1 + len(cids):07d}"])
            b_no += len(cids)
        per = 30
        idx_pages = []
        for i in range(0, len(rows), per):
            body = [('T', 'INDEX OF EXHIBITS - RECORDS REVIEW BINDER'), ('L', f"{self.pt['last']} v. defendant(s), Claim {self.claimno}"), ('L', f"Prepared {dfn.d(d4)} by {dfn.person('para')}"), ('B', '')] + \
                   dfn.table(['Exhibit', 'Source', 'Date', 'Bates range'], rows[i:i + per])
            idx_pages.append(body)
        idx = self.doc(dfn, 'admin', idx_pages, d4, hdr='letter', label='def_index')
        bates = start
        for c in idx['cids']:
            bates += 1
            self.emit(c, dfn.name, 4, 'provider_production', own=[('bates', f"{prefix}{bates:07d}", 'bc', ('cour', 8))])
        for k, (D, cids) in enumerate(chosen):
            exno = k + 1
            ocr = m.random() < 0.3
            p_ocr = m.uniform(0.015, 0.05)
            crop = None
            if m.random() < 0.2:
                crop = m.choice([dict(top=m.uniform(60, 110)), dict(right=m.uniform(25, 60)), dict(top=m.uniform(40, 80), right=m.uniform(20, 40)), dict(bottom=m.uniform(60, 120))])
            inherit = m.random() < 0.55
            orng = random.Random(hash_seed(D['id'], 'def', len(self.out)))
            for j, cid in enumerate(cids):
                bates += 1
                lab = ['defense_exhibit']
                src = self.source_rec(cid) if inherit else None
                items = src['items'] if src else None
                st = src['st'] if src else None
                inh = (src['inh'] + src['own']) if src else []
                if src:
                    lab.append('copy_of_copy')
                if ocr:
                    items = ocr_items(items if items is not None else self.content[cid]['items'], orng, p_ocr)
                    lab.append('ocr')
                if crop:
                    lab.append('cropped')
                own = [('bates', f"{prefix}{bates:07d}", 'bc', ('cour', 8)), ('side', f"DEF. EX. {exno} - PAGE {j + 1}")]
                if j == 0:
                    own.append(('sticker', ['DEFENDANT', 'EXHIBIT', str(exno)], PW - 110, PH - 120))
                if m.random() < 0.09:
                    own.append(('sticky', m.choice([['Gap in tx?', 'check dates'], ['pre-existing?', 'see PCP note'], ['dup of Ex.', 'earlier set?'], ['MRI films', 'requested'], ['bill > usual', 'and customary'],
                                                     ['no signature', 'on this pg'], ['ask IME doc', 're: causation']]), m.uniform(360, 450), m.uniform(150, 420)))
                    lab.append('sticky_note')
                elif m.random() < 0.07:
                    own.append(('hand', m.choice(['reviewed - KD', 'see p. 14', '?? date', 'compare w/ ER', 'ok', 'prior hx!', 'NB']), m.uniform(380, 500), m.uniform(90, 300), m.uniform(-14, 14)))
                    lab.append('handwritten_note')
                self.emit(cid, dfn.name, 4, '+'.join(lab), items=items, st=st, crop=crop, inh=inh, own=own)


def hash_seed(*parts):
    s = '|'.join(str(x) for x in parts)
    h = 2166136261
    for ch in s.encode():
        h = ((h ^ ch) * 16777619) & 0xffffffff
    return h


# ------------------------------------------------------------------ write case
def check_originals(case):
    """Every content id rendered clean (no copy overlays) must give distinct text."""
    scratch = fitz.open()
    seen = {}
    for cid, c in case.content.items():
        pg = scratch.new_page(width=PW, height=PH)
        draw_body(pg, c['items'], c['st'])
        t = ' '.join(pg.get_text().split())
        if t in seen:
            raise SystemExit(f"{case.id}: originals {seen[t]} and {cid} render identical text")
        seen[t] = cid
    scratch.close()


def write_case(case):
    check_originals(case)
    out_dir = os.path.join(OUTROOT, case.id)
    os.makedirs(out_dir, exist_ok=True)
    pdf = fitz.open()
    pages = []
    for i, rec in enumerate(case.out):
        render_rec(pdf, rec)
        pages.append(dict(page=i + 1, content_id=rec['cid'], provider=rec['producer'], production=rec['prod'], mechanism=rec['mech'], doc_kind=rec['kind']))
    pdf.set_metadata({'title': f"{case.id} records", 'author': 'alt2 synthetic generator', 'creator': 'alt2', 'producer': 'PyMuPDF',
                      'creationDate': 'D:20260101000000', 'modDate': 'D:20260101000000'})
    pdf.save(os.path.join(out_dir, 'records.pdf'), garbage=3, deflate=True, no_new_id=True)
    pdf.close()
    evs = sorted(case.events, key=lambda e: (e['date'], e['doc_id']))
    events = []
    for i, e in enumerate(evs):
        events.append(dict(event_id=f"e{i + 1:03d}", date=mdY(e['date']), provider=e['provider'], kind=e['kind'], summary=e['summary'], codes=e['codes'], procedures=e['procedures'],
                           doc_id=e['doc_id'], pages=e['pages']))
    truth = {'case_id': case.id, 'patient': {'first': case.pt['first'], 'last': case.pt['last'], 'dob': mdY(case.pt['dob'])}, 'accident_date': mdY(case.acc),
             'regions': case.spec['regions'], 'events': events, 'pages': pages}
    with open(os.path.join(out_dir, 'truth.json'), 'w', encoding='utf-8') as f:
        json.dump(truth, f, indent=1)
    return truth


def main():
    tot_p = tot_u = 0
    for n, spec in enumerate(CASES, start=1):
        case = Case(n, spec)
        case.build()
        case.productions()
        truth = write_case(case)
        P = len(truth['pages'])
        U = len({p['content_id'] for p in truth['pages']})
        tot_p += P
        tot_u += U
        print(f"{case.id}: {spec['key']:<18} pages={P:4d}  unique originals={U:4d}  duplicates={100 * (P - U) / P:5.1f}%  events={len(truth['events'])}")
    print(f"TOTAL: pages={tot_p}  unique={tot_u}  duplicates={100 * (tot_p - tot_u) / tot_p:.1f}%")


if __name__ == '__main__':
    main()
