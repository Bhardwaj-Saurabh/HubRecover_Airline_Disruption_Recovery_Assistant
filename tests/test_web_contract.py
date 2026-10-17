from pathlib import Path
import re


def test_shipped_design_tokens_preserved_and_dom_controls_exist():
    source=Path('starter/index.html').read_text()
    block=source[source.index('/* PF-DESIGN-START'):source.index('/* PF-DESIGN-END */')+len('/* PF-DESIGN-END */')]
    assert Path('hubrecover/web/design.css').read_text().strip()==block
    html=Path('hubrecover/web/index.html').read_text()
    js=Path('hubrecover/web/app.js').read_text()
    ids=set(re.findall(r'id="([^"]+)"',html))
    referenced=set(re.findall(r"\$\('([^']+)'\)",js))
    assert referenced-ids=={'execute'}  # this button is rendered only after approval
    assert 'data-skin="ops"' in html
    assert '<script src="/assets/app.js" defer>' in html
