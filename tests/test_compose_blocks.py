"""The install snippets people copy must be the hardened compose file."""
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def _compose():
    lines = (ROOT / "docker-compose.yml").read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("#")).strip()

def _blocks(text):
    return [html.unescape(b).strip() for b in re.findall(r"<pre><code>(services:.*?)</code></pre>", text, re.S)]

def test_home_page_compose_block_is_the_compose_file():
    blocks = _blocks((ROOT / "docs" / "index.html").read_text(encoding="utf-8"))
    assert blocks == [_compose()]

def test_documentation_compose_block_is_the_compose_file():
    blocks = _blocks((ROOT / "docs" / "documentation.html").read_text(encoding="utf-8"))
    assert blocks == [_compose()]

def test_readme_compose_block_is_the_compose_file():
    blocks = re.findall(r"```yaml\n(services:.*?)```", (ROOT / "README.md").read_text(encoding="utf-8"), re.S)
    assert [b.strip() for b in blocks] == [_compose()]
