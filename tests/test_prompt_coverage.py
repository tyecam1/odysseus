"""Guard: no pipeline may hold a large inline system prompt; they live in prompts/library (see src/prompt_library.py)."""
import ast
import re
from pathlib import Path

from src import prompt_library as lib

ROOT = Path(__file__).resolve().parent.parent
NAME = re.compile(r"(SYSTEM|PROMPT)")


def test_no_large_inline_prompt_constants_in_src():
    offenders = []
    for f in sorted((ROOT / "src").rglob("*.py")):
        for node in ast.parse(f.read_text(encoding="utf-8")).body:
            if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                    and NAME.search(node.targets[0].id) and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str) and len(node.value.value) > 200):
                offenders.append(f"{f.relative_to(ROOT)}:{node.targets[0].id}")
    assert not offenders, f"move to prompts/library: {offenders}"


def test_library_is_structurally_healthy():
    assert lib.lint() == []
