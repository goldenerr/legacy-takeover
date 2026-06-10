"""Code quality metrics: size stats, complexity, duplicates, god classes, long methods."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from legacy_takeover.plugins.base import Risk, RiskCategory, RiskSeverity


def compute_stats(repo_path: Path) -> dict:
    """Compute aggregate code statistics: total files, LOC, by extension."""
    stats = {"total_files": 0, "total_loc": 0, "by_extension": {}}
    for f in repo_path.rglob("*"):
        if f.is_file() and ".git" not in f.parts and "target" not in f.parts and "node_modules" not in f.parts:
            try:
                loc = len(f.read_text().splitlines())
                if loc > 0:
                    stats["total_files"] += 1
                    stats["total_loc"] += loc
                    ext = f.suffix or "noext"
                    stats["by_extension"][ext] = stats["by_extension"].get(ext, 0) + loc
            except Exception:
                pass
    return stats


def cyclomatic_complexity(content: str) -> int:
    """Approximate cyclomatic complexity by counting branch keywords.

    Counts: if, for, while, case, catch, when, else if, ternary ?:
    """
    branches = len(re.findall(
        r'\b(if|for|while|case|catch|when|else\s+if|\?\s*:)',
        content,
    ))
    return branches + 1


def comment_ratio(content: str) -> float:
    """Ratio of comment lines to total lines."""
    lines = content.splitlines()
    if not lines:
        return 0.0
    comments = sum(
        1 for l in lines
        if l.strip().startswith("//")
        or l.strip().startswith("#")
        or l.strip().startswith("/*")
        or l.strip().startswith("*")
    )
    return comments / len(lines)


def detect_duplicates(repo_path: Path, min_lines: int = 6) -> list[dict]:
    """Find duplicate code blocks via hash comparison.

    Returns up to 20 duplicate groups.
    """
    hashes: dict[str, list] = {}
    for f in repo_path.rglob("*.java"):
        try:
            lines = f.read_text().splitlines()
            for i in range(len(lines) - min_lines + 1):
                block = "\n".join(lines[i:i + min_lines]).strip()
                if len(block) > 80:
                    h = hashlib.md5(block.encode()).hexdigest()
                    if h not in hashes:
                        hashes[h] = []
                    hashes[h].append(
                        {"file": str(f.relative_to(repo_path)), "line": i + 1}
                    )
        except Exception:
            pass
    return [
        {"files": v, "lines": min_lines, "content_preview": k[:100]}
        for k, v in hashes.items()
        if len(v) > 1
    ][:20]


def find_god_classes(repo_path: Path, threshold: int = 500) -> list[dict]:
    """Find classes exceeding the LOC threshold.

    Returns top 10 largest classes sorted by LOC descending.
    """
    classes = []
    for f in repo_path.rglob("*.java"):
        try:
            loc = len(f.read_text().splitlines())
            if loc > threshold:
                classes.append(
                    {"file": str(f.relative_to(repo_path)), "loc": loc}
                )
        except Exception:
            pass
    return sorted(classes, key=lambda c: c["loc"], reverse=True)[:10]


def find_long_methods(repo_path: Path, threshold: int = 50) -> list[dict]:
    """Find Java methods exceeding the line-count threshold.

    Returns up to 20 methods sorted by body line count descending.
    """
    methods = []
    _method_re = re.compile(
        r'(?:public|private|protected)\s+(?:static\s+)?[\w<>,\[\]]+\s+(\w+)\s*\(',
        re.MULTILINE,
    )

    for f in repo_path.rglob("*.java"):
        try:
            content = f.read_text()
            for m in _method_re.finditer(content):
                body_start = content.find("{", m.end())
                if body_start == -1:
                    continue
                depth = 0
                end = body_start
                for i, ch in enumerate(content[body_start:], body_start):
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            end = i
                            break
                body_lines = content[body_start:end].count("\n")
                if body_lines > threshold:
                    methods.append({
                        "method": m.group(1),
                        "file": str(f.relative_to(repo_path)),
                        "line": content[:m.start()].count("\n") + 1,
                        "loc": body_lines,
                    })
        except Exception:
            pass
    return sorted(methods, key=lambda m: m["loc"], reverse=True)[:20]
