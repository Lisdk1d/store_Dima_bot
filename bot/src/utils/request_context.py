"""Per-request correlation id, propagated via a context variable.

Set by the API request-id middleware and read by the audit logger so each
audit entry can be tied back to the HTTP request that produced it.
"""

import contextvars
import uuid

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


def new_request_id() -> str:
    request_id = uuid.uuid4().hex
    _request_id.set(request_id)
    return request_id


def get_request_id() -> str:
    return _request_id.get()
