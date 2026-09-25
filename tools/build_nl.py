"""Genera le versioni olandesi (statiche, per la SEO) delle pagine principali.

Uso:  python3 tools/build_nl.py
Legge le pagine italiane in artebianca_site/ e scrive artebianca_site/nl/...
Da rilanciare ogni volta che si modifica una delle pagine sorgente.

Cosa fa:
- nelle pagine italiane aggiunge (una sola volta) PAGE_LANG e i link hreflang
- nelle copie /nl/: <html lang="nl">, title/description/og in olandese,
  canonical e hreflang, testi statici [data-i18n] già in olandese, lingua
  iniziale olandese e collegamenti interni verso le altre pagine /nl/.
"""
import html
import json
import re
import subprocess
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / 'artebianca_site'
BASE = 'https://artebianca.be'

PAGES = {
    # percorso: (title NL, description NL, og:title NL)
    '': (
        'Arte Bianca — Italiaans restaurant & pizzeria in Tisselt en Wintam',
        'Authentieke Napolitaanse pizza in Tisselt (Willebroek) en Italiaanse keuken in Wintam (Bornem). '
        'Afhalen, tafel reserveren, catering en business lunch.',
        'Arte Bianca — Italiaans restaurant & pizzeria',
    ),
    'tisselt-willebroek/': (
        'Pizzeria Arte Bianca Tisselt (Willebroek) | Napolitaanse pizza',
        'Authentieke Napolitaanse pizza in Tisselt, Willebroek: lang gerijpt deeg en Italiaanse ingrediënten. '
        'Menu, online afhalen en tafel reserveren. Hoogstraat 50, 2830 Tisselt.',
        'Pizzeria Arte Bianca — Tisselt, Willebroek',
    ),
    'wintam-bornem/': (
        'Italiaans restaurant & pizzeria Arte Bianca Wintam (Bornem)',
        'Italiaanse gerechten en pizza in een elegant kader in Wintam, Bornem. Reserveren, afhalen, '
        'business lunch en catering. Egied de Jonghestraat 165, 2880 Bornem.',
        'Restaurant & Pizzeria Arte Bianca — Wintam, Bornem',
    ),
    'business-lunch/': (
        'Business Lunch — Italiaanse lunch op kantoor | Arte Bianca Wintam',
        'Italiaanse lunch op kantoor in Bornem en omgeving: Menu Pizza €16 of Menu Restaurant €21 per persoon, '
        'warm geleverd in uw bedrijf. Vanaf 10 personen.',
        'Business Lunch — Italiaanse lunch op kantoor | Arte Bianca',
    ),
}
KEYWORDS_NL = ('pizzeria Tisselt, pizzeria Willebroek, Italiaans restaurant Bornem, Wintam, Napolitaanse pizza, '
               'afhalen, business lunch, catering, Arte Bianca')


def js_object(src, start_marker):
    """Estrae un oggetto JS letterale (es. const translations = {...}) e lo restituisce come dict."""
    a = src.index(start_marker)
    i = src.index('{', a)
    depth, j = 0, i
    in_str = None
    while j < len(src):
        c = src[j]
        if in_str:
            if c == '\\':
                j += 2
                continue
            if c == in_str:
                in_str = None
        elif c in '\'"`':
            in_str = c
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                break
        j += 1
    code = 'process.stdout.write(JSON.stringify((' + src[i:j + 1] + ')))'
    return json.loads(subprocess.run(['node', '-e', code], capture_output=True, text=True, check=True).stdout)


def hreflang_block(path):
    return (f'<link rel="alternate" hreflang="it" href="{BASE}/{path}">\n'
            f'<link rel="alternate" hreflang="nl" href="{BASE}/nl/{path}">\n'
            f'<link rel="alternate" hreflang="x-default" href="{BASE}/{path}">\n')


def sub1(s, pattern, repl, flags=0):
    s2, n = re.subn(pattern, repl, s, count=1, flags=flags)
    assert n == 1, pattern
    return s2


def outside_scripts(s, fn):
    """Applica fn solo all'HTML fuori dai blocchi <script>."""
    parts = re.split(r'(<script\b.*?</script>)', s, flags=re.S)
    return ''.join(p if p.startswith('<script') else fn(p) for p in parts)


def translate_static(s, tr):
    def one(p):
        def text(m):
            key = m.group(3)
            if key not in tr or not isinstance(tr[key], str):
                return m.group(0)
            return m.group(1) + html.escape(tr[key], quote=False) + m.group(5)

        def rich(m):
            key = m.group(3)
            if key not in tr or not isinstance(tr[key], str):
                return m.group(0)
            return m.group(1) + tr[key] + m.group(5)

        p = re.sub(r'(<(\w+)\b[^>]*\bdata-i18n="(\w+)"[^>]*>)([^<]*)(</\2>)', text, p)
        p = re.sub(r'(<(\w+)\b[^>]*\bdata-i18n-html="(\w+)"[^>]*>)(.*?)(</\2>)', rich, p, flags=re.S)
        return p
    return outside_scripts(s, one)


