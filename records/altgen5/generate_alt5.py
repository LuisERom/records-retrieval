#!/usr/bin/env python3
"""generate_alt5.py - independent synthetic personal-injury medical-records generator.

Writes records/data/alt5/alt5-1 .. alt5-10, each with records.pdf (text layer) and
truth.json.  Deterministic: fixed seeds, no timestamps or random IDs in the PDF, so a
rerun produces byte-identical files.  Standard library only (own minimal PDF writer).

Usage:  python generate_alt5.py [--out DIR] [--cases N]
"""
import copy
import datetime as dt
import json
import os
import random
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.normpath(os.path.join(HERE, '..', 'data', 'alt5'))
MASTER_SEED = 51109

# ---------------------------------------------------------------------------
# Minimal PDF writer (Type1 standard fonts, WinAnsi, Flate content streams)
# ---------------------------------------------------------------------------
FONTS = ['Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique', 'Times-Roman', 'Times-Bold',
         'Times-Italic', 'Courier', 'Courier-Bold', 'Courier-Oblique']
FONT_KEY = {f: 'F%d' % (i + 1) for i, f in enumerate(FONTS)}


def pdf_escape(s):
    s = s.encode('latin-1', 'replace').decode('latin-1')
    return s.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def build_pdf(pages):
    """pages: list of lists of items (x, y, font, size, text, rot)."""
    objs = {}
    n_fonts = len(FONTS)
    first_page_obj = 3 + n_fonts
    kids = []
    for i in range(len(pages)):
        kids.append(first_page_obj + 2 * i)
    objs[1] = b'<< /Type /Catalog /Pages 2 0 R >>'
    objs[2] = ('<< /Type /Pages /Count %d /Kids [%s] >>' % (
        len(pages), ' '.join('%d 0 R' % k for k in kids))).encode()
    font_res = []
    for i, f in enumerate(FONTS):
        objs[3 + i] = ('<< /Type /Font /Subtype /Type1 /BaseFont /%s /Encoding /WinAnsiEncoding >>' % f).encode()
        font_res.append('/%s %d 0 R' % (FONT_KEY[f], 3 + i))
    font_dict = '<< %s >>' % ' '.join(font_res)
    for i, items in enumerate(pages):
        pobj = first_page_obj + 2 * i
        cobj = pobj + 1
        ops = []
        for (x, y, font, size, text, rot) in items:
            if not text:
                continue
            if rot:
                m = '0 1 -1 0 %.2f %.2f Tm' % (x, y)
            else:
                m = '1 0 0 1 %.2f %.2f Tm' % (x, y)
            ops.append('BT /%s %.1f Tf %s (%s) Tj ET' % (FONT_KEY[font], size, m, pdf_escape(text)))
        raw = '\n'.join(ops).encode('latin-1')
        comp = zlib.compress(raw, 6)
        objs[pobj] = ('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font %s >> /Contents %d 0 R >>'
                      % (font_dict, cobj)).encode()
        objs[cobj] = b'<< /Length %d /Filter /FlateDecode >>\nstream\n' % len(comp) + comp + b'\nendstream'
    out = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offsets = {}
    nmax = max(objs)
    for k in range(1, nmax + 1):
        offsets[k] = len(out)
        out += b'%d 0 obj\n' % k + objs[k] + b'\nendobj\n'
    xref = len(out)
    out += b'xref\n0 %d\n' % (nmax + 1)
    out += b'0000000000 65535 f \n'
    for k in range(1, nmax + 1):
        out += b'%010d 00000 n \n' % offsets[k]
    out += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (nmax + 1, xref)
    return bytes(out)


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------
MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
          'September', 'October', 'November', 'December']
MON3 = [m[:3] for m in MONTHS]
MONDOT = ['Jan.', 'Feb.', 'Mar.', 'Apr.', 'May', 'June', 'July', 'Aug.', 'Sept.', 'Oct.', 'Nov.', 'Dec.']
WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


def ordn(n):
    if 10 <= n % 100 <= 20:
        suf = 'th'
    else:
        suf = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return '%d%s' % (n, suf)


def fd(d, st, hm=(9, 0)):
    y, m, dd = d.year, d.month, d.day
    h, mi = hm
    M = MONTHS[m - 1]
    A = MON3[m - 1]
    W = WEEKDAYS[d.weekday()]
    w = W[:3]
    h12 = h % 12 or 12
    ap = 'AM' if h < 12 else 'PM'
    y2 = y % 100
    t = {
        'mdy4': '%02d/%02d/%d' % (m, dd, y),
        'mdy4n': '%d/%d/%d' % (m, dd, y),
        'mdy2': '%02d/%02d/%02d' % (m, dd, y2),
        'mdy2n': '%d/%d/%02d' % (m, dd, y2),
        'mdy4dash': '%02d-%02d-%d' % (m, dd, y),
        'mdy2dash': '%02d-%02d-%02d' % (m, dd, y2),
        'mdy4dot': '%02d.%02d.%d' % (m, dd, y),
        'mdy2dotn': '%d.%d.%02d' % (m, dd, y2),
        'iso': '%d-%02d-%02d' % (y, m, dd),
        'ymdslash': '%d/%02d/%02d' % (y, m, dd),
        'compact': '%d%02d%02d' % (y, m, dd),
        'long': '%s %d, %d' % (M, dd, y),
        'longpad': '%s %02d, %d' % (M, dd, y),
        'longnc': '%s %d %d' % (M, dd, y),
        'LONG': '%s %d, %d' % (M.upper(), dd, y),
        'abbr': '%s %d, %d' % (A, dd, y),
        'abbrdot': '%s %d, %d' % (MONDOT[m - 1], dd, y),
        'abbrnc': '%s %d %d' % (A, dd, y),
        'ABBRPAD': '%s %02d %d' % (A.upper(), dd, y),
        'oracle': '%02d-%s-%d' % (dd, A.upper(), y),
        'oraclecompact': '%02d%s%d' % (dd, A.upper(), y),
        'dmonthy': '%d %s %d' % (dd, M, y),
        'dmony': '%d-%s-%d' % (dd, A, y),
        'mondash': '%s-%02d-%d' % (A, dd, y),
        'wklong': '%s, %s %d, %d' % (W, M, dd, y),
        'wknum': '%s %02d/%02d/%d' % (w, m, dd, y),
        'wkabbr': '%s, %s %d, %d' % (w, A, dd, y),
        'ord': '%s %s, %d' % (M, ordn(dd), y),
        'legal': 'the %s day of %s, %d' % (ordn(dd), M, y),
        'ordof': '%s of %s %d' % (ordn(dd), M, y),
        'ts24': '%02d/%02d/%d %02d:%02d' % (m, dd, y, h, mi),
        'ts12': '%02d/%02d/%d %d:%02d %s' % (m, dd, y, h12, mi, ap),
        'tsiso': '%d-%02d-%02dT%02d:%02d:00' % (y, m, dd, h, mi),
        'tsisosp': '%d-%02d-%02d %02d:%02d' % (y, m, dd, h, mi),
        'tscompact': '%d%02d%02d%02d%02d' % (y, m, dd, h, mi),
        'tsabbr12': '%s %d %d %d:%02d%s' % (A, dd, y, h12, mi, ap),
        'tsmdy2mil': '%d/%d/%02d %02d%02d' % (m, dd, y2, h, mi),
        'tslongat': '%s %d, %d at %d:%02d %s.m.' % (M, dd, y, h12, mi, 'a' if h < 12 else 'p'),
        'tsdashn12': '%d-%d-%d %d:%02d%s' % (m, dd, y, h12, mi, ap.lower()),
    }
    return t[st]


DATE_ONLY_STYLES = ['mdy4', 'mdy4n', 'mdy2', 'mdy2n', 'mdy4dash', 'mdy2dash', 'mdy4dot', 'mdy2dotn',
                    'iso', 'ymdslash', 'compact', 'long', 'longpad', 'longnc', 'LONG', 'abbr', 'abbrdot',
                    'abbrnc', 'ABBRPAD', 'oracle', 'oraclecompact', 'dmonthy', 'dmony', 'mondash', 'wklong',
                    'wknum', 'wkabbr', 'ord', 'legal', 'ordof']
TS_STYLES = ['ts24', 'ts12', 'tsiso', 'tsisosp', 'tscompact', 'tsabbr12', 'tsmdy2mil', 'tslongat', 'tsdashn12']
VISIT_STYLES = [s for s in DATE_ONLY_STYLES if s not in ('legal', 'ordof')]
BODY_STYLES = ['long', 'abbr', 'mdy2n', 'mdy4n', 'abbrdot', 'ord', 'longnc', 'mdy4', 'dmonthy', 'abbrnc']
BILL_STYLES = ['mdy4', 'mdy2', 'compact', 'iso', 'mdy4dash', 'oracle', 'mdy2n']


def date_variants(d):
    return [fd(d, s) for s in DATE_ONLY_STYLES]


def add_days(d, n):
    return d + dt.timedelta(days=n)


def weekday_on_or_after(d):
    while d.weekday() >= 5:
        d = add_days(d, 1)
    return d


# ---------------------------------------------------------------------------
# Invented world
# ---------------------------------------------------------------------------
STEMS = ['Harrowgate', 'Pellston', 'Quillmark', 'Brindlecreek', 'Ostrander', 'Calloway Ridge', 'Wexmoor',
         'Tamsin Valley', 'Larchfield', 'Corbin Hollow', 'Sable Point', 'Merriweather', 'Fallowmere',
         'Ashgrove', 'Kettering Bluff', 'Dunmore Park', 'Veridian', 'Holloway Bay', 'Stonebrook',
         'Marlow Heights', 'Penrose', 'Copperline', 'Juniper Flats', 'Redfern', 'Ironwood', 'Halcyon',
         'Bellhaven', 'Graystone', 'Thornbury', 'Lakemont', 'Willowmere', 'Cresthaven', 'Silverleaf',
         'Northgate', 'Kingsbridge', 'Riverbend', 'Fairmount', 'Hawthorne Glen', 'Oakhurst', 'Sutter Creek',
         'Blue Heron', 'Cedar Knoll', 'Windward', 'Granite Hill', 'Pine Hollow', 'Elmstead', 'Rosemont',
         'Cobalt Bay', 'Mossbank', 'Trillium', 'Saltmarsh', 'Brackenridge', 'Westerly', 'Owlcreek',
         'Linden Reach', 'Galloway', 'Pembury', 'Hartwell', 'Castine', 'Ridgeback', 'Quarry Lane',
         'Amberfield', 'Tolland', 'Winslow Cove', 'Draycott', 'Fenwick', 'Larkspur', 'Morrow', 'Kestrel']
TYPE_NAMES = {
    'ems': ['{s} Fire Rescue', '{s} County EMS', '{s} Ambulance Authority', '{s} Emergency Medical Services'],
    'er': ['{s} Regional Medical Center', '{s} General Hospital', '{s} Memorial Hospital', '{s} Community Hospital'],
    'urgent': ['{s} Urgent Care', '{s} Walk-In Clinic', '{s} Immediate Care'],
    'pcp': ['{s} Family Medicine', '{s} Primary Care Associates', '{s} Internal Medicine Group', '{s} Family Health Clinic'],
    'ortho': ['{s} Orthopaedic & Spine', '{s} Bone and Joint Institute', '{s} Sports Medicine & Orthopedics', '{s} Orthopedic Specialists'],
    'imaging': ['{s} Diagnostic Imaging', '{s} Open MRI', '{s} Radiology Partners', '{s} Imaging Center'],
    'pt': ['{s} Physical Therapy', '{s} Rehab & Performance', '{s} Physiotherapy Center', '{s} Movement Clinic'],
    'chiro': ['{s} Chiropractic', '{s} Spine & Wellness', '{s} Chiropractic Health Center'],
    'pain': ['{s} Pain & Interventional Spine', '{s} Pain Management Specialists', '{s} Interventional Pain Institute'],
    'asc': ['{s} Surgery Center', '{s} Ambulatory Surgical Center', '{s} Outpatient Surgical Suites'],
    'neuro': ['{s} Neurology Associates', '{s} Headache & Neurology Clinic', '{s} Brain and Spine Neurology'],
}
CITIES = [('Danforth', 'OH', '43'), ('Millbrae Junction', 'NV', '89'), ('Port Carrow', 'GA', '30'),
          ('Easton Mills', 'PA', '18'), ('Velasco', 'TX', '77'), ('Harlan Springs', 'KY', '40'),
          ('Brookhollow', 'MO', '63'), ('Sanderling', 'FL', '33'), ('Wickham', 'NC', '27'),
          ('Ostrava Falls', 'MN', '55'), ('Tallis', 'AZ', '85'), ('Corriveau', 'MI', '48'),
          ('New Bexley', 'NJ', '07'), ('Arden Crossing', 'TN', '37'), ('Shawcross', 'IN', '46')]
STREETS = ['Corliss Ave', 'Medical Pkwy', 'Laurel Rd', 'N. Halsted Blvd', 'Grange St', 'Pioneer Dr',
           'Commerce Way', 'Old Mill Rd', 'Wellness Ct', 'Briar Ln', 'Route 9', 'Hospital Dr',
           'Market St', 'Kingfisher Blvd', 'Ashby Ave', 'Tremont Pl']
PFIRST_M = ['Dorian', 'Thaddeus', 'Mateo', 'Rashid', 'Kellan', 'Bertrand', 'Osvaldo', 'Anders', 'Cyrus',
            'Desmond', 'Ignacio', 'Lionel', 'Percival', 'Quentin', 'Rowan', 'Silas', 'Tobias', 'Wendell']
PFIRST_F = ['Annelise', 'Bettina', 'Cordelia', 'Dahlia', 'Esperanza', 'Fiona', 'Giselle', 'Henrietta',
            'Imogen', 'Juliana', 'Katrin', 'Leonora', 'Maribel', 'Noemi', 'Ottilie', 'Priya', 'Rosalind',
            'Soledad', 'Tamsin', 'Yvette']
PLAST = ['Achterberg', 'Balestrieri', 'Castellanos', 'Drummond-Pike', 'Eberhardt', 'Fairbanks', 'Gallardo',
         'Haverford', 'Ishikawa', 'Jablonski', 'Kowalczyk', 'Lindqvist', 'Mbeki', 'Nakashima', 'Okonkwo',
         'Petrakis', 'Quigley', 'Rasmussen', 'Szabo', 'Thibodeaux', 'Underhill', 'Valdivia', 'Whitlock',
         'Yarborough', 'Zielinski', 'Ferreira-Lund', 'Oyelaran']
CFIRST = ['Adaeze', 'Brennan', 'Celestine', 'Dmitri', 'Elspeth', 'Farid', 'Gwendolyn', 'Hollis', 'Ingrid',
          'Jasper', 'Kalinda', 'Lucian', 'Marisa', 'Nikhil', 'Orla', 'Pascal', 'Renata', 'Sorin', 'Theda',
          'Umberto', 'Vesna', 'Warrick', 'Xiomara', 'Yusuf', 'Zelda', 'Cormac', 'Delphine', 'Emeka']
CLAST = ['Abernathy', 'Bhattacharya', 'Coyle', 'Delacroix', 'Esterhaus', 'Furtado', 'Grimaldi', 'Hendry',
         'Iversen', 'Joubert', 'Kaczmarek', 'Lombardo', 'Mendelsohn', 'Nwosu', 'Ostrowski', 'Prentiss',
         'Ravensworth', 'Sokolova', 'Tremblay', 'Uchida', 'Vanterpool', 'Wojcik', 'Yeager', 'Zamora',
         'Ashcombe', 'Brightwater', 'Castellane', 'Duquesne', 'Ellery', 'Fontaine']
LAW_PLAINTIFF = ['Okafor Brandt & Liu, PLLC', 'Merrow Sandoval Injury Law', 'The Kessler-Obi Law Group',
                 'Pruett, Halvorsen & Dey, P.A.', 'Anwar & Castellucci LLP', 'Treadwell Justice Partners',
                 'Lomax & Ferraro Trial Lawyers', 'Hightower Nakamura, LLC', 'Bramlett Quinones PLLC',
                 'Saint-Clair & Moody Attorneys']
LAW_DEFENSE = ['Strand Whitcombe LLP', 'Garrity Fenn & Polk', 'Ashdown Mercer Defense Counsel',
               'Ruiz-Kaplan Litigation, P.C.', 'Dunleavy & Orr LLP', 'Conway Pritchard Hale',
               'Vickery Osei LLP', 'Marchetti Bolton & Webb', 'Hollins Grant Parrish', 'Eastman Rudd LLC']
INSURERS = ['Bluehaven Mutual Casualty Co.', 'Keystone Shield Insurance Company', 'Pinnacle Harbor Indemnity',
            'Northfield Assurance Group', 'Covenant Plains Insurance Exchange', 'Meridian Oak Casualty',
            'Granary Mutual Insurance', 'Tidewater General Indemnity', 'Arrowline Property & Casualty',
            'Sentinel Ridge Insurance Co.']
PORTALS = ['MyHealthLink', 'CareConnect Portal', 'PatientGate', 'HealthTrail', 'ChartView Online']

INCIDENTS = [
    dict(kind='rear-end motor vehicle collision', story='was the restrained driver of a sedan stopped at a red light when struck from behind by a pickup truck traveling an estimated 35 mph',
         ext='V43.52XA', ems=True, regions=['neck', 'lumbar', 'shoulder', 'head', 'thoracic']),
    dict(kind='T-bone intersection collision', story='was the restrained front passenger in a minivan broadsided on the passenger side by a vehicle that ran a stop sign; airbags deployed',
         ext='V43.63XA', ems=True, regions=['neck', 'shoulder', 'head', 'lumbar', 'hip']),
    dict(kind='slip and fall in a grocery store', story='slipped on liquid on the floor of a grocery store aisle, falling backward and landing on the buttocks and outstretched hand',
         ext='W01.0XXA', ems=False, regions=['lumbar', 'wrist', 'shoulder', 'neck']),
    dict(kind='trip on a raised sidewalk slab', story='tripped on a raised section of municipal sidewalk and fell forward onto the knee and outstretched arms',
         ext='W01.0XXA', ems=False, regions=['knee', 'wrist', 'shoulder']),
    dict(kind='motorcycle versus car collision', story='was operating a motorcycle when a car turned left across the lane; patient laid the bike down and slid approximately 20 feet, wearing a helmet',
         ext='V23.4XXA', ems=True, regions=['knee', 'shoulder', 'neck', 'lumbar', 'ankle']),
    dict(kind='pedestrian struck in a crosswalk', story='was walking in a marked crosswalk when struck by a slow-moving SUV making a right turn, thrown onto the hood and then to the pavement',
         ext='V03.10XA', ems=True, regions=['head', 'neck', 'hip', 'knee', 'lumbar']),
    dict(kind='fall from a collapsing apartment stairway railing', story='was descending exterior apartment stairs when the handrail gave way and the patient fell approximately six feet to the landing below',
         ext='W10.8XXA', ems=True, regions=['lumbar', 'shoulder', 'ankle', 'thoracic']),
    dict(kind='rideshare passenger collision', story='was a seat-belted rear passenger in a rideshare vehicle that rear-ended a box truck on the interstate at moderate speed',
         ext='V43.62XA', ems=True, regions=['neck', 'thoracic', 'lumbar', 'knee']),
    dict(kind='sideswipe by a delivery truck', story='was driving on a four-lane highway when a delivery truck changed lanes into the driver side, pushing the car into the guardrail',
         ext='V44.5XXA', ems=False, regions=['neck', 'shoulder', 'lumbar']),
    dict(kind='fall on wet loading-dock ramp at a retail store', story='was making a vendor delivery and slipped on an untreated icy loading-dock ramp, twisting the knee and striking the shoulder',
         ext='W00.0XXA', ems=False, regions=['knee', 'shoulder', 'lumbar']),
]

PRIOR_REASONS = [
    ('annual preventive examination; no musculoskeletal complaints', ['Z00.00'], ['99396'], 'Annual wellness examination'),
    ('acute pharyngitis with sore throat for three days', ['J02.9'], ['99213'], 'Acute pharyngitis'),
    ('follow-up of essential hypertension, blood pressure controlled on lisinopril', ['I10'], ['99213'], 'Hypertension follow-up'),
    ('contact dermatitis of both forearms after gardening', ['L23.9'], ['99212'], 'Contact dermatitis'),
    ('persistent cough after a viral illness', ['R05.9'], ['99213'], 'Post-viral cough'),
    ('gastroesophageal reflux symptoms', ['K21.9'], ['99213'], 'Reflux symptoms'),
    ('mixed hyperlipidemia, review of fasting lipid panel', ['E78.2'], ['99214'], 'Lipid follow-up'),
    ('right ankle sprain from a recreational soccer game, resolved', ['S93.401D'], ['99213'], 'Healing ankle sprain'),
]


