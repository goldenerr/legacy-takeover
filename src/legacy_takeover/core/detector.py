"""Language detection: dispatch repos to matching analyzer plugins."""
from __future__ import annotations
from pathlib import Path
from legacy_takeover.plugins.base import LanguageAnalyzer


def detect_languages(
    repo_path: Path,
    available_plugins: list[LanguageAnalyzer],
    threshold: float = 0.3,
) -> list[LanguageAnalyzer]:
    matched: list[LanguageAnalyzer] = []
    for plugin in available_plugins:
        confidence = plugin.detect()
        if confidence > threshold:
            matched.append(plugin)
    return matched
