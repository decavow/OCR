# generate_object_key(), parse_object_key()

import uuid
from datetime import datetime


def generate_object_key(
    user_id: str,
    request_id: str,
    file_id: str,
    original_name: str,
) -> str:
    """Generate object key for MinIO storage.

    Format: {user_id}/{request_id}/{file_id}/{original_name}
    """
    return f"{user_id}/{request_id}/{file_id}/{original_name}"


def generate_result_key(
    user_id: str,
    request_id: str,
    file_id: str,
    output_format: str,
) -> str:
    """Generate object key for result file.

    Format: {user_id}/{request_id}/{file_id}/result.{format}
    """
    return f"{user_id}/{request_id}/{file_id}/result.{output_format}"


def parse_object_key(object_key: str) -> dict:
    """Parse object key into components."""
    parts = object_key.split("/")
    if len(parts) >= 4:
        return {
            "user_id": parts[0],
            "request_id": parts[1],
            "file_id": parts[2],
            "filename": "/".join(parts[3:]),
        }
    return {}