def region_info(key, side):
    S = side.capitalize() if side else ''
    s = side or ''
    R = {
        'neck': dict(name='cervical spine', plain='neck', A=['S13.4XXA', 'M54.2'], D=['S13.4XXD', 'M54.2'], L=['M50.20', 'M54.12'],
                     xr=('72040', 'XR CERVICAL SPINE 2-3 VIEWS'), mri=('72141', 'MRI CERVICAL SPINE WITHOUT CONTRAST'),
                     xr_find='No acute fracture or subluxation. Straightening of the normal cervical lordosis, which may be positional or related to muscle spasm. Prevertebral soft tissues are normal.',
                     mri_find='At C5-C6 there is a broad-based posterior disc protrusion measuring 3 mm that mildly flattens the ventral thecal sac with mild left neural foraminal narrowing. C4-C5 and C6-C7 show minimal disc bulging without stenosis.',
                     mri_imp='C5-C6 disc protrusion with mild left foraminal narrowing.',
                     mri_imp_alt='C5-C6 disc protrusion with moderate left foraminal narrowing.',
                     exam='Paraspinal tenderness from C3 to C7 with palpable spasm of the upper trapezius. Rotation limited to about 50 degrees bilaterally. Spurling maneuver reproduces radiating pain into the left forearm.',
                     inj=('62321', 'cervical interlaminar epidural steroid injection at C6-C7 under fluoroscopic guidance'),
                     surg=('22551', 'anterior cervical discectomy and fusion at C5-C6')),
        'lumbar': dict(name='lumbar spine', plain='low back', A=['S33.5XXA', 'M54.50'], D=['S33.5XXD', 'M54.50'], L=['M51.26', 'M54.16'],
                       xr=('72100', 'XR LUMBAR SPINE 2-3 VIEWS'), mri=('72148', 'MRI LUMBAR SPINE WITHOUT CONTRAST'),
                       xr_find='Vertebral body heights and alignment are maintained. Mild disc space narrowing at L5-S1. No pars defect. No acute fracture.',
                       mri_find='At L4-L5 there is a central and right paracentral disc protrusion measuring 4 mm with an annular fissure, contacting the traversing right L5 nerve root. Mild bilateral facet arthropathy. L5-S1 shows a small disc bulge without stenosis.',
                       mri_imp='L4-L5 right paracentral protrusion with annular fissure contacting the right L5 root.',
                       mri_imp_alt='L4-L5 right paracentral protrusion with annular fissure compressing the right L5 root.',
                       exam='Tenderness over the L4-S1 paraspinals with guarding. Flexion limited to 40 degrees with pain on return from flexion. Straight leg raise positive on the right at 45 degrees.',
                       inj=('64483', 'right L4-L5 transforaminal epidural steroid injection under fluoroscopy'),
                       surg=('63030', 'right L4-L5 hemilaminotomy and microdiscectomy')),
        'thoracic': dict(name='thoracic spine', plain='mid back', A=['S23.3XXA', 'M54.6'], D=['S23.3XXD', 'M54.6'], L=['M54.6'],
                         xr=('72070', 'XR THORACIC SPINE 2 VIEWS'), mri=('72146', 'MRI THORACIC SPINE WITHOUT CONTRAST'),
                         xr_find='Normal thoracic kyphosis. No compression deformity. Paraspinal lines are normal.',
                         mri_find='Small central disc protrusion at T7-T8 without cord contact. No marrow edema or fracture.',
                         mri_imp='Small T7-T8 protrusion without cord contact.', mri_imp_alt='Small T7-T8 protrusion abutting the ventral cord.',
                         exam='Tenderness of the mid-thoracic paraspinals T5-T9 with rhomboid spasm. Pain with trunk rotation.',
                         inj=None, surg=None),
        'shoulder': dict(name='%s shoulder' % s, plain='%s shoulder' % s,
                         A=['S43.40%dA' % (1 if s == 'right' else 2), 'M25.51%d' % (1 if s == 'right' else 2)],
                         D=['S43.40%dD' % (1 if s == 'right' else 2), 'M25.51%d' % (1 if s == 'right' else 2)],
                         L=['S46.0%d1A' % (1 if s == 'right' else 2)],
                         xr=('73030', 'XR %s SHOULDER MINIMUM 2 VIEWS' % s.upper()), mri=('73221', 'MRI %s SHOULDER WITHOUT CONTRAST' % s.upper()),
                         xr_find='No fracture or dislocation. Acromiohumeral interval is preserved. Mild acromioclavicular joint degenerative change.',
                         mri_find='Full-thickness tear of the supraspinatus tendon at the footprint measuring 11 mm in the anteroposterior dimension with 9 mm of retraction. Subacromial-subdeltoid bursal fluid. Labrum intact.',
                         mri_imp='Full-thickness supraspinatus tear with 9 mm retraction.', mri_imp_alt='Full-thickness supraspinatus tear with 14 mm retraction.',
                         exam='%s shoulder: tenderness over the greater tuberosity. Active forward flexion 110 degrees, abduction 90 degrees. Positive Hawkins and Neer signs; drop-arm test equivocal. Strength 4-/5 in external rotation.' % S,
                         inj=('20610', '%s subacromial corticosteroid injection' % s),
                         surg=('29827', '%s shoulder arthroscopic rotator cuff repair with subacromial decompression' % s)),
        'knee': dict(name='%s knee' % s, plain='%s knee' % s,
                     A=['S80.0%dXA' % (1 if s == 'right' else 2), 'M25.56%d' % (1 if s == 'right' else 2)],
                     D=['S80.0%dXD' % (1 if s == 'right' else 2), 'M25.56%d' % (1 if s == 'right' else 2)],
                     L=['S83.24%dA' % (1 if s == 'right' else 2)],
                     xr=('73562', 'XR %s KNEE 3 VIEWS' % s.upper()), mri=('73721', 'MRI %s KNEE WITHOUT CONTRAST' % s.upper()),
                     xr_find='No fracture. Small joint effusion. Joint spaces preserved.',
                     mri_find='Oblique tear of the posterior horn of the medial meniscus extending to the inferior articular surface. Grade 1 MCL sprain. Moderate joint effusion. ACL and PCL intact.',
                     mri_imp='Posterior horn medial meniscus tear; grade 1 MCL sprain.', mri_imp_alt='Posterior horn medial meniscus tear with displaced fragment; grade 1 MCL sprain.',
                     exam='%s knee: medial joint line tenderness, trace effusion, flexion to 105 degrees. McMurray test positive medially. Lachman negative.' % S,
                     inj=('20610', '%s knee intra-articular corticosteroid injection' % s),
                     surg=('29881', '%s knee arthroscopic partial medial meniscectomy' % s)),
        'wrist': dict(name='%s wrist' % s, plain='%s wrist' % s,
                      A=['S52.50%dA' % (1 if s == 'right' else 2), 'M25.53%d' % (1 if s == 'right' else 2)],
                      D=['S52.50%dD' % (1 if s == 'right' else 2), 'M25.53%d' % (1 if s == 'right' else 2)],
                      L=['S52.50%dD' % (1 if s == 'right' else 2)],
                      xr=('73110', 'XR %s WRIST 3+ VIEWS' % s.upper()), mri=('73221', 'MRI %s WRIST WITHOUT CONTRAST' % s.upper()),
                      xr_find='Nondisplaced extra-articular fracture of the distal radial metaphysis with dorsal soft tissue swelling. Ulnar styloid intact.',
                      mri_find='Healing distal radius fracture without displacement. Partial tear of the scapholunate ligament dorsal component.',
                      mri_imp='Healing distal radius fracture; partial scapholunate ligament tear.', mri_imp_alt='Healing distal radius fracture; complete scapholunate ligament tear.',
                      exam='%s wrist: swelling and tenderness over the distal radius, painful grip, sensation intact in median and ulnar distributions.' % S,
                      inj=None, surg=('25607', 'open treatment of %s distal radius fracture with internal fixation' % s)),
        'head': dict(name='head', plain='head', A=['S06.0X0A', 'R51.9'], D=['S06.0X0D', 'G44.309'], L=['F07.81', 'G44.309'],
                     xr=('70450', 'CT HEAD WITHOUT CONTRAST'), mri=('70551', 'MRI BRAIN WITHOUT CONTRAST'),
                     xr_find='No acute intracranial hemorrhage, mass effect or midline shift. Ventricles normal in size. Calvarium intact.',
                     mri_find='No acute infarct or hemorrhage. No susceptibility artifact to suggest microhemorrhage. Normal brain parenchyma for age.',
                     mri_imp='Normal MRI of the brain.', mri_imp_alt='Normal MRI of the brain; incidental mucosal thickening of the left maxillary sinus.',
                     exam='Alert and oriented, slowed responses on serial sevens, mild photophobia, normal cranial nerves, tandem gait slightly unsteady.',
                     inj=None, surg=None),
        'hip': dict(name='%s hip' % s, plain='%s hip' % s, A=['S70.0%dXA' % (1 if s == 'right' else 2), 'M25.55%d' % (1 if s == 'right' else 2)],
                    D=['S70.0%dXD' % (1 if s == 'right' else 2), 'M25.55%d' % (1 if s == 'right' else 2)], L=['M25.55%d' % (1 if s == 'right' else 2)],
                    xr=('73502', 'XR %s HIP 2-3 VIEWS' % s.upper()), mri=('73721', 'MRI %s HIP WITHOUT CONTRAST' % s.upper()),
                    xr_find='No fracture. Hip joint space preserved. Soft tissue swelling lateral to the greater trochanter.',
                    mri_find='Contusion of the greater trochanter with trochanteric bursitis. Labrum intact.',
                    mri_imp='Greater trochanteric contusion and bursitis.', mri_imp_alt='Greater trochanteric contusion, bursitis and gluteus medius tendinopathy.',
                    exam='%s hip: tenderness over the greater trochanter, pain with resisted abduction, FABER negative.' % S, inj=('20610', '%s trochanteric bursa injection' % s), surg=None),
        'ankle': dict(name='%s ankle' % s, plain='%s ankle' % s, A=['S93.40%dA' % (1 if s == 'right' else 2), 'M25.57%d' % (1 if s == 'right' else 2)],
                      D=['S93.40%dD' % (1 if s == 'right' else 2), 'M25.57%d' % (1 if s == 'right' else 2)], L=['S93.40%dD' % (1 if s == 'right' else 2)],
                      xr=('73610', 'XR %s ANKLE 3 VIEWS' % s.upper()), mri=('73721', 'MRI %s ANKLE WITHOUT CONTRAST' % s.upper()),
                      xr_find='No fracture. Lateral soft tissue swelling. Mortise intact.',
                      mri_find='High-grade partial tear of the anterior talofibular ligament; calcaneofibular ligament sprain. Small bone bruise of the talar dome.',
                      mri_imp='High-grade ATFL partial tear with talar dome bone bruise.', mri_imp_alt='Complete ATFL tear with talar dome bone bruise.',
                      exam='%s ankle: swelling and ecchymosis laterally, tenderness over the ATFL, anterior drawer mildly positive.' % S, inj=None, surg=None),
    }
    return R[key]


# ---------------------------------------------------------------------------
# Provider style profiles
# ---------------------------------------------------------------------------
GENERAL_LABELS = ['Date of Service:', 'DOS:', 'Visit Date:', 'Encounter Date:', 'Date Seen:', 'Service Date:',
                  'Appt Date:', 'Date of Visit:', 'Treatment Date:', 'Date of Encounter:', 'Svc Dt:', 'Seen:',
                  'Visit:', 'Encounter:', 'Clinic Date:', 'Office Visit:', 'Date of Exam:', 'Visit Dt', 'Seen on',
                  'D.O.S.', 'Encounter Dt/Tm:', 'Appointment:', 'Date/Time of Visit:']
KIND_LABELS = {
    'ems': ['Date of Call:', 'Run Date:', 'Dispatch Date:', 'Call Rec\'d:', 'Incident Dt:', 'PSAP Call:'],
    'er_visit': ['Arrival:', 'Arrival Date/Time:', 'Admit Date/Time:', 'ED Arrival:', 'Registration:', 'Triage Time:'],
    'imaging': ['Exam Date:', 'Date of Exam:', 'Study Date:', 'Performed:', 'Scan Date:', 'Acquired:', 'Exam Performed:'],
    'lab': ['Collected:', 'Collection Date:', 'Specimen Collected:', 'Drawn:', 'Coll Dt/Tm:'],
    'pt': ['Session Date:', 'Date of Treatment:', 'Tx Date:', 'Visit Date:', 'Treatment Session:', 'Therapy Date:'],
    'procedure': ['Date of Procedure:', 'Procedure Date:', 'DOP:', 'Procedure Performed:'],
    'surgery': ['Date of Surgery:', 'Surgery Date:', 'Date of Operation:', 'OR Date:', 'Operative Date:'],
}
SIGN_TEMPLATES = [
    'Electronically signed by {clin} on {sd}',
    'Signed: {clin}    Date: {sd}',
    'Dictated by: {clin}   D: {dd}   T: {td}   /{ini}',
    'Attested: {clin}  {sd}.  I have reviewed and agree with the documentation above.',
    'Reviewed and authenticated {sd} by {clin}',
    '{clin}  -- e-signature applied {sd}',
    'Note finalized {sd}  Author: {clin}',
    'Authenticated by {clin} (Electronic Signature)  {sd}',
]
FOOTER_TEMPLATES = [
    'Page {i} of {n}',
    'pg {i}/{n}    Printed {pd}',
    '{pname} - CONFIDENTIAL PATIENT INFORMATION - Page {i}',
    'Run Date {pd}   User: ROI{uid}   Page {i} of {n}',
    'Printed by HIM on {pd} -- {i}/{n}',
    '{mrn} | Page {i} | {pd}',
    '*** End of page {i} ***   Report printed {pd}',
]
NAME_FORMATS = ['LAST, FIRST', 'First Last', 'LAST, First', 'Last, First M.', 'FIRST M LAST']


def fmt_name(p, style):
    f, l, mi = p['first'], p['last'], p['mi']
    return {'LAST, FIRST': '%s, %s' % (l.upper(), f.upper()), 'First Last': '%s %s' % (f, l),
            'LAST, First': '%s, %s' % (l.upper(), f), 'Last, First M.': '%s, %s %s.' % (l, f, mi),
            'FIRST M LAST': '%s %s %s' % (f.upper(), mi, l.upper())}[style]


def make_provider(rng, ptype, used_stems):
    stem = rng.choice([s for s in STEMS if s not in used_stems])
    used_stems.append(stem)
    name = rng.choice(TYPE_NAMES[ptype]).format(s=stem)
    city, st, z = rng.choice(CITIES)
    addr = '%d %s%s, %s, %s %s%03d' % (rng.randint(100, 9899), rng.choice(STREETS),
                                       rng.choice(['', ', Suite %d' % rng.randint(100, 480), ', Bldg %s' % rng.choice('ABC')]),
                                       city, st, z, rng.randint(0, 999))
    area = rng.randint(201, 989)
    phone = '(%d) 555-%04d' % (area, rng.randint(100, 199))
    fax = '(%d) 555-%04d' % (area, rng.randint(100, 199))
    creds = {'ems': ['EMT-P', 'Paramedic', 'EMT-B'], 'er': ['MD', 'DO', 'PA-C', 'RN'], 'urgent': ['MD', 'PA-C', 'NP'],
             'pcp': ['MD', 'DO', 'NP'], 'ortho': ['MD', 'DO', 'PA-C'], 'imaging': ['MD'], 'pt': ['PT, DPT', 'DPT', 'PTA'],
             'chiro': ['DC'], 'pain': ['MD', 'DO'], 'asc': ['MD', 'CRNA', 'RN'], 'neuro': ['MD', 'DO']}[ptype]
    clins = []
    for k in range(rng.randint(2, 3)):
        clins.append('%s %s, %s' % (rng.choice(CFIRST), rng.choice(CLAST), creds[min(k, len(creds) - 1)]))
    font = rng.choice(['Helvetica', 'Times-Roman', 'Courier', 'Helvetica', 'Times-Roman'])
    bold = {'Helvetica': 'Helvetica-Bold', 'Times-Roman': 'Times-Bold', 'Courier': 'Courier-Bold'}[font]
    p = dict(type=ptype, name=name, stem=stem, addr=addr, phone=phone, fax=fax, clins=clins,
             font=font, bold=bold, size=rng.choice([9.0, 9.5, 10.0]),
             hdr=rng.randint(0, 4), pblock=rng.randint(0, 3), name_fmt=rng.choice(NAME_FORMATS),
             visit_style=rng.choice(VISIT_STYLES + ['ts24', 'ts12', 'tsiso'] if ptype in ('ems', 'er') else VISIT_STYLES),
             run_style=rng.choice(VISIT_STYLES), body_style=rng.choice(BODY_STYLES),
             sign_style=rng.choice(TS_STYLES + ['mdy4', 'abbr', 'iso', 'long']),
             print_style=rng.choice(TS_STYLES + ['mdy4', 'iso', 'mdy2']),
             dob_style=rng.choice(['mdy4', 'mdy4n', 'iso', 'abbr', 'mdy4dash', 'oracle', 'long', 'mdy2']),
             bill_style=rng.choice(BILL_STYLES),
             sign_tpl=rng.choice(SIGN_TEMPLATES), footer_tpl=rng.choice(FOOTER_TEMPLATES),
             mrn=rng.choice(['MRN: %09d', 'Acct# H%07d', 'Chart ID %06d', 'Pt ID: %d', 'Med Rec No. %08d', 'Account %d']) % rng.randint(100000, 9999999),
             mrn_short=None, uid='%02d' % rng.randint(1, 40),
             unlabeled=(rng.random() < 0.22),
             fax_fmt=rng.randint(0, 5),
             labels={}, label_rng_seed=rng.randint(0, 10 ** 9))
    p['mrn_short'] = p['mrn'].split()[-1]
    return p


def visit_label(p, kind):
    if kind not in p['labels']:
        r = random.Random(p['label_rng_seed'] + hash_str(kind))
        key = {'ems': 'ems', 'er_visit': 'er_visit', 'imaging': 'imaging', 'lab': 'lab', 'pt_eval': 'pt', 'pt_visit': 'pt',
               'pt_reeval': 'pt', 'procedure': 'procedure', 'surgery': 'surgery'}.get(kind)
        pool = list(KIND_LABELS.get(key, [])) * 2 + GENERAL_LABELS if key else GENERAL_LABELS
        p['labels'][kind] = r.choice(pool)
    return p['labels'][kind]


def hash_str(s):
    h = 0
    for ch in s:
        h = (h * 131 + ord(ch)) % 1000000007
    return h


# ---------------------------------------------------------------------------
# Page model helpers
# ---------------------------------------------------------------------------
CHAR_W = {'Helvetica': 0.53, 'Helvetica-Bold': 0.58, 'Helvetica-Oblique': 0.53, 'Times-Roman': 0.47,
          'Times-Bold': 0.5, 'Times-Italic': 0.46, 'Courier': 0.6, 'Courier-Bold': 0.6, 'Courier-Oblique': 0.6}
USABLE = 500.0


def wrap(text, font, size, indent=0):
    width = int((USABLE - indent) / (size * CHAR_W[font]))
    words = text.split(' ')
    lines, cur = [], ''
    for w in words:
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= width:
            cur += ' ' + w
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or ['']


class PB:
    """Page builder."""
    _pid = [0]

    def __init__(self, p):
        self.p = p
        self.lines = []

    def ln(self, t, role='body', font=None, size=None, x=0, prot=False, gap=0):
        self.lines.append(dict(t=t, role=role, f=font or self.p['font'], s=size or self.p['size'], x=x, prot=prot, para=None, gap=gap))

    def para(self, t, heading=None, x=0, role='body'):
        if heading:
            self.ln(heading, role=role, font=self.p['bold'], gap=4)
        PB._pid[0] += 1
        pid = PB._pid[0]
        for w in wrap(t, self.p['font'], self.p['size'], x):
            self.lines.append(dict(t=w, role=role, f=self.p['font'], s=self.p['size'], x=x, prot=False, para=pid, gap=0))

    def row(self, cells, widths, font='Courier', size=8.5):
        tabs, x = [], 0.0
        for w in widths:
            tabs.append(x)
            x += w * size * CHAR_W[font]
        self.lines.append(dict(t='\t'.join(c.strip() for c in cells), role='body', f=font, s=size, x=0, prot=False, para=None,
                               gap=0, tabs=tabs))

    def blank(self):
        self.lines.append(dict(t='', role='body', f=self.p['font'], s=self.p['size'], x=0, prot=False, para=None, gap=0))

    def page(self):
        return dict(lines=self.lines, abs=[])