def prepare_it(path, s):
    """Pagina italiana: aggiunge PAGE_LANG e hreflang se mancano."""
    if 'hreflang="nl"' not in s:
        s = sub1(s, r'(<link rel="canonical"[^>]*>\n)', lambda m: m.group(1) + hreflang_block(path))
    if 'const PAGE_LANG' not in s:
        if path == 'business-lunch/':
            s = sub1(s, r'(const LINGUE = )', "const PAGE_LANG = 'it';   // lingua della pagina (le copie /nl/ usano 'nl')\n\\1")
        else:
            s = sub1(s, r'(        const SEDE_FISSA = )',
                     "        const PAGE_LANG = 'it';   // lingua della pagina (le copie /nl/ usano 'nl')\n\\1")
    return s


def make_nl(path, s, tr):
    title, desc, og_title = PAGES[path]
    esc = lambda t: html.escape(t, quote=True)
    s = sub1(s, r'<html lang="it"', '<html lang="nl"')
    s = sub1(s, r'<title>.*?</title>', f'<title>{esc(title)}</title>', re.S)
    s = sub1(s, r'(<meta name="description" content=")[^"]*(")', lambda m: m.group(1) + esc(desc) + m.group(2))
    s = re.sub(r'(<meta name="keywords" content=")[^"]*(")', lambda m: m.group(1) + esc(KEYWORDS_NL) + m.group(2), s)
    s = sub1(s, r'(<link rel="canonical" href=")[^"]*(")', lambda m: m.group(1) + f'{BASE}/nl/{path}' + m.group(2))
    s = re.sub(r'(<meta property="og:url" content=")[^"]*(")', lambda m: m.group(1) + f'{BASE}/nl/{path}' + m.group(2), s)
    s = re.sub(r'(<meta property="og:title" content=")[^"]*(")', lambda m: m.group(1) + esc(og_title) + m.group(2), s)
    s = re.sub(r'(<meta name="twitter:title" content=")[^"]*(")', lambda m: m.group(1) + esc(og_title) + m.group(2), s)
    s = re.sub(r'(<meta property="og:description" content=")[^"]*(")', lambda m: m.group(1) + esc(desc) + m.group(2), s)
    s = s.replace('<meta property="og:locale" content="it_IT">', '<meta property="og:locale" content="nl_BE">')
    s = s.replace('<meta property="og:locale:alternate" content="nl_BE">', '<meta property="og:locale:alternate" content="it_IT">')
    s = s.replace("const PAGE_LANG = 'it';", "const PAGE_LANG = 'nl';")
    # collegamenti interni verso le pagine olandesi
    s = s.replace("const SEDE_URL = { tisselt: '/tisselt-willebroek/', wintam: '/wintam-bornem/' };",
                  "const SEDE_URL = { tisselt: '/nl/tisselt-willebroek/', wintam: '/nl/wintam-bornem/' };")
    s = s.replace("'/business-lunch/?lang='", "'/nl/business-lunch/?lang='")
    s = s.replace('href="/business-lunch/?lang=${currentLanguage}"', 'href="/nl/business-lunch/?lang=${currentLanguage}"')
    s = s.replace('href="/business-lunch/"', 'href="/nl/business-lunch/"')
    s = s.replace('<a href="https://artebianca.be/tisselt-willebroek/"', '<a href="https://artebianca.be/nl/tisselt-willebroek/"')
    s = s.replace('<a href="https://artebianca.be/wintam-bornem/"', '<a href="https://artebianca.be/nl/wintam-bornem/"')
    s = translate_static(s, tr)
    return s


def main():
    main_src = (SITE / 'index.html').read_text(encoding='utf-8')
    tr_main = js_object(main_src, 'const translations = {')['nl']
    bl_src = (SITE / 'business-lunch/index.html').read_text(encoding='utf-8')
    tr_bl = js_object(bl_src, 'const TRAD = {')['nl']
    for path in PAGES:
        src_file = SITE / path / 'index.html'
        s = prepare_it(path, src_file.read_text(encoding='utf-8'))
        src_file.write_text(s, encoding='utf-8')
        out = SITE / 'nl' / path / 'index.html'
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(make_nl(path, s, tr_bl if path == 'business-lunch/' else tr_main), encoding='utf-8')
        print('ok', '/nl/' + path)


if __name__ == '__main__':
    main()
