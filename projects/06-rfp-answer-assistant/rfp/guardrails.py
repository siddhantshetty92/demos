import re

OVERCLAIMS = [r"\bguarantee[sd]?\b", r"\b100\s?%", r"\bnever\b", r"\bfully compliant\b", r"\bunhackable\b", r"\bzero risk\b"]
MAX_LONG_WORDS = 120


def lint(answer) -> list[str]:
    flags = []
    for pattern in OVERCLAIMS:
        if re.search(pattern, answer.long_answer, re.IGNORECASE):
            flags.append(f"overclaim: /{pattern}/")
    if len(answer.long_answer.split()) > MAX_LONG_WORDS:
        flags.append(f"long answer over {MAX_LONG_WORDS} words")
    if answer.short_answer in {"Yes", "Partial"} and not answer.source_ids:
        flags.append("affirmative answer without a source")
    if answer.confidence == "low":
        flags.append("low confidence")
    return flags