def layout(page):
    """Return list of PDF items."""
    items = []
    lines = [l for l in page['lines']]
    total = sum(l['s'] * 1.22 + l['gap'] for l in lines)
    scale = 1.0
    if total > 728:
        scale = 728.0 / total
    y = 760.0
    for l in lines:
        y -= (l['s'] * 1.22 + l['gap']) * scale
        if l['t'] and l.get('tabs') and '\t' in l['t']:
            for cell, tx in zip(l['t'].split('\t'), l['tabs']):
                if cell:
                    items.append((54 + l['x'] + tx, y, l['f'], round(max(6.0, l['s'] * scale), 1), cell, 0))
        elif l['t']:
            sz = l['s'] * scale
            est = len(l['t']) * sz * CHAR_W[l['f']]
            if 54 + l['x'] + est > 566:
                sz = sz * (566 - 54 - l['x']) / est
            items.append((54 + l['x'], y, l['f'], round(max(5.0, sz), 1), l['t'].replace('\t', '  '), 0))
    for a in page['abs']:
        items.append((a['x'], a['y'], a['f'], a['s'], a['t'], a.get('rot', 0)))
    return items


def page_text(page):
    return '\n'.join([l['t'].replace('\t', ' ') for l in page['lines']] + [a['t'] for a in page['abs']])


# ---------------------------------------------------------------------------
# Headers, footers, signatures
# ---------------------------------------------------------------------------
NETWORKS = ['Tri-County', 'Lakeshore', 'Prairie Crest', 'Coastal Plains', 'Summit Valley', 'Blue Ridge Allied']
DEPTS = {'ems': 'Field Operations', 'er': 'Emergency Department', 'urgent': 'Walk-In Services', 'pcp': 'Adult Medicine',
         'ortho': 'Orthopaedic Clinic', 'imaging': 'Radiology', 'pt': 'Outpatient Rehabilitation', 'chiro': 'Clinical Services',
         'pain': 'Interventional Spine', 'asc': 'Perioperative Services', 'neuro': 'Neurology Clinic'}


def begin_page(C, p, title, ev, i, n):
    """Start a clinical page; returns PB with header written. ev: dict(date, time, kind)."""
    pb = PB(p)
    vd = fd(ev['date'], p['visit_style'], ev.get('time', (9, 0)))
    lab = visit_label(p, ev['kind'])
    pname = fmt_name(C['patient'], p['name_fmt'])
    dob = fd(C['dob'], p['dob_style'])
    big = p['size'] + 2
    if i == 0:
        h = p['hdr']
        if h == 0:
            pb.ln(p['name'].upper(), role='hdr', font=p['bold'], size=big)
            pb.ln(p['addr'], role='hdr')
            pb.ln('Tel %s    Fax %s' % (p['phone'], p['fax']), role='hdr')
            pb.ln('-' * 72, role='hdr', size=p['size'] - 1)
        elif h == 1:
            pb.ln('%s | %s | Ph %s | Fx %s' % (p['name'], p['addr'], p['phone'], p['fax']), role='hdr', size=p['size'] - 1.5)
        elif h == 2:
            pb.ln('**** %s ****' % p['name'].upper(), role='hdr', font='Courier-Bold', size=p['size'] + 1)
            pb.ln('Dept: %s    %s' % (DEPTS[p['type']], p['phone']), role='hdr')
        elif h == 3:
            pb.ln(p['name'], role='hdr', font=p['bold'], size=big, x=210)
            pb.ln(p['addr'], role='hdr', x=210, size=p['size'] - 1)
            pb.ln('A member of %s Health Network' % NETWORKS[hash_str(p['name']) % len(NETWORKS)], role='hdr', x=210, size=p['size'] - 1)
        if p['unlabeled']:
            pb.ln('%s        %s' % (title.upper(), vd), role='hdr', font=p['bold'], size=p['size'] + 1, prot=True, gap=6)
        else:
            pb.ln(title.upper() if h != 1 else '== %s ==' % title.upper(), role='hdr', font=p['bold'], size=p['size'] + 1, gap=6)
        pv = p['pblock']
        dl = '' if p['unlabeled'] else '%s %s' % (lab, vd)
        if pv == 0:
            pb.ln('Patient: %s      DOB: %s      %s' % (pname, dob, p['mrn']), role='hdr')
            if dl:
                pb.ln(dl, role='hdr', prot=True)
        elif pv == 1:
            pb.ln(('NAME: %s   BIRTHDATE: %s   %s   %s' % (pname, dob, p['mrn'], dl)).rstrip(), role='hdr', prot=bool(dl))
        elif pv == 2:
            pb.ln('Pt Name: %s' % pname, role='hdr')
            pb.ln(('D.O.B.: %s      %s' % (dob, dl)).rstrip(), role='hdr', prot=bool(dl))
        else:
            if dl:
                pb.ln('%s     Patient %s (%s)     %s' % (dl, pname, dob, p['mrn']), role='hdr', prot=True)
            else:
                pb.ln('Patient %s (%s)     %s' % (pname, dob, p['mrn']), role='hdr')
        pb.ln('', role='hdr')
    else:
        rd = fd(ev['date'], p['run_style'])
        v = hash_str(p['name']) % 3
        if v == 0:
            pb.ln(('%s  |  DOB %s  |  %s %s  |  continued' % (pname, dob, '' if p['unlabeled'] else lab, rd)).replace('|   ', '| '),
                  role='hdr', prot=True, size=p['size'] - 0.5)
        elif v == 1:
            pb.ln('%s (cont.) - %s - %s' % (title, pname, rd), role='hdr', prot=True, font=p['bold'])
        else:
            pb.ln('%s    %s    %s    %s' % (p['name'], pname, p['mrn'], rd), role='hdr', prot=True, size=p['size'] - 0.5)
        pb.ln('', role='hdr')
    return pb


def end_page(pb, C, p, i, n, print_date):
    pd = fd(print_date, p['print_style'], (10 + hash_str(p['name']) % 7, 5 + hash_str(p['stem']) % 50))
    t = p['footer_tpl'].format(i=i + 1, n=n, pd=pd, pname=fmt_name(C['patient'], p['name_fmt']), mrn=p['mrn'], uid=p['uid'])
    pb.ln('', role='ftr')
    if p['hdr'] == 4:
        pb.ln(p['name'] + '  ' + p['phone'], role='ftr', size=p['size'] - 1.5)
    pb.ln(t, role='ftr', size=p['size'] - 1.5)
    return pb.page()


def sign_line(p, clin, d, rng):
    sd_date = add_days(d, rng.choice([0, 0, 1, 1, 2, 3, 5]))
    hm = (rng.randint(7, 21), rng.randint(0, 59))
    sd = fd(sd_date, p['sign_style'], hm)
    dd = fd(d, p['run_style'])
    td = fd(add_days(d, rng.choice([1, 2])), p['run_style'])
    ini = ''.join(rng.choice('abcdefghjkmnprstw') for _ in range(3))
    return p['sign_tpl'].format(clin=clin, sd=sd, dd=dd, td=td, ini=ini)


def bt(p, d):
    return fd(d, p['body_style'])


# ---------------------------------------------------------------------------
# Clinical document builders.  Each returns list of page models.
# ---------------------------------------------------------------------------
def regs_text(C, ev):
    names = [C['reg'][r]['plain'] for r in ev['regions']]
    if len(names) == 1:
        return names[0]
    return ', '.join(names[:-1]) + ' and ' + names[-1]


def doc_prior(C, p, ev, rng, pdate):
    reason, codes, procs, short = ev['extra']
    pb = begin_page(C, p, rng.choice(['Office Visit', 'Progress Note', 'Clinic Note']), ev, 0, 1)
    pb.para('Patient presents for %s.' % reason, 'CHIEF COMPLAINT')
    pb.para('%s %s, a %d-year-old established patient, is seen today (%s). Last seen in this office %s. No interval '
            'hospitalizations or injuries. Works full time as %s without restrictions.' % (
                C['patient']['first'], C['patient']['last'], C['age_at'](ev['date']), bt(p, ev['date']),
                bt(p, add_days(ev['date'], -rng.randint(120, 400))), C['job']), 'HISTORY')
    pb.para('Musculoskeletal: denies neck pain, back pain, joint pain, stiffness or weakness. Neurologic: denies headaches, '
            'numbness or tingling. All other systems reviewed and negative except as noted.', 'REVIEW OF SYSTEMS')
    pb.para('BP %d/%d, HR %d, Temp 98.%d F, SpO2 %d%%, Wt %d lb. General: well appearing. Neck: supple, full range of motion. '
            'Back: no spinal or paraspinal tenderness. Extremities: full strength and range of motion in all four limbs.' % (
                rng.randint(112, 138), rng.randint(70, 88), rng.randint(60, 88), rng.randint(0, 9), rng.randint(96, 99), C['weight']),
            'EXAMINATION')
    pb.para('%s (%s).' % (short, ', '.join(codes)), 'ASSESSMENT')
    pb.para('Continue current medications. Return in %d months or sooner as needed; next appointment %s.' % (
        rng.choice([3, 6, 12]), bt(p, add_days(ev['date'], rng.choice([91, 182, 365])))), 'PLAN')
    pb.ln('')
    pb.ln(sign_line(p, ev['clin'], ev['date'], rng))
    return [end_page(pb, C, p, 0, 1, pdate)]


