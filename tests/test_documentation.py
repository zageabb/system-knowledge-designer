from pathlib import Path
import re

from services.er_language import parse_er_source

ROOT = Path(__file__).resolve().parents[1]


def test_every_documented_erd_example_parses():
    files = sorted((ROOT / "docs" / "er-language").glob("*.md"))
    includes = {path.stem.replace("-", " "): path.read_text() for path in (ROOT / "docs" / "er-language" / "include-examples").glob("*.erd")}
    examples = []
    for path in files:
        examples.extend((path, source) for source in re.findall(r"```erd\n(.*?)```", path.read_text(), re.DOTALL))
    assert examples, "The syntax reference must contain executable examples."
    for path, source in examples:
        try: parse_er_source(source, includes=includes)
        except Exception as exc: raise AssertionError(f"Invalid documented ER example in {path.name}: {exc}") from exc


def test_manual_and_reference_links_point_to_existing_files():
    for directory in (ROOT / "docs" / "manual", ROOT / "docs" / "er-language"):
        for path in directory.glob("*.md"):
            for target in re.findall(r"\[[^]]+\]\(([^)#]+)(?:#[^)]+)?\)", path.read_text()):
                if "://" not in target:
                    assert (path.parent / target).resolve().exists(), f"Broken documentation link in {path}: {target}"
