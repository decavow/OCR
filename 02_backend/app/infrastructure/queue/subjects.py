# Subject patterns, DLQ subjects


def get_subject(method: str, tier: int) -> str:
    """Get subject for job routing.

    Format: ocr.{method}.tier{tier}
    Example: ocr.ocr_text_raw.tier0
    """
    return f"ocr.{method}.tier{tier}"


def get_dlq_subject(method: str, tier: int) -> str:
    """Get DLQ subject for dead letter jobs.

    Format: dlq.{method}.tier{tier}
    """
    return f"dlq.{method}.tier{tier}"


def parse_subject(subject: str) -> dict:
    """Parse subject into components."""
    parts = subject.split(".")
    if len(parts) == 3 and parts[0] == "ocr":
        tier_str = parts[2].replace("tier", "")
        return {
            "method": parts[1],
            "tier": int(tier_str),
        }
    return {}
