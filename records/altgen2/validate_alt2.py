#!/usr/bin/env python3
"""Self-check for the alt2 output: truth schema, page coverage, and text uniqueness.

python records/altgen2/validate_alt2.py [--show N]   (N = sample pages to print per case)
"""
import json
import os
import re
import sys

import fitz

HERE = os.path.dirname(os.path.abspath(__file__))
OUTROOT = os.path.normpath(os.path.join(HERE, '..', 'data', 'alt2'))
KINDS = {'er_visit', 'office_visit', 'prior_visit', 'imaging', 'lab', 'pt_eval', 'pt_reeval', 'pt_visit', 'injection', 'surgery'}
DATE = re.compile(r'^(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])/\d{4}$')


def norm(t):
    return re.sub(r'\s+', ' ', t).strip()


def main():
    show = int(sys.argv[sys.argv.index('--show') + 1]) if '--show' in sys.argv else 0
    bad = 0
    for n in range(1, 11):
        d = os.path.join(OUTROOT, f'alt2-{n}')
        truth = json.load(open(os.path.join(d, 'truth.json'), encoding='utf-8'))
        pdf = fitz.open(os.path.join(d, 'records.pdf'))
        errs = []
        assert set(truth) == {'case_id', 'patient', 'accident_date', 'regions', 'events', 'pages'}
        pages = truth['pages']
        if [p['page'] for p in pages] != list(range(1, len(pdf) + 1)):
            errs.append('page list does not cover the PDF exactly once')
        cids = {p['content_id'] for p in pages}
        for p in pages:
            if p['doc_kind'] not in ('clinical', 'billing', 'admin'):
                errs.append(f"bad doc_kind {p}")
            if not isinstance(p['production'], int):
                errs.append('production not int')
        for k in ('dob',):
            if not DATE.match(truth['patient'][k]):
                errs.append('dob format')
        if not DATE.match(truth['accident_date']):
            errs.append('accident date format')
        for e in truth['events']:
            if e['kind'] not in KINDS:
                errs.append(f"kind {e['kind']}")
            if not DATE.match(e['date']):
                errs.append(f"date {e['date']}")
            if not e['pages'] or any(c not in cids for c in e['pages']):
                errs.append(f"event pages missing {e['event_id']}")
        # text uniqueness: identical extracted text must imply identical content_id
        texts = {}
        for p in pages:
            t = norm(pdf[p['page'] - 1].get_text())
            if not t:
                errs.append(f"empty text page {p['page']}")
            texts.setdefault(t, set()).add(p['content_id'])
        clash = [v for v in texts.values() if len(v) > 1]
        if clash:
            errs.append(f"identical text across different content_ids: {clash[:3]}")
        # first-appearance (cleanest) copy of each content id must differ from every other content id's
        first = {}
        for p in pages:
            if p['content_id'] not in first:
                first[p['content_id']] = norm(pdf[p['page'] - 1].get_text())
        if len(set(first.values())) != len(first):
            errs.append('two originals share the same first-copy text')
        P, U = len(pages), len(cids)
        mechs = {}
        for p in pages:
            for m in p['mechanism'].split('+'):
                mechs[m] = mechs.get(m, 0) + 1
        print(f"alt2-{n}: pages={P} unique={U} dup={100 * (P - U) / P:.1f}% events={len(truth['events'])} errors={len(errs)}")
        print('   mechanisms:', ', '.join(f"{k}={v}" for k, v in sorted(mechs.items())))
        for e in errs[:5]:
            print('   ERR', e)
        bad += len(errs)
        if show:
            import random
            rr = random.Random(n)
            for p in rr.sample(pages, show):
                print(f"   --- page {p['page']} {p['content_id']} {p['mechanism']} ---")
                print('   ' + pdf[p['page'] - 1].get_text()[:600].replace('\n', '\n   '))
    print('ALL OK' if not bad else f'{bad} errors')


if __name__ == '__main__':
    main()
