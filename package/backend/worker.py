import asyncio
import os
import socket

from app.config import reload_settings, settings
from app.database import check_database_connection, init_db
from app.services.task_queue import process_next_queued_session


async def worker_loop() -> None:
    worker_id = os.environ.get("TASK_WORKER_ID") or f"{socket.gethostname()}-{os.getpid()}"
    print(f"GankAIGC worker started: {worker_id}", flush=True)

    while True:
        try:
            reload_settings()
        except Exception as exc:
            print(f"[WARN] Worker reload settings failed, keep previous config: {exc}", flush=True)

        processed = await process_next_queued_session(worker_id)
        if not processed:
            await asyncio.sleep(settings.TASK_WORKER_POLL_INTERVAL)


def main() -> None:
    check_database_connection()
    init_db()
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()
