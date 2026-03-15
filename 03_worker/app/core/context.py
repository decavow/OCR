# Shared context variables (avoids circular imports)

import contextvars

job_id_ctx = contextvars.ContextVar("job_id", default=None)
