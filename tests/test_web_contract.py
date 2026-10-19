from pathlib import Path
import re
import hashlib


def test_shipped_design_tokens_preserved_and_dom_controls_exist():
    # Preserve the shipped design baseline without retaining the unused starter app.
    design=Path('hubrecover/web/design.css').read_text().strip()
    assert hashlib.sha256(design.encode()).hexdigest()=='71219a5a57e0853646851642c9fff9515a82afd58e1280a0686fd045ca4f92f7'
    html=Path('hubrecover/web/index.html').read_text()
    js=Path('hubrecover/web/app.js').read_text()
    ids=set(re.findall(r'id="([^"]+)"',html))
    referenced=set(re.findall(r"\$\('([^']+)'\)",js))
    dynamic_ids=set(re.findall(r'id="([^"$]+)"',js))
    assert not referenced-ids-dynamic_ids  # generated controls must also have declared IDs
    assert 'data-skin="ops"' in html
    assert '<script src="/assets/app.js" defer>' in html
