# generate_object_key(), parse_object_key()
#
# Path format (human-readable, traceable):
#   uploads:  {date}/{HHmmss}_{service_type}_{user_short8}/{original_name}
#   results:  {date}/{HHmmss}_{service_type}_{user_short8}/{basename}_result.{fmt}
#
# Example:
#   uploads/2026-03-15/221542_ocr-paddle-vl_4d1df76a/invoice_scan.png
#   results/2026-03-15/221542_ocr-paddle-vl_4d1df76a/invoice_scan_result.txt

import os
from datetime import datetime, timezone, timedelta

# Vietnam timezone (UTC+7, no DST)
_VN_TZ = timezone(timedelta(hours=7))


def _sanitize_filename(name: str) -> str:
    """Remove path separators and limit length for safe object keys."""
    name = os.path.basename(name)
    name = name.replace("/", "_").replace("\\", "_")
    if len(name) > 200:
        base, ext = os.path.splitext(name)
        name = base[:200 - len(ext)] + ext
    return name


def generate_object_key(
    user_id: str,
    request_id: str,
    file_id: str,
    original_name: str,
    method: str = "ocr",
    created_at: datetime | None = None,
    service_type_id: str = "",
) -> str:
    """Generate object key for MinIO uploads bucket.

    Format: {YYYY-MM-DD}/{HHmmss}_{service_type}_{user_short8}/{original_name}

    Example: 2026-03-15/221542_ocr-paddle-vl_4d1df76a/invoice.png
    """
    ts = created_at or datetime.now(timezone.utc)
    ts_vn = ts.astimezone(_VN_TZ)
    date_part = ts_vn.strftime("%Y-%m-%d")
    time_part = ts_vn.strftime("%H%M%S")
    user_short = user_id[:8]
    safe_name = _sanitize_filename(original_name)
    label = service_type_id or method

    return f"{date_part}/{time_part}_{label}_{user_short}/{safe_name}"


def generate_result_key(
    user_id: str,
    request_id: str,
    file_id: str,
    output_format: str,
    original_name: str = "",
    method: str = "ocr",
    created_at: datetime | None = None,
    service_type_id: str = "",
) -> str:
    """Generate object key for MinIO results bucket.

    Format: {YYYY-MM-DD}/{HHmmss}_{service_type}_{user_short8}/{basename}_result.{fmt}

    Example: 2026-03-15/221542_ocr-paddle-vl_4d1df76a/invoice_result.txt
    """
    ts = created_at or datetime.now(timezone.utc)
    ts_vn = ts.astimezone(_VN_TZ)
    date_part = ts_vn.strftime("%Y-%m-%d")
    time_part = ts_vn.strftime("%H%M%S")
    user_short = user_id[:8]
    label = service_type_id or method

    if original_name:
        base = os.path.splitext(_sanitize_filename(original_name))[0]
    else:
        base = file_id[:8]

    return f"{date_part}/{time_part}_{label}_{user_short}/{base}_result.{output_format}"


def parse_object_key(object_key: str) -> dict:
    """Parse object key into components.

    Supports both new format (date/time_method_user/file)
    and legacy format (user_id/request_id/file_id/file).
    """
    parts = object_key.split("/")
    if len(parts) >= 3:
        return {
            "date": parts[0],
            "folder": parts[1],
            "filename": "/".join(parts[2:]),
        }
    return {}
