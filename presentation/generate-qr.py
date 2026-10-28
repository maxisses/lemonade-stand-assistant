#!/usr/bin/env python3
"""Regenerate the local audience QR after changing the public URL in config.js."""
import json
from pathlib import Path
import segno

root = Path(__file__).resolve().parent
source = (root / 'config.js').read_text()
config = json.loads(source.split('window.LEMONADE_DECK =', 1)[1].strip().removesuffix(';'))
url = config['links']['audience']
if not url.startswith('https://') or any(c.isspace() for c in url):
    raise SystemExit('The audience URL must be an HTTPS URL without whitespace.')
qr = segno.make(url, error='m', micro=False, boost_error=False)
qr.save(root / 'assets' / 'audience-qr.svg', scale=10, border=4, dark='#151515', light='#ffffff', xmldecl=False)
(root / 'assets' / 'audience-qr.json').write_text(json.dumps({'url': url, 'errorCorrection': 'M', 'version': qr.version}, indent=2) + '\n')
print(f'Generated local audience QR (version {qr.version}, error correction M).')