def doc_ems(C, p, ev, rng, pdate):
    pages = []
    t0 = ev['time']

    def tt(add):
        m = t0[0] * 60 + t0[1] + add
        return '%02d:%02d' % ((m // 60) % 24, m % 60)
    pb = begin_page(C, p, 'Patient Care Report', ev, 0, 2)
    pb.para('Incident #%s   Unit M-%d   Response: Emergent   Priority 2' % (ev['inc_no'], rng.randint(11, 59)))
    pb.para('Dispatched %s  Enroute %s  On scene %s  Pt contact %s  Transport %s  At destination %s  Back in service %s' % (
        tt(0), tt(1), tt(9), tt(10), tt(24), tt(41), tt(70)), 'TIMES')
    pb.para('%s, %s.' % (C['location'], C['city']), 'INCIDENT LOCATION')
    pb.para('Crew arrived to find a %d-year-old %s who %s. Complains of %s pain rated %d/10. Denies loss of consciousness%s. '
            'Spinal motion restriction applied per protocol.' % (
                C['age_at'](ev['date']), C['sex_word'], C['incident']['story'], regs_text(C, ev), rng.randint(6, 9),
                ' but reports feeling dazed' if 'head' in ev['regions'] else ''), 'NARRATIVE')
    pb.ln('VITALS', font=p['bold'], gap=4)
    for k in range(3):
        pb.ln('  %s   BP %d/%d   P %d   R %d   SpO2 %d%%   GCS %d   Pain %d/10' % (
            tt(12 + 10 * k), rng.randint(128, 158), rng.randint(78, 96), rng.randint(84, 112), rng.randint(16, 22),
            rng.randint(95, 99), 15 if 'head' not in ev['regions'] or k else 14, rng.randint(6, 9)))
    pages.append(end_page(pb, C, p, 0, 2, pdate))
    pb = begin_page(C, p, 'Patient Care Report', ev, 1, 2)
    for r in ev['regions']:
        ri = C['reg'][r]
        pb.para('%s: tenderness and guarding reported; no deformity; distal pulses and sensation intact.' % ri['name'].capitalize(), None)
    pb.para('Cervical collar and padded scoop per protocol. IV access 18g L AC, saline lock. Fentanyl %d mcg IV for pain with '
            'improvement to %d/10. Cold pack to affected areas.' % (rng.choice([50, 75, 100]), rng.randint(4, 6)), 'TREATMENT')
    pb.para('Transported without incident to %s Emergency Department; care transferred to the charge nurse with verbal report. '
            'Date of injury %s.' % (C['er_name'], fd(C['acc'], p['run_style'])), 'DISPOSITION')
    pb.ln('Crew: %s (lead); %s' % (ev['clin'], p['clins'][-1]))
    pb.ln('Receiving RN signature on file  Time %s' % tt(43))
    pb.ln(sign_line(p, ev['clin'], ev['date'], rng))
    pages.append(end_page(pb, C, p, 1, 2, pdate))
    return pages


def doc_er(C, p, ev, rng, pdate):
    pages = []
    n = 3
    h, m = ev['time']
    pb = begin_page(C, p, 'Emergency Department Record', ev, 0, n)
    pb.para('Arrived by %s. Acuity ESI %d. Allergies: %s. Home medications: %s.' % (
        'ambulance' if C['has_ems'] else 'private vehicle', rng.choice([3, 3, 4]), rng.choice(['NKDA', 'penicillin (rash)', 'sulfa', 'NKDA']),
        rng.choice(['none', 'lisinopril 10 mg daily', 'oral contraceptive', 'sertraline 50 mg daily', 'none'])), 'TRIAGE')
    pb.para('Triage note: %s per patient. Complains of %s pain. Pain %d/10. Accident occurred %s.' % (
        C['incident']['kind'], regs_text(C, ev), rng.randint(6, 9), fd(C['acc'], p['body_style'])))
    pb.ln('Vitals at triage: BP %d/%d  HR %d  RR %d  T 98.%d  SpO2 %d%%' % (
        rng.randint(124, 150), rng.randint(76, 94), rng.randint(80, 104), rng.randint(14, 20), rng.randint(1, 8), rng.randint(96, 100)))
    pb.para('Patient placed in room %d. Ice applied. Instructed on call light. Fall-risk screen negative.' % rng.randint(4, 31), 'NURSING')
    pb.ln('Triage RN: %s' % p['clins'][-1])
    pages.append(end_page(pb, C, p, 0, n, pdate))
    pb = begin_page(C, p, 'Emergency Department Record', ev, 1, n)
    pb.para('%s %s is a %d-year-old %s who %s. Presents with %s pain. %s' % (
        C['patient']['first'], C['patient']['last'], C['age_at'](ev['date']), C['sex_word'], C['incident']['story'],
        regs_text(C, ev), 'Reports brief confusion after the event, no vomiting.' if 'head' in ev['regions'] else 'No loss of consciousness.'),
        'HISTORY OF PRESENT ILLNESS')
    pb.para(' '.join(C['reg'][r]['exam'] for r in ev['regions']), 'PHYSICAL EXAM')
    pb.para('Imaging ordered: %s. Results reviewed: no acute dislocation%s. %s' % (
        '; '.join(C['reg'][r]['xr'][1] for r in ev['regions']),
        '' if 'wrist' not in ev['regions'] else '; nondisplaced distal radius fracture, splinted',
        'Labs reviewed, unremarkable.' if ev.get('has_lab') else ''), 'MEDICAL DECISION MAKING')
    pb.para('; '.join(ev['codes']), 'DIAGNOSES (ICD-10)')
    pb.ln('ED Physician: %s' % ev['clin'])
    pb.ln(sign_line(p, ev['clin'], ev['date'], rng))
    pages.append(end_page(pb, C, p, 1, n, pdate))
    pb = begin_page(C, p, 'Discharge Instructions', ev, 2, n)
    pb.para('You were seen today for injuries from a %s. Your diagnosis: %s.' % (C['incident']['kind'], regs_text(C, ev) + ' sprain/strain'), None)
    pb.para('Ibuprofen 600 mg by mouth every 6 hours with food as needed. Cyclobenzaprine 5 mg at bedtime as needed for spasm; '
            'do not drive while taking. Apply ice 20 minutes at a time.', 'MEDICATIONS')
    pb.para('Follow up with your primary care provider or orthopedics within 3 to 5 days, on or before %s. Return immediately '
            'for numbness, weakness, worsening headache or loss of bladder control.' % fd(add_days(ev['date'], 5), p['body_style']), 'FOLLOW-UP')
    pb.ln('Discharged %02d:%02d in stable condition, ambulatory, accompanied by family.' % ((h + 4) % 24, (m + 17) % 60))
    pb.ln('Patient signature: on file      Witness: %s' % p['clins'][-1])
    pages.append(end_page(pb, C, p, 2, n, pdate))
    return pages


def doc_urgent(C, p, ev, rng, pdate):
    pb = begin_page(C, p, 'Urgent Care Visit', ev, 0, 2)
    pb.para('%s; onset %s. Complains of %s pain, %d/10, worse with movement.' % (
        C['incident']['kind'].capitalize(), fd(C['acc'], p['body_style']), regs_text(C, ev), rng.randint(5, 8)), 'CHIEF COMPLAINT / HPI')
    pb.para('Patient %s. Did not go to an emergency department. Took acetaminophen at home with minimal relief.' % C['incident']['story'])
    pb.para(' '.join(C['reg'][r]['exam'] for r in ev['regions']), 'EXAM')
    pb.para('X-rays obtained in clinic: %s.' % '; '.join(C['reg'][r]['xr'][1] for r in ev['regions']), 'STUDIES')
    pages = [end_page(pb, C, p, 0, 2, pdate)]
    pb = begin_page(C, p, 'Urgent Care Visit', ev, 1, 2)
    pb.para('; '.join(ev['codes']), 'ASSESSMENT')
    pb.para('Naproxen 500 mg twice daily with food. Methocarbamol 750 mg three times daily as needed. Work note: off work for 3 days. '
            'Follow up with primary care in one week (by %s) and orthopedics if not improving.' % fd(add_days(ev['date'], 7), p['body_style']), 'PLAN')
    pb.ln(sign_line(p, ev['clin'], ev['date'], rng))
    pages.append(end_page(pb, C, p, 1, 2, pdate))
    return pages


def doc_imaging(C, p, ev, rng, pdate):
    r = ev['regions'][0]
    ri = C['reg'][r]
    mri = ev['extra'] == 'mri'
    cpt, title = ri['mri'] if mri else ri['xr']
    pages = []
    report_d = add_days(ev['date'], rng.choice([0, 1, 1, 2]))

    def body(pb, corrected):
        pb.para('%s   CPT %s   Accession %s' % (title, cpt, ev['acc_no']), None)
        pb.para('Ordering: %s.  Indication: %s on %s; %s pain.' % (ev['ordering'], C['incident']['kind'], fd(C['acc'], p['body_style']), ri['plain']), None)
        comp = ev.get('comparison')
        pb.para('Comparison: %s' % ('%s dated %s.' % (comp[1], fd(comp[0], p['body_style'])) if comp else 'None available.'), None)
        pb.para('Technique: %s' % ('Multiplanar multisequence MR imaging was performed without intravenous contrast on a 1.5T system.' if mri
                                   else 'Standard views were obtained.'), None)
        pb.para(ri['mri_find'] if mri else ri['xr_find'], 'FINDINGS')
        imp = (ri['mri_imp_alt'] if corrected else ri['mri_imp']) if mri else ('No acute osseous abnormality.' if r != 'wrist' else 'Nondisplaced distal radius fracture.')
        pb.para(imp, 'IMPRESSION')
    pb = begin_page(C, p, 'Radiology Report', ev, 0, 1)
    body(pb, False)
    pb.ln('Reading radiologist: %s' % ev['clin'])
    pb.ln('Report date: %s' % fd(report_d, p['sign_style'], (rng.randint(8, 22), rng.randint(0, 59))))
    pb.ln(sign_line(p, ev['clin'], report_d, rng))
    pages.append(end_page(pb, C, p, 0, 1, pdate))
    if ev.get('amended'):
        pb = begin_page(C, p, 'Radiology Report - Corrected', ev, 0, 1)
        pb.ln('*** CORRECTED REPORT ***  This report supersedes the version signed %s.' % fd(report_d, p['run_style']), font=p['bold'])
        body(pb, True)
        ad = add_days(report_d, rng.randint(2, 9))
        pb.para('Addendum %s: On re-review, the degree of narrowing/retraction was understated in the original impression. '
                'Findings discussed with %s by telephone.' % (fd(ad, p['run_style']), ev['ordering']), 'ADDENDUM')
        pb.ln('Reading radiologist: %s' % ev['clin'])
        pb.ln(sign_line(p, ev['clin'], ad, rng))
        pages.append(end_page(pb, C, p, 0, 1, pdate))
    return pages


def doc_lab(C, p, ev, rng, pdate):
    pb = begin_page(C, p, 'Laboratory Results', ev, 0, 1)
    h, m = ev['time']
    pb.ln('Ordering: %s    Specimen: venous blood    Accession L%07d' % (ev['ordering'], rng.randint(1000000, 9999999)))
    pb.ln('Received in lab: %s' % fd(ev['date'], p['sign_style'], (h, (m + 23) % 60)))
    pb.ln('Resulted: %s' % fd(ev['date'], p['sign_style'], ((h + 1) % 24, (m + 41) % 60)))
    pb.ln('')
    rows = [('WBC', '%.1f' % rng.uniform(6.0, 12.5), '4.0-11.0 K/uL'), ('Hemoglobin', '%.1f' % rng.uniform(12.1, 15.8), '12.0-17.5 g/dL'),
            ('Hematocrit', '%.1f' % rng.uniform(36, 46), '36-52 %'), ('Platelets', '%d' % rng.randint(180, 390), '150-400 K/uL'),
            ('Sodium', '%d' % rng.randint(136, 144), '135-145 mmol/L'), ('Potassium', '%.1f' % rng.uniform(3.6, 4.9), '3.5-5.1 mmol/L'),
            ('Glucose', '%d' % rng.randint(86, 148), '70-99 mg/dL'), ('Creatinine', '%.2f' % rng.uniform(0.6, 1.1), '0.6-1.3 mg/dL'),
            ('CK', '%d' % rng.randint(140, 620), '30-200 U/L')]
    pb.row(['TEST', 'RESULT', 'REFERENCE'], [20, 12, 20], font='Courier-Bold', size=9)
    for name, val, ref in rows:
        lo, hi = ref.split()[0].split('-')
        flag = 'H' if float(val) > float(hi) else ''
        pb.row([name, (val + ' ' + flag).strip(), ref], [20, 12, 20], size=9)
    pb.ln('')
    pb.ln('Verified by: %s' % ev['clin'])
    return [end_page(pb, C, p, 0, 1, pdate)]


def doc_office(C, p, ev, rng, pdate):
    """Office visits: pcp follow-up, ortho, neuro, pain, chiro."""
    role = ev['role']
    pages = []
    two = ev.get('two_page', False)
    n = 2 if two else 1
    title = {'pcp': 'Follow-Up Visit', 'ortho': 'Orthopaedic Consultation' if ev.get('first') else 'Orthopaedic Follow-Up',
             'neuro': 'Neurology Consultation' if ev.get('first') else 'Neurology Follow-Up',
             'pain': 'Pain Management Evaluation' if ev.get('first') else 'Pain Management Follow-Up',
             'chiro': 'Chiropractic Daily Note' if not ev.get('first') else 'Chiropractic Initial Examination'}[role]
    if ev.get('postop'):
        title = 'Postoperative Visit'
    if ev.get('preop'):
        title = 'Preoperative Consultation'
    pb = begin_page(C, p, title, ev, 0, n)
    first = C['patient']['first']
    if role == 'chiro' and not ev.get('first'):
        pb.para('Visit %d. Patient reports %s pain at %d/10, %s since last adjustment. Sleep %s.' % (
            ev['visit_no'], regs_text(C, ev), ev['pain'], ev['subj'], ev['sleep']), 'S:')
        pb.para('Subluxation/segmental dysfunction noted at %s with hypertonicity of paraspinal musculature. Cervical ROM %d%% of normal.' % (
            ', '.join(ev['segs']), ev['rom']), 'O:')
        pb.para('; '.join(ev['codes']) + '. Responding to care as expected.', 'A:')
        pb.para('CMT %d regions (98941); myofascial release 97140 x 1 unit; mechanical traction 97012. Continue 3x/week. Next visit %s.' % (
            len(ev['segs']), bt(p, ev['next'])), 'P:')
        pb.ln(sign_line(p, ev['clin'], ev['date'], rng))
        return [end_page(pb, C, p, 0, 1, pdate)]
    if ev.get('first'):
        pb.para('%s is a %d-year-old %s referred by %s for evaluation of %s pain following a %s on %s.' % (
            first, C['age_at'](ev['date']), C['sex_word'], ev.get('ref_by', 'self'), regs_text(C, ev), C['incident']['kind'],
            fd(C['acc'], p['body_style'])), 'HISTORY OF PRESENT ILLNESS')
        pb.para('The patient %s. Initial treatment at %s. Pain is %d/10, constant with intermittent sharp exacerbations, worse with '
                'lifting and prolonged sitting. %s' % (C['incident']['story'], C['first_care'], ev['pain'],
                                                       'Reports headaches, light sensitivity and difficulty concentrating at work.' if role == 'neuro' else
                                                       'Denies prior injury or treatment to these areas.'), None)
    else:
        pb.para('Returns for follow-up of %s pain. Last visit %s. Pain now %d/10. %s' % (
            regs_text(C, ev), bt(p, ev['prev']), ev['pain'], rng.choice([
                'Physical therapy is helping some but symptoms persist with activity.',
                'Reports partial relief that lasted about two weeks.',
                'Continues to have difficulty with overhead reaching and sleep.',
                'Notes numbness in the hand/foot intermittently in the evenings.'])), 'INTERVAL HISTORY')
        if ev.get('postop'):
            pb.para('Status post %s on %s. Incisions healing well, no signs of infection.' % (
                C['surgery_desc'], bt(p, C['surgery_date'])), None)
    pb.para(' '.join(C['reg'][r]['exam'] for r in ev['regions']), 'EXAMINATION')
    if ev.get('mri_ref'):
        md, rk = ev['mri_ref']
        pb.para('MRI of the %s dated %s reviewed with the patient: %s' % (C['reg'][rk]['name'], bt(p, md), C['reg'][rk]['mri_imp']), 'IMAGING')
    if two:
        pages.append(end_page(pb, C, p, 0, n, pdate))
        pb = begin_page(C, p, title, ev, 1, n)
    pb.para('; '.join(ev['codes']), 'ASSESSMENT')
    plan = ev.get('plan') or 'Continue home exercise program and physical therapy.'
    pb.para('%s Return in %d weeks; next appointment scheduled %s.' % (plan, ev['rtc_w'], bt(p, ev['next'])), 'PLAN')
    pb.ln('')
    pb.ln(sign_line(p, ev['clin'], ev['date'], rng))
    pages.append(end_page(pb, C, p, n - 1, n, pdate))
    if ev.get('work_form'):
        pb = begin_page(C, p, 'Work / Activity Status Report', ev, 0, 1)
        pb.ln('Employer: %s' % C['employer'])
        pb.ln('Diagnosis: %s' % ', '.join(ev['codes']))
        st = ev['work_form']
        pb.ln('[%s] Off work    [%s] Modified duty    [%s] Full duty' % ('X' if st == 'off' else ' ', 'X' if st == 'mod' else ' ', 'X' if st == 'full' else ' '))
        pb.para('Restrictions: no lifting over %d lb, no repetitive overhead work, alternate sitting and standing as needed.' % ev['lift'], None)
        pb.ln('Effective through: %s' % bt(p, ev['next']))
        pb.ln('Provider: %s' % ev['clin'])
        pb.ln(sign_line(p, ev['clin'], ev['date'], rng))
        pages.append(end_page(pb, C, p, 0, 1, pdate))
    return pages


def doc_pt(C, p, ev, rng, pdate):
    k = ev['kind']
    if k == 'pt_visit':
        pb = begin_page(C, p, 'Daily Treatment Note', ev, 0, 1)
        pb.ln('Visit %d of %d authorized    Referring: %s' % (ev['visit_no'], ev['auth'], ev['ordering']))
        pb.para('Patient reports %s pain %d/10 today; %s. HEP compliance %s.' % (
            regs_text(C, ev), ev['pain'], ev['subj'], ev['hep']), 'SUBJECTIVE')
        pb.ln('INTERVENTIONS', font=p['bold'], gap=4)
        for cpt, desc, mins in ev['ints']:
            pb.ln('  %s  %-38s %d min' % (cpt, desc, mins))
        pb.para('Tolerated treatment %s. %s' % (ev['tol'], ev['obj']), 'ASSESSMENT')
        pb.para('Continue plan of care. Next visit %s.' % bt(p, ev['next']), 'PLAN')
        pb.ln('Total timed minutes: %d    Units: %d' % (sum(i[2] for i in ev['ints']), len(ev['ints'])))
        pb.ln(sign_line(p, ev['clin'], ev['date'], rng))
        return [end_page(pb, C, p, 0, 1, pdate)]
    title = 'Physical Therapy Initial Evaluation' if k == 'pt_eval' else 'Physical Therapy Re-Evaluation / Progress Report'
    pb = begin_page(C, p, title, ev, 0, 2)
    if k == 'pt_eval':
        pb.para('Referred by %s for %s pain after %s on %s. Prior level of function: independent, working full duty, exercising '
                '3x/week.' % (ev['ordering'], regs_text(C, ev), C['incident']['kind'], fd(C['acc'], p['body_style'])), 'SUBJECTIVE')
    else:
        pb.para('Patient has attended %d visits since initial evaluation on %s. Reports %d%% overall improvement. %s' % (
            ev['visits_so_far'], bt(p, ev['eval_date']), ev['improve'],
            'Post-operative course since %s.' % bt(p, C['surgery_date']) if ev.get('postop') else 'Still limited with lifting and prolonged postures.'),
            'PROGRESS SUMMARY')
    pb.ln('OBJECTIVE MEASURES', font=p['bold'], gap=4)
    for r in ev['regions']:
        pb.ln('  %-18s  ROM %d%% of expected   Strength %s/5   Pain %d/10' % (C['reg'][r]['name'], ev['rom'], ev['mmt'], ev['pain']))
    pb.ln('  Outcome measure: %s %d%%' % (ev['scale'], ev['score']))
    pb.para(' '.join(C['reg'][r]['exam'] for r in ev['regions']), 'SPECIAL TESTS / PALPATION')
    pages = [end_page(pb, C, p, 0, 2, pdate)]
    pb = begin_page(C, p, title, ev, 1, 2)
    pb.para('Patient demonstrates impairments in range of motion, strength and functional tolerance consistent with diagnoses %s. '
            'Good rehabilitation potential.' % ', '.join(ev['codes']), 'ASSESSMENT')
    pb.para('STG (3 wks): pain under %d/10; independent HEP. LTG (by %s): %s score under 20%%; return to prior level of work.' % (
        max(2, ev['pain'] - 3), bt(p, add_days(ev['date'], 42)), ev['scale']), 'GOALS')
    pb.para('Frequency 2-3x/week for 6 weeks. Certification period %s through %s. Interventions: therapeutic exercise, neuromuscular '
            're-education, manual therapy, modalities as indicated.' % (fd(ev['date'], p['run_style']), fd(add_days(ev['date'], 44), p['run_style'])), 'PLAN OF CARE')
    pb.ln('Physician certification requested from %s.' % ev['ordering'])
    pb.ln(sign_line(p, ev['clin'], ev['date'], rng))
    pages.append(end_page(pb, C, p, 1, 2, pdate))
    return pages


def doc_procedure(C, p, ev, rng, pdate):
    cpt, desc = ev['proc']
    pb = begin_page(C, p, 'Procedure Note', ev, 0, 2)
    pb.para('; '.join(ev['codes']), 'PRE-PROCEDURE DIAGNOSIS')
    pb.para('Same.', 'POST-PROCEDURE DIAGNOSIS')
    pb.para('%s (CPT %s).' % (desc[0].upper() + desc[1:], cpt), 'PROCEDURE')
    pb.para('Informed consent obtained after discussion of risks including infection, bleeding, nerve injury and headache. Time-out '
            'performed. Patient positioned and prepped with chlorhexidine. Under image guidance the needle was advanced to the target. '
            'Contrast confirmed appropriate spread without vascular uptake. Injected 80 mg methylprednisolone with 2 mL '
            'preservative-free saline. Fluoroscopy time %.1f seconds. No complications.' % rng.uniform(18, 60), 'DESCRIPTION')
    pb.ln('Pre-procedure pain %d/10; post-procedure pain %d/10.' % (ev['pain'], max(0, ev['pain'] - rng.randint(3, 5))))
    pb.ln(sign_line(p, ev['clin'], ev['date'], rng))
    pages = [end_page(pb, C, p, 0, 2, pdate)]
    pb = begin_page(C, p, 'Procedure Nursing Record', ev, 1, 2)
    h, m = ev['time']
    for lab, add in [('In room', 0), ('Procedure start', 9), ('Procedure end', 24), ('Recovery', 26), ('Discharged', 55)]:
        mm = h * 60 + m + add
        pb.ln('  %-16s %02d:%02d   BP %d/%d  HR %d  SpO2 %d%%' % (lab, mm // 60, mm % 60, rng.randint(118, 142), rng.randint(70, 88),
                                                                rng.randint(62, 90), rng.randint(96, 100)))
    pb.para('Discharged ambulatory with driver. Instructions reviewed. Nurse follow-up call scheduled %s.' % bt(p, add_days(ev['date'], 1)), None)
    pb.ln('RN: %s' % p['clins'][-1])
    pages.append(end_page(pb, C, p, 1, 2, pdate))
    return pages


def doc_surgery(C, p, ev, rng, pdate):
    cpt, desc = ev['proc']
    pb = begin_page(C, p, 'Operative Report', ev, 0, 3)
    pb.para('; '.join(ev['codes']), 'PREOPERATIVE DIAGNOSIS')
    pb.para('Same, confirmed intraoperatively.', 'POSTOPERATIVE DIAGNOSIS')
    pb.para('%s (CPT %s).' % (desc[0].upper() + desc[1:], cpt), 'PROCEDURE PERFORMED')
    pb.ln('Surgeon: %s     Assistant: %s' % (ev['clin'], p['clins'][-1]))
    pb.ln('Anesthesia: general endotracheal    EBL: %d mL    Complications: none' % rng.choice([10, 25, 50, 75]))
    pb.para('The patient was identified in the preoperative holding area, the operative site was marked, and consent was confirmed. '
            'The patient was brought to the operating room and general anesthesia was induced. Preoperative antibiotics were given '
            'within 60 minutes of incision. The patient was positioned with all bony prominences padded and prepped and draped in the '
            'usual sterile fashion. A surgical time-out was completed.', 'DESCRIPTION OF PROCEDURE')
    pages = [end_page(pb, C, p, 0, 3, pdate)]
    pb = begin_page(C, p, 'Operative Report', ev, 1, 3)
    pb.para('Findings were consistent with the preoperative MRI dated %s. The pathology was addressed as planned and the '
            'repair was confirmed to be stable. The wounds were irrigated and closed in layers. Sterile dressing applied. The patient '
            'was awakened and taken to the recovery room in stable condition.' % bt(p, ev['mri_date']), None)
    pb.para('Discharge home same day when criteria are met. Follow up in clinic in 10 to 14 days.', 'DISPOSITION')
    pb.ln(sign_line(p, ev['clin'], ev['date'], rng))
    pages.append(end_page(pb, C, p, 1, 3, pdate))
    pb = begin_page(C, p, 'Anesthesia Record', ev, 2, 3)
    h, m = ev['time']
    pb.ln('ASA class %s    Weight %d lb    NPO since midnight' % (rng.choice(['I', 'II']), C['weight']))
    pb.ln('Anesthesiologist: %s' % rng.choice(p['clins']))
    for lab, add in [('Anesthesia start', 0), ('Induction', 6), ('Incision', 21), ('Closure', 98), ('Out of room', 112)]:
        mm = h * 60 + m + add
        pb.ln('  %-18s %02d:%02d' % (lab, (mm // 60) % 24, mm % 60))
    pb.para('Medications: propofol 180 mg, fentanyl 150 mcg, rocuronium 40 mg, cefazolin 2 g, ondansetron 4 mg, dexamethasone 8 mg.', 'MEDICATIONS')
    pb.para('Uneventful anesthetic. Extubated in the OR, to PACU with stable vital signs.', 'NOTES')
    pages.append(end_page(pb, C, p, 2, 3, pdate))
    return pages


# ---------------------------------------------------------------------------
# Non-clinical entities (law offices, insurer) and admin / billing documents
# ---------------------------------------------------------------------------
LETTER_STYLES = ['long', 'ord', 'wklong', 'LONG', 'longpad', 'abbrdot']


def make_entity(rng, name, kind):
    city, st, z = rng.choice(CITIES)
    area = rng.randint(201, 989)
    font = rng.choice(['Times-Roman', 'Helvetica', 'Times-Roman', 'Courier'])
    bold = {'Helvetica': 'Helvetica-Bold', 'Times-Roman': 'Times-Bold', 'Courier': 'Courier-Bold'}[font]
    people = ['%s %s' % (rng.choice(CFIRST), rng.choice(CLAST)) for _ in range(3)]
    return dict(name=name, kind=kind, font=font, bold=bold, size=rng.choice([9.5, 10.0, 10.5]),
                addr='%d %s, %s, %s %s%03d' % (rng.randint(10, 9900), rng.choice(STREETS), city, st, z, rng.randint(0, 999)),
                phone='(%d) 555-%04d' % (area, rng.randint(100, 199)), fax='(%d) 555-%04d' % (area, rng.randint(100, 199)),
                people=people, letter_style=rng.choice(LETTER_STYLES), ref_style=rng.choice(['mdy4', 'abbr', 'iso', 'mdy2n']),
                fax_fmt=rng.randint(0, 6))


def letterhead(pb, e):
    pb.ln(e['name'], role='hdr', font=e['bold'], size=e['size'] + 3)
    pb.ln('%s  |  Tel %s  |  Fax %s' % (e['addr'], e['phone'], e['fax']), role='hdr', size=e['size'] - 1.5)
    pb.ln('_' * 80, role='hdr', size=e['size'] - 2)
    pb.ln('', role='hdr')


def adm_request_letter(C, firm, prov, d, ref):
    pb = PB(firm)
    letterhead(pb, firm)
    pb.ln(fd(d, firm['letter_style']))
    pb.ln('')
    pb.ln('VIA FACSIMILE %s AND FIRST-CLASS MAIL' % prov['fax'], font=firm['bold'])
    pb.ln('Custodian of Records')
    pb.ln(prov['name'])
    pb.ln(prov['addr'])
    pb.ln('')
    pb.ln('Re:   Request for Complete Medical and Billing Records', font=firm['bold'])
    pb.ln('      Patient: %s %s' % (C['patient']['first'], C['patient']['last']))
    pb.ln('      Date of Birth: %s' % fd(C['dob'], firm['ref_style']))
    pb.ln('      Date of Loss: %s' % fd(C['acc'], firm['ref_style']))
    pb.ln('      Our Ref: %s' % ref)
    pb.ln('')
    pb.para('Dear Custodian of Records:')
    pb.para('This office represents the above-named individual for injuries sustained on the date of loss shown above. Please '
            'provide complete and legible copies of all records in your possession for dates of service from two years before the '
            'date of loss through the present, including office and progress notes, intake forms, diagnostic imaging reports, test '
            'results, operative and procedure reports, therapy notes, correspondence, and an itemized billing statement showing all '
            'charges, payments and adjustments by CPT code.')
    pb.para('A HIPAA-compliant authorization signed by our client is enclosed. Please also complete and return the enclosed '
            'certification of records custodian. If there is a fee for copies exceeding the statutory maximum, contact our office '
            'before processing. Records may be sent by fax or secure email.')
    pb.ln('')
    pb.ln('Very truly yours,')
    pb.ln(firm['people'][0] + ', Esq.')
    pb.ln('Paralegal contact: ' + firm['people'][1])
    pb.ln('Enclosures: Authorization; Custodian Certification form', size=firm['size'] - 1)
    return [pb.page()]


def adm_hipaa(C, firm, d):
    pb = PB(firm)
    pb.ln('AUTHORIZATION FOR USE AND DISCLOSURE OF PROTECTED HEALTH INFORMATION', font=firm['bold'], size=firm['size'] + 1)
    pb.ln('(45 C.F.R. 164.508)', size=firm['size'] - 1)
    pb.ln('')
    pb.ln('Patient name: %s %s %s.        Date of birth: %s' % (C['patient']['first'], C['patient']['mi'], C['patient']['last'], fd(C['dob'], 'mdy4')))
    pb.ln('Last four of SSN: %04d' % C['ssn4'])
    pb.para('I authorize any physician, hospital, clinic, therapist, pharmacy, imaging center, ambulance service or other health care '
            'provider to release to %s, %s, my complete medical, billing and radiology records for the purpose of evaluating and '
            'pursuing a claim for personal injury.' % (firm['name'], firm['addr']))
    pb.para('Information to be released includes records relating to mental health, alcohol or drug treatment and HIV/AIDS testing only '
            'if initialed here: ____. This authorization expires one year from the date signed. I understand I may revoke it in writing '
            'at any time except to the extent action has already been taken. A photocopy or fax of this form is as valid as the original.')
    pb.ln('')
    pb.ln('Signature of patient: ______________________________      Date signed: %s' % fd(d, 'mdy2n'))
    pb.ln('Witness: %s' % firm['people'][1])
    return [pb.page()]


def adm_provider_cover(C, prov, d, req_date, ref, n_pages, roi, fee, first_dos, last_dos):
    pb = PB(prov)
    pb.ln(prov['name'].upper(), role='hdr', font=prov['bold'], size=prov['size'] + 2)
    pb.ln('Health Information Management / Release of Information', role='hdr')
    pb.ln('%s   Ph %s   Fax %s' % (prov['addr'], prov['phone'], prov['fax']), role='hdr', size=prov['size'] - 1)
    pb.ln('')
    pb.ln('Date: %s' % fd(d, prov['print_style'], (11, 20)))
    pb.ln('Request ID: %s' % roi)
    pb.ln('Requester reference: %s     Request received: %s' % (ref, fd(req_date, prov['run_style'])))
    pb.ln('Patient: %s     DOB %s' % (fmt_name(C['patient'], prov['name_fmt']), fd(C['dob'], prov['dob_style'])))
    pb.ln('')
    pb.para('In response to the above request, enclosed please find %d pages of records for dates of service %s through %s. '
            'Records were reproduced from the legal medical record. Billing records are produced by the business office and are '
            'included where requested.' % (n_pages, fd(first_dos, prov['run_style']), fd(last_dos, prov['run_style'])))
    pb.ln('')
    pb.ln('Invoice %s-INV     Copy fee $%.2f     Payment due within 30 days.' % (roi, fee))
    pb.ln('Processed by: %s, ROI Specialist' % prov['clins'][-1].split(',')[0])
    return [pb.page()]


def adm_cert(C, prov, custodian, d, n_pages, county, notary):
    pb = PB(prov)
    pb.ln('CERTIFICATION OF CUSTODIAN OF RECORDS', font=prov['bold'], size=prov['size'] + 2)
    pb.ln('State of %s, County of %s' % (prov['addr'].split(',')[-1].split()[0], county))
    pb.ln('')
    pb.para('I, %s, being of lawful age and duly sworn, state that I am a duly authorized custodian of the records of %s and have '
            'authority to certify those records. The attached %d pages are true and correct copies of the records of the patient '
            '%s %s (date of birth %s). The records were made at or near the time of the acts and events recorded, by or from '
            'information transmitted by persons with knowledge, and were kept in the course of regularly conducted business activity.' % (
                custodian, prov['name'], n_pages, C['patient']['first'], C['patient']['last'], fd(C['dob'], prov['dob_style'])))
    pb.ln('')
    pb.ln('______________________________')
    pb.ln('%s, Custodian of Records' % custodian)
    pb.ln('')
    pb.ln('Sworn to and subscribed before me this %s.' % fd(d, 'legal'))
    pb.ln('______________________________')
    pb.ln('Notary Public: %s     My commission expires %s' % (notary, fd(add_days(d, 900 + hash_str(notary) % 400), 'mdy4')))
    return [pb.page()]


def adm_billing(C, prov, events, stmt_date, acct, rng, title='ITEMIZED STATEMENT'):
    rows = []
    for ev in events:
        for k, cpt in enumerate(ev['procedures']):
            amt = CHARGES.get(cpt, 150 + (hash_str(cpt) % 300))
            rows.append([fd(ev['date'], prov['bill_style']), cpt, DESC.get(cpt, 'Professional service')[:30], amt])
    per = 26
    n = max(1, (len(rows) + per - 1) // per)
    pages = []
    total = sum(r[3] for r in rows)
    paid = round(total * rng.uniform(0.0, 0.35), 2)
    for i in range(n):
        pb = PB(prov)
        pb.ln(prov['name'], role='hdr', font=prov['bold'], size=prov['size'] + 1)
        pb.ln('Patient Financial Services   %s   %s' % (prov['phone'], prov['addr']), role='hdr', size=prov['size'] - 1.5)
        pb.ln('%s    Statement date: %s    Page %d of %d' % (title, fd(stmt_date, prov['print_style'], (6, 0)), i + 1, n), font=prov['bold'], gap=4)
        pb.ln('Guarantor/Patient: %s    Account: %s' % (fmt_name(C['patient'], prov['name_fmt']), acct))
        pb.ln('')
        pb.row(['DOS', 'CODE', 'DESCRIPTION', 'CHARGE'], [14, 9, 34, 12], font='Courier-Bold')
        for r in rows[i * per:(i + 1) * per]:
            pb.row([r[0], r[1], r[2], '%.2f' % r[3]], [14, 9, 34, 12])
        if i == n - 1:
            pb.ln('')
            pb.row(['TOTAL CHARGES', '%.2f' % total], [57, 12], font='Courier-Bold')
            pb.row(['PAYMENTS/ADJUSTMENTS', '-%.2f' % paid], [57, 12])
            pb.row(['BALANCE DUE', '%.2f' % (total - paid)], [57, 12], font='Courier-Bold')
            pb.ln('')
            pb.ln('Balance held pending resolution of third-party liability claim.', size=prov['size'] - 1)
        pages.append(pb.page())
    return pages


CHARGES = {'99284': 1180.00, '99285': 1765.00, '99203': 245.00, '99204': 365.00, '99212': 110.00, '99213': 165.00, '99214': 240.00,
           '99215': 320.00, '99396': 290.00, '99024': 0.00, 'A0427': 1425.00, 'A0425': 18.50, '72040': 210.00, '72100': 225.00,
           '72070': 195.00, '73030': 180.00, '73562': 205.00, '73110': 175.00, '70450': 1340.00, '73502': 190.00, '73610': 170.00,
           '72141': 2250.00, '72148': 2250.00, '72146': 2190.00, '73221': 2100.00, '73721': 2100.00, '70551': 2480.00,
           '85025': 48.00, '80048': 62.00, '97162': 285.00, '97164': 190.00, '97110': 72.00, '97112': 78.00, '97140': 68.00,
           '97530': 80.00, '97014': 35.00, '97010': 22.00, '97035': 40.00, '98941': 95.00, '98940': 70.00, '97012': 45.00,
           '64483': 2150.00, '62321': 1980.00, '20610': 310.00, '29827': 14200.00, '29881': 7800.00, '63030': 18900.00,
           '22551': 31500.00, '25607': 9600.00, '99202': 140.00}
DESC = {'99284': 'ED visit, moderate MDM', '99285': 'ED visit, high MDM', '99203': 'New pt office visit, low', '99204': 'New pt office visit, mod',
        '99212': 'Est pt office visit, straightfwd', '99213': 'Est pt office visit, low', '99214': 'Est pt office visit, mod',
        '99215': 'Est pt office visit, high', '99396': 'Preventive visit 40-64', '99024': 'Postop visit, global',
        'A0427': 'ALS1 emergency transport', 'A0425': 'Ground mileage', '72040': 'X-ray cervical spine', '72100': 'X-ray lumbar spine',
        '72070': 'X-ray thoracic spine', '73030': 'X-ray shoulder', '73562': 'X-ray knee 3 views', '73110': 'X-ray wrist',
        '70450': 'CT head w/o contrast', '73502': 'X-ray hip', '73610': 'X-ray ankle', '72141': 'MRI cervical w/o',
        '72148': 'MRI lumbar w/o', '72146': 'MRI thoracic w/o', '73221': 'MRI upper ext joint w/o', '73721': 'MRI lower ext joint w/o',
        '70551': 'MRI brain w/o', '85025': 'CBC w/ differential', '80048': 'Basic metabolic panel', '97162': 'PT eval moderate',
        '97164': 'PT re-evaluation', '97110': 'Therapeutic exercise 15m', '97112': 'Neuromuscular reeduc 15m', '97140': 'Manual therapy 15m',
        '97530': 'Therapeutic activities 15m', '97014': 'E-stim unattended', '97010': 'Hot/cold packs', '97035': 'Ultrasound 15m',
        '98941': 'CMT spinal 3-4 regions', '98940': 'CMT spinal 1-2 regions', '97012': 'Mechanical traction', '64483': 'TF ESI lumbar',
        '62321': 'IL ESI cervical w/ imaging', '20610': 'Arthrocentesis/inj major jt', '29827': 'Arthroscopic RC repair',
        '29881': 'Knee scope meniscectomy', '63030': 'Laminotomy/discectomy lumbar', '22551': 'ACDF single level',
        '25607': 'ORIF distal radius', '99202': 'New pt office visit, straightfwd'}


def adm_insurer_ack(C, ins, d, firm, rep_date):
    pb = PB(ins)
    letterhead(pb, ins)
    pb.ln(fd(d, ins['letter_style']))
    pb.ln('')
    pb.ln(firm['name'])
    pb.ln(firm['addr'])
    pb.ln('')
    pb.ln('RE:  Claim number %s' % C['claim'], font=ins['bold'])
    pb.ln('     Our insured: %s' % C['insured'])
    pb.ln('     Your client: %s %s' % (C['patient']['first'], C['patient']['last']))
    pb.ln('     Date of loss: %s' % fd(C['acc'], ins['ref_style']))
    pb.ln('')
    pb.para('We acknowledge receipt of your letter of representation dated %s. Please direct all further correspondence regarding this '
            'claim to the undersigned and reference the claim number above. To evaluate the bodily injury claim we will need complete '
            'medical records and itemized bills for all treatment related to this loss, together with records of any treatment to the '
            'same body parts during the five years before the loss.' % fd(rep_date, ins['ref_style']))
    pb.para('This letter is not an admission of liability or coverage. %s reserves all rights under the policy.' % ins['name'])
    pb.ln('')
    pb.ln('Sincerely,')
    pb.ln('%s, Senior Bodily Injury Adjuster' % ins['people'][0])
    pb.ln('Direct %s   Claims fax %s' % (ins['phone'], ins['fax']))
    return [pb.page()]


def adm_bill_review(C, ins, d, rows):
    pb = PB(ins)
    pb.ln('%s  -  MEDICAL BILL REVIEW SUMMARY' % ins['name'].upper(), font=ins['bold'])
    pb.ln('Claim %s    Claimant %s %s    Review completed %s' % (C['claim'], C['patient']['first'], C['patient']['last'], fd(d, 'mdy4')))
    pb.ln('Reviewer: %s' % ins['people'][2])
    pb.ln('')
    pb.row(['PROVIDER', 'BILLED', 'ALLOWED', 'REDUCTION'], [42, 13, 13, 13], font='Courier-Bold')
    tb = ta = 0
    for name, billed, allowed in rows:
        tb += billed
        ta += allowed
        pb.row([name[:40], '%.2f' % billed, '%.2f' % allowed, '%.2f' % (billed - allowed)], [42, 13, 13, 13])
    pb.row(['TOTAL', '%.2f' % tb, '%.2f' % ta, '%.2f' % (tb - ta)], [42, 13, 13, 13], font='Courier-Bold')
    pb.ln('')
    pb.para('Allowed amounts reflect usual and customary fee schedule comparison for the provider zip code. Reductions are not a '
            'determination of reasonableness of treatment. Gap in treatment and causation questions referred to the adjuster.')
    return [pb.page()]


def adm_defense_cover(C, de, d, firm, prefix, start, end, case_no_court):
    pb = PB(de)
    letterhead(pb, de)
    pb.ln(fd(d, de['letter_style']))
    pb.ln('')
    pb.ln('%s, Esq.' % firm['people'][0])
    pb.ln(firm['name'])
    pb.ln('')
    pb.ln('Re:  %s v. %s' % (C['patient']['last'], C['insured']), font=de['bold'])
    pb.ln('     Case No. %s' % case_no_court)
    pb.ln('')
    pb.para('Enclosed please find Defendant\'s Supplemental Production of Documents, consisting of medical records obtained by '
            'subpoena and records produced to the carrier during the claim, Bates numbered %s %06d through %s %06d. These documents '
            'are produced subject to and without waiving the objections previously served.' % (prefix, start, prefix, end))
    pb.ln('')
    pb.ln('Sincerely,')
    pb.ln('%s' % de['people'][0])
    pb.ln('cc: %s (via email)' % de['people'][1])
    return [pb.page()]


def adm_defense_index(C, de, prefix, rows):
    pb = PB(de)
    pb.ln('INDEX OF RECORDS PRODUCED', font=de['bold'], size=de['size'] + 1)
    pb.ln('%s v. %s' % (C['patient']['last'], C['insured']))
    pb.ln('')
    pb.row(['SOURCE', 'BATES RANGE'], [62, 30], font='Courier-Bold')
    for name, a, b in rows:
        pb.row([name[:60], '%s %06d - %06d' % (prefix, a, b)], [62, 30])
    return [pb.page()]


def adm_portal_cover(C, prov, portal, d, first, last):
    pb = PB(prov)
    pb.ln('%s  |  %s' % (portal, prov['name']), font='Helvetica-Bold', size=11)
    pb.ln('Health Record Export', font='Helvetica', size=10)
    pb.ln('')
    pb.ln('Requested by: %s %s (patient account holder)' % (C['patient']['first'], C['patient']['last']), font='Helvetica', size=9)
    pb.ln('Export generated: %s' % fd(d, 'tsabbr12', (20, 14)), font='Helvetica', size=9)
    pb.ln('Encounters included: %s to %s' % (fd(first, 'abbr'), fd(last, 'abbr')), font='Helvetica', size=9)
    pb.ln('')
    pb.para('This export contains notes and results released to your online account. Some documents may be formatted differently '
            'from the official medical record. For a certified copy contact Health Information Management.')
    return [pb.page()]


def adm_exhibit_slip(firm, n, desc):
    pb = PB(firm)
    for _ in range(14):
        pb.ln('')
    pb.ln('EXHIBIT %d' % n, font=firm['bold'], size=28, x=150)
    pb.ln('')
    pb.ln(desc, size=12, x=110)
    return [pb.page()]


# ---------------------------------------------------------------------------
# Case construction: patient, providers, timeline of events, original documents
# ---------------------------------------------------------------------------
JOBS = [('warehouse lead', 'Corvane Logistics'), ('dental hygienist', 'Brightline Dental Group'), ('electrician', 'Halvard Electric Co.'),
        ('middle-school teacher', 'Easton Unified School District'), ('line cook', 'Saltgrass Kitchen'), ('bank teller', 'First Prairie Savings'),
        ('HVAC technician', 'Coldfront Mechanical'), ('retail store manager', 'Penny Lane Outfitters'), ('home health aide', 'Comfort Keepers of the Valley'),
        ('delivery driver', 'Swiftroute Parcel'), ('paralegal', 'Ostrom & Kidd'), ('auto mechanic', 'Gearhead Garage')]
LOCATIONS = ['intersection of Maple Ave and 3rd St', 'northbound I-71 near mile marker 118', 'parking lot of 2201 Commerce Way',
             'aisle 7 of 640 Laurel Rd', 'sidewalk in front of 15 Market St', 'apartment complex at 908 Briar Ln',
             'County Road 12 at Tremont Pl', 'loading dock behind 77 Pioneer Dr']
PT_INTS = [('97110', 'Therapeutic exercise'), ('97112', 'Neuromuscular re-education'), ('97140', 'Manual therapy'),
           ('97530', 'Therapeutic activities'), ('97035', 'Ultrasound'), ('97014', 'Electrical stimulation, unattended'),
           ('97010', 'Hot/cold pack')]
PT_SUBJ = ['sore after yesterday\'s work shift', 'slept better this week', 'pain worse in the morning', 'able to drive 30 minutes',
           'flare-up after carrying groceries', 'less stiffness overall', 'headache this morning resolved', 'tingling decreased',
           'still guarding with overhead reach', 'reports fatigue after exercises']
PT_OBJ = ['Improved scapular control with cueing.', 'ROM gains noted end of session.', 'Decreased muscle guarding after manual work.',
          'Required rest breaks during closed-chain activity.', 'Gait symmetric without device.', 'Progressed resistance band to green.',
          'Pain peripheralized briefly with extension, resolved.', 'Good tolerance to progression of load.']
_pool = {}


def shuffled_pool(name, items):
    if name not in _pool:
        lst = list(items)
        random.Random('alt5-pool-' + name).shuffle(lst)
        _pool[name] = lst
    return _pool[name]


def R(case_no, tag):
    return random.Random('alt5-%d-%d-%s' % (MASTER_SEED, case_no, tag))


def build_world(case_no):
    rw = R(case_no, 'world')
    idx = case_no - 1
    sex = 'F' if idx % 2 == 0 else 'M'
    first = shuffled_pool('ff', PFIRST_F)[idx] if sex == 'F' else shuffled_pool('fm', PFIRST_M)[idx]
    last = shuffled_pool('last', PLAST)[idx]
    acc = dt.date(2022, 5, 1) + dt.timedelta(days=rw.randint(0, 1050))
    age = rw.randint(23, 63)
    dob = dt.date(acc.year - age, rw.randint(1, 12), rw.randint(1, 28))
    incident = shuffled_pool('inc', INCIDENTS)[idx]
    job, employer = rw.choice(JOBS)
    C = dict(case_no=case_no, case_id='alt5-%d' % case_no,
             patient=dict(first=first, last=last, mi=rw.choice('ABCDEGHJKLMRST')), dob=dob, acc=acc, incident=incident,
             sex_word='woman' if sex == 'F' else 'man', job=job, employer=employer, weight=rw.randint(128, 236),
             location=rw.choice(LOCATIONS), city=rw.choice(CITIES)[0], ssn4=rw.randint(1000, 9999))
    C['age_at'] = lambda d, dob=dob: d.year - dob.year - ((d.month, d.day) < (dob.month, dob.day))
    k = rw.choice([2, 2, 3, 3])
    keys = [incident['regions'][0]] + rw.sample(incident['regions'][1:], k - 1)
    C['regions'] = keys
    C['reg'] = {}
    for key in keys:
        side = rw.choice(['right', 'left']) if key in ('shoulder', 'knee', 'wrist', 'hip', 'ankle') else None
        C['reg'][key] = region_info(key, side)
    # providers
    has_ems = incident['ems'] and rw.random() < 0.85
    types = (['ems'] if has_ems else []) + (['er'] if (has_ems or rw.random() < 0.55) else ['urgent']) + ['pcp', 'ortho']
    surg_cands = [r for r in keys if C['reg'][r]['surg']]
    C['surg_region'] = surg_cands[0] if surg_cands and rw.random() < 0.6 else None
    inj_cands = [r for r in keys if C['reg'][r]['inj'] and r in ('neck', 'lumbar')]
    if 'head' in keys:
        types.append('neuro')
    if rw.random() < 0.7:
        types.append('imaging')
    types.append('pt')
    if rw.random() < 0.45:
        types.append('chiro')
    if inj_cands and rw.random() < 0.7:
        types.append('pain')
    C['inj_region'] = inj_cands[0] if 'pain' in types else None
    if C['surg_region'] and ('er' not in types or rw.random() < 0.65):
        types.append('asc')
    while len(types) > 9:
        types.remove('chiro' if 'chiro' in types else 'imaging')
    C['has_ems'] = has_ems
    used = []
    stem_pool = shuffled_pool('stems', STEMS)
    window = [stem_pool[(idx * 7 + j) % len(stem_pool)] for j in range(14)]
    used.extend(s for s in stem_pool if s not in window)
    C['P'] = {}
    for t in types:
        C['P'][t] = make_provider(rw, t, used)
    C['firm'] = make_entity(rw, shuffled_pool('lp', LAW_PLAINTIFF)[idx], 'plaintiff')
    C['defense'] = make_entity(rw, shuffled_pool('ld', LAW_DEFENSE)[idx], 'defense')
    C['ins'] = make_entity(rw, shuffled_pool('ins', INSURERS)[idx], 'insurer')
    C['claim'] = '%s-%d-%05d-%s' % (''.join(w[0] for w in C['ins']['name'].split()[:2]).upper(), rw.randint(10, 99), rw.randint(10000, 99999), rw.choice(['AU', 'BI', 'GL', 'PL']))
    C['insured'] = '%s %s' % (rw.choice(CFIRST), rw.choice(CLAST)) if 'collision' in incident['kind'] or 'struck' in incident['kind'] or 'sideswipe' in incident['kind'] \
        else rw.choice(['Fresh Basket Markets, Inc.', 'Harbor Point Apartments LLC', 'City of %s' % C['city'], 'Greenway Retail Holdings'])
    C['firm_ref'] = '%s-%d-%04d' % (''.join(w[0] for w in C['firm']['name'].replace('&', '').split()[:3]).upper(), acc.year % 100, rw.randint(100, 9999))
    C['court_no'] = '%d-CV-%05d' % (acc.year + 1, rw.randint(100, 99999))
    C['portal'] = rw.choice(PORTALS)
    return C


def mk_ev(kind, ptype, date, regions, codes, procs, summary, builder, clin, **kw):
    e = dict(kind=kind, ptype=ptype, date=date, regions=regions, codes=codes, procedures=procs, summary=summary,
             builder=builder, clin=clin, time=kw.pop('time', (9, 0)))
    e.update(kw)
    return e


def codes_for(C, regs, phase):
    out = []
    for r in regs:
        for c in C['reg'][r][phase]:
            if c not in out:
                out.append(c)
    return out


def build_events(C, n_fill):
    re_ = R(C['case_no'], 'events')
    P = C['P']
    acc = C['acc']
    regs = C['regions']
    nonhead = [r for r in regs if r != 'head'] or regs
    evs = []
    # prior visits
    n_prior = re_.randint(1, 3)
    offs = sorted(re_.sample(range(35, 720), n_prior), reverse=True)
    for o, reason in zip(offs, re_.sample(PRIOR_REASONS, n_prior)):
        d = weekday_on_or_after(add_days(acc, -o))
        evs.append(mk_ev('prior_visit', 'pcp', d, [], reason[1], reason[2], '%s; no complaints involving the later-injured body regions.' % reason[3],
                         doc_prior, P['pcp']['clins'][0], extra=reason, time=(re_.randint(8, 16), re_.choice([0, 15, 30, 45]))))
    ext = C['incident']['ext']
    t_acc = (re_.randint(6, 20), re_.randint(0, 59))
    if 'ems' in P:
        evs.append(mk_ev('ems', 'ems', acc, regs, codes_for(C, regs, 'A') + [ext], ['A0427', 'A0425'],
                         'Ambulance response to the %s and transport to the emergency department.' % C['incident']['kind'],
                         doc_ems, P['ems']['clins'][0], time=t_acc, inc_no='%d-%06d' % (acc.year % 100, re_.randint(1000, 999999))))
    if 'er' in P:
        fc = P['er']
        d = acc if (C['has_ems'] or re_.random() < 0.7) else add_days(acc, 1)
        t = ((t_acc[0] + 1) % 24, (t_acc[1] + 7) % 60)
        lab = re_.random() < 0.5
        evs.append(mk_ev('er_visit', 'er', d, regs, codes_for(C, regs, 'A') + [ext], [re_.choice(['99284', '99285'])],
                         'Emergency department evaluation of %s after the %s; discharged home.' % (', '.join(C['reg'][r]['plain'] for r in regs), C['incident']['kind']),
                         doc_er, fc['clins'][0], time=t, has_lab=lab))
        for k, r in enumerate(regs):
            evs.append(mk_ev('imaging', 'er', d, [r], C['reg'][r]['A'][:1], [C['reg'][r]['xr'][0]],
                             '%s obtained in the emergency department.' % C['reg'][r]['xr'][1].capitalize(),
                             doc_imaging, fc['clins'][1], time=((t[0] + 1) % 24, (t[1] + 11 * k) % 60), extra='xr',
                             acc_no='RA%08d' % re_.randint(10 ** 7, 10 ** 8 - 1), ordering=fc['clins'][0]))
        if lab:
            evs.append(mk_ev('lab', 'er', d, [], codes_for(C, regs, 'A')[:1], ['85025', '80048'],
                             'CBC and basic metabolic panel drawn in the emergency department.', doc_lab, fc['clins'][-1],
                             time=((t[0] + 1) % 24, (t[1] + 30) % 60), ordering=fc['clins'][0]))
        C['first_care'] = fc['name']
    else:
        fc = P['urgent']
        d = add_days(acc, re_.choice([0, 1, 2]))
        evs.append(mk_ev('office_visit', 'urgent', d, regs, codes_for(C, regs, 'A') + [ext], ['99204'],
                         'Urgent care evaluation of %s after the %s.' % (', '.join(C['reg'][r]['plain'] for r in regs), C['incident']['kind']),
                         doc_urgent, fc['clins'][0], time=(re_.randint(9, 19), re_.randint(0, 59))))
        for k, r in enumerate(nonhead):
            evs.append(mk_ev('imaging', 'urgent', d, [r], C['reg'][r]['A'][:1], [C['reg'][r]['xr'][0]],
                             '%s obtained at urgent care.' % C['reg'][r]['xr'][1].capitalize(), doc_imaging, fc['clins'][1],
                             extra='xr', acc_no='UC%06d' % re_.randint(10 ** 5, 10 ** 6 - 1), ordering=fc['clins'][0]))
        C['first_care'] = fc['name']
    C['er_name'] = fc['name']
    er_d = d
    # PCP follow-up
    pcp_d = weekday_on_or_after(add_days(er_d, re_.randint(3, 9)))
    evs.append(mk_ev('office_visit', 'pcp', pcp_d, regs, codes_for(C, regs, 'D'), ['99214'],
                     'Primary care follow-up after the injury; referred to orthopedics and physical therapy.', doc_office,
                     P['pcp']['clins'][0], role='pcp', prev=er_d, pain=re_.randint(6, 8), rtc_w=4,
                     plan='Referral placed to orthopedics and to physical therapy. Continue NSAID; muscle relaxant at night.'))
    # Neurology
    if 'neuro' in P:
        n1 = weekday_on_or_after(add_days(acc, re_.randint(14, 30)))
        n2 = weekday_on_or_after(add_days(n1, re_.randint(35, 60)))
        evs.append(mk_ev('office_visit', 'neuro', n1, ['head'], C['reg']['head']['L'], ['99204'],
                         'Neurology consultation for post-concussive headaches and cognitive complaints.', doc_office, P['neuro']['clins'][0],
                         role='neuro', first=True, pain=re_.randint(5, 7), rtc_w=6, ref_by=P['pcp']['clins'][0], two_page=True,
                         plan='Start amitriptyline 10 mg at bedtime. Vestibular therapy referral. MRI brain if not improving.'))
        evs.append(mk_ev('office_visit', 'neuro', n2, ['head'], C['reg']['head']['L'], ['99214'],
                         'Neurology follow-up; headaches improving on preventive medication.', doc_office, P['neuro']['clins'][0],
                         role='neuro', prev=n1, pain=re_.randint(3, 5), rtc_w=8))
    # Ortho + MRI
    O = P['ortho']
    o1 = weekday_on_or_after(add_days(acc, re_.randint(9, 24)))
    mri_regs = [C['surg_region']] if C['surg_region'] else []
    for r in ([C['inj_region']] if C['inj_region'] else []) + nonhead:
        if r and r not in mri_regs and len(mri_regs) < 2:
            mri_regs.append(r)
    mri_prov = 'imaging' if 'imaging' in P else ('er' if 'er' in P else 'ortho')
    mri_dates = {}
    amended_idx = re_.randrange(len(mri_regs)) if re_.random() < 0.7 else -1
    xr_dates = {e['regions'][0]: e['date'] for e in evs if e['kind'] == 'imaging'}
    for k, r in enumerate(mri_regs):
        md = weekday_on_or_after(add_days(o1, re_.randint(4, 15)))
        mri_dates[r] = md
        comp = (xr_dates[r], C['reg'][r]['xr'][1].title()) if r in xr_dates and re_.random() < 0.75 else None
        evs.append(mk_ev('imaging', mri_prov, md, [r], C['reg'][r]['L'], [C['reg'][r]['mri'][0]],
                         'MRI of the %s showing %s' % (C['reg'][r]['name'], C['reg'][r]['mri_imp'][0].lower() + C['reg'][r]['mri_imp'][1:]),
                         doc_imaging, P[mri_prov]['clins'][-1 if mri_prov != 'imaging' else 0], extra='mri',
                         acc_no='MR%07d' % re_.randint(10 ** 6, 10 ** 7 - 1), ordering=O['clins'][0], comparison=comp,
                         amended=(k == amended_idx), time=(re_.randint(7, 18), re_.choice([0, 20, 40]))))
    last_mri = max(mri_dates.values()) if mri_dates else add_days(o1, 10)
    ortho = []
    ortho.append(dict(d=o1, first=True, codes=codes_for(C, nonhead, 'D'), procs=['99204'], work='off', two=True,
                      s='Orthopedic consultation for %s pain; MRI ordered and physical therapy started.' % ', '.join(C['reg'][r]['plain'] for r in nonhead)))
    o2 = weekday_on_or_after(add_days(last_mri, re_.randint(3, 12)))
    ortho.append(dict(d=o2, codes=codes_for(C, mri_regs or nonhead, 'L'), procs=['99214'], mri=True,
                      s='Orthopedic follow-up reviewing MRI results with the patient.'))
    o3 = weekday_on_or_after(add_days(o2, re_.randint(21, 42)))
    ortho.append(dict(d=o3, codes=codes_for(C, mri_regs or nonhead, 'L'), procs=['99214'], work='mod',
                      s='Orthopedic follow-up with persistent symptoms despite therapy; modified duty.'))
    last_o = o3
    if C['surg_region']:
        sr = C['surg_region']
        pre = weekday_on_or_after(add_days(o3, re_.randint(7, 21)))
        S = weekday_on_or_after(add_days(pre, re_.randint(7, 20)))
        C['surgery_date'] = S
        C['surgery_desc'] = C['reg'][sr]['surg'][1]
        ortho.append(dict(d=pre, codes=C['reg'][sr]['L'], procs=['99215'], preop=True,
                          s='Preoperative consultation; surgery planned for %s.' % C['reg'][sr]['name'],
                          plan='Discussed risks, benefits and alternatives of %s; patient elects to proceed.' % C['reg'][sr]['surg'][1]))
        sprov = 'asc' if 'asc' in P else 'er'
        evs.append(mk_ev('surgery', sprov, S, [sr], C['reg'][sr]['L'], [C['reg'][sr]['surg'][0]],
                         '%s.' % C['reg'][sr]['surg'][1].capitalize(), doc_surgery, O['clins'][0],
                         proc=C['reg'][sr]['surg'], mri_date=mri_dates.get(sr, last_mri), time=(re_.randint(7, 12), re_.choice([0, 15, 30]))))
        po1 = weekday_on_or_after(add_days(S, re_.randint(10, 14)))
        po2 = weekday_on_or_after(add_days(S, re_.randint(38, 50)))
        ortho.append(dict(d=po1, codes=['Z47.89'] + C['reg'][sr]['L'], procs=['99024'], postop=True, s='First postoperative visit; wound check.'))
        ortho.append(dict(d=po2, codes=['Z47.89'] + C['reg'][sr]['L'], procs=['99024'], postop=True, s='Postoperative follow-up; progressing with therapy.'))
        last_o = po2
    else:
        C['surgery_date'] = None
        C['surgery_desc'] = ''
        o4 = weekday_on_or_after(add_days(o3, re_.randint(30, 55)))
        ortho.append(dict(d=o4, codes=codes_for(C, mri_regs or nonhead, 'L'), procs=['99214'],
                          s='Orthopedic follow-up; near maximal medical improvement with residual symptoms.'))
        last_o = o4
    prev = None
    for k, o in enumerate(ortho):
        mref = None
        if o.get('mri') and mri_regs:
            mref = (mri_dates[mri_regs[0]], mri_regs[0])
        evs.append(mk_ev('office_visit', 'ortho', o['d'], nonhead, o['codes'], o['procs'], o['s'], doc_office,
                         O['clins'][0] if k != 2 else O['clins'][-1], role='ortho', first=o.get('first', False), prev=prev,
                         pain=max(2, 8 - k), rtc_w=re_.choice([3, 4, 6]), two_page=o.get('two', False), work_form=o.get('work'),
                         lift=re_.choice([10, 15, 20, 25]), mri_ref=mref, postop=o.get('postop'), preop=o.get('preop'),
                         plan=o.get('plan'), ref_by=P['pcp']['clins'][0]))
        prev = o['d']
    # Pain management
    if 'pain' in P:
        ir = C['inj_region']
        p1 = weekday_on_or_after(add_days(mri_dates.get(ir, last_mri), re_.randint(10, 25)))
        pp = P['pain']
        evs.append(mk_ev('office_visit', 'pain', p1, [ir], C['reg'][ir]['L'], ['99204'],
                         'Pain management evaluation; epidural steroid injection recommended.', doc_office, pp['clins'][0],
                         role='pain', first=True, pain=7, rtc_w=2, two_page=True, ref_by=O['clins'][0],
                         plan='Schedule %s.' % C['reg'][ir]['inj'][1]))
        injd = [weekday_on_or_after(add_days(p1, re_.randint(10, 20)))]
        if re_.random() < 0.55:
            injd.append(weekday_on_or_after(add_days(injd[0], re_.randint(21, 35))))
        for k, d in enumerate(injd):
            evs.append(mk_ev('procedure', 'pain', d, [ir], C['reg'][ir]['L'], [C['reg'][ir]['inj'][0]],
                             '%s %s.' % ('Repeat' if k else 'First', C['reg'][ir]['inj'][1]), doc_procedure, pp['clins'][0],
                             proc=C['reg'][ir]['inj'], pain=re_.randint(6, 8), time=(re_.randint(7, 13), re_.choice([0, 30]))))
        pf = weekday_on_or_after(add_days(injd[-1], re_.randint(14, 21)))
        evs.append(mk_ev('office_visit', 'pain', pf, [ir], C['reg'][ir]['L'], ['99214'],
                         'Pain management follow-up after injection with partial relief.', doc_office, pp['clins'][0],
                         role='pain', prev=injd[-1], pain=re_.randint(3, 5), rtc_w=6))
    # PT course
    rp = R(C['case_no'], 'pt')
    PT = P['pt']
    n_ch = int(round(n_fill * 0.35)) if 'chiro' in P else 0
    n_pt = max(4, n_fill - n_ch)
    E = weekday_on_or_after(add_days(o1, rp.randint(3, 10)))
    evals = [E]
    auth = min(a for a in (18, 24, 30, 36, 48, 60, 72, 96, 120) if a >= n_pt + rp.choice([0, 2, 5]))
    evs.append(mk_ev('pt_eval', 'pt', E, nonhead, codes_for(C, nonhead, 'D') + ['M62.81'], ['97162'],
                     'Physical therapy initial evaluation; plan of care 2-3 times weekly.', doc_pt, PT['clins'][0],
                     ordering=O['clins'][0], rom=rp.randint(45, 65), mmt='3+', pain=rp.randint(6, 8),
                     scale=rp.choice(['Oswestry Disability Index', 'Neck Disability Index', 'QuickDASH', 'LEFS deficit']),
                     score=rp.randint(38, 62), time=(rp.randint(7, 17), rp.choice([0, 15, 30, 45]))))
    d = E
    visits = 0
    since = 0
    S = C['surgery_date']
    post_done = False
    while visits < n_pt:
        d = weekday_on_or_after(add_days(d, rp.choice([2, 2, 3, 3, 4])))
        if S and add_days(S, -3) <= d <= add_days(S, 9):
            continue
        if S and d > S and not post_done:
            post_done = True
            evs.append(mk_ev('pt_reeval', 'pt', d, nonhead, ['Z47.89'] + C['reg'][C['surg_region']]['L'], ['97164'],
                             'Postoperative physical therapy re-evaluation.', doc_pt, PT['clins'][0], ordering=O['clins'][0],
                             visits_so_far=visits, eval_date=E, improve=rp.randint(5, 25), postop=True, rom=rp.randint(35, 55), mmt='3',
                             pain=rp.randint(5, 7), scale='QuickDASH' if C['surg_region'] in ('shoulder', 'wrist') else 'LEFS deficit',
                             score=rp.randint(45, 70), time=(rp.randint(7, 17), rp.choice([0, 30]))))
            since = 0
            continue
        if since >= 12:
            evs.append(mk_ev('pt_reeval', 'pt', d, nonhead, codes_for(C, nonhead, 'D') + ['M62.81'], ['97164'],
                             'Physical therapy progress re-evaluation with recertification.', doc_pt, PT['clins'][0], ordering=O['clins'][0],
                             visits_so_far=visits, eval_date=E, improve=rp.randint(25, 60), rom=rp.randint(60, 85), mmt='4',
                             pain=rp.randint(3, 6), scale='Oswestry Disability Index' if 'lumbar' in nonhead else 'Neck Disability Index',
                             score=rp.randint(18, 40), time=(rp.randint(7, 17), rp.choice([0, 30]))))
            since = 0
            continue
        visits += 1
        since += 1
        ints = rp.sample(PT_INTS, rp.choice([2, 3, 3, 4]))
        ints = [(c, n_, rp.choice([8, 12, 15, 23, 25])) for c, n_ in ints]
        evs.append(mk_ev('pt_visit', 'pt', d, nonhead, codes_for(C, nonhead, 'D'), [c for c, _, _ in ints],
                         'Physical therapy treatment visit %d.' % visits, doc_pt, PT['clins'][rp.choice([0, 0, 1, 2]) % len(PT['clins'])],
                         visit_no=visits, auth=auth, pain=max(1, 7 - visits // 6 + rp.choice([-1, 0, 0, 1])), subj=rp.choice(PT_SUBJ),
                         hep=rp.choice(['good', 'fair', 'partial', 'good']), ints=ints, tol=rp.choice(['well', 'fairly well', 'with mild increase in pain']),
                         obj=rp.choice(PT_OBJ), ordering=O['clins'][0], time=(rp.randint(7, 18), rp.choice([0, 15, 30, 45]))))
    if 'chiro' in P:
        rc = R(C['case_no'], 'chiro')
        CH = P['chiro']
        spine = [r for r in regs if r in ('neck', 'lumbar', 'thoracic')] or nonhead
        c1 = weekday_on_or_after(add_days(acc, rc.randint(5, 16)))
        chcodes = codes_for(C, spine, 'D') + (['M99.01'] if 'neck' in spine else ['M99.03'])
        evs.append(mk_ev('office_visit', 'chiro', c1, spine, chcodes, ['99203', '98941'],
                         'Chiropractic initial examination and first spinal manipulation.', doc_office, CH['clins'][0],
                         role='chiro', first=True, pain=rc.randint(6, 8), rtc_w=1, two_page=True, ref_by='self'))
        d = c1
        for k in range(n_ch):
            d = weekday_on_or_after(add_days(d, rc.choice([2, 2, 3, 4, 5])))
            evs.append(mk_ev('office_visit', 'chiro', d, spine, chcodes, ['98941', '97140', '97012'],
                             'Chiropractic treatment visit %d.' % (k + 1), doc_office, CH['clins'][0], role='chiro', visit_no=k + 1,
                             pain=max(2, 7 - k // 5 + rc.choice([-1, 0, 1])), subj=rc.choice(['slightly better', 'unchanged', 'improved', 'worse after work shift']),
                             sleep=rc.choice(['fair', 'improving', 'interrupted by pain']), segs=rc.sample(['C2', 'C4', 'C5', 'C6', 'T3', 'T6', 'L3', 'L4', 'L5', 'SI-R', 'SI-L'], 3),
                             rom=rc.randint(55, 85), rtc_w=1))
    order = {'prior_visit': 0, 'ems': 1, 'er_visit': 2, 'office_visit': 3, 'lab': 4, 'imaging': 5, 'pt_eval': 6, 'pt_reeval': 7,
             'pt_visit': 8, 'procedure': 9, 'surgery': 10}
    evs.sort(key=lambda e: (e['date'], order[e['kind']], e['ptype'], e['summary']))
    # next appointment per provider
    byp = {}
    for e in evs:
        byp.setdefault(e['ptype'], []).append(e)
    for t, lst in byp.items():
        for i, e in enumerate(lst):
            e['next'] = lst[i + 1]['date'] if i + 1 < len(lst) else add_days(e['date'], 7 * e.get('rtc_w', 2))
    return evs


# ---------------------------------------------------------------------------
# Productions and copy mechanics
# ---------------------------------------------------------------------------
OCR_SUBS = [('rn', 'm'), ('m', 'rn'), ('cl', 'd'), ('l', '1'), ('1', 'l'), ('O', '0'), ('0', 'O'), ('e', 'c'), ('h', 'b'),
            ('S', '5'), ('5', 'S'), ('B', '8'), ('8', 'B'), ('u', 'v'), ('a', 'o'), ('g', 'q'), ('t', 'f'), ('i', 'l'),
            ('ri', 'n'), ('w', 'vv'), ('.', ','), (',', '.'), ('I', '|'), ('y', 'v'), ('n', 'ri'), ('d', 'cl'), ('E', 'F'),
            ('6', 'b'), ('fi', 'ti'), ('/', 'l')]


def ocr_text(s, rate, rng):
    out = []
    i = 0
    while i < len(s):
        if rng.random() < rate:
            opts = [(a, b) for a, b in OCR_SUBS if s.startswith(a, i)]
            if opts:
                a, b = rng.choice(opts)
                out.append(b)
                i += len(a)
                continue
            if s[i] == ' ' and rng.random() < 0.5:
                i += 1
                continue
        out.append(s[i])
        i += 1
    return ''.join(out)


def t_ocr(page, rng, rate):
    for l in page['lines']:
        if l['t'] and not l['prot']:
            l['t'] = '\t'.join(ocr_text(c, rate, rng) for c in l['t'].split('\t'))
    for a in page['abs']:
        a['t'] = ocr_text(a['t'], rate / 2, rng)


def t_crop(page, rng):
    how = rng.choice(['top', 'bottom', 'right', 'top', 'right'])
    L = page['lines']
    if how == 'top':
        k = rng.randint(1, 3)
        removed = 0
        while removed < k and L and not L[0]['prot']:
            L.pop(0)
            removed += 1
        page['abs'] = [a for a in page['abs'] if a['y'] < 740]
    elif how == 'bottom':
        k = rng.randint(1, 3)
        removed = 0
        while removed < k and L and not L[-1]['prot']:
            L.pop()
            removed += 1
        page['abs'] = [a for a in page['abs'] if a['y'] > 50]
    else:
        n = rng.randint(58, 80)
        for l in L:
            if not l['prot'] and len(l['t']) > n:
                l['t'] = l['t'][:n]
    return how


def t_reflow(page, font, size):
    out = []
    i = 0
    L = page['lines']
    while i < len(L):
        l = L[i]
        if l['para'] is None:
            nl = dict(l)
            nl['f'] = font if 'Bold' not in l['f'] else 'Helvetica-Bold'
            nl['s'] = size
            nl['x'] = 0
            out.append(nl)
            i += 1
            continue
        pid = l['para']
        words = []
        while i < len(L) and L[i]['para'] == pid:
            words.append(L[i]['t'])
            i += 1
        for w in wrap(' '.join(words), font, size):
            out.append(dict(t=w, role='body', f=font, s=size, x=0, prot=False, para=pid, gap=0))
    page['lines'] = out
    page['abs'] = []


def ovl_line(t, font='Courier', size=7.5, prot=False):
    return dict(t=t, role='ovl', f=font, s=size, x=0, prot=prot, para=None, gap=0)


def digits(s):
    return ''.join(ch for ch in s if ch.isdigit())


def fax_line(fmt, sender, sfax, to, tfax, d, hm, i, n, job):
    h, m = hm
    if fmt == 0:
        return '%s FAX %s    %s    P.%03d/%03d' % (fd(d, 'ts24', hm), sfax, sender.upper()[:30], i, n)
    if fmt == 1:
        return 'From: %s  Fax: %s  To: %s  Date: %s  Page %d of %d' % (sender[:22], sfax, to[:20], fd(d, 'tsabbr12', hm), i, n)
    if fmt == 2:
        return '%s ; -> %s ; Page %d' % (fd(d, 'tsdashn12', hm), to[:30], i)
    if fmt == 3:
        return 'RCVD %s FROM %s TO %s PG %d/%d *' % (fd(d, 'tscompact', hm), digits(sfax), digits(tfax), i, n)
    if fmt == 4:
        return '%s %02d:%02d   %s   #%04d P %02d' % (fd(d, 'ABBRPAD'), h, m, sfax, job, i)
    if fmt == 5:
        return 'Sent %s via eFax | %s | pg %d of %d' % (fd(d, 'tsiso', hm), sender[:34], i, n)
    return '%s %d:%02d%s  %s -> %s  [%d/%d]' % (fd(d, 'mdy2n'), h % 12 or 12, m, 'a' if h < 12 else 'p', sfax, tfax, i, n)


def stamp(page, text, place, rng, font='Helvetica-Bold', size=9):
    if place == 'line':
        k = min(len(page['lines']), rng.randint(0, 3))
        page['lines'].insert(k, ovl_line(text, font, size))
    elif place == 'margin':
        if rng.random() < 0.5:
            page['abs'].append(dict(x=30, y=rng.randint(220, 520), f=font, s=size, t=text, rot=1))
        else:
            page['abs'].append(dict(x=rng.randint(360, 420), y=rng.choice([776, 30]), f=font, s=size, t=text, rot=0))
    else:  # append to an existing line
        cands = [l for l in page['lines'][:10] if l['t'] and len(l['t']) + len(text) < 88]
        if not cands:
            return stamp(page, text, 'line', rng, font, size)
        l = rng.choice(cands)
        l['t'] = l['t'] + '     ' + text
    return place


HANDNOTES = ['-> gap in tx?', 'see MRI', 'pre-existing?? no', 'ck bill vs. note', 'ok - LR', 'compare ER', '!! surgery rec',
             'pt missed 2 wks', 'f/u w/ client', 'date?', 'causation - good', 'IME to address', 'missing pg 2?', 'nice', 'call adj.']


class Inst:
    __slots__ = ('doc', 'pages', 'prod', 'group', 'seq', 'mech', 'src', 'extra', 'models', 'first')

    def __init__(self, doc, pages, prod, group, mech, src=None, extra=None):
        self.doc = doc
        self.pages = pages
        self.prod = prod
        self.group = group
        self.seq = 0
        self.mech = mech
        self.src = src
        self.extra = extra or {}
        self.models = None
        self.first = None


def build_case(case_no, n_fill):
    PB._pid[0] = 0
    C = build_world(case_no)
    P = C['P']
    evs = build_events(C, n_fill)
    rt = R(case_no, 'text')
    rp = R(case_no, 'plan')
    last_by, first_by, count_by = {}, {}, {}
    for e in evs:
        t = e['ptype']
        last_by[t] = max(last_by.get(t, e['date']), e['date'])
        first_by[t] = min(first_by.get(t, e['date']), e['date'])
        count_by[t] = count_by.get(t, 0) + 1
    prov_order = sorted(P.keys(), key=lambda t: (first_by.get(t, C['acc']), t))
    # production kinds
    kinds = ['release', 'insurer']
    for k, pr in (('defense', 0.85), ('portal', 0.55), ('rerequest', 0.65), ('exhibit', 0.5)):
        if rp.random() < pr:
            kinds.append(k)
    for k in ('rerequest', 'defense', 'portal', 'exhibit'):
        if len(kinds) < 4 and k not in kinds:
            kinds.append(k)
    mid = [k for k in ('insurer', 'portal', 'rerequest') if k in kinds]
    rp.shuffle(mid)
    chrono = ['release'] + mid + [k for k in ('defense', 'exhibit') if k in kinds]
    prod_no = {k: i + 1 for i, k in enumerate(chrono)}
    cands = [t for t in ('pt', 'chiro', 'ortho') if t in P and count_by.get(t, 0) >= 5]
    rereq = []
    if 'rerequest' in kinds:
        rereq = cands[:1] if (len(cands) < 2 or rp.random() < 0.6) else cands[:2]
        if not rereq:
            rereq = ['ortho']
    cut = {}
    for t in rereq:
        ds = sorted(e['date'] for e in evs if e['ptype'] == t)
        cut[t] = ds[int(len(ds) * rp.uniform(0.55, 0.75))]
    rel = {t: add_days(cut.get(t, last_by[t]), rp.randint(12, 45)) for t in P}
    rerel = {t: add_days(last_by[t], rp.randint(15, 40)) for t in rereq}
    last_all = max(last_by.values())
    pdates = {}
    d0 = max(rel.values())
    for k in chrono[1:]:
        d0 = add_days(max(d0, last_all) if k != 'insurer' else d0, rp.randint(20, 70))
        if k == 'rerequest':
            d0 = max(d0, max(rerel.values()))
        pdates[k] = d0
    portal_provs = [t for t in ('er', 'pcp', 'ortho') if t in P][:rp.choice([1, 2])] if 'portal' in kinds else []
    # ---- clinical docs
    docs = []

    def new_doc(kind, author, ptype, date, pages, tag, event=None, home='release', ent=None):
        d = dict(id='d%03d' % (len(docs) + 1), kind=kind, author=author, ptype=ptype, date=date, pages=pages, tag=tag,
                 event=event, home=home, cids=[], ent=ent)
        docs.append(d)
        return d
    for e in evs:
        t = e['ptype']
        late = t in cut and e['date'] > cut[t]
        pdate = rerel[t] if late else rel[t]
        pages = e['builder'](C, P[t], e, rt, pdate)
        e['doc'] = new_doc('clinical', P[t]['name'], t, e['date'], pages, 'clinical', event=e, home='rerequest' if late else 'release')
    # ---- admin / billing originals
    firm = C['firm']
    adm = {}
    auth_date = add_days(C['acc'], rp.randint(6, 25))
    adm['auth'] = new_doc('admin', firm['name'], None, auth_date, adm_hipaa(C, firm, auth_date), 'auth')
    custodians = {}
    for i, t in enumerate(prov_order):
        p = P[t]
        ref = '%s/%02d' % (C['firm_ref'], i + 1)
        rq = add_days(rel[t], -rp.randint(15, 40))
        adm[('req1', t)] = new_doc('admin', firm['name'], None, rq, adm_request_letter(C, firm, p, rq, ref), 'req1')
        adm[('req1', t)]['req'] = (rq, ref)
        custodians[t] = ['%s %s' % (rp.choice(CFIRST), rp.choice(CLAST)) for _ in range(2)]
        adm[('cover1', t)] = new_doc('admin', p['name'], t, rel[t], None, 'cover1')
        adm[('cert1', t)] = new_doc('admin', p['name'], t, add_days(rel[t], rp.randint(0, 2)), None, 'cert1')
        bev = [e for e in evs if e['ptype'] == t and not (t in cut and e['date'] > cut[t])]
        sd = add_days(rel[t], -rp.randint(1, 6))
        acct = 'A%s-%06d' % (p['stem'][:2].upper(), rp.randint(1000, 999999))
        adm[('bill1', t)] = new_doc('billing', p['name'], t, sd, adm_billing(C, p, bev, sd, acct, rp), 'bill1')
        if t in rereq:
            rq2 = add_days(rerel[t], -rp.randint(10, 30))
            ref2 = '%s-%s' % (ref, rp.choice(['B', '2', 'RR', 'SUPP']))
            adm[('req2', t)] = new_doc('admin', firm['name'], None, rq2, adm_request_letter(C, firm, p, rq2, ref2), 'req2', home='rerequest')
            adm[('req2', t)]['req'] = (rq2, ref2)
            adm[('cover2', t)] = new_doc('admin', p['name'], t, rerel[t], None, 'cover2', home='rerequest')
            adm[('cert2', t)] = new_doc('admin', p['name'], t, add_days(rerel[t], rp.randint(0, 3)), None, 'cert2', home='rerequest')
            sd2 = add_days(rerel[t], -rp.randint(1, 5))
            adm[('bill2', t)] = new_doc('billing', p['name'], t, sd2,
                                        adm_billing(C, p, [e for e in evs if e['ptype'] == t], sd2, acct, rp), 'bill2', home='rerequest')
    # corrected statement look-alike (one billing line differs only in code or amount)
    bt_ = max(prov_order, key=lambda t: count_by.get(t, 0))
    src = adm[('bill1', bt_)]
    pg = copy.deepcopy(src['pages'][0])
    swaps = {'97110': '97112', '97112': '97110', '99214': '99213', '98941': '98940', '97140': '97530', '97530': '97140'}
    rows = [l for l in pg['lines'] if l['f'] == 'Courier' and l['t'].count('\t') == 3 and l['t'].split('\t')[1] in CHARGES]
    rl = rows[rp.randrange(len(rows))]
    cells = rl['t'].split('\t')
    if cells[1] in swaps and rp.random() < 0.7:
        cells[1] = swaps[cells[1]]
    else:
        cells[3] = '%.2f' % (float(cells[3]) + rp.choice([10, 25, -15, 40]))
    rl['t'] = '\t'.join(cells)
    adm['corrected'] = new_doc('billing', src['author'], bt_, src['date'], [pg], 'corrected')
    ins = C['ins']
    if 'insurer' in kinds:
        ad = add_days(C['acc'], rp.randint(20, 60))
        adm['ack'] = new_doc('admin', ins['name'], None, ad, adm_insurer_ack(C, ins, ad, firm, add_days(ad, -rp.randint(5, 15))), 'ack', home='insurer')
        rows_ = []
        for t in prov_order:
            billed = sum(CHARGES.get(c, 150) for e in evs if e['ptype'] == t for c in e['procedures'])
            rows_.append((P[t]['name'], billed, round(billed * rp.uniform(0.45, 0.85), 2)))
        adm['review'] = new_doc('billing', ins['name'], None, pdates['insurer'], adm_bill_review(C, ins, pdates['insurer'], rows_), 'review', home='insurer')
    if 'defense' in kinds:
        adm['dcover'] = new_doc('admin', C['defense']['name'], None, pdates['defense'], None, 'dcover', home='defense')
        adm['dindex'] = new_doc('admin', C['defense']['name'], None, pdates['defense'], None, 'dindex', home='defense')
    for t in portal_provs:
        ds = [e['date'] for e in evs if e['ptype'] == t]
        adm[('pcover', t)] = new_doc('admin', P[t]['name'], t, pdates['portal'],
                                     adm_portal_cover(C, P[t], C['portal'], pdates['portal'], min(ds), max(ds)), 'pcover', home='portal')
    n_ex = rp.randint(4, 7) if 'exhibit' in kinds else 0
    for k in range(n_ex):
        adm[('slip', k)] = new_doc('admin', firm['name'], None, pdates['exhibit'], None, 'slip', home='exhibit')
    O = sum(1 if d['pages'] is None else len(d['pages']) for d in docs)
    return dict(C=C, evs=evs, docs=docs, adm=adm, kinds=kinds, chrono=chrono, prod_no=prod_no, rereq=rereq, cut=cut, rel=rel,
                rerel=rerel, pdates=pdates, prov_order=prov_order, portal_provs=portal_provs, n_ex=n_ex, custodians=custodians, O=O)


def assemble(K, T):
    C = K['C']
    P = C['P']
    docs, adm, evs = K['docs'], K['adm'], K['evs']
    rp = R(C['case_no'], 'assemble')
    O = K['O']
    budget_total = T - O
    pn = K['prod_no']
    clin = [d for d in docs if d['kind'] == 'clinical']
    by_t = {}
    for d in clin:
        by_t.setdefault(d['ptype'], []).append(d)
    # ---------------- release production (production 1)
    other = []
    def ev_docs(t, kinds_):
        return [d for d in by_t.get(t, []) if d['event']['kind'] in kinds_]
    fc = 'er' if 'er' in P else 'urgent'
    for d in ev_docs(fc, ('er_visit', 'office_visit', 'imaging')):
        for holder, pr in (('pcp', 0.6), ('ortho', 0.45)):
            if rp.random() < pr:
                other.append((d, holder))
    for d in [d for d in clin if d['event']['kind'] == 'imaging' and d['event'].get('extra') == 'mri']:
        for holder, pr in (('ortho', 0.7), ('pain', 0.5)):
            if holder in P and rp.random() < pr:
                other.append((d, holder))
    if 'ems' in P and rp.random() < 0.7:
        other.append((by_t['ems'][0], 'er'))
    for d in [d for d in clin if d['event']['kind'] == 'surgery']:
        if rp.random() < 0.6:
            other.append((d, 'pt'))
    o1 = [d for d in by_t['ortho'] if d['event'].get('first')]
    if o1 and rp.random() < 0.5:
        other.append((o1[0], 'pcp'))
    # holder must be released after source date and not the same provider
    other = [(d, h) for d, h in other if h in P and h != d['ptype'] and K['rel'][h] > d['date']]
    auth_enc = [t for t in K['prov_order'] if rp.random() < 0.55]
    fixed = sum(len(d['pages']) if h != 'pt' else min(2, len(d['pages'])) for d, h in other) + max(0, len(auth_enc) - 1)
    while fixed > budget_total * 0.25 and other:
        d, h = other.pop()
        fixed -= len(d['pages']) if h != 'pt' else min(2, len(d['pages']))
    insts = []

    def add(doc, pages, prod, group, mech, src=None, extra=None):
        i = Inst(doc, pages, prod, group, mech, src, extra)
        insts.append(i)
        return i
    seqs = {}
    rel_list = []
    auth_used = False
    for t in K['prov_order']:
        p = P[t]
        g = p['name']
        own = [d for d in by_t.get(t, []) if d['home'] == 'release']
        oc = [(d, h) for d, h in other if h == t]
        body = []
        for d in own:
            body.append((d['date'], 0, d, ['original'], None))
        for d, h in oc:
            pages = list(range(len(d['pages']))) if t != 'pt' else list(range(min(2, len(d['pages']))))
            body.append((add_days(d['date'], rp.randint(1, 12)), 1, d, ['filed_in_other_chart'], pages))
        body.sort(key=lambda x: (x[0], x[1], x[2]['id']))
        head = [(adm[('req1', t)], ['original'])]
        if t in auth_enc:
            head.append((adm['auth'], ['original'] if not auth_used else ['provider_release', 'enclosure_copy']))
            auth_used = True
        head += [(adm[('cover1', t)], ['original']), (adm[('cert1', t)], ['original'])]
        bills = [(adm[('bill1', t)], ['original'])]
        if adm['corrected']['ptype'] == t:
            bills.append((adm['corrected'], ['original']))
        if rp.random() < 0.3:
            seq = head + bills + [(x[2], x[3], x[4], x[0]) for x in body]
        else:
            seq = head + [(x[2], x[3], x[4], x[0]) for x in body] + bills
        n_rel_pages = 0
        for item in seq:
            doc, mech = item[0], item[1]
            pages = item[2] if len(item) > 2 and item[2] is not None else list(range(len(doc['pages']) if doc['pages'] else 1))
            extra = {'scan_date': item[3]} if len(item) > 3 and mech[0] == 'filed_in_other_chart' else None
            add(doc, pages, pn['release'], g, mech, extra=extra)
            if doc['tag'] not in ('req1', 'auth', 'cover1', 'cert1'):
                n_rel_pages += len(pages)
        rel_list.append((t, n_rel_pages, [d for d in own]))
    fixed_actual = sum(len(i.pages) for i in insts if i.mech[0] != 'original')
    remaining = budget_total - fixed_actual
    # ---------------- other productions; fill order
    fill_order = [k for k in ('exhibit', 'portal', 'rerequest', 'insurer', 'defense') if k in K['kinds']]
    weights = {'exhibit': 1.0, 'portal': 1.3, 'rerequest': 1.6, 'insurer': 3.0, 'defense': 4.0}
    wsum = sum(weights[k] for k in fill_order)
    budgets = {k: int(remaining * weights[k] / wsum) for k in fill_order}
    carry = 0
    prod_insts = {}
    for idx, k in enumerate(fill_order):
        last = idx == len(fill_order) - 1
        b = (remaining - sum(len(i.pages) for kk in prod_insts for i in prod_insts[kk] if i.mech[0] != 'original')) if last else budgets[k] + carry
        made = fill_production(K, k, b, rp, last, prod_insts)
        prod_insts[k] = made
        used = sum(len(i.pages) for i in made if i.mech[0] != 'original')
        carry = b - used
    for k in fill_order:
        insts.extend(prod_insts[k])
    return insts


def take(pool, b, rp, cycle=False, min_pages=1):
    """Pick (doc, pages) from pool up to b pages; last may be partial."""
    out = []
    used = 0
    i = 0
    passes = 0
    while used < b and pool:
        if i >= len(pool):
            if not cycle:
                break
            i = 0
            passes += 1
            if passes > 6:
                break
        d = pool[i]
        i += 1
        n = len(d['pages'])
        if used + n <= b:
            out.append((d, list(range(n)), passes))
            used += n
        else:
            k = b - used
            out.append((d, list(range(k)), passes))
            used += k
    return out


def fill_production(K, kind, b, rp, last, prod_insts):
    C = K['C']
    P = C['P']
    adm = K['adm']
    no = K['prod_no'][kind]
    docs = K['docs']
    clin = [d for d in docs if d['kind'] == 'clinical']
    made = []

    def mk(doc, pages, group, mech, src=None, extra=None):
        i = Inst(doc, pages, no, group, mech, src, extra)
        made.append(i)
        return i
    b = max(0, b)
    if kind == 'exhibit':
        key = [d for d in clin if d['event']['kind'] in ('er_visit', 'surgery', 'procedure', 'ems') or
               (d['event']['kind'] == 'imaging' and d['event'].get('extra') == 'mri') or d['event'].get('first')]
        key += [adm[k] for k in adm if isinstance(k, tuple) and k[0] == 'bill1']
        rp.shuffle(key)
        key = key[:K['n_ex']]
        while len(key) < K['n_ex']:
            key.append(clin[len(key)])
        key.sort(key=lambda d: d['date'])
        per = max(1, b // max(1, K['n_ex']))
        used = 0
        for k, d in enumerate(key):
            n = min(len(d['pages']), per if k < len(key) - 1 else max(1, b - used))
            n = max(1, n)
            slip = adm[('slip', k)]
            slip['ex'] = (k + 1, d)
            mk(slip, [0], C['firm']['name'], ['original'], extra={'ex': k + 1})
            mk(d, list(range(n)), d['author'], ['exhibit'], extra={'ex': k + 1})
            used += n
        return made
    if kind == 'portal':
        for t in K['portal_provs']:
            mk(adm[('pcover', t)], [0], P[t]['name'], ['original'])
        pool = [d for d in clin if d['ptype'] in K['portal_provs']]
        pool.sort(key=lambda d: d['date'], reverse=True)
        picks = take(pool, b, rp, cycle=last)
        for d, pages, ps in picks:
            mk(d, pages, d['author'], ['portal_download', 'reflow'] + (['double_scan'] if ps else []))
        return made
    if kind == 'rerequest':
        share = {t: b // len(K['rereq']) for t in K['rereq']}
        share[K['rereq'][-1]] += b - sum(share.values())
        for t in K['rereq']:
            g = P[t]['name']
            mk(adm[('req2', t)], [0], g, ['original'])
            mk(adm[('cover2', t)], [0], g, ['original'])
            mk(adm[('cert2', t)], [0], g, ['original'])
            older = [d for d in clin if d['ptype'] == t and d['home'] == 'release']
            older.sort(key=lambda d: d['date'], reverse=True)
            picks = take(older, share[t], rp, cycle=last)
            newer = [d for d in clin if d['ptype'] == t and d['home'] == 'rerequest']
            items = [(d['date'], d, pages, ['rerequest'] + (['double_scan'] if ps else [])) for d, pages, ps in picks]
            items += [(d['date'], d, list(range(len(d['pages']))), ['original']) for d in newer]
            items.sort(key=lambda x: (x[0], x[1]['id']))
            for _, d, pages, mech in items:
                mk(d, pages, g, mech)
            mk(adm[('bill2', t)], list(range(len(adm[('bill2', t)]['pages']))), g, ['original'])
        return made
    if kind == 'insurer':
        mk(adm['ack'], [0], C['ins']['name'], ['original'])
        pool = [d for d in docs if (d['kind'] == 'clinical' and d['event']['kind'] != 'prior_visit') or d['tag'] in ('bill1', 'bill2')]
        rp.shuffle(pool)
        picks = take(pool, b, rp, cycle=last)
        picks.sort(key=lambda x: (x[0]['date'], x[0]['id'], x[2]))
        for d, pages, ps in picks:
            mk(d, pages, d['author'], ['insurer_file'] + (['double_scan'] if ps else []))
        mk(adm['review'], [0], C['ins']['name'], ['original'])
        return made
    if kind == 'defense':
        mk(adm['dcover'], [0], C['defense']['name'], ['original'])
        mk(adm['dindex'], [0], C['defense']['name'], ['original'])
        used = 0
        secA = []
        if 'insurer' in prod_insts:
            src = [i for i in prod_insts['insurer'] if i.mech[0] != 'original']
            rp.shuffle(src)
            lim = int(b * rp.uniform(0.25, 0.45))
            for s in src:
                if used + len(s.pages) > lim:
                    continue
                secA.append(s)
                used += len(s.pages)
            secA.sort(key=lambda s: (s.doc['date'], s.doc['id']))
        for s in secA:
            mk(s.doc, list(s.pages), s.doc['author'], ['opposing_production', 'copy_of_copy'], src=s)
        pool = [d for d in docs if d['kind'] in ('clinical', 'billing') or d['tag'] in ('cert1', 'req1', 'cover1')]
        pool = [d for d in pool if d['pages'] is not None or d['tag'] in ('cert1', 'cover1')]
        rp.shuffle(pool)
        # pages of lazily-built admin docs (covers, certifications) are 1 page
        out = []
        u = 0
        i = 0
        passes = 0
        while u < b - used and pool:
            if i >= len(pool):
                if not last:
                    break
                i, passes = 0, passes + 1
                if passes > 6:
                    break
            d = pool[i]
            i += 1
            n = len(d['pages']) if d['pages'] is not None else 1
            k = min(n, b - used - u)
            out.append((d, list(range(k)), passes))
            u += k
        order = {t: j for j, t in enumerate(K['prov_order'])}
        out.sort(key=lambda x: (order.get(x[0]['ptype'], 99), x[0]['author'], x[0]['date'], x[0]['id'], x[2]))
        for d, pages, ps in out:
            mk(d, pages, d['author'], ['opposing_production'] + (['double_scan'] if ps else []))
        return made
    raise ValueError(kind)


# ---------------------------------------------------------------------------
# Finalize: lazy admin pages, ordering, first occurrences, rendering, truth
# ---------------------------------------------------------------------------
RECV_STAMPS = [lambda d, s: 'RECEIVED %s' % fd(d, 'ABBRPAD'),
               lambda d, s: "REC'D %s CLAIMS" % fd(d, 'mdy2n'),
               lambda d, s: '[ RECEIVED  %s  %s ]' % (fd(d, 'oracle'), s),
               lambda d, s: 'Received %s - %s' % (fd(d, 'abbrdot'), s),
               lambda d, s: 'RCVD %s' % fd(d, 'mdy4dot'),
               lambda d, s: '%s  RECEIVED  %s' % (s, fd(d, 'iso'))]
OUTSIDE_STAMPS = [lambda d, h: 'OUTSIDE RECORDS - SCANNED %s' % fd(d, 'mdy4'),
                  lambda d, h: "Rec'd from outside facility %s - filed to chart" % fd(d, 'abbr'),
                  lambda d, h: 'EXTERNAL DOCUMENT | %s | %s' % (h, fd(d, 'iso')),
                  lambda d, h: 'Scanned into %s chart %s' % (h, fd(d, 'mdy2n')),
                  lambda d, h: 'MEDIA: OUTSIDE RECORD  %s' % fd(d, 'compact')]
COPY_STAMPS = [lambda d: 'COPY', lambda d: 'DUPLICATE RELEASE %s' % fd(d, 'mdy4dash'), lambda d: '** RE-RELEASED %s **' % fd(d, 'long'),
               lambda d: 'COPY - ORIGINAL ON FILE', lambda d: 'SUPPLEMENTAL PRODUCTION %s' % fd(d, 'abbrnc')]


def short_name(name):
    w = [x for x in name.replace('&', ' ').replace(',', ' ').split() if x[0].isupper()]
    return ''.join(x[0] for x in w[:4]).upper()


def finalize(K, insts):
    C = K['C']
    P = C['P']
    adm = K['adm']
    rp = R(C['case_no'], 'final')
    ents = {p['name']: p for p in P.values()}
    for e in (C['firm'], C['defense'], C['ins']):
        ents[e['name']] = e
    for n, i in enumerate(insts):
        i.seq = n
    by_prod = sorted(insts, key=lambda i: (i.prod, i.seq))
    # exhibit copies sourced from opposing-counsel copies (copy of a copy)
    dprod = K['prod_no'].get('defense')
    eprod = K['prod_no'].get('exhibit')
    if dprod and eprod:
        dlist = [i for i in insts if i.prod == dprod and i.mech[0] == 'opposing_production']
        for i in insts:
            if i.prod == eprod and i.mech[0] == 'exhibit' and rp.random() < 0.45:
                cands = [s for s in dlist if s.doc is i.doc and s.pages[:len(i.pages)] == i.pages]
                if cands:
                    i.src = cands[0]
                    i.mech = i.mech + ['copy_of_copy']
    # ---- lazy admin documents
    for t in K['prov_order']:
        p = P[t]
        relp = [i for i in insts if i.prod == K['prod_no']['release'] and i.group == p['name'] and
                i.doc['tag'] not in ('req1', 'auth', 'cover1', 'cert1')]
        n1 = sum(len(i.pages) for i in relp)
        own = [i.doc['date'] for i in relp if i.doc['kind'] == 'clinical' and i.doc['ptype'] == t] or [K['rel'][t]]
        rq, ref = adm[('req1', t)]['req']
        roi = 'ROI-%s%05d' % (p['stem'][:3].upper(), rp.randint(10000, 99999))
        adm[('cover1', t)]['pages'] = adm_provider_cover(C, p, adm[('cover1', t)]['date'], rq, ref, n1, roi, 6.5 + 0.25 * n1, min(own), max(own))
        county = rp.choice(['Ashland', 'Burke', 'Crawford', 'Delmar', 'Essex', 'Franklin', 'Grafton', 'Harlan'])
        notary = '%s %s' % (rp.choice(CFIRST), rp.choice(CLAST))
        adm[('cert1', t)]['pages'] = adm_cert(C, p, K['custodians'][t][0], adm[('cert1', t)]['date'], n1, county, notary)
        if t in K['rereq']:
            rr = K['prod_no']['rerequest']
            rrp = [i for i in insts if i.prod == rr and i.group == p['name'] and i.doc['tag'] not in ('cover2', 'cert2')]
            n2 = sum(len(i.pages) for i in rrp)
            own2 = [i.doc['date'] for i in rrp if i.doc['kind'] == 'clinical'] or [K['rerel'][t]]
            rq2, ref2 = adm[('req2', t)]['req']
            adm[('cover2', t)]['pages'] = adm_provider_cover(C, p, adm[('cover2', t)]['date'], rq2, ref2, n2, roi + '-S', 6.5 + 0.25 * n2, min(own2), max(own2))
            adm[('cert2', t)]['pages'] = adm_cert(C, p, K['custodians'][t][1], adm[('cert2', t)]['date'], n2, county,
                                                  '%s %s' % (rp.choice(CFIRST), rp.choice(CLAST)))
    bates = {}
    if dprod:
        prefix = rp.choice(['%s-PLTF' % short_name(C['defense']['name']), 'DEF-MED', '%s' % short_name(C['defense']['name']), 'D-%s' % C['patient']['last'][:4].upper()])
        n = rp.randint(1, 400)
        start = n
        rows = []
        cur = None
        for i in by_prod:
            if i.prod != dprod or i.doc['tag'] in ('dcover', 'dindex'):
                continue
            for k in range(len(i.pages)):
                bates[(id(i), k)] = n
                src_name = ('Carrier claim file - ' if 'copy_of_copy' in i.mech else '') + i.doc['author']
                if cur and cur[0] == src_name:
                    cur[2] = n
                else:
                    cur = [src_name, n, n]
                    rows.append(cur)
                n += 1
        merged = []
        for r in rows:
            merged.append(tuple(r))
        while len(merged) > 40:
            merged = merged[:40]
        adm['dcover']['pages'] = adm_defense_cover(C, C['defense'], adm['dcover']['date'], C['firm'], prefix, start, n - 1, C['court_no'])
        adm['dindex']['pages'] = adm_defense_index(C, C['defense'], prefix, merged)
        K['bates_prefix'] = prefix
    for k in range(K['n_ex']):
        s = adm[('slip', k)]
        num, d = s['ex']
        title = d['pages'][0]['lines'][0]['t'] if d['kind'] != 'clinical' else '%s - %s' % (d['author'], d['event']['kind'].replace('_', ' '))
        s['pages'] = adm_exhibit_slip(C['firm'], num, title[:70])
    # ---- content ids
    docs = K['docs']
    cid = {}
    n = 0
    for d in sorted(docs, key=lambda d: (d['date'], d['id'])):
        for pi in range(len(d['pages'])):
            n += 1
            cid[(d['id'], pi)] = 'c%04d' % n
        d['cids'] = [cid[(d['id'], pi)] for pi in range(len(d['pages']))]
    # ---- final order
    arrangement = rp.choice(['by_production', 'by_production', 'by_production', 'by_provider', 'by_provider'])
    grank = {}
    for t in K['prov_order']:
        grank[P[t]['name']] = len(grank)
    for nm in (C['firm']['name'], C['ins']['name'], C['defense']['name']):
        grank.setdefault(nm, len(grank))
    if arrangement == 'by_production':
        final = sorted(insts, key=lambda i: (i.prod, i.seq))
    else:
        final = sorted(insts, key=lambda i: (grank.get(i.group, 99), i.prod, i.seq))
    seen = set()
    for i in final:
        i.first = []
        for pi in i.pages:
            key = (i.doc['id'], pi)
            i.first.append(key not in seen)
            seen.add(key)
    # ---- render in chronological production order
    ctr = {}
    handnoted = set()
    for i in by_prod:
        i.models = []
        i.extra['tokens'] = []
        kind0 = i.mech[0]
        ent = ents.get(i.doc['author'])
        nn = len(i.pages)
        tx_date = None
        for k, pi in enumerate(i.pages):
            if i.first[k]:
                i.models.append(copy.deepcopy(i.doc['pages'][pi]))
                i.extra['tokens'].append(['original'])
                continue
            toks = []
            use_src = i.src is not None and 'copy_of_copy' in i.mech and not i.src.first[k]
            if use_src:
                m = copy.deepcopy(i.src.models[k])
                toks.append('copy_of_copy')
            else:
                m = copy.deepcopy(i.doc['pages'][pi])
            if kind0 == 'original':
                toks = ['provider_release'] + toks
            elif kind0 == 'filed_in_other_chart':
                toks = ['filed_in_other_chart'] + toks
                sd = i.extra.get('scan_date') or add_days(i.doc['date'], 3)
                f = OUTSIDE_STAMPS[hash_str(i.group) % len(OUTSIDE_STAMPS)]
                place = stamp(m, f(sd, short_name(i.group)), rp.choice(['line', 'margin', 'append']), rp, size=8.5)
                toks.append('stamp_' + place)
            elif kind0 == 'provider_release':
                toks = ['provider_release', 'enclosure_copy']
            elif kind0 == 'insurer_file':
                toks = ['insurer_file'] + toks
                if tx_date is None:
                    tx_date = min(add_days(i.doc['date'], rp.randint(4, 50)), K['pdates']['insurer'])
                    hm = (rp.randint(8, 17), rp.randint(0, 59))
                    job = rp.randint(1, 9999)
                    fwd = rp.random() < 0.3 and ent is not C['firm']
                    off = rp.randint(1, 12)
                if ent and ent is not C['ins']:
                    m['lines'].insert(0, ovl_line(fax_line(ent.get('fax_fmt', 0), ent['name'], ent['fax'], C['ins']['name'], C['ins']['fax'],
                                                           tx_date, hm, k + 1, nn, job)))
                    toks.append('fax_header')
                    if fwd:
                        f2 = C['firm']
                        m['lines'].insert(0, ovl_line(fax_line(f2['fax_fmt'], f2['name'], f2['fax'], C['ins']['name'], C['ins']['fax'],
                                                               add_days(tx_date, 2), (hm[0], (hm[1] + 7) % 60), k + 1 + off, nn + off + 3, job + 1)))
                        toks.append('fax_header_x2')
                if k == 0 or rp.random() < 0.5:
                    st = RECV_STAMPS[hash_str(C['ins']['name']) % len(RECV_STAMPS)](add_days(tx_date, rp.choice([0, 1, 1, 3])), short_name(C['ins']['name']))
                    toks.append('stamp_' + stamp(m, st, rp.choice(['line', 'margin', 'append', 'margin']), rp))
                ctr['ins'] = ctr.get('ins', 0) + 1
                m['abs'].append(dict(x=54, y=16, f='Helvetica', s=7, t='Claim %s  p.%04d' % (C['claim'], ctr['ins']), rot=0))
                toks.append('page_counter')
            elif kind0 == 'portal_download':
                toks = ['portal_download'] + toks
                pf = rp.choice(['Helvetica', 'Times-Roman'])
                t_reflow(m, pf, 9.0 if pf == 'Helvetica' else 10.0)
                toks.append('reflow')
                pd = K['pdates']['portal']
                m['lines'].insert(0, ovl_line('%s  -  %s' % (C['portal'], i.doc['author']), 'Helvetica-Bold', 9))
                m['lines'].append(ovl_line('Printed from %s on %s   |   Page %d of %d' % (C['portal'], fd(pd, 'wkabbr'), k + 1, nn), 'Helvetica', 7.5))
                if rp.random() < 0.25:
                    toks.append('crop_' + t_crop(m, rp))
            elif kind0 == 'rerequest':
                toks = ['rerequest'] + toks
                d2 = K['rerel'].get(i.doc['ptype'], K['pdates']['rerequest'])
                txt = COPY_STAMPS[hash_str(i.group) % len(COPY_STAMPS)](d2)
                toks.append('stamp_' + stamp(m, txt, rp.choice(['append', 'margin', 'line']), rp))
                if hash_str(i.group + 'fx') % 2 == 0 and ent and ent is not C['firm']:
                    m['lines'].insert(0, ovl_line(fax_line((ent.get('fax_fmt', 0) + 3) % 7, ent['name'], ent['fax'], C['firm']['name'],
                                                           C['firm']['fax'], d2, (14, 2 + k % 50), k + 1, nn, 77 + i.seq)))
                    toks.append('fax_header')
            elif kind0 == 'opposing_production':
                toks = ['opposing_production'] + toks
                b = bates.get((id(i), k))
                if b is not None:
                    if rp.random() < 0.7:
                        m['abs'].append(dict(x=470, y=18, f='Helvetica-Bold', s=8, t='%s %06d' % (K['bates_prefix'], b), rot=0))
                    else:
                        m['lines'].append(ovl_line('%s %06d' % (K['bates_prefix'], b), 'Helvetica-Bold', 8))
                    toks.append('bates')
                if rp.random() < 0.55:
                    t_ocr(m, rp, rp.uniform(0.012, 0.04))
                    toks.append('ocr')
                if rp.random() < 0.2:
                    toks.append('crop_' + t_crop(m, rp))
            elif kind0 == 'exhibit':
                toks = ['exhibit'] + toks
                m['abs'].append(dict(x=440, y=777, f='Helvetica-Bold', s=9, t="PLAINTIFF'S EX. %d - %d" % (i.extra['ex'], k + 1), rot=0))
                toks.append('exhibit_label')
                ckey = (i.doc['id'], pi)
                if ckey not in handnoted and rp.random() < 0.4:
                    handnoted.add(ckey)
                    hx, hy, hr = rp.choice([(60, 784, 0), (250, 784, 0), (60, 40, 0), (250, 40, 0), (44, rp.randint(250, 560), 1)])
                    m['abs'].append(dict(x=hx, y=hy, f='Times-Italic', s=11, t=rp.choice(HANDNOTES), rot=hr))
                    toks.append('handnote')
            if 'double_scan' in i.mech:
                t_ocr(m, rp, 0.02)
                toks.append('double_scan')
                if 'ocr' not in toks:
                    toks.append('ocr')
            i.models.append(m)
            i.extra['tokens'].append(toks)
    # ---- output pages
    out_pages = []
    truth_pages = []
    for i in final:
        for k, pi in enumerate(i.pages):
            out_pages.append(i.models[k])
            truth_pages.append(dict(page=len(truth_pages) + 1, content_id=cid[(i.doc['id'], pi)], provider=i.doc['author'],
                                    production=i.prod, mechanism='+'.join(i.extra['tokens'][k]), doc_kind=i.doc['kind']))
    events = []
    for n_, e in enumerate(K['evs']):
        events.append(dict(event_id='e%03d' % (n_ + 1), date=fd(e['date'], 'mdy4'), provider=P[e['ptype']]['name'], kind=e['kind'],
                           summary=e['summary'], codes=list(e['codes']), procedures=list(e['procedures']), doc_id=e['doc']['id'],
                           pages=list(e['doc']['cids'])))
    regions = [C['reg'][r]['name'] for r in C['regions']]
    truth = dict(case_id=C['case_id'], patient=dict(first=C['patient']['first'], last=C['patient']['last'], dob=fd(C['dob'], 'mdy4')),
                 accident_date=fd(C['acc'], 'mdy4'), regions=regions, events=events, pages=truth_pages)
    meta = dict(arrangement=arrangement, chrono=K['chrono'])
    return out_pages, truth, meta


def self_check(K, out_pages, truth):
    """Structural checks done inside the generator (text-layer checks are in _scratch/check_alt5.py)."""
    docs = K['docs']
    seen_txt = {}
    for d in docs:
        for pi, pg in enumerate(d['pages']):
            t = ' '.join(page_text(pg).split())
            assert t, 'empty original page'
            assert t not in seen_txt, 'identical text for two content ids: %s %s' % (seen_txt[t], d['cids'][pi])
            seen_txt[t] = d['cids'][pi]
    for e, ev in zip(truth['events'], K['evs']):
        variants = [v.lower() for v in date_variants(ev['date'])]
        for pi, pg in enumerate(ev['doc']['pages']):
            t = page_text(pg).lower()
            assert any(v in t for v in variants), 'visit date missing on %s %s' % (e['event_id'], e['pages'][pi])
    for pg in out_pages:
        assert page_text(pg).strip(), 'empty output page'


def generate(case_no, out_dir):
    rt = R(case_no, 'target')
    dup = rt.uniform(0.565, 0.635)
    T_target = rt.randint(232, 408)
    O_target = int(round(T_target * (1 - dup)))
    n_fill = 30
    K = None
    for _ in range(10):
        K = build_case(case_no, n_fill)
        diff = O_target - K['O']
        if diff == 0:
            break
        n_fill = max(4, n_fill + diff)
    O = K['O']
    T = int(round(O / (1 - dup)))
    T = max(222, min(418, T))
    insts = assemble(K, T)
    out_pages, truth, meta = finalize(K, insts)
    self_check(K, out_pages, truth)
    cdir = os.path.join(out_dir, K['C']['case_id'])
    os.makedirs(cdir, exist_ok=True)
    pdf = build_pdf([layout(p) for p in out_pages])
    with open(os.path.join(cdir, 'records.pdf'), 'wb') as f:
        f.write(pdf)
    with open(os.path.join(cdir, 'truth.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(truth, f, indent=1)
        f.write('\n')
    n_unique = len(set(p['content_id'] for p in truth['pages']))
    return dict(case=K['C']['case_id'], pages=len(truth['pages']), originals=n_unique,
                dup_pct=round(100.0 * (len(truth['pages']) - n_unique) / len(truth['pages']), 1),
                events=len(truth['events']), providers=len(K['C']['P']), arrangement=meta['arrangement'],
                productions=meta['chrono'])


def main(argv):
    out = DEFAULT_OUT
    n = 10
    a = list(argv)
    if '--out' in a:
        out = a[a.index('--out') + 1]
    if '--cases' in a:
        n = int(a[a.index('--cases') + 1])
    os.makedirs(out, exist_ok=True)
    for c in range(1, n + 1):
        s = generate(c, out)
        print('%-8s pages=%3d originals=%3d dup=%4.1f%% events=%3d providers=%d %s %s' % (
            s['case'], s['pages'], s['originals'], s['dup_pct'], s['events'], s['providers'], s['arrangement'], '>'.join(s['productions'])))


if __name__ == '__main__':
    main(sys.argv[1:])
