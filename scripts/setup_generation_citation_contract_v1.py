"""
One-time patch for deterministic and LLM citation metadata contracts.
"""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = (
    PROJECT_ROOT / "src" / "seismosearch" / "generator.py"
)
LLM_GENERATOR_PATH = (
    PROJECT_ROOT / "src" / "seismosearch" / "llm_generator.py"
)

GENERATOR_REPLACEMENTS = [('from __future__ import annotations\n\nfrom typing import Any\n', 'from __future__ import annotations\n\nimport re\nfrom typing import Any\n\n\nEVIDENCE_ID_PATTERN = re.compile(\n    r"\\[(event_\\d{3}|computed_\\d{3}|doc_\\d{3})\\]"\n)\n'), ('def _collect_used_evidence_ids(evidence_pack: dict[str, Any]) -> list[str]:\n    """Collect all evidence IDs available to the deterministic generator."""\n    used_evidence_ids: list[str] = []\n\n    for item in evidence_pack.get("event_evidence", []):\n        evidence_id = item.get("evidence_id")\n        if evidence_id is not None:\n            used_evidence_ids.append(evidence_id)\n\n    for item in evidence_pack.get("computed_evidence", []):\n        evidence_id = item.get("evidence_id")\n        if evidence_id is not None:\n            used_evidence_ids.append(evidence_id)\n\n    for item in evidence_pack.get("doc_evidence", []):\n        evidence_id = item.get("evidence_id")\n        if evidence_id is not None:\n            used_evidence_ids.append(evidence_id)\n\n    return used_evidence_ids\n', 'def _collect_used_evidence_ids(answer: str) -> list[str]:\n    """Collect only evidence IDs that are cited in the final answer."""\n    used_evidence_ids: list[str] = []\n\n    for evidence_id in EVIDENCE_ID_PATTERN.findall(answer):\n        if evidence_id not in used_evidence_ids:\n            used_evidence_ids.append(evidence_id)\n\n    return used_evidence_ids\n'), ('    used_evidence_ids = _collect_used_evidence_ids(evidence_pack)\n', '    used_evidence_ids = _collect_used_evidence_ids(answer)\n')]
LLM_REPLACEMENTS = [('    declared_ids = set(normalized_used_ids)\n    cited_ids = set(\n        EVIDENCE_ID_PATTERN.findall(answer)\n    )\n\n    unknown_declared_ids = declared_ids - available_ids\n', '    declared_ids = set(normalized_used_ids)\n    ordered_cited_ids: list[str] = []\n\n    for evidence_id in EVIDENCE_ID_PATTERN.findall(answer):\n        if evidence_id not in ordered_cited_ids:\n            ordered_cited_ids.append(evidence_id)\n\n    cited_ids = set(ordered_cited_ids)\n\n    unknown_declared_ids = declared_ids - available_ids\n'), ('    if declared_ids != cited_ids:\n        raise LLMGenerationValidationError(\n            "used_evidence_ids must exactly match inline citations"\n        )\n\n    if available_ids and not cited_ids:\n', '    validation_warnings: list[str] = []\n\n    if declared_ids != cited_ids:\n        normalized_used_ids = ordered_cited_ids\n        validation_warnings.append(\n            "used_evidence_ids_normalized_to_inline_citations"\n        )\n\n    if available_ids and not cited_ids:\n'), ('        "used_evidence_ids": normalized_used_ids,\n        "grounding_notes": grounding_notes,\n    }\n', '        "used_evidence_ids": normalized_used_ids,\n        "grounding_notes": grounding_notes,\n        "validation_warnings": validation_warnings,\n    }\n'), ('            "warnings": evidence_pack.get(\n                "warnings",\n                [],\n            ),\n', '            "warnings": (\n                list(evidence_pack.get("warnings", []))\n                + validated_output.get(\n                    "validation_warnings",\n                    [],\n                )\n            ),\n')]


def read_preserving_newlines(path: Path) -> tuple[str, str]:
    """Read UTF-8 text and detect its newline convention."""
    with path.open("r", encoding="utf-8", newline="") as file:
        text = file.read()

    newline = "\r\n" if "\r\n" in text else "\n"
    return text, newline


def normalize_block(block: str, newline: str) -> str:
    """Adapt an LF-authored code block to the target file."""
    return block.replace("\n", newline)


def apply_replacements(
    path: Path,
    replacements: list[tuple[str, str]],
    already_applied_marker: str,
) -> None:
    """Apply exact replacements and fail without partial ambiguity."""
    text, newline = read_preserving_newlines(path)

    if already_applied_marker in text:
        raise RuntimeError(f"Patch already applied: {path}")

    for index, (old, new) in enumerate(replacements, start=1):
        old_value = normalize_block(old, newline)
        new_value = normalize_block(new, newline)
        count = text.count(old_value)

        if count != 1:
            raise RuntimeError(
                f"{path.name} replacement {index}: "
                f"expected one match, found {count}"
            )

        text = text.replace(old_value, new_value, 1)

    with path.open("w", encoding="utf-8", newline="") as file:
        file.write(text)


def main() -> None:
    """Apply the citation contract patch once."""
    apply_replacements(
        GENERATOR_PATH,
        GENERATOR_REPLACEMENTS,
        "Collect only evidence IDs that are cited",
    )
    apply_replacements(
        LLM_GENERATOR_PATH,
        LLM_REPLACEMENTS,
        "used_evidence_ids_normalized_to_inline_citations",
    )

    print("[PASS] generation citation contract patch applied")
    print(f"  updated: {GENERATOR_PATH}")
    print(f"  updated: {LLM_GENERATOR_PATH}")


if __name__ == "__main__":
    main()
