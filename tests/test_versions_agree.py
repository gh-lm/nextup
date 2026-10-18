"""The version is written in several places by hand; this stops them drifting apart."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def _read(name):
    return (ROOT / name).read_text(encoding="utf-8")

def test_every_place_that_names_the_version_agrees():
    version = _read("VERSION").strip()

    assert re.search(r"badge/version-%s-" % re.escape(version), _read("README.md"))
    assert f"| {version} (latest) | Yes |" in _read("SECURITY.md")

    changelog = re.search(r"^## \[([\d.]+)\]", _read("CHANGELOG.md"), re.M).group(1)
    assert changelog == version, "the newest CHANGELOG entry is not the current version"

    first = re.search(r'<h2 id="v([\d.]+)"', _read("docs/whats-new.html")).group(1)
    assert first == version, "the newest entry on the What's new page is not the current version"
    assert f'<a href="#v{version}">{version}</a>' in _read("docs/whats-new.html")

def test_the_readme_does_not_quote_a_test_count_that_can_go_stale():
    assert not re.search(r"\d+ tests", _read("README.md"))
