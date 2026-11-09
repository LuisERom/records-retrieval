"""Minimal deterministic PDF writer with a real text layer.

Only the 14 standard Type1 fonts are used (no embedding), text is drawn with
Tj operators in WinAnsiEncoding, content streams are zlib-compressed with a
fixed level, and no timestamps or random IDs are written, so the same input
always produces the same bytes.
"""
import math
import zlib

FONTS = [
    ("H", "Helvetica"), ("HB", "Helvetica-Bold"), ("HO", "Helvetica-Oblique"),
    ("C", "Courier"), ("CB", "Courier-Bold"),
    ("T", "Times-Roman"), ("TB", "Times-Bold"), ("TI", "Times-Italic"),
]
FKEY = {k: "F%d" % (i + 1) for i, (k, _) in enumerate(FONTS)}
# rough average glyph width as a fraction of the font size
CHAR_W = {"H": 0.50, "HB": 0.54, "HO": 0.50, "C": 0.60, "CB": 0.60,
          "T": 0.45, "TB": 0.48, "TI": 0.43}


def _esc(s):
    s = s.encode("cp1252", "replace").decode("cp1252")
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def text_width(text, font, size):
    return len(text) * CHAR_W[font] * size


def _page_stream(ops):
    out = []
    for op in ops:
        if op[0] == "T":
            _, font, size, x, y, angle, text = op
            if angle:
                a = math.radians(angle)
                c, s = math.cos(a), math.sin(a)
                m = "%.4f %.4f %.4f %.4f %.2f %.2f" % (c, s, -s, c, x, y)
            else:
                m = "1 0 0 1 %.2f %.2f" % (x, y)
            out.append("BT /%s %.1f Tf %s Tm (%s) Tj ET" % (FKEY[font], size, m, _esc(text)))
        elif op[0] == "L":
            _, x1, y1, x2, y2, w = op
            out.append("%.2f w %.2f %.2f m %.2f %.2f l S" % (w, x1, y1, x2, y2))
        elif op[0] == "G":  # gray level for following text
            out.append("%.2f g" % op[1])
    return ("\n".join(out) + "\n").encode("cp1252", "replace")


def write_pdf(path, pages, title="records"):
    """pages: list of op lists. Writes a letter-size PDF."""
    objs = {}
    n_fonts = len(FONTS)
    # 1 catalog, 2 pages, 3 info, 4.. fonts, then page/content pairs
    font_ids = list(range(4, 4 + n_fonts))
    first_page = 4 + n_fonts
    kids = []
    for i, ops in enumerate(pages):
        pid = first_page + 2 * i
        cid = pid + 1
        kids.append(pid)
        data = zlib.compress(_page_stream(ops), 9)
        objs[cid] = b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(data) + data + b"\nendstream"
        objs[pid] = ("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << %s >> >> /Contents %d 0 R >>"
                     % (" ".join("/%s %d 0 R" % (FKEY[k], font_ids[j]) for j, (k, _) in enumerate(FONTS)), cid)).encode()
    for j, (k, name) in enumerate(FONTS):
        objs[font_ids[j]] = ("<< /Type /Font /Subtype /Type1 /BaseFont /%s /Encoding /WinAnsiEncoding >>" % name).encode()
    objs[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objs[2] = ("<< /Type /Pages /Kids [%s] /Count %d >>" % (" ".join("%d 0 R" % k for k in kids), len(kids))).encode()
    objs[3] = ("<< /Title (%s) /Producer (altgen4 pdfmini) >>" % _esc(title)).encode()
    maxid = max(objs)
    buf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0] * (maxid + 1)
    for oid in range(1, maxid + 1):
        offsets[oid] = len(buf)
        buf += b"%d 0 obj\n" % oid + objs[oid] + b"\nendobj\n"
    xref = len(buf)
    buf += b"xref\n0 %d\n0000000000 65535 f \n" % (maxid + 1)
    for oid in range(1, maxid + 1):
        buf += b"%010d 00000 n \n" % offsets[oid]
    buf += b"trailer\n<< /Size %d /Root 1 0 R /Info 3 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (maxid + 1, xref)
    with open(path, "wb") as f:
        f.write(bytes(buf))
