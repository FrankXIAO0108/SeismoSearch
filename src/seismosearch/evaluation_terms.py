"""
Bilingual required-term matching for SeismoSearch evaluation contracts.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable


TERM_MATCH_CONTRACT_VERSION = "bilingual_terms_1.0.0"

TERM_EQUIVALENCE_GROUPS: tuple[tuple[str, ...], ...] = (
    ("深度", "震源深度", "depth", "focal depth", "hypocentral depth"),
    ("距离", "震中距", "距震中", "distance", "epicentral distance", "source distance"),
    ("地质", "局地地质", "local geology", "geology"),
    ("建筑", "建筑物", "建成环境", "building", "buildings", "built environment"),
    ("烈度", "mmi", "intensity", "modified mercalli intensity"),
    ("震级", "magnitude"),
)


def normalize_evaluation_text(value: object) -> str:
    """Normalize Unicode, case, and whitespace for evaluation matching."""
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    return " ".join(text.split())


def _build_alias_index() -> dict[str, tuple[str, ...]]:
    """Map every configured alias to its complete equivalence group."""
    index: dict[str, tuple[str, ...]] = {}

    for group in TERM_EQUIVALENCE_GROUPS:
        normalized_group = tuple(
            dict.fromkeys(
                normalize_evaluation_text(alias)
                for alias in group
                if normalize_evaluation_text(alias)
            )
        )

        for alias in normalized_group:
            index[alias] = normalized_group

    return index


TERM_ALIAS_INDEX = _build_alias_index()


def get_equivalent_terms(required_term: object) -> tuple[str, ...]:
    """Return aliases for one required term, or the normalized term itself."""
    normalized = normalize_evaluation_text(required_term)

    if not normalized:
        return ()

    return TERM_ALIAS_INDEX.get(normalized, (normalized,))


def _contains_alias(normalized_text: str, normalized_alias: str) -> bool:
    """
    Match one normalized alias.

    Pure ASCII identifiers use token boundaries so ``depth`` does not
    accidentally match ``depthError``.
    """
    if re.fullmatch(r"[a-z0-9_]+", normalized_alias):
        pattern = (
            r"(?<![a-z0-9_])"
            + re.escape(normalized_alias)
            + r"(?![a-z0-9_])"
        )
        return re.search(pattern, normalized_text) is not None

    return normalized_alias in normalized_text


def contains_required_term(text: object, required_term: object) -> bool:
    """Check one required term using configured bilingual equivalence."""
    normalized_text = normalize_evaluation_text(text)

    return any(
        _contains_alias(normalized_text, alias)
        for alias in get_equivalent_terms(required_term)
    )


def find_missing_required_terms(
    text: object,
    required_terms: Iterable[object],
) -> list[str]:
    """Return original required terms that are not covered by the text."""
    missing: list[str] = []

    for term in required_terms:
        original = str(term)

        if not original:
            continue

        if not contains_required_term(text, original):
            missing.append(original)

    return missing


def check_required_terms(
    text: object,
    required_terms: Iterable[object],
) -> bool:
    """Return True when every required term is covered."""
    return not find_missing_required_terms(text, required_terms)
