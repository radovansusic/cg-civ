"""Robust row extraction from Monstat PDFs: merges thousand-separated digit groups by x-gap."""
import pdfplumber, re

def page_rows(pdf_path, page_no, gap=None):
    pg = pdfplumber.open(pdf_path).pages[page_no]
    words = pg.extract_words(x_tolerance=1, y_tolerance=2, keep_blank_chars=False)
    # group by line
    lines = {}
    for w in words:
        key = round(w['top'] / 3)
        lines.setdefault(key, []).append(w)
    out = []
    for k in sorted(lines):
        ws = sorted(lines[k], key=lambda w: w['x0'])
        out.append(ws)
    return out

def merge_numbers(ws, gap):
    """merge consecutive numeric tokens if gap < gap threshold and next token has exactly 3 digits"""
    toks = []
    for w in ws:
        t = w['text']
        if toks and re.fullmatch(r'\d{3}([.,]\d+)?', t) and re.fullmatch(r'-?\d{1,3}( \d{3})*', toks[-1]['text']) \
           and (w['x0'] - toks[-1]['x1']) < gap:
            toks[-1] = {'text': toks[-1]['text'] + ' ' + t, 'x0': toks[-1]['x0'], 'x1': w['x1']}
        else:
            toks.append({'text': t, 'x0': w['x0'], 'x1': w['x1']})
    return toks

def gaps(pdf_path, page_no):
    import collections
    rows = page_rows(pdf_path, page_no)
    c = collections.Counter()
    for ws in rows:
        for a, b in zip(ws, ws[1:]):
            if re.fullmatch(r'[\d.,]+', a['text']) and re.fullmatch(r'[\d.,]+', b['text']):
                c[round(b['x0'] - a['x1'], 1)] += 1
    return sorted(c.items())
