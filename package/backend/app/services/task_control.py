"""Control-flow signals shared by durable background task transports."""
from __future__ import annotations


class TaskSuspended(RuntimeError):
    """Pause a durable task without treating it as failed.

    The worker must release its processing slot. External completion code is
    responsible for moving the persisted session back to ``queued``.
    """

    def __init__(self, message: str, *, reason: str, external_job_id: str | None = None):
        super().__init__(message)
        self.reason = reason
        self.external_job_id = external_job_id
