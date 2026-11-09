#!/usr/bin/env python3
"""alt3: independent synthetic personal-injury medical-record generator.

Run from the provider-match folder:
    python records/altgen3/generate_alt3.py

Writes records/data/alt3/alt3-<n>/records.pdf and truth.json for 10 fictional
cases. Everything is fictional. Deterministic (fixed seeds). See README.md.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import random
import textwrap
from dataclasses import dataclass, field

import fitz  # PyMuPDF
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUTROOT = os.path.join(ROOT, 'records', 'data', 'alt3')
D = dt.date
TD = dt.timedelta

MON = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()
MONTH = ('January February March April May June July August September '
         'October November December').split()
DATEFMTS = ['mdy_slash', 'mdy_dash', 'd_mon_y', 'month_ord', 'ymd_slash', 'mon_d_yy', 'ymd_compact']


def _ord(n):
    return 'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')


def fmtd(d, f):
    if f == 'mdy_slash':
        return f'{d.month:02d}/{d.day:02d}/{d.year}'
    if f == 'mdy_dash':
        return f'{d.month}-{d.day}-{d.year}'
    if f == 'd_mon_y':
        return f'{d.day:02d} {MON[d.month - 1]} {d.year}'
    if f == 'month_ord':
        return f'{MONTH[d.month - 1]} {d.day}{_ord(d.day)}, {d.year}'
    if f == 'ymd_slash':
        return f'{d.year}/{d.month:02d}/{d.day:02d}'
    if f == 'mon_d_yy':
        return f"{MON[d.month - 1]} {d.day}, '{d.year % 100:02d}"
    if f == 'ymd_compact':
        return f'{d.year}{d.month:02d}{d.day:02d}'
    raise ValueError(f)


def mdy(d):
    return f'{d.month:02d}/{d.day:02d}/{d.year}'


def clinic_day(d):
    return d + TD(1) if d.weekday() == 6 else d


def subseq(code):
    """Initial-encounter code -> subsequent-encounter code (7th character D)."""
    if code[0] in 'STVW' and len(code) == 8 and code.endswith('A'):
        return code[:-1] + 'D'
    return code


# --------------------------------------------------------------------------
# blocks and styles
# --------------------------------------------------------------------------
@dataclass
class Blk:
    text: str
    font: str = ''
    size: float = 0.0
    align: str = 'l'      # l r c lr
    indent: int = 0
    hdr: bool = False
    para: bool = False
    role: str = 'body'    # body | over | late | annot


ES = {
    'Patient': 'Paciente', 'Date of birth': 'Fecha de nacimiento', 'Date of service': 'Fecha de servicio',
    'Chief complaint': 'Motivo de consulta', 'History of present illness': 'Historia de la enfermedad actual',
    'Past medical history': 'Antecedentes médicos', 'Medications': 'Medicamentos', 'Allergies': 'Alergias',
    'Review of systems': 'Revisión por sistemas', 'Vital signs': 'Signos vitales', 'Examination': 'Examen físico',
    'Imaging': 'Imágenes', 'Clinic course': 'Curso en clínica', 'Assessment': 'Evaluación', 'Plan': 'Plan',
    'Disposition': 'Disposición', 'Account': 'Cuenta', 'Interval history': 'Historia interval',
    'Work status': 'Estado laboral', 'Follow-up': 'Seguimiento', 'Diagnosis': 'Diagnóstico',
    'Instructions': 'Instrucciones', 'Records reviewed': 'Expedientes revisados', 'Subjective': 'Subjetivo',
    'Objective': 'Objetivo', 'Interventions': 'Intervenciones', 'Goals': 'Metas', 'Response': 'Respuesta',
    'Restrictions': 'Restricciones', 'Signature': 'Firma', 'Procedure': 'Procedimiento',
}
SOAP = {'Chief complaint': 'CC', 'Subjective': 'S', 'History of present illness': 'S',
        'Interval history': 'S', 'Examination': 'O', 'Objective': 'O', 'Vital signs': 'O',
        'Assessment': 'A', 'Diagnosis': 'A', 'Plan': 'P', 'Follow-up': 'P'}
FAM = {'eqbox': 'cour', 'colon': 'cour', 'grid': 'cour', 'hashbox': 'tiro', 'narrative': 'tiro',
       'tilde': 'tiro', 'soap': 'helv', 'bilingual': 'helv', 'stamped': 'helv', 'dash': 'helv'}
BOLD = {'helv': 'hebo', 'tiro': 'tibo', 'cour': 'cobo'}
ITAL = {'helv': 'heit', 'tiro': 'tiit', 'cour': 'coit'}
CW = {'cour': .6, 'helv': .5, 'tiro': .45}
KINDS = ['eqbox', 'hashbox', 'soap', 'narrative', 'colon', 'stamped', 'dash', 'tilde', 'grid']


class Style:
    def __init__(self, kind, datefmt, rng):
        self.kind = kind
        self.datefmt = datefmt
        fam = FAM[kind]
        if kind == 'stamped' and rng.random() < .5:
            fam = 'cour'
        if kind == 'dash' and rng.random() < .4:
            fam = 'tiro'
        self.fam = fam
        self.font, self.bold, self.ital = fam, BOLD[fam], ITAL[fam]
        self.size = round(rng.uniform(8.2, 9.0), 1) if fam == 'cour' else round(rng.uniform(8.7, 10.0), 1)
        self.wrap = int(495 / (CW[fam] * self.size))
        self.lang = 'bi' if kind == 'bilingual' else 'en'
        self.n = 0
        self.clock = 8 * 60
        self.rng = rng

    def L(self, s):
        return f'{ES[s]} / {s}' if self.lang == 'bi' and s in ES else s

    def d(self, day):
        return fmtd(day, self.datefmt)

    def reset(self, start_min=None):
        self.n = 0
        self.clock = start_min if start_min is not None else self.rng.randint(7 * 60, 15 * 60)

    def tick(self, lo=3, hi=25):
        self.clock += self.rng.randint(lo, hi)
        m = self.clock % (24 * 60)
        return f'{m // 60:02d}:{m % 60:02d}'

    def ptname(self, pt):
        if self.kind in ('eqbox', 'colon', 'grid', 'dash'):
            return f"{pt['last'].upper()}, {pt['first'].upper()}"
        if self.kind in ('hashbox', 'stamped'):
            return f"{pt['last']}, {pt['first']}"
        return f"{pt['first']} {pt['last']}"

    def field(self, lab, val):
        k = self.kind
        if k == 'colon':
            return f'{lab.ljust(20)}: {val}'
        if k == 'bilingual':
            return f'{self.L(lab)}: {val}'
        if k == 'tilde':
            return f'[{lab}] {val}'
        if k == 'grid':
            return f'| {lab.upper()}: {val}'
        return f'{lab}: {val}'

    def header(self, P, title, pt, day, extra=()):
        k = self.kind
        nm, dob, dos = self.ptname(pt), self.d(pt['dob']), self.d(day)
        Bd, s = self.bold, self.size
        if k == 'eqbox':
            bar = '=' * 70
            H = [Blk(bar), Blk('|| ' + P.name.upper().center(64) + ' ||', font=Bd),
                 Blk('|| ' + P.addr.center(64) + ' ||'),
                 Blk('|| ' + f'Tel {P.phone}   Fax {P.fax}'.center(64) + ' ||'), Blk(bar),
                 Blk(f'{title}\t{dos}', align='lr', font=Bd),
                 Blk(f'Patient: {nm}    DOB: {dob}    MRN: {P.mrn}')]
        elif k == 'hashbox':
            bar = '#' * 62
            H = [Blk(bar), Blk('#  ' + P.name, font=Bd, size=s + 1.5), Blk('#  ' + P.addr + '  *  ' + P.phone),
                 Blk(bar), Blk(title, align='c', font=Bd, size=s + 1),
                 Blk(f'Pt: {nm}  |  DOB {dob}  |  Acct {P.mrn}'), Blk(f'Date of Service: {dos}', align='r')]
        elif k == 'soap':
            H = [Blk(P.name, align='c', font=Bd, size=s + 3), Blk(f'{P.addr}  Phone {P.phone}', align='c', size=s - 1),
                 Blk(title, font=Bd), Blk(f'Patient: {nm}   DOB: {dob}   MRN: {P.mrn}   Visit date: {dos}')]
        elif k == 'narrative':
            H = [Blk(P.name, align='c', font=Bd, size=s + 4), Blk(P.addr, align='c', size=s - .5),
                 Blk(f'Telephone {P.phone}  -  Facsimile {P.fax}', align='c', size=s - .5), Blk('_' * 78),
                 Blk(dos, align='r'), Blk(title, font=Bd), Blk(f'RE: {nm}   (DOB {dob})   Chart {P.mrn}')]
        elif k == 'colon':
            H = [Blk(P.name.upper(), font=Bd, size=s + 2), Blk(P.addr), Blk('-' * 72), Blk(title, font=Bd),
                 Blk(self.field('Patient', nm)), Blk(self.field('Date of Birth', dob)),
                 Blk(self.field('Date of Service', dos)), Blk(self.field('Medical Record No', P.mrn))]
        elif k == 'bilingual':
            H = [Blk(P.name, align='c', font=Bd, size=s + 3), Blk(f'{P.addr} | Tel. {P.phone}', align='c'),
                 Blk(title, align='c', font=Bd), Blk(f'{self.L("Patient")}: {nm}'),
                 Blk(f'{self.L("Date of birth")}: {dob}     {self.L("Date of service")}: {dos}'),
                 Blk(f'{self.L("Account")}: {P.mrn}')]
        elif k == 'stamped':
            H = [Blk(f'<< {P.name} >>', font=Bd, size=s + 2), Blk(f'{title}   ::   {nm}   ::   DOB {dob}'),
                 Blk(f'Encounter date {dos}   MRN {P.mrn}   {P.phone}')]
        elif k == 'dash':
            H = [Blk(P.name.upper(), font=Bd, size=s + 2.5), Blk(f'{P.addr}   {P.phone}'), Blk('-' * 90),
                 Blk(f'{title}\tDOS {dos}', align='lr', font=Bd), Blk(f'NAME {nm}     DOB {dob}     MRN {P.mrn}'),
                 Blk('-' * 90)]
        elif k == 'tilde':
            H = [Blk('~' * 8 + '  ' + P.name + '  ' + '~' * 8, align='c', font=Bd, size=s + 2),
                 Blk(P.addr, align='c'), Blk(f'[{title}]', font=Bd),
                 Blk(f'[Patient] {nm}   [DOB] {dob}   [Date] {dos}   [Chart] {P.mrn}')]
        else:  # grid
            bar = '+' + '-' * 76 + '+'
            H = [Blk(bar), Blk('| ' + P.name.upper().ljust(54) + dos.rjust(21) + ' |', font=Bd),
                 Blk('| ' + title.ljust(75) + '|'), Blk(bar),
                 Blk(f'| PATIENT {nm} | DOB {dob} | REF # {P.mrn}'), Blk(bar)]
        for lab, val in extra:
            H.append(Blk(self.field(lab, val)))
        for h in H:
            h.hdr = True
        return H

    def cont(self, P, title, pt, day):
        nm, dos = self.ptname(pt), self.d(day)
        k = self.kind
        if k in ('eqbox', 'grid', 'colon'):
            H = [Blk(f'{P.name.upper()} -- {title} (CONTINUED)', font=self.bold),
                 Blk(f'{nm}   MRN {P.mrn}   DOS {dos}'), Blk('-' * 70)]
        elif k == 'bilingual':
            H = [Blk(f'{P.name} -- {title} (continuación / continued)', font=self.bold),
                 Blk(f'{self.L("Patient")}: {nm}   {self.L("Date of service")}: {dos}')]
        else:
            H = [Blk(f'{P.name}  |  {title}, continued', font=self.bold), Blk(f'{nm}  -  {dos}  -  #{P.mrn}')]
        for h in H:
            h.hdr = True
        return H

    def footer(self, P, i, n, ref):
        k = self.kind
        if k == 'eqbox':
            return [Blk(''), Blk(f'Doc {ref}\tPage {i} of {n}', align='lr', size=self.size - 1)]
        if k == 'hashbox':
            return [Blk(''), Blk(f'- {i} -   ({ref})', align='c', size=self.size - 1)]
        if k == 'soap':
            return [Blk(''), Blk(f'{P.abbr} | {ref} | Page {i}/{n}', align='r', size=self.size - 1.5)]
        if k == 'narrative':
            return [Blk(''), Blk(f'Page {i} of {n}', align='c', size=self.size - 1)]
        if k == 'colon':
            return [Blk(''), Blk(f'{ref}    PAGE {i:02d} OF {n:02d}', align='r')]
        if k == 'bilingual':
            return [Blk(''), Blk(f'Página {i} de {n} / Page {i} of {n}   [{ref}]', align='c', size=self.size - 1)]
        if k == 'stamped':
            return [Blk(''), Blk(f'[{i}/{n}] {ref}', align='r', size=self.size - 1)]
        if k == 'dash':
            return [Blk(''), Blk(f'{ref}\tpg {i}/{n}', align='lr', size=self.size - 1)]
        if k == 'tilde':
            return [Blk(''), Blk(f'~ {i} of {n} ~  {ref}', align='c', size=self.size - 1)]
        return [Blk(''), Blk(f'SHEET {i} OF {n}   FORM {ref}', align='r')]

    def sec(self, label, text):
        self.n += 1
        k, L, Bd = self.kind, self.L(label), self.bold
        if k == 'eqbox':
            return [Blk(L.upper() + ':', font=Bd), Blk(text, para=True, indent=2)]
        if k == 'hashbox':
            return [Blk(f'{self.n}. {L.upper()}', font=Bd), Blk(text, para=True, indent=3)]
        if k == 'soap':
            key = SOAP.get(label)
            if key:
                return [Blk(f'{key}:  [{label}] {text}', para=True)]
            return [Blk(L, font=Bd), Blk(text, para=True)]
        if k == 'narrative':
            return [Blk(f'{L}: {text}', para=True), Blk('')]
        if k == 'colon':
            return [Blk(L.upper(), font=Bd), Blk(text, para=True, indent=2)]
        if k == 'bilingual':
            return [Blk(L, font=Bd), Blk(text, para=True)]
        if k == 'stamped':
            return [Blk(f'[{self.tick()}] {L}: {text}', para=True)]
        if k == 'dash':
            return [Blk(L.upper(), font=Bd), Blk('-' * len(L)), Blk(text, para=True)]
        if k == 'tilde':
            return [Blk(f'[{L}]', font=Bd), Blk(text, para=True)]
        return [Blk(f'| {L.upper()} |', font=Bd), Blk(text, para=True)]

    def sign(self, who, day, t):
        k, dd = self.kind, self.d(day)
        if k == 'eqbox':
            s = f'Electronically signed: {who}   {dd} {t}'
        elif k == 'hashbox':
            return [Blk(''), Blk(f'/s/ {who}', font=self.ital), Blk(f'Signed {dd} @ {t}')]
        elif k == 'soap':
            s = f'{who}  --  e-signed {dd} {t}'
        elif k == 'narrative':
            return [Blk(''), Blk('Sincerely,'), Blk(''), Blk(who, font=self.ital), Blk(f'(dictated and signed {dd} {t})')]
        elif k == 'colon':
            s = self.field('Signed by', f'{who}  {dd} {t}')
        elif k == 'bilingual':
            s = f'Firma / Signature: {who}    Fecha / Date: {dd} {t}'
        elif k == 'stamped':
            s = f'[{dd} {t}] Note signed and locked by {who}'
        elif k == 'dash':
            s = f'Attested: {who} on {dd} at {t}'
        elif k == 'tilde':
            s = f'~ authenticated {who} | {dd} {t} ~'
        else:
            s = f'| SIGNATURE: {who} | TIME {t} | DATE {dd}'
        return [Blk(''), Blk(s)]

    def table(self, cols, rows, widths):
        sep = {'colon': ' : ', 'grid': ' | ', 'eqbox': ' | ', 'dash': ' : '}.get(self.kind, '  ')

        def f(r):
            return sep.join(str(c)[:w].ljust(w) for c, w in zip(r, widths)).rstrip()
        tsz = max(7.2, min(self.size, 8.6) - .3)
        width = sum(widths) + len(sep) * (len(widths) - 1)
        out = [Blk(f(cols), font='cobo', size=tsz), Blk('-' * width, font='cour', size=tsz)]
        out += [Blk(f(r), font='cour', size=tsz) for r in rows]
        return out


@dataclass
class Prov:
    key: str
    name: str
    role: str
    addr: str
    phone: str
    fax: str
    style: Style
    mrn: str
    clin: list
    cust: list
    abbr: str


@dataclass
class Orig:
    cid: str
    prov: Prov
    kind: str
    blocks: list
    tags: list
    date: dt.date
    doc: str


# --------------------------------------------------------------------------
# reference data
# --------------------------------------------------------------------------
CL_FIRST = ['Anouk', 'Teodoro', 'Priyanka', 'Gareth', 'Selene', 'Ottavio', 'Wren', 'Dashiell', 'Ilse', 'Marisa',
            'Kwabena', 'Rosalind', 'Tobias', 'Nkechi', 'Henrik', 'Yolanda', 'Caspian', 'Mireille', 'Ezekiel',
            'Linnea', 'Bartholomew', 'Soraya', 'Fennimore', 'Imelda', 'Rafferty', 'Junia', 'Leopold', 'Ottilie',
            'Thaddeus', 'Vesna', 'Ambrose', 'Delphine', 'Ignatius', 'Zuzana', 'Peregrine', 'Odalys', 'Cormac',
            'Hyacinth', 'Lazlo', 'Benedetta', 'Ruairi', 'Philippa', 'Anselm', 'Marguerite', 'Torvald', 'Esme']
CL_LAST = ['Varga-Holm', 'Okonkwo-Reyes', 'Thistlewood', 'Marchetti', 'Ballantyne', 'Szymanska', 'Ferreira-Lind',
           'Achterberg', 'Quillfeather', 'Nakashima-Bell', 'Duvernay', 'Halvorsen', 'Pemberton-Ruiz', 'Castellanos',
           'Wexford', 'Lindqvist-Ames', 'Oyelaran', 'Brannigan', 'Kowalczyk', 'Delacroix-Moon', 'Esterhazy',
           'Fairweather', 'Gundersen', 'Hollingsworth', 'Iturbide', 'Jessop', 'Kittredge', 'Montague', 'Northcott',
           'Osei-Bonsu', 'Pellegrino', 'Rasmussen', 'Stoddard', 'Tremblay-Ash', 'Vandermeer', 'Waldgrave',
           'Yarborough', 'Zelinski', 'Abernethy-Cole', 'Brightwater', 'Cavendish-Ortiz', 'Drummond']
STREETS = ['Alder Bend Rd', 'Quarry Hill Ave', 'Tanager Way', 'Bellows Ct', 'Foundry Row', 'Kestrel Pkwy',
           'Lantern Sq', 'Millrace Dr', 'Orchard Gate Blvd', 'Pilgrim Ln', 'Sorrel St', 'Thornapple Ave',
           'Upland Terrace', 'Wicket Way', 'Copperleaf Dr', 'Harrow Rd', 'Juniper Commons', 'Salt Meadow Ln']
CRED = {'md': 'MD', 'do': 'DO', 'pa': 'PA-C', 'np': 'FNP-C', 'rn': 'RN', 'pt': 'PT, DPT', 'pta': 'PTA',
        'dc': 'DC', 'ot': 'OTR/L, CHT', 'dds': 'DDS', 'dmd': 'DMD', 'phd': 'PhD, ABPP-CN', 'emt': 'NRP',
        'emt2': 'EMT-B', 'rad': 'MD, Radiology', 'crna': 'CRNA', 'dpm': 'DPM'}
ROLE_CLIN = {'prior': ['md', 'rn'], 'ems': ['emt', 'emt2'], 'er': ['md', 'rn', 'rn'], 'uc': ['np', 'rn'],
             'hospital': ['md', 'md', 'rn', 'rn', 'md'], 'imaging': ['rad', 'rad'], 'spec': ['md', 'pa'],
             'asc': ['crna', 'rn'], 'therapy': ['pt', 'pta'], 'lab': ['md', 'rn']}

FEE = {'99202': 165, '99203': 240, '99204': 365, '99205': 455, '99212': 110, '99213': 165, '99214': 245,
       '99215': 330, '99283': 410, '99284': 720, '99285': 1150, '99221': 390, '99222': 520, '99223': 690,
       '99231': 150, '99232': 215, '99233': 310, '99238': 260, '99239': 340, '99395': 285, '99396': 310,
       '99397': 335, '97161': 210, '97162': 225, '97163': 240, '97164': 160, '97165': 230, '97166': 240,
       '97168': 160, '97110': 65, '97112': 70, '97140': 68, '97530': 72, '97012': 40, '98940': 55, '98941': 72,
       '73000': 145, '73030': 160, '72100': 175, '72148': 1650, '72114': 290, '73562': 190, '73721': 1720,
       '72125': 980, '72141': 1590, '70336': 1480, '70486': 1120, '70355': 210, '12011': 385, '41899': 640,
       '13151': 1240, '15004': 1420, '15120': 3890, '16020': 260, '17106': 520, '71260': 1310, '71046': 140,
       '32551': 980, '94010': 120, '64420': 610, '64421': 380, '64483': 1340, '70450': 890, '70551': 1680,
       '96116': 260, '96132': 410, '96136': 160, '96137': 140, '23515': 4120, '29888': 6850, '29881': 3120,
       '28485': 2310, '64520': 1290, '73630': 165, '73700': 980, '20552': 210, '85025': 38, '80053': 64,
       '80048': 49, '87045': 96, '83605': 41, '86140': 33, '99244': 395}
CPT_DESC = {'99202': 'New pt office visit, straightforward', '99203': 'New pt office visit, low MDM',
            '99204': 'New pt office visit, moderate MDM', '99212': 'Est pt visit, straightforward',
            '99213': 'Est pt visit, low MDM', '99214': 'Est pt visit, moderate MDM', '99283': 'ED visit, low MDM',
            '99284': 'ED visit, moderate MDM', '99285': 'ED visit, high MDM', '99222': 'Initial hospital care, mod',
            '99223': 'Initial hospital care, high', '99231': 'Subsequent hospital care, low',
            '99232': 'Subsequent hospital care, mod', '99239': 'Discharge day mgmt >30 min',
            '99395': 'Preventive visit 18-39', '99396': 'Preventive visit 40-64', '99397': 'Preventive visit 65+',
            '97161': 'PT eval low complexity', '97162': 'PT eval moderate complexity',
            '97163': 'PT eval high complexity', '97164': 'PT re-evaluation', '97165': 'OT eval low',
            '97166': 'OT eval moderate', '97168': 'OT re-evaluation', '97110': 'Therapeutic exercise 15 min',
            '97112': 'Neuromuscular re-education 15 min', '97140': 'Manual therapy 15 min',
            '97530': 'Therapeutic activities 15 min', '97012': 'Mechanical traction', '98940': 'CMT 1-2 regions',
            '98941': 'CMT 3-4 regions', '73000': 'X-ray clavicle complete', '73030': 'X-ray shoulder 2+ views',
            '72100': 'X-ray lumbosacral 2-3 views', '72148': 'MRI lumbar spine w/o contrast',
            '72114': 'X-ray lumbosacral w/ bending', '73562': 'X-ray knee 3 views', '73721': 'MRI knee w/o contrast',
            '72125': 'CT cervical spine w/o contrast', '72141': 'MRI cervical spine w/o contrast',
            '70336': 'MRI temporomandibular joints', '70486': 'CT maxillofacial w/o contrast',
            '70355': 'Orthopantogram', '12011': 'Simple repair face/lips <=2.5 cm',
            '41899': 'Unlisted dentoalveolar procedure', '13151': 'Complex repair lips 1.1-2.5 cm',
            '15004': 'Surgical prep wound hands first 100 sq cm', '15120': 'STSG hands first 100 sq cm',
            '16020': 'Dressing/debridement burn, small', '17106': 'Destruction vascular lesion <10 sq cm',
            '71260': 'CT chest with contrast', '71046': 'X-ray chest 2 views', '32551': 'Tube thoracostomy',
            '94010': 'Spirometry', '64420': 'Intercostal nerve block, single', '64421': 'Intercostal nerve block, addl',
            '64483': 'TFESI lumbar/sacral, single level', '70450': 'CT head w/o contrast',
            '70551': 'MRI brain w/o contrast', '96116': 'Neurobehavioral status exam',
            '96132': 'Neuropsych eval, first hour', '96136': 'Test admin by professional, first 30 min',
            '96137': 'Test admin by professional, addl 30 min', '23515': 'ORIF clavicle fracture',
            '29888': 'Arthroscopic ACL reconstruction', '29881': 'Arthroscopic meniscectomy, medial or lateral',
            '28485': 'ORIF metatarsal fracture, each', '64520': 'Lumbar sympathetic block',
            '73630': 'X-ray foot 3 views', '73700': 'CT lower extremity w/o contrast',
            '20552': 'Trigger point injection 1-2 muscles', '85025': 'CBC with differential',
            '80053': 'Comprehensive metabolic panel', '80048': 'Basic metabolic panel', '87045': 'Stool culture',
            '83605': 'Lactate', '86140': 'C-reactive protein', '99244': 'Office consultation, moderate'}

PANELS = {
    'CBC': ('85025', [('WBC', 'x10^3/uL', 4.0, 11.0), ('Hemoglobin', 'g/dL', 12.0, 16.5),
                      ('Hematocrit', '%', 36.0, 48.0), ('Platelets', 'x10^3/uL', 150, 400),
                      ('Neutrophils', '%', 40.0, 75.0)]),
    'CMP': ('80053', [('Sodium', 'mmol/L', 135, 145), ('Potassium', 'mmol/L', 3.5, 5.1),
                      ('Chloride', 'mmol/L', 98, 107), ('CO2', 'mmol/L', 22, 29), ('BUN', 'mg/dL', 7, 20),
                      ('Creatinine', 'mg/dL', 0.6, 1.2), ('Glucose', 'mg/dL', 70, 99), ('Calcium', 'mg/dL', 8.6, 10.3),
                      ('Albumin', 'g/dL', 3.5, 5.0), ('AST', 'U/L', 10, 40), ('ALT', 'U/L', 7, 56)]),
    'BMP': ('80048', [('Sodium', 'mmol/L', 135, 145), ('Potassium', 'mmol/L', 3.5, 5.1),
                      ('Chloride', 'mmol/L', 98, 107), ('CO2', 'mmol/L', 22, 29), ('BUN', 'mg/dL', 7, 20),
                      ('Creatinine', 'mg/dL', 0.6, 1.2), ('Glucose', 'mg/dL', 70, 99), ('Calcium', 'mg/dL', 8.6, 10.3)]),
    'LACTATE': ('83605', [('Lactate', 'mmol/L', 0.5, 2.2)]),
    'CRP': ('86140', [('C-reactive protein', 'mg/L', 0.0, 10.0)]),
    'STOOL': ('87045', None),
}

# --------------------------------------------------------------------------
# case specifications (all fictional)
# --------------------------------------------------------------------------
CASES = [
    dict(n=1, seed=31001, first='Marisol', last='Quintero-Hale', sex='F', dob=D(1991, 6, 22), acc=D(2025, 3, 14),
         acc_time='17:42', city='Larkmoor, OR 97399', short='electric scooter fall',
         regions=['right clavicle', 'right shoulder', 'right forearm'],
         cc='Right shoulder pain and collarbone deformity after electric scooter fall',
         mech='was riding a rented stand-up electric scooter in a bike lane when the front wheel caught a raised utility cover and she was thrown forward onto her right shoulder',
         sym='sharp right shoulder pain rated 8/10, a visible bump over the right collarbone and stinging abrasions on the right forearm',
         deny='head strike, loss of consciousness, neck pain, chest pain or numbness in the right hand',
         exam='Focal tenderness and a palpable step-off over the midshaft right clavicle without skin tenting. Abrasions 4 x 6 cm over the dorsal right forearm. Radial pulse 2+, sensation intact in axillary, median, radial and ulnar distributions. Active shoulder motion limited by pain.',
         dx=[('S42.021A', 'Displaced fracture of shaft of right clavicle, initial encounter for closed fracture'),
             ('S50.811A', 'Abrasion of right forearm, initial encounter')],
         ext=[('V00.841A', 'Fall from standing electric scooter, initial encounter')],
         pmh='No chronic medical problems. No prior shoulder injury or surgery.', allergy='Sulfa (rash)',
         home_meds='Oral contraceptive daily', disch='Keep the sling on except for bathing. Ice 20 minutes every 2 hours while awake. Clean the forearm abrasions twice daily and cover with petrolatum gauze. Return for numbness, color change in the fingers or skin breakdown over the bone.',
         providers=[
             dict(role='prior', name='Larkmoor Family Health Partners', visits=[
                 dict(off=-410, cc='Annual preventive visit', hpi='Feels well. Runs three times a week. No complaints.',
                      exam='Normal general exam. Full painless range of motion of both shoulders.',
                      codes=[('Z00.00', 'Encounter for general adult medical examination without abnormal findings')],
                      cpt=['99395'], plan='Routine labs. Return in one year.', summary='Annual physical, no shoulder complaints'),
                 dict(off=-95, cc='Sinus congestion for 10 days', hpi='Facial pressure, thick nasal drainage, low grade temperature.',
                      exam='Maxillary sinus tenderness. Lungs clear.', codes=[('J01.90', 'Acute sinusitis, unspecified')],
                      cpt=['99213'], plan='Amoxicillin-clavulanate 875 mg twice daily for 7 days.', summary='Acute sinusitis')]),
             dict(role='ems', name='Larkmoor Fire & Rescue - Medic 7', course=['Sling and swathe applied', 'Ice pack to right shoulder', 'Fentanyl 50 mcg IN given']),
             dict(role='er', name='Tamsin Valley Medical Center', cpt=['99284'], extra=[],
                  course=['Fentanyl 50 mcg IV given', 'Right clavicle radiographs obtained', 'Forearm abrasions irrigated and dressed', 'Sling fitted', 'Orthopaedics paged and agreed with outpatient follow-up'],
                  img=[dict(cpt='73000', name='XR CLAVICLE RIGHT 2 VIEWS', findings=['Displaced midshaft right clavicle fracture with 1.8 cm shortening.', 'Inferior displacement of the lateral fragment by one shaft width.', 'No pneumothorax at the visualized right apex.'], impression='Displaced and shortened midshaft right clavicle fracture.')],
                  plan='Sling for comfort, ibuprofen 600 mg every 6 hours and acetaminophen 1000 mg every 8 hours, oxycodone 5 mg #10 for severe pain. Orthopaedics follow-up in 2 to 3 days.'),
             dict(role='spec', name='Fernhill Orthopaedic Associates', label='Orthopaedic Surgery', visits=[3, 10, 24, 45, 80],
                  first_cpt='99204', fu_cpt='99213',
                  exam=['Swelling and ecchymosis over the right clavicle, skin intact, 1.8 cm shortening, neurovascularly intact.',
                        'Unchanged deformity, skin intact. Distal neurovascular exam normal.',
                        'Incision clean and dry, sutures removed. Forward flexion 80 degrees passive.',
                        'Incision healed. Active forward flexion 135, abduction 120, external rotation 50.',
                        'Full symmetric range of motion. No tenderness over the plate.'],
                  plans=['Discussed operative versus nonoperative care given shortening and displacement; patient elects open reduction and internal fixation. Sling, hold NSAIDs 5 days before surgery.',
                         'Pre-operative visit. Consent signed for ORIF right clavicle at Fernhill Outpatient Surgery Center.',
                         'Post-op day 13. Begin physical therapy with pendulums and passive range of motion. No lifting over 2 lb.',
                         'Stiffness improving. Advance to active-assisted motion and strengthening. Light duty at work.',
                         'Radiographic union. Full duty. Possible hardware removal later if the plate is bothersome.']),
             dict(role='asc', name='Fernhill Outpatient Surgery Center', off=11, cpts=['23515'],
                  proc='Open reduction and internal fixation of right midshaft clavicle fracture',
                  findings='Comminuted midshaft fracture with a butterfly fragment and interposed periosteum. Supraclavicular nerve branch identified and protected.',
                  implant='Precontoured superior clavicle plate, 8-hole, with 7 cortical screws', ebl='40 mL', anes='General endotracheal with interscalene block'),
             dict(role='imaging', name='Northcrest Diagnostic Imaging', studies=[
                 dict(off=24, cpt='73000', name='RADIOGRAPH RIGHT CLAVICLE 2 VIEWS', ind='Status post ORIF right clavicle fracture',
                      findings=['Superior plate and seven screws spanning the midshaft clavicle fracture.', 'Fracture line visible with near-anatomic alignment.', 'No hardware loosening or periprosthetic lucency.', 'Acromioclavicular joint maintained.'],
                      impression='Postoperative fixation of right clavicle fracture in near-anatomic alignment; early healing.',
                      fix=(1, 'Fracture line visible with 2 mm residual superior displacement of the medial fragment.')),
                 dict(off=45, cpt='73030', name='RADIOGRAPH RIGHT SHOULDER 2+ VIEWS', ind='Shoulder stiffness after clavicle fixation',
                      findings=['Glenohumeral joint congruent.', 'Clavicle hardware intact.', 'No heterotopic ossification.'],
                      impression='No glenohumeral abnormality. Intact clavicle fixation.'),
                 dict(off=80, cpt='73000', name='RADIOGRAPH RIGHT CLAVICLE 2 VIEWS', ind='Follow-up of healing clavicle fracture',
                      findings=['Bridging callus across the fracture site.', 'Hardware intact without loosening.', 'Alignment unchanged from prior.'],
                      impression='Healed right clavicle fracture with intact hardware.')]),
             dict(role='therapy', name='Momentum Physical Therapy & Sports Rehab', ttype='Physical Therapy', start=26, n=16,
                  eval_cpt='97162', reeval_cpt='97164', cpts=['97110', '97140', '97530'], reeval_at=10, form='QuickDASH',
                  measure=('Right shoulder active flexion (deg)', 70, 165),
                  ex=['pendulums', 'table slides', 'pulley flexion', 'isometric rotator cuff', 'scapular retraction with band', 'wall walks', 'prone T and Y', 'serratus punch']),
         ]),
    dict(n=2, seed=31002, first='Desmond', last='Achebe-Lorne', sex='M', dob=D(1978, 11, 3), acc=D(2025, 1, 22),
         acc_time='07:55', city='Granite Hollow, MN 55999', short='slip and fall on ice',
         regions=['lumbar spine', 'left leg'],
         cc='Low back pain radiating to the left leg after slipping on ice',
         mech='slipped on an unsalted, ice-covered sidewalk outside a grocery store and fell backward onto his buttocks and lower back',
         sym='low back pain rated 7/10 with burning pain down the back of the left thigh to the calf',
         deny='head strike, bowel or bladder changes, saddle numbness or prior back surgery',
         exam='Paraspinal spasm L3-S1, tenderness at the lumbosacral junction. Straight leg raise positive on the left at 40 degrees. Strength 5/5 except left great toe extension 4+/5. Reflexes symmetric. Gait antalgic.',
         dx=[('S33.5XXA', 'Sprain of ligaments of lumbar spine, initial encounter'),
             ('M51.26', 'Other intervertebral disc displacement, lumbar region'),
             ('M54.16', 'Radiculopathy, lumbar region')],
         ext=[('W00.0XXA', 'Fall on same level due to ice and snow, initial encounter')],
         pmh='Hypertension. Episode of mechanical low back pain 2023 treated with chiropractic care, resolved.',
         allergy='No known drug allergies', home_meds='Lisinopril 10 mg daily',
         disch='Relative rest for 48 hours then walk as tolerated. Heat 20 minutes three times daily. Return for leg weakness, numbness in the groin or loss of bladder or bowel control.',
         providers=[
             dict(role='prior', name='Northfork Spine & Chiropractic', visits=[
                 dict(off=-610, cc='Low back stiffness after moving furniture', hpi='Two weeks of mechanical low back pain without leg symptoms.',
                      exam='Restricted lumbar flexion, no neurologic deficit.', codes=[('M54.50', 'Low back pain, unspecified')],
                      cpt=['98940'], plan='Adjustments for 3 visits, then home exercise.', summary='Prior mechanical low back pain, no radicular symptoms')]),
             dict(role='prior', name='Bramblewood Internal Medicine', visits=[
                 dict(off=-180, cc='Blood pressure follow-up', hpi='Home readings 128-136/80s. No back complaints.',
                      exam='BP 134/84. Normal exam. Lumbar spine nontender.', codes=[('I10', 'Essential (primary) hypertension')],
                      cpt=['99214'], plan='Continue lisinopril 10 mg. BMP. Return 6 months.', summary='Hypertension follow-up; no back complaints')]),
             dict(role='uc', name='Clínica Puente Urgent Care', bi=True, cpt=['99204'], extra=[],
                  course=['Ketorolac 60 mg IM given', 'Lumbar radiographs obtained', 'Lidocaine patch applied'],
                  img=[dict(cpt='72100', name='XR LUMBAR SPINE 2-3 VIEWS', findings=['Normal lumbar alignment.', 'No acute fracture or spondylolisthesis.', 'Mild disc space narrowing at L4-L5.'], impression='No acute osseous abnormality. Mild L4-L5 disc space narrowing.')],
                  plan='Naproxen 500 mg twice daily, cyclobenzaprine 5 mg at night, MRI if radicular pain persists beyond 2 weeks. Follow up with chiropractor or primary care.'),
             dict(role='imaging', name='Granite Hollow MRI & Imaging', studies=[
                 dict(off=18, cpt='72148', name='MRI LUMBAR SPINE WITHOUT CONTRAST', ind='Left L5 radiculopathy after fall on ice',
                      findings=['L3-L4: mild disc bulge without stenosis.', 'L4-L5: left paracentral disc extrusion measuring 6 mm, contacting the traversing left L5 nerve root.', 'L5-S1: small central protrusion without nerve root contact.', 'Conus terminates at L1. No marrow edema or fracture.'],
                      impression='Left paracentral L4-L5 disc extrusion contacting the left L5 nerve root.',
                      fix=(1, 'L4-L5: left paracentral disc extrusion measuring 9 mm with inferior migration, compressing the traversing left L5 nerve root.')),
                 dict(off=125, cpt='72114', name='RADIOGRAPHS LUMBAR SPINE WITH FLEXION/EXTENSION', ind='Persistent back pain, evaluate instability',
                      findings=['No dynamic instability.', 'Mild L4-L5 disc space narrowing, unchanged.'], impression='No instability on flexion-extension views.')]),
             dict(role='therapy', name='Northfork Spine & Chiropractic', ttype='Chiropractic', start=5, n=20, eval_cpt='99203',
                  reeval_cpt='99213', cpts=['98941', '97140', '97012'], reeval_at=12, form='Oswestry',
                  measure=('Lumbar flexion (deg)', 30, 70), merge_prior=True,
                  ex=['flexion-distraction', 'diversified adjustment L4-S1', 'thoracic adjustment', 'mechanical traction', 'instrument-assisted soft tissue', 'McKenzie extension']),
             dict(role='spec', name='Altamira Pain & Spine Institute', label='Pain Medicine', visits=[30, 56, 90], first_cpt='99204', fu_cpt='99214',
                  exam=['Positive left straight leg raise at 45 degrees. Diminished light touch over the left dorsal foot.', 'Straight leg raise positive at 60 degrees. Sensation improving.', 'Straight leg raise negative. Mild left EHL weakness persists.'],
                  plans=['Left L5 transforaminal epidural steroid injection. Gabapentin 300 mg at night.', 'About 50 percent relief after first injection. Repeat injection scheduled.', 'Sustained partial relief. Refer to neurosurgery for opinion. Continue gabapentin.'],
                  procs=[dict(off=42, cpts=['64483'], kind='injection', name='Left L5 transforaminal epidural steroid injection under fluoroscopy', detail='Triamcinolone 40 mg with 1 mL 0.25% bupivacaine. Contrast flow along the left L5 root without vascular uptake.'),
                         dict(off=70, cpts=['64483'], kind='injection', name='Repeat left L5 transforaminal epidural steroid injection under fluoroscopy', detail='Dexamethasone 10 mg with 1 mL 1% lidocaine. Epidurogram confirms spread to the L4-L5 foramen.')]),
             dict(role='spec', name='Whitlock Neurosurgical Group', label='Neurosurgery', visits=[100, 140], first_cpt='99204', fu_cpt='99213',
                  exam=['Mild left EHL weakness 4+/5, straight leg raise negative.', 'Strength full. Sensation intact.'],
                  plans=['No surgical indication now. Physical therapy with core stabilization. Discussed microdiscectomy if deficit progresses.', 'Improved. Continue home program. Return as needed.']),
             dict(role='therapy', name='Keystone Motion Physical Therapy', ttype='Physical Therapy', start=105, n=12, eval_cpt='97161',
                  reeval_cpt='97164', cpts=['97110', '97112', '97140'], reeval_at=8, form='Oswestry',
                  measure=('Lumbar flexion (deg)', 45, 75),
                  ex=['dead bug progression', 'bird dog', 'side plank', 'hip hinge with dowel', 'sciatic nerve glides', 'bridges', 'Pallof press']),
         ]),
    dict(n=3, seed=31003, first='Kenji', last='Oduya-Barrett', sex='M', dob=D(2003, 2, 17), acc=D(2025, 5, 10),
         acc_time='15:20', city='Brookhaven Springs, CO 80999', short='trampoline park landing injury',
         regions=['right knee'],
         cc='Right knee pain and swelling after awkward landing at a trampoline park',
         mech='was performing a twisting jump at an indoor trampoline park and landed on the padded edge with his right knee buckling inward with a pop',
         sym='immediate right knee pain rated 7/10, rapid swelling and a sense that the knee gives way',
         deny='hip or ankle pain, numbness in the foot or prior surgery on the knee',
         exam='Large right knee effusion. Lachman test positive with soft endpoint. Medial joint line tenderness. Range of motion 10 to 85 degrees limited by swelling. Neurovascularly intact distally.',
         dx=[('S83.511A', 'Sprain of anterior cruciate ligament of right knee, initial encounter'),
             ('S83.241A', 'Other tear of medial meniscus, current injury, right knee, initial encounter')],
         ext=[('W09.8XXA', 'Fall on or from other playground equipment, initial encounter'), ('Y93.44', 'Activity, trampolining')],
         pmh='Right ankle sprain 2023, resolved. Otherwise healthy.', allergy='No known drug allergies', home_meds='None',
         disch='Knee immobilizer and crutches, weight bearing as tolerated. Ice and elevate. Return for calf pain, numbness or a cold foot.',
         providers=[
             dict(role='prior', name='Brookhaven Student Health Clinic', visits=[
                 dict(off=-300, cc='Pre-participation physical', hpi='Plays club volleyball. No current complaints.',
                      exam='Normal musculoskeletal screen. Knees stable, full motion.', codes=[('Z00.00', 'Encounter for general adult medical examination without abnormal findings')],
                      cpt=['99395'], plan='Cleared for sport.', summary='Sports physical, normal knees')]),
             dict(role='prior', name='Cedar Lane Sports Medicine', visits=[
                 dict(off=-880, cc='Right ankle injury playing volleyball', hpi='Inversion injury yesterday, able to bear weight.',
                      exam='ATFL tenderness, negative Ottawa rules. Knee exam normal.', codes=[('S93.401A', 'Sprain of unspecified ligament of right ankle, initial encounter')],
                      cpt=['99213'], plan='Lace-up brace, home exercise.', summary='Prior right ankle sprain; knee normal')]),
             dict(role='uc', name='QuickStep Urgent Care - Brookhaven', cpt=['99203'], extra=[],
                  course=['Ibuprofen 800 mg PO given', 'Knee radiographs obtained', 'Knee immobilizer fitted', 'Crutch training completed'],
                  img=[dict(cpt='73562', name='XR KNEE RIGHT 3 VIEWS', findings=['Moderate suprapatellar effusion.', 'Small avulsion fragment at the lateral tibial plateau (Segond).', 'No other fracture.'], impression='Joint effusion with Segond fracture, suggesting ACL injury.')],
                  plan='Knee immobilizer, crutches, ibuprofen 600 mg every 6 hours. MRI and sports orthopaedics referral.'),
             dict(role='imaging', name='Halcyon Imaging Partners', studies=[
                 dict(off=5, cpt='73721', name='MRI RIGHT KNEE WITHOUT CONTRAST', ind='Knee injury with Segond fracture',
                      findings=['Complete tear of the anterior cruciate ligament at the femoral attachment.', 'Vertical tear of the posterior horn of the medial meniscus.', 'Bone bruises of the lateral femoral condyle and posterolateral tibial plateau.', 'MCL low-grade sprain. PCL and LCL intact.'],
                      impression='Complete ACL tear and medial meniscus posterior horn tear with typical pivot-shift bone bruising.',
                      fix=(1, 'Bucket-handle tear of the medial meniscus with a displaced fragment in the intercondylar notch.')),
                 dict(off=60, cpt='73562', name='XR KNEE RIGHT 3 VIEWS', ind='Status post ACL reconstruction',
                      findings=['Femoral and tibial tunnels with interference screws in expected position.', 'Small effusion.', 'No hardware complication.'],
                      impression='Expected appearance after ACL reconstruction.')]),
             dict(role='spec', name='Pinecrest Sports Orthopedics', label='Sports Medicine & Orthopaedics', visits=[8, 20, 40, 75, 120, 170],
                  first_cpt='99204', fu_cpt='99213',
                  exam=['Effusion, Lachman 3+, pivot shift positive, medial joint line tenderness.', 'Effusion smaller, motion 0-120. Lachman 3+.', 'Post-op day 14: portals healed, motion 0-95, quadriceps lag 10 degrees.', 'Motion 0-125. Lachman 1+ firm endpoint.', 'Motion full. Single leg squat good.', 'Full motion, stable knee, hop test 88 percent of the other side.'],
                  plans=['Arthroscopic ACL reconstruction with medial meniscus repair or meniscectomy. Pre-hab exercises.', 'Surgery scheduled. Consent obtained.', 'Start formal physical therapy, ACL protocol. Brace locked for ambulation 2 more weeks.', 'Progress therapy, begin stationary bike resistance.', 'Begin straight-line jogging.', 'Cleared for return to sport testing, no trampolining for 9 months total.']),
             dict(role='asc', name='Pinecrest Ambulatory Surgery Center', off=26, cpts=['29888', '29881'],
                  proc='Right knee arthroscopic ACL reconstruction with hamstring autograft and partial medial meniscectomy',
                  findings='Complete ACL tear. Unrepairable complex tear of the posterior horn of the medial meniscus. Articular cartilage intact.',
                  implant='Femoral suspensory button and 9 x 25 mm tibial interference screw', ebl='25 mL', anes='General with adductor canal block'),
             dict(role='therapy', name='Rebound Physical Therapy Collective', ttype='Physical Therapy', start=30, n=22,
                  eval_cpt='97163', reeval_cpt='97164', cpts=['97110', '97112', '97530'], reeval_at=12, form='LEFS',
                  measure=('Right knee flexion (deg)', 85, 135),
                  ex=['quad sets', 'straight leg raise', 'heel slides', 'mini squats', 'step-ups', 'single leg balance', 'stationary bike', 'lateral band walks', 'leg press 0-60']),
         ]),
    dict(n=4, seed=31004, first='Priya', last='Castellane-Moore', sex='F', dob=D(1981, 9, 9), acc=D(2025, 2, 7),
         acc_time='08:15', city='Hollowmere, WA 98999', short='rideshare rear-end collision',
         regions=['cervical spine', 'jaw', 'temporomandibular joints', 'head'],
         cc='Neck pain, jaw pain and headache after rear-end collision',
         mech='was the rear-seat passenger in a rideshare sedan stopped at a light when it was struck from behind by another car at about 30 mph; her head whipped forward and back and her chin struck the seat-back in front of her',
         sym='neck pain rated 6/10, pain in both jaw joints when chewing and a frontal headache',
         deny='loss of consciousness, vomiting, arm weakness or numbness',
         exam='Paraspinal tenderness C3-C7 without midline step-off. Cervical rotation limited 50 percent. Bilateral TMJ tenderness, mouth opening 28 mm with deviation to the left. Neuro exam normal.',
         dx=[('S13.4XXA', 'Sprain of ligaments of cervical spine, initial encounter'),
             ('S03.43XA', 'Sprain of jaw, bilateral, initial encounter'),
             ('M26.623', 'Arthralgia of bilateral temporomandibular joint')],
         ext=[('V43.62XA', 'Car passenger injured in collision with other type car in traffic accident, initial encounter')],
         pmh='Migraine without aura, about two a year. No prior neck or jaw problems.', allergy='Codeine (nausea)',
         home_meds='Sumatriptan 50 mg as needed',
         disch='Soft diet for one week. Heat or ice to the neck. Return for worsening headache, vomiting, weakness or numbness.',
         providers=[
             dict(role='prior', name='Seabright Dental Group', visits=[
                 dict(off=-150, cc='Routine cleaning and exam', hpi='No dental complaints. No jaw pain or clicking.',
                      exam='Normal occlusion. TMJ without clicking, opening 46 mm.', codes=[('Z01.20', 'Encounter for dental examination and cleaning without abnormal findings')],
                      cpt=[], plan='Recall in 6 months.', summary='Routine dental exam; normal TMJ, opening 46 mm')]),
             dict(role='prior', name='Halverson Internal Medicine', visits=[
                 dict(off=-500, cc='Annual preventive visit', hpi='Occasional migraine. No neck pain.',
                      exam='Normal exam. Full cervical motion.', codes=[('Z00.00', 'Encounter for general adult medical examination without abnormal findings'), ('G43.009', 'Migraine without aura, not intractable, without status migrainosus')],
                      cpt=['99396'], plan='Continue sumatriptan as needed.', summary='Annual physical; migraine history, normal neck')]),
             dict(role='er', name='Hollowmere Regional Hospital', cpt=['99284'], extra=[],
                  course=['Cervical collar maintained pending imaging', 'CT cervical spine obtained', 'Acetaminophen 1000 mg PO given', 'Collar cleared clinically after negative CT'],
                  img=[dict(cpt='72125', name='CT CERVICAL SPINE WITHOUT CONTRAST', findings=['No acute fracture or malalignment.', 'Straightening of the normal cervical lordosis.', 'Prevertebral soft tissues normal.'], impression='No acute cervical spine fracture. Straightened lordosis, which may reflect muscle spasm.')],
                  plan='Acetaminophen and naproxen, soft diet, primary care or chiropractic follow-up, dental follow-up for jaw pain.'),
             dict(role='therapy', name='Tidewater Chiropractic Wellness', ttype='Chiropractic', start=3, n=18, eval_cpt='99203',
                  reeval_cpt='99213', cpts=['98940', '97140', '97110'], reeval_at=10, form='NDI',
                  measure=('Cervical rotation right (deg)', 40, 75),
                  ex=['cervical diversified adjustment', 'upper thoracic adjustment', 'suboccipital release', 'trigger point therapy upper trapezius', 'deep neck flexor training', 'chin tucks']),
             dict(role='imaging', name='Clearwater Open MRI', studies=[
                 dict(off=20, cpt='72141', name='MRI CERVICAL SPINE WITHOUT CONTRAST', ind='Neck pain after motor vehicle collision',
                      findings=['C4-C5: small central disc protrusion without cord contact.', 'C5-C6: broad-based disc bulge with mild left foraminal narrowing.', 'No cord signal abnormality.', 'No prevertebral edema.'],
                      impression='Small C4-C5 protrusion and C5-C6 bulge with mild left foraminal narrowing.',
                      fix=(1, 'C5-C6: broad-based disc bulge with moderate left foraminal narrowing.')),
                 dict(off=35, cpt='70336', name='MRI BILATERAL TEMPOROMANDIBULAR JOINTS', ind='Bilateral TMJ pain after collision',
                      findings=['Right TMJ: anterior disc displacement with reduction.', 'Left TMJ: anterior disc displacement without reduction, small joint effusion.', 'No condylar fracture.'],
                      impression='Bilateral anterior disc displacement, without reduction on the left, with left joint effusion.')]),
             dict(role='spec', name='Orofacial Pain & TMJ Center of Brennan County', label='Orofacial Pain', visits=[14, 28, 57, 90],
                  first_cpt='99204', fu_cpt='99213',
                  exam=['Opening 27 mm, deviation left, bilateral masseter and temporalis tenderness, left joint closed lock signs.', 'Opening 31 mm, reciprocal click right.', 'Opening 35 mm, trigger points in bilateral masseters.', 'Opening 41 mm, mild tenderness left joint.'],
                  plans=['Soft diet, jaw rest, naproxen. Fabricate stabilization splint for nighttime use.', 'Splint delivered and adjusted. TMJ MRI reviewed. Jaw exercises.', 'Trigger point injections bilateral masseters today. Continue splint.', 'Improving. Continue splint at night. Return in 3 months.'],
                  visit_procs={2: ['20552']}),
             dict(role='spec', name='Lindqvist Neurology Associates', label='Neurology', visits=[45, 100], first_cpt='99204', fu_cpt='99214',
                  exam=['Normal neurologic exam. Pericranial tenderness.', 'Normal neurologic exam.'],
                  plans=['Post-traumatic headache superimposed on prior migraine. Amitriptyline 10 mg at night. Headache diary.', 'Headache days down from 14 to 5 per month. Continue amitriptyline.'],
                  dx_extra=[('G44.309', 'Post-traumatic headache, unspecified, not intractable')]),
             dict(role='therapy', name='Harborlight Physical Therapy', ttype='Physical Therapy', start=40, n=10, eval_cpt='97162',
                  reeval_cpt='97164', cpts=['97110', '97140', '97112'], reeval_at=7, form='NDI',
                  measure=('Cervical rotation right (deg)', 55, 80),
                  ex=['jaw controlled opening', 'tongue-up rotations', 'deep neck flexor holds', 'scapular retraction', 'thoracic extension over roll', 'manual TMJ distraction']),
         ]),
    dict(n=5, seed=31005, first='Tobias', last='Renwick-Salazar', sex='M', dob=D(1969, 4, 30), acc=D(2025, 6, 3),
         acc_time='12:05', city='Quarry Point, ME 04999', short='struck by falling storefront sign',
         regions=['upper lip', 'maxillary incisors', 'face'],
         cc='Broken front teeth and upper lip laceration after being hit by a falling sign',
         mech='was walking on a downtown sidewalk when a hanging storefront sign broke from its bracket and struck him in the face',
         sym='bleeding from the upper lip, two broken upper front teeth and one loose tooth',
         deny='loss of consciousness, vision change, neck pain or difficulty breathing',
         exam='1.8 cm full-thickness laceration of the upper lip crossing the vermilion border. Teeth #8 and #9 fractured with pulp exposure on #8; tooth #7 mobile and displaced palatally. No facial bone step-off.',
         dx=[('S02.5XXA', 'Fracture of tooth (traumatic), initial encounter for closed fracture'),
             ('S03.2XXA', 'Dislocation of tooth, initial encounter'),
             ('S01.511A', 'Laceration without foreign body of lip, initial encounter')],
         ext=[('W20.8XXA', 'Other cause of strike by thrown, projected or falling object, initial encounter')],
         pmh='Type 2 diabetes, diet controlled. Prior dental crowns on lower molars.', allergy='Penicillin (hives)',
         home_meds='None', disch='Rinse with salt water after meals. Soft diet. Sutures out in 5 days. See oral surgery tomorrow.',
         providers=[
             dict(role='prior', name='Marigold Family Dentistry', visits=[
                 dict(off=-180, cc='Six-month recall', hpi='No complaints.', exam='Anterior teeth intact, no mobility. Crowns #19 and #30 intact.',
                      codes=[('Z01.20', 'Encounter for dental examination and cleaning without abnormal findings')], cpt=[],
                      plan='Recall 6 months.', summary='Routine dental recall; anterior teeth intact')]),
             dict(role='prior', name='Ridgeview Primary Care', visits=[
                 dict(off=-400, cc='Annual visit and diabetes check', hpi='A1c 6.4 on diet alone.', exam='Normal exam.',
                      codes=[('Z00.01', 'Encounter for general adult medical examination with abnormal findings'), ('E11.9', 'Type 2 diabetes mellitus without complications')],
                      cpt=['99396'], plan='Continue diet. A1c in 6 months.', summary='Annual physical; diet-controlled diabetes')]),
             dict(role='er', name='Quarry Point Medical Center', cpt=['99283'], extra=['12011'],
                  course=['Lidocaine with epinephrine infraorbital block', 'Lip laceration repaired, vermilion border aligned first', 'CT maxillofacial obtained', 'Clindamycin 300 mg PO given (penicillin allergy)'],
                  img=[dict(cpt='70486', name='CT MAXILLOFACIAL WITHOUT CONTRAST', findings=['Fractures of the crowns of the right and left maxillary central incisors.', 'Palatal displacement of the right maxillary lateral incisor with widened periodontal ligament space.', 'No alveolar or facial bone fracture.'], impression='Dental fractures and luxation without facial fracture.')],
                  plan='Lip repair with 6-0 nylon and 5-0 chromic. Clindamycin 300 mg four times daily for 5 days. Oral surgery next day.'),
             dict(role='spec', name='Sterling Oral & Maxillofacial Surgery', label='Oral & Maxillofacial Surgery', visits=[1, 8, 21, 45, 90],
                  first_cpt='99203', fu_cpt='99212', dental=True,
                  exam=['#7 palatally luxated, #8 complicated crown fracture, #9 uncomplicated crown fracture. Lip sutures intact.', 'Splint intact, #7 firm. Lip healing.', 'Splint removed, #7 mobility grade 1.', '#7 vitality test negative.', 'Teeth stable, gingiva healthy.'],
                  plans=['Repositioned #7 and placed flexible wire-composite splint 7-10. Pulp cap on #8. Endodontics referral.', 'Lip sutures removed. Splint maintained. Soft diet.', 'Splint removed. Monitor vitality.', '#7 now nonvital. Endodontics for #7. Discussed crowns.', 'Stable. Restorative dentist for permanent crowns.'],
                  visit_procs={0: ['41899', '70355'], 2: ['41899']}),
             dict(role='spec', name='Lumen Endodontic Specialists', label='Endodontics', visits=[10, 24, 60], first_cpt='99203', fu_cpt='99212', dental=True,
                  exam=['#8 pulp exposure, sensitive to cold. #9 vital.', '#8 asymptomatic after pulpectomy.', '#7 nonvital, periapical lucency.'],
                  plans=['Pulpectomy #8, calcium hydroxide placed.', 'Obturation #8 completed.', 'Root canal therapy #7 initiated.'],
                  visit_procs={0: ['41899'], 1: ['41899'], 2: ['41899']}),
             dict(role='imaging', name='Vantage Dental & Facial Imaging', studies=[
                 dict(off=30, cpt='70355', name='PANORAMIC RADIOGRAPH (ORTHOPANTOGRAM)', ind='Dental trauma follow-up',
                      findings=['Endodontic fill in #8 to working length.', 'Widened periodontal ligament space at #7.', 'No root fracture identified.', 'Restorations #19 and #30 intact.'],
                      impression='Treated #8. Persistent PDL widening at #7 without root fracture.',
                      fix=(2, 'Horizontal root fracture of #7 at the junction of the middle and apical thirds.')),
                 dict(off=120, cpt='70355', name='PANORAMIC RADIOGRAPH (ORTHOPANTOGRAM)', ind='Follow-up after endodontic treatment',
                      findings=['Endodontic fills #7 and #8.', 'Periapical lucency #7 decreasing.'], impression='Healing periapical lesion #7.')]),
             dict(role='spec', name='Ashgrove Plastic & Reconstructive Surgery', label='Plastic Surgery', visits=[70, 150], first_cpt='99203', fu_cpt='99212',
                  exam=['Hypertrophic scar across the right upper lip vermilion border with 1.5 mm step-off.', 'Revised scar flat, vermilion aligned.'],
                  plans=['Scar revision of the upper lip under local anesthesia.', 'Healed. Silicone gel for 2 more months.'],
                  procs=[dict(off=120, cpts=['13151'], kind='surgery', name='Excision and complex layered repair of upper lip scar, 2.1 cm', detail='Fusiform excision, orbicularis reapproximated with 5-0 Monocryl, vermilion border aligned, 6-0 nylon skin.')]),
         ]),
    dict(n=6, seed=31006, first='Annelise', last='Moreau-Kipling', sex='F', dob=D(1986, 12, 12), acc=D(2025, 8, 19),
         acc_time='18:30', city='Westmere, IA 52999', short='scald burn from defective pressure cooker',
         regions=['right hand', 'right forearm'],
         cc='Scald burns to the right hand and forearm from a pressure cooker',
         mech='was cooking with an electric pressure cooker when the lid released while still pressurized and sprayed boiling contents over her right hand and forearm',
         sym='severe burning pain rated 9/10 with blistering of the back of the right hand and forearm',
         deny='facial or airway burns, inhalation of steam or other injuries',
         exam='Partial-thickness burns of the dorsal right hand and fingers and the volar and dorsal distal forearm, blistered and moist, about 4 percent total body surface area. Capillary refill brisk. No circumferential burn.',
         dx=[('T23.201A', 'Burn of second degree of right hand, unspecified site, initial encounter'),
             ('T22.211A', 'Burn of second degree of right forearm, initial encounter'),
             ('T31.0', 'Burns involving less than 10% of body surface')],
         ext=[('X15.8XXA', 'Contact with other hot household appliances, initial encounter')],
         pmh='Seasonal allergies. Right-hand dominant.', allergy='No known drug allergies', home_meds='Cetirizine 10 mg daily',
         disch='Transfer to burn center for admission.',
         providers=[
             dict(role='prior', name='Tamarind Family Practice', visits=[
                 dict(off=-250, cc='Allergy symptoms', hpi='Spring sneezing and itchy eyes.', exam='Boggy nasal turbinates. Skin normal.',
                      codes=[('J30.9', 'Allergic rhinitis, unspecified')], cpt=['99213'], plan='Cetirizine and nasal steroid.', summary='Allergic rhinitis; skin normal')]),
             dict(role='ems', name='Coldwater County EMS - Unit 14', course=['Cool sterile saline to burns for 10 minutes', 'Dry sterile dressing', 'Fentanyl 75 mcg IV given', 'Right hand elevated']),
             dict(role='er', name='Westmere General Hospital', cpt=['99285'], extra=[],
                  course=['Morphine 4 mg IV given', 'Burns cleansed and blisters left intact', 'Tetanus-diphtheria-pertussis booster given', 'Burn center accepted transfer'],
                  img=[], plan='Transfer to burn center by ground ambulance for hand burn care.', dispo='Transferred to Halloran Regional Burn Center.'),
             dict(role='hospital', name='Halloran Regional Burn Center', off=0, days=5, reason='partial-thickness scald burns of the dominant right hand and forearm',
                  surgery=dict(day=2, cpts=['15004', '15120'], name='Tangential excision and split-thickness skin graft to dorsal right hand, 85 sq cm',
                               findings='Deep partial-thickness burn of dorsal hand and index-long fingers. Donor site right anterior thigh.', implant='Split-thickness skin graft 0.012 inch meshed 1:1', ebl='60 mL', anes='General endotracheal'),
                  course=['Burns debrided at bedside, silver dressing applied. Hand splinted in safe position.', 'Dorsal hand appears deep partial thickness; surgery planned.', 'Excision and grafting performed.', 'Graft take about 95 percent at first dressing change. Donor site comfortable.', 'Stable for discharge with outpatient burn clinic and hand therapy.']),
             dict(role='spec', name='Halloran Burn & Wound Clinic', label='Burn Surgery', visits=[12, 19, 26, 40, 62, 100],
                  first_cpt='99214', fu_cpt='99213',
                  exam=['Graft 98 percent adherent, forearm wounds 80 percent healed.', 'Graft stable, small open area 1 cm over long finger MP joint.', 'All wounds closed.', 'Early hypertrophic scarring dorsal hand.', 'Scar pink and raised, MP flexion improving.', 'Scar softening, flat in most areas.'],
                  plans=['Dressing change, compression glove fitting.', 'Silver dressing to open area.', 'Start silicone sheeting, compression garments 23 hours a day.', 'Continue compression, scar massage.', 'Refer for laser scar treatment.', 'Continue garments 6 more months.'],
                  visit_procs={0: ['16020'], 1: ['16020'], 2: ['16020']}),
             dict(role='therapy', name='Dexterity Hand Therapy', ttype='Occupational Therapy', start=14, n=18, eval_cpt='97166',
                  reeval_cpt='97168', cpts=['97530', '97110', '97140'], reeval_at=11, form='QuickDASH',
                  measure=('Right grip strength (lb)', 12, 48),
                  ex=['tendon gliding', 'composite fist stretch', 'putty grip', 'retrograde massage', 'scar mobilization', 'fine motor pegboard', 'wrist flexion-extension with weight']),
             dict(role='spec', name='Lumina Dermatology & Laser', label='Dermatology', visits=[150, 185], first_cpt='99203', fu_cpt='99213',
                  exam=['Erythematous hypertrophic scar dorsal right hand 9 x 7 cm.', 'Erythema reduced after first session.'],
                  plans=['Pulsed dye laser to scar today, series of 3.', 'Second pulsed dye laser session today.'],
                  visit_procs={0: ['17106'], 1: ['17106']}),
         ]),
    dict(n=7, seed=31007, first='Harold', last='Vasquez-Whitcombe', sex='M', dob=D(1957, 7, 4), acc=D(2025, 4, 26),
         acc_time='10:50', city='Kingsferry, SC 29999', short='golf-cart rollover',
         regions=['right chest wall', 'ribs', 'right shoulder'],
         cc='Right chest wall pain and shortness of breath after golf-cart rollover',
         mech='was the passenger in a golf cart that tipped onto its right side while turning on a sloped cart path, pinning his right chest under the frame',
         sym='severe right chest pain with breathing rated 9/10 and shortness of breath',
         deny='head strike, loss of consciousness, abdominal pain or blood in the urine',
         exam='Tenderness and crepitus over right ribs 5 through 8 laterally. Decreased breath sounds at the right apex. Abdomen soft. Right shoulder contusion without deformity.',
         dx=[('S22.41XA', 'Multiple fractures of ribs, right side, initial encounter for closed fracture'),
             ('S27.0XXA', 'Traumatic pneumothorax, initial encounter'),
             ('S40.011A', 'Contusion of right shoulder, initial encounter')],
         ext=[('V89.0XXA', 'Person injured in unspecified motor-vehicle accident, nontraffic, initial encounter')],
         pmh='Hypertension, hyperlipidemia. Former smoker, quit 2010.', allergy='No known drug allergies',
         home_meds='Amlodipine 5 mg daily, atorvastatin 20 mg daily', disch='Admitted.',
         providers=[
             dict(role='prior', name='Juniper Ridge Internal Medicine', visits=[
                 dict(off=-470, cc='Annual Medicare wellness and physical', hpi='Plays golf twice a week. No breathing problems.',
                      exam='Lungs clear. Normal chest wall.', codes=[('Z00.00', 'Encounter for general adult medical examination without abnormal findings')],
                      cpt=['99397'], plan='Lipid panel, colonoscopy due.', summary='Annual physical; lungs normal'),
                 dict(off=-100, cc='Blood pressure check', hpi='Home BP 130s/80s.', exam='BP 138/82, lungs clear.',
                      codes=[('I10', 'Essential (primary) hypertension'), ('E78.5', 'Hyperlipidemia, unspecified')],
                      cpt=['99214'], plan='Continue amlodipine and atorvastatin.', summary='Hypertension and lipid follow-up')]),
             dict(role='ems', name='Saltmarsh Township Rescue Squad', course=['Oxygen 4 L by nasal cannula', 'Splinting with pillow', 'Fentanyl 50 mcg IV given', 'Trauma alert called']),
             dict(role='er', name='Ostrander Valley Hospital', cpt=['99285'], extra=[],
                  course=['Trauma team evaluation', 'CT chest with contrast obtained', 'Hydromorphone 0.5 mg IV given', 'Transfer to Kingsferry Medical Center trauma service accepted'],
                  img=[dict(cpt='71260', name='CT CHEST WITH CONTRAST', findings=['Displaced fractures of right ribs 5, 6 and 7 laterally; nondisplaced right rib 8 fracture.', 'Small right apical pneumothorax, about 15 percent.', 'Right lower lobe contusion.', 'No mediastinal injury.'], impression='Four right rib fractures with small pneumothorax and pulmonary contusion.')],
                  plan='Transfer to level II trauma center for possible chest tube and pain control.', dispo='Transferred to Kingsferry Medical Center.'),
             dict(role='hospital', name='Kingsferry Medical Center', off=0, days=5, reason='right rib fractures 5-8 with pneumothorax and pulmonary contusion',
                  surgery=dict(day=0, cpts=['32551'], name='Right tube thoracostomy, 24 French', findings='Rush of air on entry. Tube to -20 cm water suction.', implant='24 Fr chest tube', ebl='minimal', anes='Local with IV sedation'),
                  course=['Chest tube placed for enlarging pneumothorax. Incentive spirometry 750 mL.', 'Air leak resolved. Incentive spirometry 1000 mL.', 'Chest tube to water seal, lung expanded.', 'Chest tube removed, no recurrent pneumothorax.', 'Ambulating, pain controlled on oral medicines. Discharged.']),
             dict(role='imaging', name='Bayline Radiology Associates', studies=[
                 dict(off=14, cpt='71046', name='CHEST RADIOGRAPH 2 VIEWS', ind='Follow-up rib fractures and pneumothorax',
                      findings=['No pneumothorax.', 'Healing right rib fractures 5 through 8.', 'Small right pleural effusion.', 'Linear atelectasis right base.'],
                      impression='No recurrent pneumothorax. Small right effusion.',
                      fix=(2, 'Moderate right pleural effusion, increased from the discharge film.')),
                 dict(off=42, cpt='71046', name='CHEST RADIOGRAPH 2 VIEWS', ind='Follow-up effusion',
                      findings=['Effusion resolved.', 'Callus at right rib fractures.'], impression='Resolved effusion. Healing fractures.')]),
             dict(role='spec', name='Kingsferry Pulmonary & Sleep', label='Pulmonology', visits=[14, 42, 90], first_cpt='99204', fu_cpt='99213',
                  exam=['Splinted breathing, decreased right base breath sounds.', 'Breath sounds improved.', 'Clear lungs.'],
                  plans=['Spirometry shows restriction (FVC 62 percent). Incentive spirometry, continue analgesia.', 'FVC 74 percent. Continue rehab.', 'Spirometry FVC 88 percent. Discharge from clinic.'],
                  visit_procs={0: ['94010'], 2: ['94010']}),
             dict(role='spec', name='Coastal Interventional Pain Center', label='Pain Medicine', visits=[21, 50], first_cpt='99204', fu_cpt='99213',
                  exam=['Point tenderness right ribs 5-8 posterolaterally, pain 7/10 with deep breath.', 'Tenderness reduced, pain 3/10.'],
                  plans=['Right intercostal nerve blocks T5-T8.', 'Good response. Wean opioid. Return as needed.'],
                  procs=[dict(off=30, cpts=['64420', '64421'], kind='injection', name='Right intercostal nerve blocks T5 through T8 under ultrasound guidance', detail='Bupivacaine 0.25% 4 mL with dexamethasone 2 mg at each of four levels.')]),
             dict(role='therapy', name='Second Wind Rehabilitation', ttype='Physical Therapy', start=35, n=12, eval_cpt='97162',
                  reeval_cpt='97164', cpts=['97110', '97530', '97112'], reeval_at=8, form='PSFS',
                  measure=('Six-minute walk distance (m)', 280, 450),
                  ex=['diaphragmatic breathing', 'incentive spirometry', 'treadmill walking', 'thoracic rotation', 'sit to stand', 'step training', 'scapular setting']),
         ]),
    dict(n=8, seed=31008, first='Saoirse', last='Delgado-Fenwick', sex='F', dob=D(1996, 1, 29), acc=D(2025, 7, 12),
         acc_time='09:40', city='Thornbury, VA 24999', short='fall from horse',
         regions=['head', 'neck'],
         cc='Headache, dizziness and neck pain after being thrown from a horse',
         mech='was riding at a boarding stable when the horse spooked and she was thrown, striking the left side of her helmeted head on the arena rail',
         sym='headache rated 7/10, dizziness, nausea, light sensitivity and neck pain; witnesses report she was unresponsive for about 1 minute',
         deny='vomiting more than once, weakness, numbness or vision loss',
         exam='GCS 15. Amnesic for the fall. Left parietal tenderness, no hematoma. Neck paraspinal tenderness without midline tenderness. Positive vestibulo-ocular provocation. Normal strength and sensation.',
         dx=[('S06.0X1A', 'Concussion with loss of consciousness of 30 minutes or less, initial encounter'),
             ('S16.1XXA', 'Strain of muscle, fascia and tendon at neck level, initial encounter')],
         ext=[('V80.010A', 'Animal-rider injured by fall from or being thrown from horse in noncollision accident, initial encounter')],
         pmh='No prior concussion. Anxiety, mild, untreated.', allergy='No known drug allergies', home_meds='None',
         disch='Cognitive and physical rest for 48 hours then gradual return. No riding until cleared. Return for worsening headache, repeated vomiting, confusion or weakness.',
         providers=[
             dict(role='prior', name='Glenmoor Health Associates', visits=[
                 dict(off=-365, cc='Annual exam', hpi='Rides horses weekly. No headaches.', exam='Normal neurologic exam.',
                      codes=[('Z00.00', 'Encounter for general adult medical examination without abnormal findings')],
                      cpt=['99395'], plan='Routine.', summary='Annual exam, normal neurologic exam')]),
             dict(role='prior', name='Bridle Path Chiropractic', visits=[
                 dict(off=-700, cc='Neck stiffness', hpi='Two weeks of neck stiffness after long drive.', exam='Restricted cervical rotation.',
                      codes=[('M54.2', 'Cervicalgia')], cpt=['98940'], plan='Two adjustments.', summary='Prior cervicalgia, resolved')]),
             dict(role='ems', name='Thornbury Valley Ambulance', course=['Cervical collar applied', 'Spinal motion restriction', 'Ondansetron 4 mg IV given', 'Serial GCS 15']),
             dict(role='er', name='Fallowfield General Hospital', cpt=['99285'], extra=[],
                  course=['CT head obtained', 'Ondansetron 4 mg IV and acetaminophen 1000 mg PO given', 'Collar cleared by NEXUS criteria', 'Observed 4 hours, symptoms stable'],
                  img=[dict(cpt='70450', name='CT HEAD WITHOUT CONTRAST', findings=['No intracranial hemorrhage.', 'No skull fracture.', 'Small left parietal scalp swelling.'], impression='No acute intracranial abnormality.')],
                  plan='Concussion instructions, acetaminophen, neurology follow-up within 2 weeks.'),
             dict(role='imaging', name='Cobalt Imaging Center', studies=[
                 dict(off=25, cpt='70551', name='MRI BRAIN WITHOUT CONTRAST', ind='Persistent post-concussion symptoms',
                      findings=['No intracranial hemorrhage or contusion.', 'No microhemorrhage on susceptibility images.', 'Normal ventricles.', 'Paranasal sinuses clear.'],
                      impression='Normal MRI of the brain.',
                      fix=(1, 'Single punctate focus of susceptibility in the left frontal subcortical white matter, possibly microhemorrhage.'))]),
             dict(role='spec', name='Brightline Neurology & Headache Clinic', label='Neurology', visits=[10, 40, 90, 150], first_cpt='99204', fu_cpt='99214',
                  exam=['Normal neurologic exam, abnormal VOMS with symptom provocation.', 'Mild convergence insufficiency.', 'VOMS near normal.', 'Normal exam.'],
                  plans=['Vestibular therapy, sub-symptom aerobic exercise, MRI brain.', 'MRI reviewed. Neuropsychological testing ordered. Nortriptyline 10 mg.', 'Improving. Return to work full time.', 'Post-concussion symptoms largely resolved. Graduated return to riding.'],
                  dx_extra=[('F07.81', 'Postconcussional syndrome')]),
             dict(role='therapy', name='Equilibrium Vestibular Therapy', ttype='Vestibular Physical Therapy', start=20, n=14, eval_cpt='97162',
                  reeval_cpt='97164', cpts=['97112', '97530', '97110'], reeval_at=9, form='DHI',
                  measure=('Dynamic Gait Index (0-24)', 14, 23),
                  ex=['VOR x1 viewing', 'saccade training', 'smooth pursuit', 'tandem walking', 'head turns while walking', 'stationary bike sub-symptom', 'optokinetic exposure']),
             dict(role='spec', name='Calloway Neuropsychology Group', label='Neuropsychology', visits=[60, 75], first_cpt='96116', fu_cpt='96132',
                  exam=['Testing administered: processing speed 18th percentile, working memory 32nd percentile.', 'Feedback session.'],
                  plans=['Complete testing battery; feedback in 2 weeks.', 'Mild processing speed weakness consistent with recent concussion. Workplace accommodations for 2 months.'],
                  visit_procs={0: ['96136', '96137']}),
         ]),
    dict(n=9, seed=31009, first='Leopold', last='Abernathy-Osei', sex='M', dob=D(1973, 3, 15), acc=D(2025, 9, 5),
         acc_time='19:30', city='Calderon Bay, CA 93999', short='restaurant food poisoning',
         regions=['gastrointestinal tract', 'kidneys'],
         cc='Fever, bloody diarrhea and vomiting after restaurant meal',
         mech='ate a chicken and rice dish at a restaurant on the evening of the incident and developed cramping, fever and diarrhea about 14 hours later',
         sym='more than 12 watery and later bloody stools a day, vomiting, fever to 102.6 F and lightheadedness on standing',
         deny='recent travel, antibiotics, sick contacts at home or prior bowel disease',
         exam='Dry mucous membranes, orthostatic. Diffuse abdominal tenderness without guarding. Hyperactive bowel sounds.',
         dx=[('A02.0', 'Salmonella enteritis'), ('E86.0', 'Dehydration'), ('N17.9', 'Acute kidney failure, unspecified')],
         ext=[], pmh='Gastroesophageal reflux. No kidney disease.', allergy='No known drug allergies',
         home_meds='Omeprazole 20 mg daily', disch='Admitted.',
         providers=[
             dict(role='prior', name='Pinewood Primary Care', visits=[
                 dict(off=-400, cc='Heartburn', hpi='Reflux after late meals.', exam='Normal abdominal exam.', codes=[('K21.9', 'Gastro-esophageal reflux disease without esophagitis')],
                      cpt=['99213'], plan='Omeprazole 20 mg daily.', summary='GERD'),
                 dict(off=-60, cc='Annual visit', hpi='Feels well. Normal bowel habits.', exam='Normal exam.',
                      codes=[('Z00.00', 'Encounter for general adult medical examination without abnormal findings')], cpt=['99396'],
                      plan='Creatinine 0.9 on routine labs.', summary='Annual physical; normal bowel habits, creatinine 0.9')],
                  post=[dict(off=10, cc='Hospital follow-up', hpi='Diarrhea resolved two days ago. Tired.', exam='Mucous membranes moist. Abdomen soft, nontender.',
                             codes=[('A02.0', 'Salmonella enteritis'), ('N17.9', 'Acute kidney failure, unspecified')], cpt=['99214'],
                             plan='Repeat metabolic panel. Hold lisinopril-type drugs (not on any). Return 2 weeks.', summary='Post-hospital follow-up; diarrhea resolved')]),
             dict(role='uc', name='Riverlight Urgent Care', bi=True, off=1, cpt=['99214'], extra=[], delay=900,
                  course=['Ondansetron 4 mg ODT given', 'Oral rehydration trial, tolerated poorly', 'Stool culture and labs sent to reference lab'],
                  img=[], plan='Advised emergency department if unable to keep fluids down. Stool culture pending.'),
             dict(role='er', name='Northbridge Emergency Center', off=2, cpt=['99285'], extra=[], delay=200,
                  course=['Normal saline 2 L IV bolus', 'Ondansetron 4 mg IV', 'Labs show creatinine 2.4', 'Ceftriaxone 2 g IV after blood cultures', 'Transfer for admission'],
                  img=[], plan='Admit for IV fluids and acute kidney injury.', dispo='Transferred to Calderon Bay Hospital.'),
             dict(role='hospital', name='Calderon Bay Hospital', off=2, days=5, reason='salmonella enteritis with dehydration and acute kidney injury',
                  surgery=None, labs=True,
                  course=['IV fluids at 200 mL/h. Stool culture from urgent care growing gram-negative rods.', 'Creatinine 2.0. Diarrhea 8 episodes.', 'Culture confirms Salmonella enterica serogroup D, ceftriaxone continued.', 'Creatinine 1.4. Tolerating diet.', 'Creatinine 1.1. Switched to oral azithromycin. Discharged.']),
             dict(role='lab', name='Meridian Reference Laboratories', collections=[
                 dict(off=1, panels=['CBC', 'CMP', 'STOOL'], shift={'WBC': 13.8, 'BUN': 31, 'Creatinine': 1.7, 'Potassium': 3.3, 'CO2': 20}),
                 dict(off=2, panels=['BMP', 'LACTATE', 'CBC', 'CRP'], shift={'BUN': 44, 'Creatinine': 2.4, 'Potassium': 3.0, 'CO2': 18, 'Lactate': 2.9, 'WBC': 15.2, 'C-reactive protein': 96}),
                 dict(off=4, panels=['BMP'], shift={'BUN': 30, 'Creatinine': 1.6, 'Potassium': 3.6}),
                 dict(off=6, panels=['BMP', 'CBC'], shift={'BUN': 18, 'Creatinine': 1.1}),
                 dict(off=24, panels=['CMP'], shift={'Creatinine': 0.9})]),
             dict(role='spec', name='Calderon Bay Infectious Disease Clinic', label='Infectious Disease', visits=[14, 35], first_cpt='99204', fu_cpt='99213',
                  exam=['Afebrile, abdomen benign.', 'Well appearing.'],
                  plans=['Completed azithromycin. Repeat stool culture not needed. Public health notified of restaurant source.', 'Recovered. Discharged from ID care.']),
             dict(role='spec', name='Ashford Digestive Health', label='Gastroenterology', visits=[28, 70, 120], first_cpt='99204', fu_cpt='99214',
                  exam=['Mild lower abdominal tenderness. Bloating.', 'Mild tenderness.', 'Normal exam.'],
                  plans=['Post-infectious irritable bowel symptoms likely. Low FODMAP diet trial, dicyclomine as needed.', 'Partial improvement. Continue diet.', 'Symptoms much improved. Follow up as needed.'],
                  dx_extra=[('K58.0', 'Irritable bowel syndrome with diarrhea')]),
         ]),
    dict(n=10, seed=31010, first='Rafael', last='Montoya-Brisbane', sex='M', dob=D(1984, 5, 21), acc=D(2025, 10, 2),
         acc_time='13:25', city='Harlow, NV 89999', short='forklift crush injury of right foot',
         regions=['right foot'],
         cc='Right foot crush injury from forklift',
         mech='was walking through a warehouse aisle when a reversing forklift ran over his right forefoot through his work boot',
         sym='severe right forefoot pain rated 9/10, swelling and inability to bear weight',
         deny='other injuries, numbness of the toes or head strike',
         exam='Marked swelling and ecchymosis of the dorsal right forefoot. Tenderness over the 2nd and 3rd metatarsals. Compartments soft. Toes warm with brisk capillary refill.',
         dx=[('S92.321A', 'Displaced fracture of second metatarsal bone, right foot, initial encounter for closed fracture'),
             ('S92.331A', 'Displaced fracture of third metatarsal bone, right foot, initial encounter for closed fracture'),
             ('S97.81XA', 'Crushing injury of right foot, initial encounter')],
         ext=[('W23.0XXA', 'Caught, crushed, jammed, or pinched between moving objects, initial encounter'), ('Y99.0', 'Civilian activity done for income or pay')],
         pmh='No chronic conditions. Prior toenail fungus treated.', allergy='No known drug allergies', home_meds='None',
         disch='Posterior splint, non-weight-bearing with crutches. Elevate above the heart. Return for numbness, increasing pain despite medicine or pale toes.',
         providers=[
             dict(role='prior', name='Eastgate Community Clinic', visits=[
                 dict(off=-200, cc='Annual exam', hpi='Works warehouse shifts. No foot pain.', exam='Normal exam. Feet normal.',
                      codes=[('Z00.00', 'Encounter for general adult medical examination without abnormal findings')], cpt=['99396'],
                      plan='Routine.', summary='Annual exam; feet normal')]),
             dict(role='prior', name='Westbrook Foot & Ankle', visits=[
                 dict(off=-800, cc='Thick toenails', hpi='Thick discolored great toenails.', exam='Onychomycosis both halluces. Normal forefoot.',
                      codes=[('B35.1', 'Tinea unguium')], cpt=['99213'], plan='Topical efinaconazole.', summary='Prior onychomycosis; normal forefoot')]),
             dict(role='ems', name='Harlow Industrial Park Ambulance', course=['Boot cut away', 'Vacuum splint applied', 'Fentanyl 100 mcg IN given', 'Ice and elevation']),
             dict(role='er', name='Stonebridge Valley Hospital', cpt=['99284'], extra=[],
                  course=['Hydromorphone 1 mg IV given', 'Foot radiographs obtained', 'Compartment checks every hour x3, soft', 'Posterior splint applied'],
                  img=[dict(cpt='73630', name='XR FOOT RIGHT 3 VIEWS', findings=['Displaced fracture of the 2nd metatarsal neck.', 'Displaced fracture of the 3rd metatarsal shaft.', 'No Lisfranc widening.'], impression='Displaced 2nd and 3rd metatarsal fractures.')],
                  plan='Splint, crutches, oxycodone 5 mg #12, foot and ankle surgery follow-up in 1-3 days.'),
             dict(role='spec', name='SaludWorks Occupational Medicine', label='Occupational Medicine', bi=True, visits=[1, 5, 19, 47, 110], first_cpt='99203', fu_cpt='99213',
                  exam=['Splint intact, toes warm.', 'Swelling decreasing.', 'Post-op, boot, non-weight-bearing.', 'Weight bearing in boot.', 'Walking in shoe, mild limp.'],
                  plans=['Off work. Workers compensation forms completed.', 'Off work pending surgery.', 'Sedentary duty only.', 'Seated duty, no ladders.', 'Light duty 4 hours standing per shift.']),
             dict(role='imaging', name='Meadowlark Imaging', studies=[
                 dict(off=4, cpt='73700', name='CT RIGHT FOOT WITHOUT CONTRAST', ind='Crush injury, surgical planning',
                      findings=['Comminuted fracture of the 2nd metatarsal neck with 4 mm dorsal displacement.', 'Oblique fracture of the 3rd metatarsal shaft with 3 mm shortening.', 'Nondisplaced fracture of the 4th metatarsal base.', 'Lisfranc joint congruent.'],
                      impression='Displaced 2nd and 3rd metatarsal fractures and nondisplaced 4th metatarsal base fracture. Lisfranc intact.',
                      fix=(3, 'Subtle 2 mm widening between the medial cuneiform and 2nd metatarsal base, cannot exclude Lisfranc ligament injury.')),
                 dict(off=50, cpt='73630', name='XR FOOT RIGHT 3 VIEWS', ind='Post ORIF follow-up',
                      findings=['Plate fixation 2nd and 3rd metatarsals.', 'Bridging callus.', 'Hardware intact.'], impression='Healing metatarsal fractures after fixation.')]),
             dict(role='spec', name='Keystone Foot & Ankle Surgeons', label='Foot & Ankle Surgery', visits=[3, 8, 23, 51, 93], first_cpt='99204', fu_cpt='99213',
                  exam=['Swelling, skin wrinkles absent, displaced 2nd and 3rd metatarsals.', 'Skin wrinkle sign present, ready for surgery.', 'Incisions healed, sutures out.', 'Callus on x-ray, mild swelling.', 'Healed, tender over 2nd metatarsal plate.'],
                  plans=['ORIF when swelling allows.', 'Consent for ORIF 2nd and 3rd metatarsals.', 'Boot, non-weight-bearing 2 more weeks.', 'Weight bearing as tolerated in boot, start PT.', 'Persistent burning pain; refer pain medicine to evaluate for CRPS.']),
             dict(role='asc', name='Keystone Surgery Center', off=9, cpts=['28485'],
                  proc='Open reduction internal fixation of right 2nd and 3rd metatarsal fractures',
                  findings='Comminuted 2nd metatarsal neck fracture and oblique 3rd metatarsal shaft fracture. Lisfranc stable on stress exam.',
                  implant='Two 2.0 mm locking plates', ebl='15 mL', anes='General LMA with popliteal block'),
             dict(role='therapy', name='Trailhead Physical Therapy', ttype='Physical Therapy', start=55, n=16, eval_cpt='97162',
                  reeval_cpt='97164', cpts=['97110', '97140', '97530'], reeval_at=10, form='LEFS',
                  measure=('Right ankle dorsiflexion (deg)', 2, 15),
                  ex=['towel scrunches', 'marble pickup', 'calf stretch', 'heel raises', 'gait training', 'balance board', 'desensitization with textures']),
             dict(role='spec', name='Summit Pain Medicine', label='Pain Medicine', visits=[120, 160], first_cpt='99204', fu_cpt='99214',
                  exam=['Allodynia dorsal right foot, temperature 1.5 C cooler, mottling. Meets Budapest criteria.', 'Allodynia reduced, temperature asymmetry 0.5 C.'],
                  plans=['Complex regional pain syndrome type I. Lumbar sympathetic block. Gabapentin titration.', 'Improved after block. Continue PT desensitization.'],
                  dx_extra=[('G90.521', 'Complex regional pain syndrome I of right lower limb')],
                  procs=[dict(off=135, cpts=['64520'], kind='injection', name='Right L2-L3 lumbar sympathetic block under fluoroscopy', detail='Ropivacaine 0.2% 10 mL. Foot temperature rose 2.4 C after block.')]),
         ]),
]

FORMS = {
    'QuickDASH': ['Open a tight jar', 'Do heavy household chores', 'Carry a shopping bag', 'Wash your back',
                  'Use a knife to cut food', 'Recreational activities with force', 'Interference with social activities',
                  'Limited in work', 'Arm, shoulder or hand pain', 'Tingling', 'Difficulty sleeping'],
    'Oswestry': ['Pain intensity', 'Personal care', 'Lifting', 'Walking', 'Sitting', 'Standing', 'Sleeping',
                 'Sex life', 'Social life', 'Travelling'],
    'NDI': ['Pain intensity', 'Personal care', 'Lifting', 'Reading', 'Headaches', 'Concentration', 'Work',
            'Driving', 'Sleeping', 'Recreation'],
    'LEFS': ['Usual work or housework', 'Usual hobbies', 'Getting into the bath', 'Walking between rooms',
             'Putting on shoes', 'Squatting', 'Lifting a bag of groceries', 'Light activities around the home',
             'Heavy activities around the home', 'Getting in and out of a car', 'Walking 2 blocks',
             'Walking a mile', 'Going up or down 10 stairs', 'Standing for 1 hour', 'Sitting for 1 hour',
             'Running on even ground', 'Running on uneven ground', 'Making sharp turns while running',
             'Hopping', 'Rolling over in bed'],
    'DHI': ['Looking up increases problem', 'Frustrated', 'Restrict travel', 'Walking down a supermarket aisle',
            'Getting into or out of bed', 'Restrict social activities', 'Difficulty reading', 'Ambitious activities',
            'Afraid to leave home alone', 'Embarrassed', 'Quick head movements', 'Avoid heights',
            'Turning over in bed', 'Strenuous housework', 'Afraid people think you are intoxicated',
            'Walking by yourself', 'Walking down a sidewalk', 'Difficulty concentrating', 'Walking in the dark',
            'Afraid to stay home alone', 'Handicapped', 'Stress on relationships', 'Depressed', 'Job responsibilities',
            'Bending over'],
    'PSFS': ['Walking 30 minutes', 'Climbing stairs', 'Carrying golf bag', 'Sleeping on right side', 'Lifting groceries'],
}
FORM_SCALE = {'QuickDASH': (1, 5), 'Oswestry': (0, 5), 'NDI': (0, 5), 'LEFS': (0, 4), 'DHI': (0, 4), 'PSFS': (0, 10)}
FORM_TITLE = {'QuickDASH': 'QuickDASH OUTCOME MEASURE', 'Oswestry': 'MODIFIED OSWESTRY LOW BACK PAIN DISABILITY QUESTIONNAIRE',
              'NDI': 'NECK DISABILITY INDEX', 'LEFS': 'LOWER EXTREMITY FUNCTIONAL SCALE',
              'DHI': 'DIZZINESS HANDICAP INVENTORY', 'PSFS': 'PATIENT-SPECIFIC FUNCTIONAL SCALE'}


# --------------------------------------------------------------------------
# case generator
# --------------------------------------------------------------------------
class CaseGen:
    def __init__(self, spec):
        self.c = spec
        self.n = spec['n']
        self.rng = random.Random(spec['seed'])
        self.nrng = np.random.default_rng(spec['seed'])
        self.acc = spec['acc']
        self.pt = dict(first=spec['first'], last=spec['last'], dob=spec['dob'])
        self.sexw = 'female' if spec['sex'] == 'F' else 'male'
        self.he = 'she' if spec['sex'] == 'F' else 'he'
        self.origs = []
        self.by_cid = {}
        self.records = {}
        self.events = []
        self.charges = {}
        self.tags = {}
        self.provs = []
        self.byname = {}
        self.embeds = {}
        self.used_names = set()
        self.kinds = []
        self.fmts = []
        self.docn = 0
        self.last_spec = None
        self.payer = None

    # ---- utilities ----
    def next_kind(self):
        if not self.kinds:
            self.kinds = KINDS[:]
            self.rng.shuffle(self.kinds)
        return self.kinds.pop()

    def next_fmt(self):
        if not self.fmts:
            self.fmts = DATEFMTS[:]
            self.rng.shuffle(self.fmts)
        return self.fmts.pop()

    def person(self, cred):
        while True:
            nm = f'{self.rng.choice(CL_FIRST)} {self.rng.choice(CL_LAST)}'
            if nm not in self.used_names:
                self.used_names.add(nm)
                return f'{nm}, {CRED[cred]}' if cred else nm

    def addr(self):
        return f'{self.rng.randint(12, 9890)} {self.rng.choice(STREETS)}, {self.c["city"]}'

    def phone(self):
        return f'({self.rng.choice([209, 312, 415, 503, 612, 704, 802, 919])}) 555-01{self.rng.randint(10, 99)}'

    def mkprov(self, name, role, bi=False, kind=None):
        if name in self.byname:
            return self.byname[name]
        key = f'p{len(self.provs) + 1}'
        kind = 'bilingual' if bi else (kind or self.next_kind())
        st = Style(kind, self.next_fmt(), self.rng)
        words = name.replace('&', ' ').replace('-', ' ').split()
        abbr = ''.join(w[0] for w in words if w[0].isupper())[:5] or 'X'
        r = self.rng
        mrn = r.choice([f'{r.randint(100000, 999999)}', f'MR-{r.randint(1000, 9999)}-{r.randint(10, 99)}',
                        f'A00{r.randint(10000, 99999)}', f'{abbr}{r.randint(10000, 99999)}'])
        clin = [self.person(cr) for cr in ROLE_CLIN.get(role, ['md'])]
        P = Prov(key, name, role, self.addr(), self.phone(), self.phone(), st, mrn, clin,
                 [self.person(None), self.person(None)], abbr)
        self.provs.append(P)
        self.byname[name] = P
        self.records[P.key] = []
        return P

    def age(self, d):
        b = self.pt['dob']
        return d.year - b.year - ((d.month, d.day) < (b.month, b.day))

    def tm(self, lo=8, hi=17):
        return f'{self.rng.randint(lo, hi - 1):02d}:{self.rng.choice(range(0, 60, 1)):02d}'

    def vit(self):
        r = self.rng
        return (f'{r.randint(108, 152)}/{r.randint(64, 96)}', r.randint(58, 112), r.randint(12, 22),
                r.randint(93, 100), round(r.uniform(97.4, 99.6), 1))

    def vit_str(self):
        bp, hr, rr, sp, t = self.vit()
        return f'BP {bp}  HR {hr}  RR {rr}  SpO2 {sp}% RA  Temp {t} F  Wt {self.rng.randint(54, 104)} kg'

    def pain(self, day):
        dd = max(0, (day - self.acc).days)
        base = 8.2 - 6.0 * (1 - np.exp(-dd / 70.0))
        return int(max(1, min(9, round(base + self.nrng.normal(0, .6)))))

    def codes(self, day, extra=(), initial=None):
        if initial is None:
            initial = (day - self.acc).days <= 14
        cs = [c for c, _ in self.c['dx']] + [c for c, _ in extra]
        if initial:
            cs += [c for c, _ in self.c['ext']]
        else:
            cs = [subseq(c) for c in cs]
        out = []
        for c in cs:
            if c not in out:
                out.append(c)
        return out

    def dxtext(self, day, extra=()):
        initial = (day - self.acc).days <= 14
        items = list(self.c['dx']) + list(extra)
        return '; '.join(f'{d.split(", initial")[0]} ({c if initial else subseq(c)})' for c, d in items)

    def paginate(self, P, title, day, body, extra=(), maxl=43):
        st = P.style
        self.docn += 1
        ref = f'{P.abbr}-{day.year % 100:02d}{self.docn:04d}'
        pages, cur, n = [], [], 0
        for b in body:
            h = len(textwrap.wrap(b.text, st.wrap)) if b.para else 1
            h = max(h, 1)
            if cur and n + h > maxl:
                pages.append(cur)
                cur, n = [], 0
            cur.append(b)
            n += h
        if cur:
            pages.append(cur)
        out = []
        N = len(pages)
        for i, pb in enumerate(pages, 1):
            hd = st.header(P, title, self.pt, day, extra) if i == 1 else st.cont(P, title, self.pt, day)
            out.append(hd + [Blk('')] + pb + st.footer(P, i, N, ref))
        return out, ref

    def add_doc(self, P, pages, kind, day, tags=(), chart=True):
        pages, ref = pages
        cids = []
        for pg in pages:
            cid = f'c{len(self.origs) + 1:04d}'
            o = Orig(cid, P, kind, pg, list(tags), day, ref)
            self.origs.append(o)
            self.by_cid[cid] = o
            if chart:
                self.records[P.key].append(o)
            for t in tags:
                self.tags.setdefault(t, []).append(o)
            cids.append(cid)
        return cids

    def event(self, day, P, kind, summary, codes, procs, cids):
        self.events.append(dict(date=day, provider=P.name, kind=kind, summary=summary, codes=list(codes),
                                procedures=list(procs), pages=list(cids)))

    def charge(self, P, day, cpts, codes, facility=False):
        for c in cpts:
            self.charges.setdefault(P.key, []).append((day, c, list(codes), facility))

    def embed(self, holder, origs):
        if origs:
            self.embeds.setdefault(holder.key, []).extend(origs)

    # ---- builders ----
    def b_prior(self, P, s):
        for v in s['visits'] + s.get('post', []):
            day = clinic_day(self.acc + TD(v['off']))
            st = P.style
            st.reset()
            md = P.clin[0]
            body = []
            body += st.sec('Chief complaint', v['cc'])
            body += st.sec('History of present illness', f"{self.age(day)}-year-old {self.sexw}. {v['hpi']}")
            body += st.sec('Medications', self.c.get('home_meds', 'None'))
            body += st.sec('Allergies', self.c['allergy'])
            body += st.sec('Vital signs', self.vit_str())
            body += st.sec('Examination', v['exam'])
            body += st.sec('Assessment', '; '.join(f'{d} ({c})' for c, d in v['codes']))
            body += st.sec('Plan', v['plan'])
            body += st.sign(md, day, self.tm())
            post = v['off'] > 0
            title = 'OFFICE VISIT' if post else ('PREVENTIVE VISIT' if v.get('cpt') and v['cpt'][0].startswith('993') else 'PROGRESS NOTE')
            cids = self.add_doc(P, self.paginate(P, title, day, body), 'clinical', day, tags=['prior'])
            codes = [c for c, _ in v['codes']]
            self.event(day, P, 'office_visit' if post else 'prior_visit', v['summary'], codes, v.get('cpt', []), cids)
            self.charge(P, day, v.get('cpt', []), codes)

    def b_ems(self, P, s):
        c, st = self.c, P.style
        day = self.acc
        h, m = map(int, c['acc_time'].split(':'))
        t0 = h * 60 + m + self.rng.randint(4, 9)
        st.reset(t0)
        crew = P.clin
        times = []
        lab = ['Call received', 'Dispatched', 'En route', 'On scene', 'Patient contact', 'Depart scene', 'At destination', 'Transfer of care']
        for x in lab:
            times.append((x, st.tick(1, 9)))
        body = [Blk(st.field('Incident #', P.mrn + f'-{self.rng.randint(10, 99)}'))]
        body += st.table(['Event', 'Time'], times, [22, 6])
        body += st.sec('Chief complaint', c['cc'])
        body += st.sec('Narrative', f"Dispatched for {c['short']}. Found {self.age(day)}-year-old {self.sexw} who {c['mech']}. Patient reports {c['sym']}. Denies {c['deny']}. {c['exam']}")
        body += st.sec('Treatment', '; '.join(s.get('course', [])) + '.')
        pages1 = self.paginate(P, 'PATIENT CARE REPORT', day, body)
        st.reset(t0 + 12)
        rows = []
        for i in range(4):
            bp, hr, rr, sp, _ = self.vit()
            rows.append((st.tick(4, 9), bp, hr, rr, sp, max(3, self.pain(day) + 1 - i // 2), 15))
        b2 = st.table(['Time', 'BP', 'HR', 'RR', 'SpO2', 'Pain', 'GCS'], rows, [6, 8, 4, 4, 5, 5, 4])
        b2 += st.sec('Assessment', 'Primary impression: ' + c['short'] + '. Secondary: ' + ', '.join(c['regions']) + ' injury.')
        b2 += st.sec('Disposition', f"Transported emergent to {self.next_dest} without incident. Report given to receiving RN.")
        b2 += st.sign(crew[0], day, st.tick(10, 30)) + [Blk(f'Partner: {crew[1]}')]
        pages2 = self.paginate(P, 'PATIENT CARE REPORT - VITALS AND SIGNATURES', day, b2)
        cids = self.add_doc(P, pages1, 'clinical', day, tags=['ems']) + self.add_doc(P, pages2, 'clinical', day, tags=['ems'])
        self.event(day, P, 'er_visit', f"EMS response and transport after {c['short']}", self.codes(day), [], cids)
        self.charge(P, day, ['A0427', 'A0425'], self.codes(day))

    def b_er(self, P, s):
        c, st = self.c, P.style
        uc = s['role'] == 'uc'
        day = self.acc + TD(s.get('off', 0))
        h, m = map(int, c['acc_time'].split(':'))
        arr = h * 60 + m + s.get('delay', self.rng.randint(35, 80))
        if s.get('off', 0):
            arr = self.rng.randint(8 * 60, 14 * 60)
        md, rn = P.clin[0], P.clin[1]
        st.reset(arr)
        body = []
        body += st.sec('Chief complaint', c['cc'])
        lead = (f"{self.age(day)}-year-old {self.sexw} who {c['mech']}." if not s.get('off') else
                f"{self.age(day)}-year-old {self.sexw} who {c['mech']}. Now day {s['off']} of illness.")
        body += st.sec('History of present illness', f"{lead} Reports {c['sym']}. Denies {c['deny']}.")
        body += st.sec('Past medical history', c['pmh'])
        body += st.sec('Medications', c['home_meds'])
        body += st.sec('Allergies', c['allergy'])
        body += st.sec('Review of systems', 'Twelve-system review negative except as documented in the history.')
        body += st.sec('Vital signs', self.vit_str())
        body += st.sec('Examination', c['exam'])
        for im in s.get('img', []):
            body += st.sec('Imaging', f"{im['name']}: {im['impression']}")
        crs = []
        for x in s.get('course', []):
            crs.append(f'{st.tick(10, 35)} {x}.')
        body += st.sec('Clinic course' if uc else 'ED course', ' '.join(crs))
        body += st.sec('Assessment', self.dxtext(day))
        body += st.sec('Plan', s['plan'])
        body += st.sec('Disposition', s.get('dispo', 'Discharged home in stable condition with written instructions.'))
        body += st.sign(md, day, st.tick(10, 40))
        title = 'URGENT CARE PROVIDER NOTE' if uc else 'EMERGENCY DEPARTMENT PHYSICIAN RECORD'
        cids = self.add_doc(P, self.paginate(P, title, day, body), 'clinical', day, tags=['er_note'])
        # nursing / triage record
        st.reset(arr - 5)
        rows = []
        for i in range(self.rng.randint(4, 6)):
            bp, hr, rr, sp, t = self.vit()
            rows.append((st.tick(15, 50), bp, hr, rr, sp, t, max(2, self.pain(day) - i // 2)))
        nb = [Blk(st.field('Triage acuity', f'ESI {self.rng.choice([2, 3, 3])}')), Blk(st.field('Arrival mode', 'Ambulance' if 'ems' in self.tags else 'Private vehicle'))]
        nb += st.table(['Time', 'BP', 'HR', 'RR', 'SpO2', 'Temp', 'Pain'], rows, [6, 8, 4, 4, 5, 6, 5])
        notes = [f'Patient arrived ambulatory/assisted, reports {c["short"]}.', 'Allergies and home medications verified.',
                 'Pain reassessed after medication.', 'Patient educated on plan of care, verbalized understanding.',
                 'IV site checked, no infiltration.' if not uc else 'Patient resting comfortably.']
        st.reset(arr)
        nb += st.sec('Nursing notes', ' '.join(f'[{st.tick(12, 40)}] {x}' for x in notes) + f' -- {rn}')
        cids += self.add_doc(P, self.paginate(P, 'TRIAGE AND NURSING RECORD', day, nb), 'clinical', day)
        # discharge / transfer page
        db = st.sec('Diagnosis', self.dxtext(day))
        db += st.sec('Instructions', c['disch'])
        db += st.sec('Medications', s['plan'])
        db += st.sec('Follow-up', 'As directed in the plan above. Bring this sheet to your appointment.')
        db += [Blk(''), Blk(f'Patient signature on file.  Discharging nurse: {rn}')]
        cids += self.add_doc(P, self.paginate(P, 'DISCHARGE INSTRUCTIONS' if 'Transfer' not in s.get('dispo', '') else 'TRANSFER SUMMARY', day, db), 'clinical', day, tags=['er_dc'])
        procs = s['cpt'] + s.get('extra', [])
        what = 'Urgent care visit' if uc else 'Emergency department visit'
        self.event(day, P, 'er_visit', f"{what} after {c['short']}: {c['dx'][0][1].split(',')[0].lower()}", self.codes(day), procs, cids)
        self.charge(P, day, procs, self.codes(day), facility=not uc)
        for im in s.get('img', []):
            ic = self.img_doc(P, day, im, P.clin[0] if uc else self.person('rad'))
            self.event(day, P, 'imaging', f"{im['name'].title()} ({'urgent care' if uc else 'emergency department'}): {im['impression']}", self.codes(day), [im['cpt']], ic)
            self.charge(P, day, [im['cpt']], self.codes(day), facility=not uc)

    def img_doc(self, P, day, im, rad, corrected=False):
        st = P.style
        st.reset()
        c = self.c
        fnd = list(im['findings'])
        title = 'DIAGNOSTIC IMAGING REPORT'
        body = []
        if corrected:
            k, new = im['fix']
            fnd[k] = new
            title = 'CORRECTED REPORT'
            body += [Blk(f'*** CORRECTED REPORT -- supersedes the report signed {st.d(day)}. Finding {k + 1} revised on over-read. ***', para=True, font=st.bold)]
        body += [Blk(st.field('Exam', f"{im['name']} (CPT {im['cpt']})"))]
        body += st.sec('Indication', im.get('ind', f"{c['short']}, evaluate {c['regions'][0]}"))
        body += st.sec('Comparison', im.get('comp', 'None available.'))
        body += st.sec('Technique', 'Standard protocol images obtained and reviewed on PACS.')
        body += st.sec('Findings', ' '.join(f'({i + 1}) {f}' for i, f in enumerate(fnd)))
        imp = im['impression']
        if corrected:
            imp = imp.rstrip('.') + '. ' + fnd[im['fix'][0]]
        body += st.sec('Impression', imp)
        sday = day + TD(2 if corrected else 0)
        body += st.sign(rad, sday, self.tm(7, 22))
        cids = self.add_doc(P, self.paginate(P, title, day, body), 'clinical', day, tags=['img_report'] + (['corrected'] if corrected else []))
        return cids

    def b_imaging(self, P, s):
        for k, im in enumerate(s['studies']):
            day = clinic_day(self.acc + TD(im['off']))
            rad = P.clin[k % 2]
            cids = self.img_doc(P, day, im, rad)
            if im.get('fix'):
                cids += self.img_doc(P, day, im, rad, corrected=True)
            self.event(day, P, 'imaging', f"{im['name'].title()}: {im['impression']}", self.codes(day, initial=False if (day - self.acc).days > 14 else True), [im['cpt']], cids)
            self.charge(P, day, [im['cpt']], self.codes(day))

    def b_spec(self, P, s):
        st = P.style
        self.last_spec = (P, s)
        ex = s.get('dx_extra', [])
        n = len(s['visits'])
        consult_cids = []
        for i, off in enumerate(s['visits']):
            day = clinic_day(self.acc + TD(off))
            md = P.clin[0] if i % 3 != 2 else P.clin[1]
            st.reset()
            body = []
            p = self.pain(day)
            if i == 0:
                body += st.sec('Chief complaint', self.c['cc'])
                body += st.sec('History of present illness',
                               f"{self.age(day)}-year-old {self.sexw} seen in {s['label'].lower()} consultation {off} days after {self.c['short']}. {self.he.capitalize()} {self.c['mech']}. Current pain {p}/10.")
                body += st.sec('Past medical history', self.c['pmh'])
                body += st.sec('Medications', self.c['home_meds'])
                body += st.sec('Allergies', self.c['allergy'])
                prior = [o for o in self.tags.get('img_report', []) if o.date <= day and o.prov is not P]
                rev = '; '.join(sorted({f'{o.prov.name} imaging of {mdy(o.date)}' for o in prior})) or 'Emergency records reviewed.'
                body += st.sec('Records reviewed', rev)
            else:
                prev = clinic_day(self.acc + TD(s['visits'][i - 1]))
                trend = 'better' if p < self.pain(prev) + 1 else 'about the same'
                body += st.sec('Interval history', f"Returns {(day - prev).days} days after the last visit. Pain {p}/10, {trend}. Visit {i + 1} of care.")
            body += st.sec('Vital signs', self.vit_str())
            body += st.sec('Examination', s['exam'][min(i, len(s['exam']) - 1)])
            body += st.sec('Assessment', self.dxtext(day, ex))
            body += st.sec('Plan', s['plans'][i])
            body += st.sign(md, day, self.tm(9, 18))
            title = (f"{s['label'].upper()} - NEW PATIENT CONSULTATION" if i == 0 else f"{s['label'].upper()} - FOLLOW-UP VISIT")
            cids = self.add_doc(P, self.paginate(P, title, day, body), 'clinical', day, tags=['spec_note'] + (['consult'] if i == 0 else []))
            if i == 0:
                consult_cids = cids
            if i < 2 and not s.get('dental') and s['label'] not in ('Neuropsychology', 'Infectious Disease', 'Dermatology'):
                cids += self.work_form(P, day, i, s)
            cpt = [s['first_cpt'] if i == 0 else s['fu_cpt']] + s.get('visit_procs', {}).get(i, [])
            self.event(day, P, 'office_visit', f"{s['label']} {'consultation' if i == 0 else 'follow-up'}: {s['plans'][i].split('.')[0]}",
                       self.codes(day, ex, initial=i < 2 and off < 60), cpt, cids)
            self.charge(P, day, cpt, self.codes(day, ex))
        for pr in s.get('procs', []):
            day = clinic_day(self.acc + TD(pr['off']))
            st.reset()
            body = st.sec('Procedure', pr['name'])
            body += st.sec('Indication', self.dxtext(day, ex))
            body += st.sec('Consent', 'Risks including bleeding, infection, nerve injury, headache and no relief discussed. Written consent signed. Time-out performed.')
            body += st.sec('Technique', pr['detail'] + ' Sterile prep and drape. Needle placement confirmed by imaging. Patient tolerated the procedure well.')
            body += st.sec('Complications', 'None. Estimated blood loss minimal.')
            body += [Blk(st.field('Pre-procedure pain', f'{self.pain(day)}/10')), Blk(st.field('Post-procedure pain', f'{max(0, self.pain(day) - 4)}/10'))]
            body += st.sign(P.clin[0], day, self.tm(8, 15))
            cids = self.add_doc(P, self.paginate(P, 'PROCEDURE NOTE', day, body), 'clinical', day, tags=['proc'])
            self.event(day, P, pr['kind'], pr['name'], self.codes(day, ex, initial=True), pr['cpts'], cids)
            self.charge(P, day, pr['cpts'], self.codes(day, ex))
        if s.get('embed_imaging', True):
            prior = [o for o in self.tags.get('img_report', []) if o.prov is not P and 'corrected' not in o.tags]
            self.rng.shuffle(prior)
            self.embed(P, prior[:self.rng.randint(1, 3)])

    def work_form(self, P, day, i, s):
        st = P.style
        st.reset()
        restr = ['No work', 'Sedentary duty, no lifting over 10 lb', 'Modified duty, no lifting over 20 lb', 'Light duty']
        r = restr[min(i + self.rng.randint(0, 1), 3)]
        b = [Blk(st.field('Employer', self.rng.choice(['Brightline Logistics', 'Juniper Market Co-op', 'Halden Civic Library', 'Tessellate Software', 'Copperpot Bistro Group', 'Marlowe County Schools']))),
             Blk(st.field('Date of injury', st.d(self.acc))), Blk(st.field('Date of evaluation', st.d(day))),
             Blk(st.field('Diagnosis', self.dxtext(day, s.get('dx_extra', []))))]
        b += st.sec('Work status', r)
        b += st.sec('Restrictions', f'Valid from {st.d(day)} until next visit. ' + ('Patient may not drive with sling or boot.' if i == 0 else 'Reassess at next visit.'))
        b += [Blk(''), Blk(st.field('Next appointment', st.d(day + TD(self.rng.randint(10, 28)))))]
        b += st.sign(P.clin[0], day, self.tm(9, 18))
        return self.add_doc(P, self.paginate(P, 'WORK STATUS / ACTIVITY RESTRICTION FORM', day, b), 'clinical', day, tags=['form'])

    def b_asc(self, P, s):
        st = P.style
        day = clinic_day(self.acc + TD(s['off']))
        sp = self.last_spec[0] if self.last_spec else P
        surgeon = sp.clin[0]
        cids = self.surgery_docs(P, day, s, surgeon)
        # perioperative nursing
        st.reset(6 * 60 + 20)
        pb = st.sec('Pre-operative checklist', 'Identity, site marking, consent, NPO since midnight and allergies verified. ' + f"Allergy: {self.c['allergy']}.")
        rows = []
        for i in range(6):
            bp, hr, rr, sp2, t = self.vit()
            rows.append((st.tick(15, 40), bp, hr, rr, sp2, ['pre-op', 'pre-op', 'PACU', 'PACU', 'PACU', 'Phase II'][i]))
        pb += st.table(['Time', 'BP', 'HR', 'RR', 'SpO2', 'Area'], rows, [6, 8, 4, 4, 5, 9])
        pb += st.sec('Discharge', 'Aldrete 10. Discharged to home with responsible adult. Written instructions reviewed.')
        pb += st.sign(P.clin[1], day, st.tick(30, 60))
        cids += self.add_doc(P, self.paginate(P, 'PERIOPERATIVE NURSING RECORD', day, pb), 'clinical', day)
        self.event(day, P, 'surgery', s['proc'], self.codes(day, initial=True), s['cpts'], cids)
        self.charge(P, day, s['cpts'], self.codes(day), facility=True)
        pre = [o for o in self.records.get(sp.key, []) if 'consult' in o.tags]
        self.embed(P, pre[:1])

    def surgery_docs(self, P, day, s, surgeon):
        st = P.style
        st.reset(7 * 60 + 30)
        b = [Blk(st.field('Surgeon', surgeon)), Blk(st.field('Assistant', self.person('pa'))),
             Blk(st.field('Anesthesia', s['anes'])), Blk(st.field('Anesthesia provider', P.clin[0]))]
        b += st.sec('Pre-operative diagnosis', self.dxtext(day))
        b += st.sec('Post-operative diagnosis', 'Same.')
        b += st.sec('Procedure', s.get('proc') or s.get('name'))
        b += st.sec('Indications', f"{self.c['short'].capitalize()} on {st.d(self.acc)}. Risks, benefits and alternatives discussed; consent signed.")
        b += st.sec('Findings', s['findings'])
        b += st.sec('Description', 'The patient was identified in the holding area and the operative site was marked. After induction a time-out was performed. The extremity or site was prepped and draped in the usual sterile fashion. ' +
                    f"The procedure was carried out as planned. Implants: {s['implant']}. Fluoroscopy or direct inspection confirmed satisfactory position. The wound was irrigated and closed in layers. Sterile dressing applied. Counts correct x2.")
        b += [Blk(st.field('Estimated blood loss', s['ebl'])), Blk(st.field('Specimens', 'None')), Blk(st.field('Complications', 'None'))]
        b += st.sign(surgeon, day, st.tick(90, 150))
        cids = self.add_doc(P, self.paginate(P, 'OPERATIVE REPORT', day, b), 'clinical', day, tags=['op_report'])
        st.reset(7 * 60 + 40)
        rows = []
        for i in range(10):
            bp, hr, rr, sp, _ = self.vit()
            rows.append((st.tick(5, 15), bp, hr, sp, self.rng.choice(['1.0', '1.1', '0.9', '1.2']), ''))
        ab = [Blk(st.field('ASA class', self.rng.choice(['I', 'II']))), Blk(st.field('Airway', 'Mallampati II'))]
        ab += st.table(['Time', 'BP', 'HR', 'SpO2', 'MAC', 'Event'], rows, [6, 8, 4, 5, 4, 10])
        ab += st.sec('Medications', 'Propofol 180 mg, fentanyl 100 mcg, rocuronium 40 mg, cefazolin 2 g, ondansetron 4 mg, dexamethasone 8 mg.')
        ab += st.sign(P.clin[0], day, st.tick(60, 120))
        cids += self.add_doc(P, self.paginate(P, 'ANESTHESIA RECORD', day, ab), 'clinical', day)
        return cids

    def b_hospital(self, P, s):
        st = P.style
        start = self.acc + TD(s['off'])
        days = s['days']
        att, att2, rn1, rn2, cons = P.clin
        meds = ['Acetaminophen 1000 mg PO q8h', 'Ondansetron 4 mg IV q6h PRN', 'Enoxaparin 40 mg SC daily',
                'Hydromorphone 0.5 mg IV q3h PRN', 'Docusate 100 mg PO BID']
        if s.get('labs'):
            meds = ['Ceftriaxone 2 g IV daily', 'Lactated Ringer 200 mL/h IV', 'Ondansetron 4 mg IV q6h PRN',
                    'Potassium chloride 20 mEq PO BID', 'Acetaminophen 650 mg PO q6h PRN']
        surg = s.get('surgery')
        for d in range(days):
            day = start + TD(d)
            cids = []
            st.reset()
            if d == 0:
                b = st.sec('Chief complaint', self.c['cc'])
                b += st.sec('History of present illness', f"{self.age(day)}-year-old {self.sexw} admitted for {s['reason']}. {self.he.capitalize()} {self.c['mech']}. Reports {self.c['sym']}.")
                b += st.sec('Past medical history', self.c['pmh'])
                b += st.sec('Medications', self.c['home_meds'])
                b += st.sec('Allergies', self.c['allergy'])
                b += st.sec('Social history', self.rng.choice(['Lives with partner. No tobacco. Social alcohol.', 'Lives alone. Former smoker. No drugs.', 'Lives with family. Nonsmoker.']))
                b += st.sec('Vital signs', self.vit_str())
                b += st.sec('Examination', self.c['exam'])
                b += st.sec('Assessment', self.dxtext(day))
                b += st.sec('Plan', s['course'][0])
                b += st.sign(att, day, self.tm(14, 23))
                cids += self.add_doc(P, self.paginate(P, 'HISTORY AND PHYSICAL', day, b), 'clinical', day, tags=['hp'])
                cpt = ['99223']
            else:
                b = st.sec('Subjective', f"Hospital day {d + 1}. Pain {self.pain(day)}/10. " + self.rng.choice(['Slept intermittently.', 'Slept well.', 'Tolerating diet.', 'Ambulated in hall with nursing.']))
                b += st.sec('Objective', self.vit_str() + '. ' + self.rng.choice(['Alert and oriented.', 'Comfortable at rest.', 'No acute distress.']))
                if s.get('labs'):
                    b += st.sec('Labs', f"Na {self.rng.randint(134, 141)}, K {round(self.rng.uniform(3.1, 4.4), 1)}, BUN {self.rng.randint(14, 40)}, Cr per reference lab report.")
                b += st.sec('Assessment', self.dxtext(day))
                b += st.sec('Plan', s['course'][min(d, len(s['course']) - 1)])
                b += st.sign(att if d % 2 else att2, day, self.tm(8, 13))
                cids += self.add_doc(P, self.paginate(P, 'PROGRESS NOTE', day, b), 'clinical', day, tags=['progress'])
                cpt = ['99239'] if d == days - 1 else ['99232' if d < 3 else '99231']
            # flowsheet
            st.reset(0)
            rows = []
            for hh in (0, 4, 8, 12, 16, 20):
                bp, hr, rr, sp, t = self.vit()
                rows.append((f'{hh:02d}:00', bp, hr, rr, sp, t, self.pain(day) + self.rng.randint(-1, 1), self.rng.randint(150, 600)))
            fb = st.table(['Time', 'BP', 'HR', 'RR', 'SpO2', 'Temp', 'Pain', 'Intake'], rows, [6, 8, 4, 4, 5, 6, 5, 6])
            fb += st.sec('Nursing assessment', f"Day {d + 1}: " + self.rng.choice(['Dressing clean, dry, intact.', 'Incentive spirometry encouraged hourly.', 'Fall precautions in place.', 'Up to chair for meals.', 'Voiding without difficulty.']) + f" Day RN {rn1}; night RN {rn2}.")
            cids += self.add_doc(P, self.paginate(P, 'NURSING FLOWSHEET - 24 HOUR', day, fb), 'clinical', day, tags=['flowsheet'])
            # MAR
            rows = []
            for med in meds:
                given = ' '.join(f'{x:02d}{self.rng.choice(["00", "05", "10", "15", "20", "30"])}' for x in sorted(self.rng.sample([2, 6, 8, 10, 14, 16, 18, 22], self.rng.randint(1, 3))))
                rows.append((med[:34], given, self.rng.choice(['KT', 'MB', 'RJ', 'LS', 'DW'])))
            mb = st.table(['Medication / dose / route', 'Given (24h)', 'Init'], rows, [34, 16, 4])
            mb += [Blk(''), Blk(st.field('MAR date', st.d(day))), Blk(st.field('Verified by pharmacist', self.rng.choice(['T. Ruelas', 'G. Amsel', 'P. Ivey'])))]
            cids += self.add_doc(P, self.paginate(P, 'MEDICATION ADMINISTRATION RECORD', day, mb), 'clinical', day, tags=['mar'])
            if d == days - 1:
                st.reset()
                b = st.sec('Admission date', st.d(start)) + st.sec('Discharge date', st.d(day))
                b += st.sec('Diagnosis', self.dxtext(day))
                b += st.sec('Hospital course', ' '.join(f'Day {k + 1}: {x}' for k, x in enumerate(s['course'])))
                b += st.sec('Discharge medications', self.rng.choice(['Acetaminophen 1000 mg every 8 hours, oxycodone 5 mg every 6 hours as needed #20.', 'Azithromycin 500 mg daily to complete course, oral rehydration.', 'Acetaminophen, ibuprofen, silver sulfadiazine to donor site.']))
                b += st.sec('Follow-up', 'Clinic follow-up in 1 to 2 weeks as arranged.')
                b += st.sign(att, day, self.tm(10, 16))
                cids += self.add_doc(P, self.paginate(P, 'DISCHARGE SUMMARY', day, b), 'clinical', day, tags=['dc_summary'])
            self.event(day, P, 'office_visit', f"Inpatient day {d + 1} of {days}: {s['course'][min(d, len(s['course']) - 1)].split('.')[0]}", self.codes(day, initial=True), cpt, cids)
            self.charge(P, day, cpt, self.codes(day), facility=True)
            if surg and surg['day'] == d:
                sc = self.surgery_docs(P, day, dict(surg, proc=surg['name']), cons)
                self.event(day, P, 'surgery', surg['name'], self.codes(day, initial=True), surg['cpts'], sc)
                self.charge(P, day, surg['cpts'], self.codes(day), facility=True)
        self.embed(P, self.tags.get('ems', []) + [o for o in self.tags.get('er_note', []) if o.date <= start])

    def b_therapy(self, P, s):
        st = P.style
        n = s['n']
        day = clinic_day(self.acc + TD(s['start']))
        dates = []
        for i in range(n):
            dates.append(day)
            day = clinic_day(day + TD(self.rng.choice([2, 2, 3, 3, 4, 7] if i > n * .6 else [2, 2, 3, 3, 4])))
        lab, m0, m1 = s['measure']
        noise = self.nrng.normal(0, abs(m1 - m0) * .03, n)
        ttype = s['ttype']
        if not hasattr(P, 'tclin'):
            cr = 'dc' if ttype == 'Chiropractic' else ('ot' if 'Occupational' in ttype else 'pt')
            P.tclin = [self.person(cr), self.person('pta' if cr != 'dc' else 'dc')]
        pt, pta = P.tclin
        for i, d in enumerate(dates):
            frac = (i / max(1, n - 1)) ** .8
            meas = round(m0 + (m1 - m0) * frac + noise[i], 1 if 'lb' in lab or 'm)' in lab else 0)
            if isinstance(meas, float) and meas.is_integer() and 'lb' not in lab and 'm)' not in lab:
                meas = int(meas)
            p = self.pain(d)
            st.reset()
            if i == 0 or i == s['reeval_at'] - 1:
                ev = i == 0
                b = st.sec('Subjective', (f"Referred for {ttype.lower()} after {self.c['short']} on {st.d(self.acc)}. " if ev else f"Re-evaluation after {i} visits. ") + f"Pain {p}/10. " + self.rng.choice(['Difficulty with work tasks.', 'Sleep disrupted by pain.', 'Improving but limited with lifting.']))
                b += st.sec('Objective', f"{lab}: {meas}. Strength and function tested; see outcome form. Palpation tenderness {'moderate' if ev else 'mild'}.")
                b += st.sec('Assessment', self.dxtext(d) + f". Rehabilitation potential good. {'Moderate' if ev else 'Reduced'} activity limitation.")
                b += st.sec('Goals', f"Short term (4 wk): {lab} to {round(m0 + (m1 - m0) * .5)}. Long term (10 wk): {lab} to {m1}; return to full work and recreation.")
                b += st.sec('Plan', f"{ttype} 2-3 times weekly for {self.rng.choice([6, 8])} weeks: " + ', '.join(s['ex'][:5]) + '.')
                b += st.sign(pt, d, self.tm(8, 18))
                title = f"{ttype.upper()} {'INITIAL EVALUATION' if ev else 'RE-EVALUATION'}"
                cids = self.add_doc(P, self.paginate(P, title, d, b), 'clinical', d, tags=['therapy_eval'] if ev else ['therapy_reeval'])
                cids += self.outcome_form(P, d, s['form'], frac)
                kind = 'pt_eval' if ev else 'pt_reeval'
                cpt = [s['eval_cpt'] if ev else s['reeval_cpt']] + s['cpts'][:1]
                summ = f"{ttype} {'initial evaluation' if ev else 're-evaluation'}; {lab} {meas}"
            else:
                ex = self.rng.sample(s['ex'], min(4, len(s['ex'])))
                units = [(c, self.rng.choice([1, 1, 2])) for c in s['cpts'][:self.rng.choice([2, 3])]]
                b = st.sec('Subjective', f"Visit {i + 1}. Pain {p}/10 today. " + self.rng.choice(['Did home exercises daily.', 'Sore after last session.', 'Reports less stiffness.', 'Worked a full shift yesterday.', 'Missed home program one day.']))
                b += st.sec('Objective', f"{lab}: {meas}.")
                b += st.sec('Interventions', '; '.join(f'{x} {self.rng.choice([2, 3])}x{self.rng.choice([10, 12, 15])}' for x in ex) + '. Billed: ' + ', '.join(f'{c} x{u}' for c, u in units) + '.')
                b += st.sec('Response', self.rng.choice(['Tolerated well.', 'Mild fatigue, no increase in pain.', 'Pain decreased 1 point after session.', 'Required cues for form.']))
                b += st.sec('Plan', 'Continue plan of care. Progress as tolerated.')
                b += st.sign(pt if i % 3 else pta, d, self.tm(7, 19))
                cids = self.add_doc(P, self.paginate(P, f'{ttype.upper()} DAILY NOTE', d, b), 'clinical', d, tags=['therapy_note'])
                kind = 'pt_visit'
                cpt = [c for c, _ in units]
                summ = f"{ttype} visit {i + 1}; pain {p}/10, {lab} {meas}"
            self.event(d, P, kind, summ, self.codes(d, initial=False), cpt, cids)
            self.charge(P, d, cpt, self.codes(d, initial=False))
        cons = [o for o in self.tags.get('consult', []) if o.prov is not P]
        if cons:
            self.embed(P, cons[-1:])

    def outcome_form(self, P, d, form, frac):
        st = P.style
        items = FORMS[form]
        lo, hi = FORM_SCALE[form]
        rows = []
        tot = 0
        for k, it in enumerate(items):
            if form == 'LEFS' or form == 'PSFS':
                v = int(np.clip(round(lo + (hi - lo) * (.25 + .6 * frac) + self.nrng.normal(0, .7)), lo, hi))
            else:
                v = int(np.clip(round(hi - (hi - lo) * (.35 + .5 * frac) + self.nrng.normal(0, .7)), lo, hi))
            tot += v
            rows.append((f'{k + 1}.', it[:38], v))
        b = [Blk(st.field('Completed by', 'Patient')), Blk(st.field('Date completed', st.d(d))), Blk(st.field('Scale', f'{lo} to {hi} per item'))]
        b += st.table(['#', 'Item', 'Score'], rows, [4, 38, 5])
        b += [Blk(''), Blk(st.field('Total score', f'{tot} / {hi * len(items)}'), font=st.bold)]
        return self.add_doc(P, self.paginate(P, FORM_TITLE[form], d, b), 'clinical', d, tags=['form'])

    def b_lab(self, P, s):
        st = P.style
        for col in s['collections']:
            day = self.acc + TD(col['off'])
            st.reset()
            b = [Blk(st.field('Collected', f'{st.d(day)} {self.tm(7, 20)}')), Blk(st.field('Received', f'{st.d(day)} {self.tm(20, 23)}')),
                 Blk(st.field('Reported', f'{st.d(day + TD(1 if "STOOL" not in col["panels"] else 3))} {self.tm(6, 12)}')),
                 Blk(st.field('Ordering', self.rng.choice([p.clin[0] for p in self.provs if p.role in ('uc', 'er', 'hospital', 'prior')] or [P.clin[0]]))),
                 Blk(st.field('Accession', f'MRL{self.rng.randint(1000000, 9999999)}'))]
            cpts = []
            for pn in col['panels']:
                cpt, tests = PANELS[pn]
                cpts.append(cpt)
                if tests is None:
                    b += st.sec('Stool culture', 'Salmonella enterica, serogroup D, isolated. Shigella, Campylobacter and Shiga toxin not detected. Susceptible to ceftriaxone and azithromycin; ciprofloxacin intermediate.')
                    continue
                rows = []
                for nm, unit, lo, hi in tests:
                    v = col['shift'].get(nm)
                    if v is None:
                        v = self.rng.uniform(lo + (hi - lo) * .2, hi - (hi - lo) * .2)
                    v = round(v, 1) if hi < 20 else int(round(v))
                    flag = 'H' if v > hi else ('L' if v < lo else '')
                    rows.append((nm, v, flag, unit, f'{lo}-{hi}'))
                b += [Blk(f'{pn} (CPT {cpt})', font=st.bold)]
                b += st.table(['Test', 'Result', 'Flag', 'Units', 'Reference'], rows, [18, 7, 4, 10, 10])
            b += [Blk(''), Blk(st.field('Laboratory director', P.clin[0]))]
            cids = self.add_doc(P, self.paginate(P, 'LABORATORY REPORT', day, b), 'clinical', day, tags=['lab'])
            self.event(day, P, 'lab', 'Labs: ' + ', '.join(col['panels']) + ('; creatinine ' + str(col['shift'].get('Creatinine')) if 'Creatinine' in col['shift'] else ''),
                       self.codes(day, initial=True), cpts, cids)
            self.charge(P, day, cpts, self.codes(day))

    # ---- billing ----
    def b_billing(self, P):
        ch = self.charges.get(P.key)
        if not ch:
            return
        st = P.style
        r = self.rng
        fees = {}

        def fee(c):
            if c not in fees:
                fees[c] = FEE.get(c, r.randint(300, 1900)) * r.uniform(.92, 1.12)
            return round(fees[c], 2)
        lines = []
        for (day, cpt, codes, fac) in ch:
            u = 1
            if cpt == 'A0425':
                u = r.randint(6, 19)
            lines.append((day, cpt, codes, u, round(fee(cpt) * (u if cpt != 'A0425' else 1) if cpt != 'A0425' else 14.25 * u, 2), fac))
        facility = any(l[5] for l in lines)
        claim = f'{r.randint(100, 999)}{r.randint(100000, 999999)}'
        # claim forms, up to 6 lines each
        chunks = [lines[i:i + 6] for i in range(0, len(lines), 6)]
        for k, chnk in enumerate(chunks):
            dx = []
            for l in chnk:
                for c in l[2]:
                    if c not in dx and len(dx) < 12:
                        dx.append(c)
            letters = 'ABCDEFGHIJKL'
            day0 = chnk[0][0]
            st.reset()
            b = [Blk(st.field('Insured', f"{self.pt['last'].upper()}, {self.pt['first'].upper()}")),
                 Blk(st.field('Payer', self.payer)), Blk(st.field('Patient account', f'{P.mrn}-{k + 1:02d}')),
                 Blk(st.field('Claim no.', f'{claim}{k:02d}')), Blk(st.field('Accident related', f'YES  date {st.d(self.acc)}')),
                 Blk(st.field('Billing NPI', f'1{r.randint(100000000, 999999999)}'))]
            b += [Blk('21. Diagnosis: ' + '  '.join(f'{letters[i]}. {c}' for i, c in enumerate(dx)), para=True)]
            rows = []
            for l in chnk:
                ptr = ''.join(letters[dx.index(c)] for c in l[2][:4] if c in dx)
                rows.append((st.d(l[0]), '21' if l[5] else '11', l[1], ptr, l[3], f'{l[4]:,.2f}'))
            b += st.table(['24A DOS', 'POS', 'CPT/HCPCS', 'Ptr', 'Units', 'Charges'], rows, [16, 3, 9, 5, 5, 11])
            b += [Blk(''), Blk(st.field('28. Total charge', f'${sum(l[4] for l in chnk):,.2f}'), font=st.bold),
                  Blk(st.field('31. Signature', P.clin[0])), Blk(st.field('Date', st.d(chnk[-1][0] + TD(r.randint(2, 9)))))]
            title = 'UB-04 INSTITUTIONAL CLAIM - FILE COPY' if facility else 'HEALTH INSURANCE CLAIM FORM (CMS-1500) - PROVIDER COPY'
            self.add_doc(P, self.paginate(P, title, day0, b), 'billing', day0, tags=['bill'])
        # ledger / itemized statement
        st.reset()
        bal = 0.0
        rows = []
        for l in lines:
            bal += l[4]
            rows.append((st.d(l[0]), l[1], CPT_DESC.get(l[1], {'A0427': 'ALS1 emergency transport', 'A0425': 'Ground mileage, per mile'}.get(l[1], 'Service'))[:30], f'{l[4]:,.2f}', '', f'{bal:,.2f}'))
            if r.random() < .25:
                pay = round(l[4] * r.uniform(.3, .7), 2)
                bal -= pay
                rows.append((st.d(l[0] + TD(r.randint(20, 50))), 'PMT', f'{self.payer[:22]} payment', '', f'-{pay:,.2f}', f'{bal:,.2f}'))
        b = [Blk(st.field('Statement date', st.d(lines[-1][0] + TD(r.randint(20, 40))))), Blk(st.field('Guarantor', f"{self.pt['first']} {self.pt['last']}"))]
        b += st.table(['Date', 'Code', 'Description', 'Charge', 'Pay/Adj', 'Balance'], rows, [16, 5, 30, 10, 10, 10])
        b += [Blk(''), Blk(st.field('Balance due', f'${bal:,.2f}'), font=st.bold)]
        title = 'ITEMIZED STATEMENT OF CHARGES' if facility else 'PATIENT ACCOUNT LEDGER'
        self.add_doc(P, self.paginate(P, title, lines[0][0], b, maxl=40), 'billing', lines[0][0], tags=['bill', 'ledger'])

    # ---- admin ----
    def letterhead(self, F, title):
        st = F.style
        if st.kind in ('eqbox', 'grid', 'hashbox'):
            ch = '=' if st.kind != 'hashbox' else '#'
            H = [Blk(ch * 64), Blk(F.name.upper(), align='c', font=st.bold, size=st.size + 2), Blk(F.addr, align='c'),
                 Blk(f'T {F.phone}  F {F.fax}', align='c'), Blk(ch * 64)]
        else:
            H = [Blk(F.name, align='c', font=st.bold, size=st.size + 3), Blk(F.addr + '  |  ' + F.phone, align='c', size=st.size - .5), Blk('_' * 70)]
        H += [Blk(title, font=st.bold)] if title else []
        for h in H:
            h.hdr = True
        return H

    def admin_page(self, F, title, day, body, owner=None, tags=()):
        st = F.style
        self.docn += 1
        ref = f'{F.abbr}-A{self.docn:04d}'
        pg = self.letterhead(F, title) + [Blk(st.d(day), align='r'), Blk('')] + body + st.footer(F, 1, 1, ref)
        cid = f'c{len(self.origs) + 1:04d}'
        o = Orig(cid, owner or F, 'admin', pg, list(tags), day, ref)
        self.origs.append(o)
        self.by_cid[cid] = o
        return o

    def request_letter(self, P, day, ref):
        F = self.firm
        st = F.style
        nm = f"{self.pt['first']} {self.pt['last']}"
        body = [Blk('VIA FACSIMILE AND MAIL'), Blk(''), Blk('Custodian of Records'), Blk(P.name), Blk(P.addr), Blk(''),
                Blk(f'Re:  Our client: {nm}'), Blk(f'     Date of birth: {st.d(self.pt["dob"])}'),
                Blk(f'     Date of incident: {st.d(self.acc)}'), Blk(f'     Our file: {ref}'), Blk(''),
                Blk('Dear Custodian:'),
                Blk(f'This office represents the above-named patient for injuries sustained in a {self.c["short"]}. Pursuant to the enclosed HIPAA-compliant authorization, please produce a complete, certified copy of all medical records, including office and progress notes, imaging reports, operative reports, therapy notes, correspondence, and an itemized statement of all charges with CPT and ICD-10 codes, for any dates of service from two years before the incident through the present.', para=True),
                Blk(''),
                Blk('Please include a signed certification of the custodian of records. We will pay reasonable copying charges in accordance with state law upon receipt of an invoice. Kindly direct questions to the undersigned paralegal.', para=True),
                Blk(''), Blk('Very truly yours,'), Blk(''), Blk(self.firm_para, font=st.ital), Blk('Litigation Paralegal'),
                Blk(f'Enclosure: Authorization dated {st.d(self.auth_date)}')]
        return self.admin_page(F, '', day, body, owner=F, tags=['request'])

    def certification(self, P, day, custodian, npages, ref):
        st = P.style
        nm = f"{self.pt['first']} {self.pt['last']}"
        body = [Blk(st.field('Patient', nm)), Blk(st.field('Date of birth', st.d(self.pt['dob']))), Blk(st.field('Request reference', ref)), Blk(''),
                Blk(f'I, {custodian}, certify that I am a duly authorized custodian of records for {P.name}, or am otherwise qualified to make this certification; that the attached {npages} pages are true and complete copies of records of the above patient maintained in the regular course of business; that the records were made at or near the time of the acts, conditions or events recorded, by or from information transmitted by a person with knowledge; and that it was the regular practice of this organization to make such records.', para=True),
                Blk(''), Blk('I declare under penalty of perjury that the foregoing is true and correct.', para=True), Blk(''),
                Blk(st.field('Signature', custodian)), Blk(st.field('Title', self.rng.choice(['Release of Information Specialist', 'HIM Supervisor', 'Records Coordinator', 'Practice Manager']))),
                Blk(st.field('Executed on', st.d(day)))]
        return self.admin_page(P, 'CERTIFICATION OF CUSTODIAN OF RECORDS', day, body, owner=P, tags=['cert'])

    def fax_cover(self, P, day, npages, note):
        st = P.style
        body = [Blk(st.field('To', self.firm.name)), Blk(st.field('Attn', self.firm_para)), Blk(st.field('Fax', self.firm.fax)),
                Blk(st.field('From', f'{P.name} - Health Information')), Blk(st.field('Pages (incl. cover)', str(npages))),
                Blk(st.field('Re', f"Records of {self.pt['first']} {self.pt['last']}")), Blk(''), Blk(note, para=True), Blk(''),
                Blk('CONFIDENTIALITY NOTICE: This transmission contains protected health information. If you received it in error, notify the sender and destroy all copies. Re-disclosure is prohibited without further authorization.', para=True, size=P.style.size - 1)]
        return self.admin_page(P, 'FAX COVER SHEET', day, body, owner=P, tags=['cover'])

    def authorization(self):
        F = self.firm
        st = F.style
        nm = f"{self.pt['first']} {self.pt['last']}"
        body = [Blk(st.field('Patient name', nm)), Blk(st.field('Date of birth', st.d(self.pt['dob']))), Blk(''),
                Blk('I authorize any physician, hospital, clinic, laboratory, imaging center, therapist, ambulance service or other health care provider to release my protected health information to ' + F.name + ', my attorneys, for the purpose of evaluating and pursuing my personal injury claim.', para=True),
                Blk(''), Blk('Information to be released: complete records, including billing, imaging reports and films, and records received from other providers. This authorization includes alcohol and drug and mental health records only if initialed: ____', para=True),
                Blk(''), Blk('This authorization expires two years from the date signed. I may revoke it in writing at any time except to the extent action has already been taken. A copy is as valid as the original.', para=True),
                Blk(''), Blk(f'Signature of patient: /s/ {nm}'), Blk(f'Date signed: {st.d(self.auth_date)}'),
                Blk(f'Authorization no. {self.auth_no}')]
        return self.admin_page(F, 'AUTHORIZATION FOR RELEASE OF PROTECTED HEALTH INFORMATION', self.auth_date, body, owner=F, tags=['auth'])

    def misc_letter(self, F, title, day, paras):
        body = []
        for p in paras:
            body += [Blk(p, para=True), Blk('')]
        body += [Blk('Sincerely,'), Blk(''), Blk(self.person('md').split(',')[0] + ', Esq.' if F is not self.ins else self.person(None) + ', Senior Claims Specialist', font=F.style.ital)]
        return self.admin_page(F, title, day, body, owner=F, tags=['letter'])

    # ---- run ----
    def build(self):
        c = self.c
        self.firm = self.mkprov(self.rng.choice(['Ostrowski Bellweather LLP', 'Varnum Thale & Pike', 'Coyle Ingersoll Injury Law', 'Delmar Fitch Trial Lawyers', 'Pratt Okafor Lindgren PC']), 'firm')
        self.firm_para = self.person(None)
        self.ins = self.mkprov(self.rng.choice(['Granite Shield Mutual Insurance', 'Paragon Harbor Casualty', 'Northwind General Indemnity', 'Bluecrest Assurance Group']), 'insurer')
        self.payer = self.rng.choice(['Cobalt Health Plan PPO', 'Evergreen Mutual Health', 'Tri-County Health Cooperative', 'Summit Shield HMO'])
        self.dfirm = self.mkprov(self.rng.choice(['Hallett Grimsby & Rowe', 'Merriweather Sato LLP', 'Abelard Quince Defense Group']), 'defense')
        self.mediator = self.mkprov(self.rng.choice(['Resolve Northwest Mediation', 'Common Ground ADR Services', 'Fairhaven Dispute Resolution']), 'mediator')
        self.claimno = f'{self.rng.choice(["GSM", "PHC", "NGI", "BAG"])}-{self.acc.year}-{self.rng.randint(10000, 99999)}'
        ems_next = [p for p in c['providers'] if p['role'] in ('er',)]
        self.next_dest = ems_next[0]['name'] if ems_next else 'receiving hospital'
        for s in c['providers']:
            role = s['role']
            P = self.mkprov(s['name'], role if role != 'uc' else 'uc', bi=s.get('bi', False))
            getattr(self, 'b_' + {'uc': 'er'}.get(role, role))(P, s)
        self.med_provs = [p for p in self.provs if p.role not in ('firm', 'insurer', 'defense', 'mediator')]
        for P in self.med_provs:
            self.b_billing(P)
        self.last_day = max(e['date'] for e in self.events)
        self.auth_date = self.last_day + TD(self.rng.randint(3, 12))
        self.auth_no = f'{self.rng.choice("ABKRT")}-{self.rng.randint(10000, 99999)}'
        self.auth = self.authorization()

    def finalize_events(self):
        order = {p.name: i for i, p in enumerate(self.provs)}
        ev = sorted(self.events, key=lambda e: (e['date'], order[e['provider']], e['kind']))
        out = []
        for i, e in enumerate(ev, 1):
            out.append(dict(event_id=f'e{i:03d}', date=mdy(e['date']), provider=e['provider'], kind=e['kind'],
                            summary=e['summary'], codes=e['codes'], procedures=e['procedures'], doc_id=f'd{i:03d}',
                            pages=e['pages']))
        return out


# --------------------------------------------------------------------------
# copies, overlays, rendering
# --------------------------------------------------------------------------
class Out:
    def __init__(self, o, provider, prod, mech):
        self.o = o
        self.provider = provider
        self.prod = prod
        self.mech = [mech]
        self.top = []
        self.bottom = []
        self.margin = []
        self.append = None
        self.mid = []
        self.ocr = 0.0
        self.reflow = None
        self.crop = False
        self.nohdr = False
        self.two = None


CONF = [('rn', 'm'), ('m', 'rn'), ('cl', 'd'), ('0', 'O'), ('O', '0'), ('1', 'l'), ('l', '1'), ('I', '|'),
        ('5', 'S'), ('S', '5'), ('8', 'B'), ('B', '8'), ('e', 'c'), ('h', 'b'), ('ii', 'u'), ('6', 'G'),
        ('.', ','), ('g', 'q'), ('Z', '2'), ('t', 'f'), ('a', 'o'), ('3', '8'), ('/', 'l'), ('u', 'v')]
STRAY = ['~', '`', '^', "'", '.', ',', '_', '°', '¦', ';']


def ocr_text(s, rng, rate):
    if not s.strip():
        return s
    out = s
    for a, b in CONF:
        if a in out and rng.random() < rate * 2.2:
            idxs = [i for i in range(len(out)) if out.startswith(a, i)]
            i = rng.choice(idxs)
            out = out[:i] + b + out[i + len(a):]
    if ' ' in out and rng.random() < rate * 4:
        sp = [i for i, ch in enumerate(out) if ch == ' ']
        i = rng.choice(sp)
        out = out[:i] + out[i + 1:]
    if len(out) > 8 and rng.random() < rate * 3:
        i = rng.randint(2, len(out) - 2)
        if out[i].isalpha() and out[i - 1].isalpha():
            out = out[:i] + ' ' + out[i:]
    if rng.random() < rate * 3:
        i = rng.randint(0, len(out))
        out = out[:i] + rng.choice(STRAY) + out[i:]
    return out


@dataclass
class Line:
    text: str
    font: str
    size: float
    align: str
    indent: int
    role: str


def layout(blocks, st, reflow=None):
    lines = []
    wscale = reflow['wrap'] if reflow else 1.0
    sscale = reflow['size'] if reflow else 1.0
    fam_swap = reflow.get('fam') if reflow else None
    for b in blocks:
        font = b.font or st.font
        size = (b.size or st.size)
        if b.role in ('body',) and reflow:
            size *= sscale
            if fam_swap and font in ('helv', 'tiro', 'cour', 'hebo', 'tibo', 'cobo', 'heit', 'tiit', 'coit'):
                bold = font in ('hebo', 'tibo', 'cobo')
                ital = font in ('heit', 'tiit', 'coit')
                font = BOLD[fam_swap] if bold else (ITAL[fam_swap] if ital else fam_swap)
        if b.para:
            w = max(28, int(st.wrap * wscale * (st.size / (b.size or st.size))))
            parts = textwrap.wrap(b.text, w) or ['']
            for p in parts:
                lines.append(Line(p, font, size, b.align, b.indent, b.role))
        else:
            lines.append(Line(b.text, font, size, b.align, b.indent, b.role))
    return lines


def put(page, ln, x0, x1, y, sz):
    avail = x1 - x0
    if ln.align == 'lr' and '\t' in ln.text:
        a, b = ln.text.split('\t', 1)
        wa = fitz.get_text_length(a, fontname=ln.font, fontsize=sz)
        wb = fitz.get_text_length(b, fontname=ln.font, fontsize=sz)
        if wa + wb + 12 > avail:
            sz = sz * avail / (wa + wb + 12)
            wb = fitz.get_text_length(b, fontname=ln.font, fontsize=sz)
        page.insert_text((x0, y), a, fontname=ln.font, fontsize=sz)
        page.insert_text((x1 - wb, y), b, fontname=ln.font, fontsize=sz)
        return
    text = ln.text.replace('\t', '    ')
    xi = x0 + ln.indent * sz * .5
    w = fitz.get_text_length(text, fontname=ln.font, fontsize=sz)
    if w > x1 - xi:
        sz = sz * (x1 - xi) / w * .995
        w = fitz.get_text_length(text, fontname=ln.font, fontsize=sz)
    if ln.align == 'r':
        x = x1 - w
    elif ln.align == 'c':
        x = x0 + (avail - w) / 2
    else:
        x = xi
    page.insert_text((x, y), text, fontname=ln.font, fontsize=sz)


def draw(page, lines, x0, x1, y0, y1):
    total = sum(l.size * 1.24 for l in lines)
    k = min(1.0, (y1 - y0) / total) if total else 1.0
    y = y0
    for ln in lines:
        sz = ln.size * k
        y += sz * 1.24
        if ln.text.strip():
            put(page, ln, x0, x1, y, sz)


def prep_lines(out, o, rng, skip_overlays=False):
    st = o.prov.style
    blocks = [copy.copy(b) for b in o.blocks if not (out.nohdr and b.hdr)]
    if not skip_overlays:
        if out.append:
            cand = [i for i, b in enumerate(blocks) if b.text.strip() and not b.para and b.align in ('l', 'c') and len(b.text) < 70]
            if cand:
                i = cand[min(len(cand) - 1, rng.randint(0, 4))]
                blocks[i].text = blocks[i].text + '   ' + out.append
        for pos, blk in sorted(out.mid, key=lambda x: -x[0]):
            blocks.insert(min(pos, len(blocks)), blk)
        blocks = out.top + blocks + out.bottom
    lines = layout(blocks, st, out.reflow)
    if out.crop:
        nonempty = [i for i, l in enumerate(lines) if l.text.strip() and l.role == 'body']
        drop = set(nonempty[:2] + nonempty[-1:])
        lines = [l for i, l in enumerate(lines) if i not in drop]
        cut = rng.randint(64, 80)
        for l in lines:
            if l.role == 'body' and len(l.text) > cut:
                l.text = l.text[:cut]
    if out.ocr:
        new = []
        for l in lines:
            if l.role in ('late',):
                new.append(l)
                continue
            t = ocr_text(l.text, rng, out.ocr)
            if len(t) > 30 and rng.random() < out.ocr * 2.5:
                i = rng.randint(10, len(t) - 10)
                new.append(Line(t[:i], l.font, l.size, 'l', l.indent, l.role))
                new.append(Line(t[i:], l.font, l.size, 'l', l.indent + 4, l.role))
            else:
                l.text = t
                new.append(l)
        lines = new
    return lines


def prov_style(o):
    return o.prov.style


def render_page(doc, out, rng):
    page = doc.new_page(width=612, height=792)
    o = out.o
    if out.two is not None:
        o2 = out.two
        base, other = Out(o, '', 0, ''), Out(o2, '', 0, '')
        base.ocr = other.ocr = out.ocr
        la = prep_lines(base, o, rng)
        lb = prep_lines(other, o2, rng)
        for l in la + lb:
            l.size *= .62
        top = layout(out.top, o.prov.style)
        bot = layout(out.bottom, o.prov.style)
        draw(page, top, 30, 582, 20, 20 + sum(l.size * 1.24 for l in top) + 2)
        h0 = 30 + sum(l.size * 1.24 for l in top)
        page.draw_line((306, h0), (306, 760), color=(.6, .6, .6), width=.5)
        draw(page, la, 26, 300, h0, 760)
        draw(page, lb, 312, 586, h0, 760)
        draw(page, bot, 30, 582, 762, 786)
    else:
        lines = prep_lines(out, o, rng)
        draw(page, lines, 50, 562, 30, 772)
    for txt, side in out.margin:
        x = 24 if side == 'l' else 596
        page.insert_text((x, 640 - rng.randint(0, 200)), txt, fontname='hebo', fontsize=7.5, rotate=90)
    return page


# --------------------------------------------------------------------------
# productions
# --------------------------------------------------------------------------
def tx_line(mode, src, when, hm, i, n, job):
    if mode == 'fax':
        return f'{when.month:02d}/{when.day:02d}/{when.year} {hm}  FROM:{src.fax}  {src.abbr} HIM   JOB {job}   P.{i:03d}/{n:03d}'
    if mode == 'efax':
        return f'eFax relay | rcvd {when.year}-{when.month:02d}-{when.day:02d}T{hm} | doc {job} | pg {i}/{n}'
    if mode == 'secure':
        return f'<<SENT VIA SECUREXCH {MON[when.month - 1].upper()} {when.day} {when.year} {hm}:{(i * 7) % 60:02d} ID={job} [{i}/{n}]>>'
    if mode == 'relay':
        return f'Received by fax {MON[when.month - 1]} {when.day} {when.year} {hm} -- page {i} of {n} -- {src.name}'
    return None


def stamp(rng, kind, when, extra=''):
    dd = f'{MON[when.month - 1].upper()} {when.day:02d} {when.year}'
    return {
        'imaged': f'IMAGED {dd}',
        'indexed': f'INDEXED BY: {extra or rng.choice(["KT", "RVM", "JLO", "AD"])} {when.year}{when.month:02d}{when.day:02d}',
        'work': 'ATTORNEY WORK COPY',
        'dup': 'DUPLICATE - DO NOT FILE',
        'released': f'Released per authorization #{extra}',
        'received': f'RECEIVED {dd} - CLAIMS DIV.',
        'scanned': 'SCANNED -- HIM',
        'mediation': 'COPY FOR MEDIATION -- CONFIDENTIAL',
        'outside': f'OUTSIDE RECORD - FILED TO CHART {when.month}-{when.day}-{when.year}',
        'noredisc': 'REVIEWED -- NOT FOR RE-RELEASE',
    }[kind]


ANNOT = ['pre-existing?? see 2023 chiro', 'gap in tx -- ask', 'causation?', 'MRI ordered late', 'check bill vs note',
         'reasonable', 'compare to ER note', '-> IME', 'pt no-show?', 'why 2 inj?', 'ok per policy', 'f/u w/ atty',
         'dup of p. 14?', 'note dated after DOS', 'high charge']


def add_overlay(out, rng, kind, text, role='over'):
    b = Blk(text, font=rng.choice(['hebo', 'cobo', 'tibo']), size=rng.choice([7.5, 8, 9]), role=role,
            align=rng.choice(['l', 'r', 'c']))
    if kind == 'top':
        out.top.append(b)
    elif kind == 'bottom':
        out.bottom.append(b)
    elif kind == 'margin':
        out.margin.append((text, rng.choice('lr')))
    elif kind == 'append':
        out.append = text
    elif kind == 'mid':
        out.mid.append((rng.randint(6, 20), b))


def add_stamp(out, rng, kind, text):
    add_overlay(out, rng, kind, text)
    out.mech.append('stamp')


def assemble(G, scale):
    rng = random.Random(G.c['seed'] * 13 + int(scale * 1000))
    outs = []
    meds = G.med_provs
    R1 = G.auth_date + TD(rng.randint(2, 9))
    ann_used = set()

    def chart(P, with_embed=True):
        recs = [o for o in G.records[P.key]]
        emb = G.embeds.get(P.key, []) if with_embed else []
        res = [(o, None) for o in recs]
        if emb:
            pos = min(len(res), rng.randint(1, max(1, len(res) // 3)))
            res = res[:pos] + [(o, 'emb') for o in emb] + res[pos:]
        return res

    # ---------- production 1: provider releases to plaintiff counsel ----------
    p1 = []
    G.req1, G.cert1 = {}, {}
    for P in meds:
        reqref = f'{G.firm.abbr}-{G.n}{rng.randint(100, 999)}-{P.key.upper()}'
        req = G.request_letter(P, R1, reqref)
        rel = R1 + TD(rng.randint(6, 35))
        recs = chart(P)
        cert = G.certification(P, rel, P.cust[0], len(recs), reqref)
        G.req1[P.key], G.cert1[P.key] = req, cert
        cover = G.fax_cover(P, rel, len(recs) + 4, f'Records released in response to your request {reqref}. Invoice to follow.')
        seq = [(cover, None), (req, None), (G.auth, None), (cert, None)] + recs
        mode = rng.choice(['fax', 'efax', 'secure', 'relay', 'mail'])
        hm = f'{rng.randint(8, 17):02d}:{rng.randint(0, 59):02d}'
        job = f'{rng.randint(1000, 99999)}'
        rel_stamp = rng.random() < .45
        pk = []
        for i, (o, tag) in enumerate(seq, 1):
            out = Out(o, P.name, 1, 'embedded_in_chart' if tag == 'emb' else 'provider_release')
            if tag == 'emb':
                src = o.prov
                when = o.date + TD(rng.randint(1, 20))
                if rng.random() < .6:
                    add_overlay(out, rng, 'top', tx_line(rng.choice(['fax', 'relay']), src, when, f'{rng.randint(8, 18):02d}:{rng.randint(0, 59):02d}', rng.randint(1, 4), rng.randint(4, 9), rng.randint(100, 9999)))
                add_stamp(out, rng, rng.choice(['top', 'margin', 'append']), stamp(rng, rng.choice(['outside', 'scanned']), when))
            line = tx_line(mode, P, rel, hm, i, len(seq), job)
            if line:
                add_overlay(out, rng, 'top' if mode in ('fax', 'secure') else 'bottom', line)
                out.mech.append(mode)
            if rel_stamp and i > 1:
                add_stamp(out, rng, 'bottom', stamp(rng, 'released', rel, G.auth_no))
            if i == 1:
                add_stamp(out, rng, rng.choice(['top', 'margin']), stamp(rng, 'imaged', rel + TD(rng.randint(1, 5))))
                add_stamp(out, rng, 'append', stamp(rng, 'indexed', rel + TD(rng.randint(1, 5))))
            pk.append(out)
        p1.append(pk)
    rng.shuffle(p1)
    prods = {1: [x for pk in p1 for x in pk]}

    # ---------- production 2: re-production after a second request ----------
    k2 = max(1, min(len(meds), round(len(meds) * .35 * scale)))
    p2provs = rng.sample(meds, k2)
    R2 = R1 + TD(rng.randint(55, 80))
    p2 = []
    for P in p2provs:
        reqref = f'{G.firm.abbr}-{G.n}{rng.randint(100, 999)}-{P.key.upper()}R'
        # same body as the first letter: rebuild with new date and new reference only
        req2 = G.request_letter(P, R2, reqref)
        rel = R2 + TD(rng.randint(5, 30))
        recs = chart(P, with_embed=rng.random() < .5)
        if rng.random() < .4:
            recs = [r for r in recs if r[0].kind != 'billing']
        cert2 = G.certification(P, rel, P.cust[1], len(recs), reqref)
        cover2 = G.fax_cover(P, rel, len(recs) + 4, f'Second production in response to request {reqref}. Records reprinted from the current electronic system.')
        seq = [(cover2, None), (req2, None), (G.auth, None), (cert2, None)] + recs
        mode = rng.choice(['fax', 'efax', 'secure', 'relay'])
        hm = f'{rng.randint(8, 17):02d}:{rng.randint(0, 59):02d}'
        job = f'{rng.choice("QWXZ")}{rng.randint(1000, 9999)}'
        refl = dict(wrap=rng.choice([.72, .8, 1.15]), size=rng.choice([.9, 1.08, .95]), fam=rng.choice([None, 'helv', 'tiro', 'cour']))
        for i, (o, tag) in enumerate(seq, 1):
            out = Out(o, P.name, 2, 'second_request_reprint' if i > 4 else 'provider_release')
            if i > 4:
                out.reflow = refl
                out.mech.append('reflow')
            if tag == 'emb':
                out.mech.append('embedded_in_chart')
            add_overlay(out, rng, 'top', tx_line(mode, P, rel, hm, i, len(seq), job))
            out.mech.append(mode)
            if i > 4 and rng.random() < .3:
                add_stamp(out, rng, rng.choice(['margin', 'top', 'append']), stamp(rng, 'dup', rel))
            p2.append(out)
    prods[2] = p2

    # ---------- production 3: patient-portal downloads ----------
    cand = [P for P in meds if P.role in ('spec', 'therapy', 'hospital', 'imaging', 'lab')]
    p3 = []
    for P in rng.sample(cand, min(len(cand), max(1, round(1.5 * scale)))):
        when = G.last_day + TD(rng.randint(5, 60))
        hm = f'{rng.randint(1, 12)}:{rng.randint(0, 59):02d} {rng.choice(["AM", "PM"])}'
        recs = [o for o in G.records[P.key] if o.kind == 'clinical']
        recs = [o for o in recs if rng.random() < min(.9, .55 * scale)]
        nh = rng.random() < .6
        for i, o in enumerate(recs, 1):
            out = Out(o, P.name, 3, 'portal_download')
            if nh and rng.random() < .55:
                out.nohdr = True
                out.mech.append('header_missing')
            add_overlay(out, rng, 'bottom', f'Downloaded from patient portal ({P.abbr} HealthLink account) on {MON[when.month - 1]} {when.day}, {when.year} {hm} by {G.pt["first"][0]}. {G.pt["last"]} -- {i}/{len(recs)}')
            p3.append(out)
    prods[3] = p3

    # ---------- production 4: insurer claim file ----------
    R4 = R2 + TD(rng.randint(10, 40))
    demand = G.misc_letter(G.firm, 'SETTLEMENT DEMAND - POLICY LIMITS', R4, [
        f'Re: Your insured / claim {G.claimno}. Our client {G.pt["first"]} {G.pt["last"]} was injured in a {G.c["short"]} on {mdy(G.acc)}.',
        'Enclosed are the medical records and itemized bills supporting the claim. Total medical specials are summarized in the attached bills. We demand the policy limits within 30 days.'])
    seq = [demand]
    frac = min(.95, .38 * scale)
    for P in meds:
        for o in G.records[P.key]:
            if o.kind == 'billing' or rng.random() < frac:
                seq.append(o)
    p4 = []
    nann = rng.randint(3, 5)
    ann_idx = set(rng.sample(range(1, len(seq)), min(nann, len(seq) - 1)))
    for i, o in enumerate(seq, 1):
        out = Out(o, G.ins.name, 4, 'insurer_claim_file')
        when = R4 + TD(rng.randint(2, 6))
        add_stamp(out, rng, rng.choice(['top', 'append', 'margin']), stamp(rng, 'received', when))
        b = Blk(f'{G.claimno} / {i:04d}', font='cobo', size=8, align='r', role='late')
        out.bottom.append(b)
        out.mech.append('claim_bates')
        if (i - 1) in ann_idx and o.cid not in ann_used:
            ann_used.add(o.cid)
            txt = rng.choice(ANNOT)
            out.mid.append((rng.randint(6, 18), Blk(f'   {txt}  -- {rng.choice(["jh", "mk", "adj."])}', font=rng.choice(['heit', 'tiit', 'coit']), size=11, role='annot')))
            if rng.random() < .5:
                out.margin.append((rng.choice(['??', '!!', 'see ER']) + ' ' + rng.choice(['(circled)', '<--', '*']), 'r'))
            out.mech.append('handwritten_annotation')
        p4.append(out)
    prods[4] = p4

    # ---------- production 5: defense subpoena production (scanned, Bates) ----------
    R5 = R4 + TD(rng.randint(30, 70))
    plet = G.misc_letter(G.dfirm, 'PRODUCTION OF RECORDS OBTAINED BY SUBPOENA', R5, [
        f'Pursuant to the parties\' agreement, defendant serves copies of records obtained by subpoena regarding plaintiff {G.pt["first"]} {G.pt["last"]}, Bates-labeled as indicated. Plaintiff may inspect the originals on request.',
        'This production includes records from the providers listed in the accompanying subpoena index.'])
    dprov = rng.sample(meds, min(len(meds), max(2, round(len(meds) * .55 * scale))))
    dseq = [(plet, None)]
    dfrac = min(.95, .7 * scale)
    for P in dprov:
        dseq.append((G.cert1[P.key], None))
        for o, tag in chart(P, with_embed=rng.random() < .6):
            if rng.random() < dfrac:
                dseq.append((o, tag))
    ocr_rate = rng.uniform(.012, .035)
    pre = ''.join(w[0] for w in G.dfirm.name.split() if w[0].isupper())
    p5 = []
    i = 0
    bates = rng.randint(1, 400)
    twoups = 0
    while i < len(dseq):
        o, tag = dseq[i]
        out = Out(o, G.dfirm.name, 5, 'defense_production')
        out.ocr = ocr_rate * rng.uniform(.6, 1.5)
        out.mech.append('ocr_scan')
        if tag == 'emb':
            out.mech.append('embedded_in_chart')
        if (twoups < 3 and i + 1 < len(dseq) and o.kind == 'clinical' and dseq[i + 1][0].kind == 'clinical'
                and dseq[i + 1][0].prov is o.prov and dseq[i + 1][0].cid != o.cid and rng.random() < .12):
            out.two = dseq[i + 1][0]
            out.mech.append('two_up')
            twoups += 1
            i += 1
        elif rng.random() < .07:
            out.crop = True
            out.mech.append('cropped')
        elif rng.random() < .05 and o.kind == 'clinical':
            out.nohdr = True
            out.mech.append('header_missing')
        if rng.random() < .12:
            add_stamp(out, rng, rng.choice(['margin', 'top', 'append']), stamp(rng, rng.choice(['work', 'noredisc']), R5))
        out.bottom.append(Blk(f'{pre}-DEF {bates:06d}', font='cobo', size=8.5, align='r', role='late'))
        out.mech.append('bates')
        bates += 1
        p5.append(out)
        i += 1
    prods[5] = p5

    # ---------- production 6: mediation binder ----------
    R6 = R5 + TD(rng.randint(40, 90))
    key = [o for o in G.origs if o.kind == 'clinical' and set(o.tags) & {'er_note', 'op_report', 'img_report', 'consult', 'dc_summary', 'hp', 'therapy_reeval', 'proc'}]
    key = [o for o in key if rng.random() < min(.95, .55 * scale)]
    key += [o for o in G.origs if 'ledger' in o.tags and rng.random() < .6]
    key.sort(key=lambda o: (o.date, o.cid))
    idx_lines = []
    exn = 1
    groups = []
    for o in key:
        if not groups or groups[-1][0].doc != o.doc:
            groups.append([o])
        else:
            groups[-1].append(o)
    for gi, g in enumerate(groups, 1):
        idx_lines.append(f'Exhibit {gi}: {g[0].prov.name} -- {mdy(g[0].date)} ({len(g)} p.)')
    idx_pages = []
    for k in range(0, len(idx_lines), 34):
        body = [Blk(f'Mediation set: {G.pt["last"]} v. defendants   Session date {mdy(R6)}'), Blk('')] + [Blk(x) for x in idx_lines[k:k + 34]]
        idx_pages.append(G.admin_page(G.mediator, f'MEDIATION BINDER - EXHIBIT INDEX ({k // 34 + 1})', R6 - TD(7), body, owner=G.mediator, tags=['index']))
    p6 = [Out(o, G.mediator.name, 6, 'mediator_binder') for o in idx_pages]
    for gi, g in enumerate(groups, 1):
        for j, o in enumerate(g, 1):
            out = Out(o, G.mediator.name, 6, 'mediator_binder')
            out.bottom.append(Blk(f'EX. {gi:02d}  |  p. {j} of {len(g)}', font='tibo', size=9, align='c', role='late'))
            out.mech.append('exhibit_stamp')
            if rng.random() < .35:
                add_stamp(out, rng, rng.choice(['top', 'margin', 'append']), stamp(rng, 'mediation', R6))
            if rng.random() < .15:
                out.reflow = dict(wrap=.85, size=1.05, fam=None)
                out.mech.append('reflow')
            elif rng.random() < .1:
                out.crop = True
                out.mech.append('cropped')
            p6.append(out)
    prods[6] = p6

    order = [2, 3, 4, 5, 6]
    rng.shuffle(order)
    final = prods[1] + [x for k in order for x in prods[k]]
    return final


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def run_case(spec):
    best = None
    for scale in [1.0, .85, 1.2, .7, 1.4, .55, 1.6, 1.85, 2.1, 2.4]:
        G = CaseGen(spec)
        G.build()
        outs = assemble(G, scale)
        T = len(outs)
        U = len({o.o.cid for o in outs})
        dup = (T - U) / T
        ok = .5 <= dup <= .75 and 220 <= T <= 420
        score = (0 if ok else 1, abs(dup - .62) + abs(T - 320) / 1000)
        if best is None or score < best[0]:
            best = (score, G, outs, scale)
        if ok:
            break
    _, G, outs, scale = best
    folder = os.path.join(OUTROOT, f'alt3-{spec["n"]}')
    os.makedirs(folder, exist_ok=True)
    doc = fitz.open()
    pages = []
    for i, out in enumerate(outs, 1):
        r = random.Random(spec['seed'] * 100003 + i)
        render_page(doc, out, r)
        pages.append(dict(page=i, content_id=out.o.cid, provider=out.provider, production=out.prod,
                          mechanism='+'.join(dict.fromkeys(m for m in out.mech if m)), doc_kind=out.o.kind))
    doc.set_metadata({'title': f'alt3-{spec["n"]} case file', 'author': 'alt3 synthetic generator', 'creator': 'generate_alt3.py',
                      'producer': 'PyMuPDF', 'creationDate': 'D:20260101000000Z', 'modDate': 'D:20260101000000Z'})
    doc.save(os.path.join(folder, 'records.pdf'), garbage=3, deflate=True, no_new_id=True)
    doc.close()
    events = G.finalize_events()
    regions = spec['regions']
    truth = dict(case_id=f'alt3-{spec["n"]}', patient=dict(first=spec['first'], last=spec['last'], dob=mdy(spec['dob'])),
                 accident_date=mdy(spec['acc']), regions=regions, events=events, pages=pages)
    with open(os.path.join(folder, 'truth.json'), 'w', encoding='utf-8') as f:
        json.dump(truth, f, indent=1, ensure_ascii=False)
    T = len(pages)
    U = len({p['content_id'] for p in pages})
    return T, U


def main():
    tot_T = tot_U = 0
    for spec in CASES:
        T, U = run_case(spec)
        tot_T += T
        tot_U += U
        print(f'alt3-{spec["n"]}: pages={T} unique_originals={U} duplicate={100 * (T - U) / T:.1f}%')
    print(f'TOTAL: pages={tot_T} unique_originals={tot_U} duplicate={100 * (tot_T - tot_U) / tot_T:.1f}%')


if __name__ == '__main__':
    main()
