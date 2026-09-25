"""Subset Latin Modern Math for the PyRUA-Lean post's equations (WOFF, MATH table kept).

    python scripts/build_math_font.py assets/pyrualean/fonts/pyrualean-math.woff [latinmodern-math.otf]

Needs fontTools (the ordinary site build does not). Keeps ASCII, the italic math alphabet that
MathML maps a single-letter <mi> to, and the few symbols the equations use, with their MATH-table
variants and assembly parts (the large sum, the stretchy underbrace). Add a character to RANGES
before using it in an equation. The family is renamed, as the GUST Font License requests for
derived fonts; the copyright and license records are kept.
"""
import sys

from fontTools import subset
from fontTools.ttLib import TTFont

SRC = sys.argv[2] if len(sys.argv) > 2 else "/usr/share/texmf/fonts/opentype/public/lm-math/latinmodern-math.otf"
FAMILY, PS_NAME = "PyRUA-Lean Math", "PyRUA-LeanMath-Regular"
#: ASCII, the italic math alphabet (and U+210E, its h), then single characters: macron, middle dot,
#: times, combining macron/overline, prime, overline, arrows, sum, minus, approx, relations, dot
#: operator, the over/under braces and brackets. The post writes \bar as <mo stretchy="false">
#: U+203E: with this font Chrome drops or misplaces a U+00AF accent, and U+02C9 is not in the font.
RANGES = [(0x20, 0x7E), (0x1D434, 0x1D467), (0x210E, 0x210E)] + [(c, c) for c in (
    0xAF, 0xB7, 0xD7, 0x304, 0x305, 0x2032, 0x203E, 0x2192, 0x21D2, 0x2211, 0x2212, 0x2248, 0x2260, 0x2264,
    0x2265, 0x22C5, 0x23B4, 0x23B5, 0x23DE, 0x23DF)]

out = sys.argv[1]
opts = subset.Options()
opts.layout_features = ["*"]
opts.name_IDs = ["*"]
opts.name_languages = ["*"]
opts.notdef_outline = True
opts.flavor = "woff"
font = TTFont(SRC)
sub = subset.Subsetter(opts)
sub.populate(unicodes=[u for lo, hi in RANGES for u in range(lo, hi + 1)])
sub.subset(font)
names = font["name"]
for rec in list(names.names):
    if rec.nameID in (1, 16):
        names.setName(FAMILY, rec.nameID, rec.platformID, rec.platEncID, rec.langID)
    elif rec.nameID == 4:
        names.setName(f"{FAMILY} Regular", rec.nameID, rec.platformID, rec.platEncID, rec.langID)
    elif rec.nameID == 6:
        names.setName(PS_NAME, rec.nameID, rec.platformID, rec.platEncID, rec.langID)
    elif rec.nameID == 3:
        names.setName(f"{PS_NAME};subset of Latin Modern Math", rec.nameID, rec.platformID, rec.platEncID, rec.langID)
names.setName("Subset of Latin Modern Math (GUST e-foundry) for the PyRUA-Lean post's equations.", 10, 3, 1, 0x409)
if "CFF " in font:  # the CFF font name is the PostScript name too
    cff = font["CFF "].cff
    cff.fontNames = [PS_NAME]
    top = cff.topDictIndex[0]
    top.FullName, top.FamilyName = f"{FAMILY} Regular", FAMILY
font.flavor = "woff"
font.save(out)
kept = font.getBestCmap()
print(out, "glyphs", len(font.getGlyphOrder()), "cmap", len(kept), "MATH" in font,
      "underbrace" if 0x23DF in kept else "NO underbrace", "sum" if 0x2211 in kept else "NO sum")
for rec in names.names:
    if rec.nameID in (0, 13, 14) and rec.platformID == 3:
        print(rec.nameID, rec.toUnicode()[:300])
