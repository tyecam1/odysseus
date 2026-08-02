"""Strict, dependency-free YAML subset used by graph source adapters.

The project does not otherwise depend on PyYAML. This parser accepts the data
shapes used by capability sources: indentation-based mappings/lists, quoted or
plain scalars, booleans/null/numbers, and JSON-style inline collections. YAML
features that can execute or alias data (tags, anchors, aliases) are rejected.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..errors import AdapterError


_NUMBER = re.compile(r"^-?(?:0|[1-9]\d*)(?:\.\d+)?$")


def _scalar(value: str, label: str) -> Any:
    value = value.strip()
    if not value:
        return None
    if value.startswith(("&", "*", "!")):
        raise AdapterError(f"{label}: YAML anchors, aliases, and tags are not supported")
    if value[0] in "[{":
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            if value.startswith("[") and value.endswith("]"):
                body = value[1:-1].strip()
                if not body:
                    return []
                items: list[str] = []
                quote: str | None = None
                start = 0
                for index, char in enumerate(body):
                    if char in "\"'":
                        quote = None if quote == char else (char if quote is None else quote)
                    elif char == "," and quote is None:
                        items.append(body[start:index].strip())
                        start = index + 1
                items.append(body[start:].strip())
                if any(not item for item in items):
                    raise AdapterError(f"{label}: malformed inline list") from exc
                return [_scalar(item, label) for item in items]
            raise AdapterError(f"{label}: malformed inline collection: {exc}") from exc
    if value[0] in "\"'":
        if len(value) < 2 or value[-1] != value[0]:
            raise AdapterError(f"{label}: unterminated quoted scalar")
        if value[0] == '"':
            try:
                return json.loads(value)
            except json.JSONDecodeError as exc:
                raise AdapterError(f"{label}: malformed quoted scalar: {exc}") from exc
        return value[1:-1].replace("''", "'")
    lowered = value.lower()
    if lowered in {"null", "~"}:
        return None
    if lowered in {"true", "false"}:
        return lowered == "true"
    if _NUMBER.match(value):
        return float(value) if "." in value else int(value)
    return value


def _strip_comment(value: str) -> str:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote == '"':
            escaped = True
        elif char in "\"'":
            quote = None if quote == char else (char if quote is None else quote)
        elif char == "#" and quote is None and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()
    return value.rstrip()


def _block_scalar(parts: list[str], style: str, chomp: str) -> str:
    """Construct the supported YAML block-scalar value, including chomping."""
    if style == "|":
        value = "\n".join(parts)
    else:
        paragraphs: list[str] = []
        current: list[str] = []
        for part in parts:
            if part:
                current.append(part)
            elif current:
                paragraphs.append(" ".join(current))
                current = []
        if current:
            paragraphs.append(" ".join(current))
        value = "\n".join(paragraphs)
    if parts:
        value += "\n"
    if chomp == "-":
        return value.rstrip("\n")
    if chomp == "+":
        return value
    return value.rstrip("\n") + ("\n" if value else "")


def parse_yaml_subset(text: str, label: str) -> Any:
    source_lines = text.splitlines()
    expanded_lines: list[str] = []
    index = 0
    block_pattern = re.compile(r"^( *)([^:#][^:]*):\s*([>|])([-+]?)\s*(?:#.*)?$")
    while index < len(source_lines):
        raw = source_lines[index]
        match = block_pattern.match(raw)
        if not match:
            expanded_lines.append(raw)
            index += 1
            continue
        prefix, key, style, chomp = match.groups()
        base_indent = len(prefix)
        index += 1
        collected: list[str] = []
        while index < len(source_lines):
            child = source_lines[index]
            child_indent = len(child) - len(child.lstrip(" "))
            if child.strip() and child_indent <= base_indent:
                break
            collected.append(child)
            index += 1
        nonempty_indents = [
            len(line) - len(line.lstrip(" ")) for line in collected if line.strip()
        ]
        trim = min(nonempty_indents) if nonempty_indents else base_indent + 1
        parts = [line[trim:] if line.strip() else "" for line in collected]
        block_value = _block_scalar(parts, style, chomp)
        expanded_lines.append(f"{prefix}{key}: {json.dumps(block_value, ensure_ascii=False)}")

    raw_lines: list[tuple[int, str, int]] = []
    for number, raw in enumerate(expanded_lines, 1):
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise AdapterError(f"{label}:{number}: tabs are not valid indentation")
        content = _strip_comment(raw.lstrip(" "))
        if not content:
            continue
        if content in {"---", "..."}:
            continue
        if content.startswith(("|", ">")):
            raise AdapterError(f"{label}:{number}: block scalars are not supported")
        raw_lines.append((len(raw) - len(raw.lstrip(" ")), content, number))
    if not raw_lines:
        raise AdapterError(f"{label}: empty YAML document")

    def parse_block(start: int, indent: int) -> tuple[Any, int]:
        if start >= len(raw_lines) or raw_lines[start][0] != indent:
            raise AdapterError(f"{label}: invalid indentation")
        is_list = raw_lines[start][1] == "-" or raw_lines[start][1].startswith("- ")
        container: Any = [] if is_list else {}
        index = start
        while index < len(raw_lines):
            current_indent, content, number = raw_lines[index]
            if current_indent < indent:
                break
            if current_indent > indent:
                raise AdapterError(f"{label}:{number}: unexpected indentation")
            item_is_list = content == "-" or content.startswith("- ")
            if item_is_list != is_list:
                raise AdapterError(f"{label}:{number}: cannot mix mapping and list entries")
            if is_list:
                body = content[1:].strip()
                if not body:
                    if index + 1 >= len(raw_lines) or raw_lines[index + 1][0] <= indent:
                        raise AdapterError(f"{label}:{number}: empty list item")
                    child, index = parse_block(index + 1, raw_lines[index + 1][0])
                    container.append(child)
                    continue
                if (
                    re.match(r"^[^:]+:(?:\s|$)", body)
                    and not body.startswith(("\"", "'", "[", "{"))
                ):
                    key, rest = body.split(":", 1)
                    key = key.strip()
                    if not key:
                        raise AdapterError(f"{label}:{number}: empty mapping key")
                    item: dict[str, Any] = {key: _scalar(rest, f"{label}:{number}")}
                    index += 1
                    if index < len(raw_lines) and raw_lines[index][0] > indent:
                        child_indent = raw_lines[index][0]
                        child, index = parse_block(index, child_indent)
                        if not isinstance(child, dict):
                            if item[key] is None:
                                item[key] = child
                            else:
                                raise AdapterError(f"{label}:{number}: invalid list mapping continuation")
                        else:
                            if item[key] is None and len(child) == 1 and key in child:
                                item[key] = child[key]
                            else:
                                duplicates = set(item).intersection(child)
                                if duplicates:
                                    raise AdapterError(f"{label}:{number}: duplicate key {sorted(duplicates)[0]!r}")
                                item.update(child)
                    container.append(item)
                    continue
                container.append(_scalar(body, f"{label}:{number}"))
                index += 1
                continue

            if ":" not in content:
                raise AdapterError(f"{label}:{number}: expected 'key: value'")
            key, rest = content.split(":", 1)
            key = key.strip()
            if not key:
                raise AdapterError(f"{label}:{number}: empty mapping key")
            if key in container:
                raise AdapterError(f"{label}:{number}: duplicate key {key!r}")
            rest = rest.strip()
            index += 1
            if rest:
                container[key] = _scalar(rest, f"{label}:{number}")
            elif index < len(raw_lines) and raw_lines[index][0] > indent:
                container[key], index = parse_block(index, raw_lines[index][0])
            else:
                container[key] = None
        return container, index

    value, end = parse_block(0, raw_lines[0][0])
    if end != len(raw_lines):
        _, _, number = raw_lines[end]
        raise AdapterError(f"{label}:{number}: trailing malformed content")
    return value


def split_frontmatter(text: str, label: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise AdapterError(f"{label}: YAML frontmatter is required")
    try:
        closing = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration as exc:
        raise AdapterError(f"{label}: unterminated YAML frontmatter") from exc
    value = parse_yaml_subset("\n".join(lines[1:closing]), f"{label} frontmatter")
    if not isinstance(value, dict):
        raise AdapterError(f"{label}: frontmatter must be a mapping")
    return value, "\n".join(lines[closing + 1 :])
