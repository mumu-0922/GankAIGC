import asyncio
import contextlib
import os
import signal
import socket
import uuid

from app.config import reload_settings, settings
from app.schema import prepare_database
from app.services.task_queue import process_next_queued_session
from app.services.worker_lease import (
    register_worker_lease,
    stop_worker_lease,
    update_worker_lease,
)


def configured_worker_capacity() -> int:
    maximum = max(1, int(settings.TASK_WORKER_MAX_CONCURRENCY or 1))
    configured = int(settings.MAX_CONCURRENT_USERS or 5)
    # Older .env.docker files used 7. Fail safely to the new 3C4G baseline
    # until the administrator explicitly saves one of the supported tiers.
    if configured not in {5, 8, 10}:
        configured = 5
    return max(1, min(maximum, configured))


def build_worker_base_id() -> str:
    prefix = (os.environ.get("TASK_WORKER_ID") or "docker-worker").strip() or "docker-worker"
    # Compose replicas must never share a lease. Always include container host
    # identity even when an operator supplies a human-readable prefix.
    return f"{prefix}-{socket.gethostname()}-{os.getpid()}"[:112]


async def _reload_settings_loop(shutdown_requested: asyncio.Event) -> None:
    while not shutdown_requested.is_set():
        try:
            reload_settings()
        except Exception as exc:
            print(
                f"[WARN] Worker reload settings failed, keep previous config: {exc}",
                flush=True,
            )
        try:
            await asyncio.wait_for(
                shutdown_requested.wait(),
                timeout=max(0.5, float(settings.TASK_WORKER_POLL_INTERVAL or 0.5)),
            )
        except asyncio.TimeoutError:
            pass


async def _worker_slot_loop(
    *,
    base_worker_id: str,
    slot_index: int,
    shutdown_requested: asyncio.Event,
) -> None:
    worker_id = f"{base_worker_id}-slot-{slot_index + 1}"[:128]
    boot_id = uuid.uuid4().hex
    runtime = {"state": "stopped", "session_id": None, "registered": False}
    heartbeat_stop = asyncio.Event()

    async def lease_heartbeat() -> None:
        while not heartbeat_stop.is_set():
            interval = min(
                max(1.0, float(settings.TASK_WORKER_HEARTBEAT_INTERVAL or 1)),
                max(1.0, float(settings.TASK_WORKER_LEASE_TIMEOUT_SECONDS) / 3),
            )
            try:
                await asyncio.wait_for(heartbeat_stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass
            if runtime["registered"]:
                update_worker_lease(
                    worker_id,
                    boot_id,
                    state=str(runtime["state"]),
                    current_session_id=runtime["session_id"],
                )

    heartbeat_task = asyncio.create_task(lease_heartbeat())
    try:
        while not shutdown_requested.is_set():
            enabled = slot_index < configured_worker_capacity()
            if not enabled:
                if runtime["registered"]:
                    runtime.update(state="stopped", session_id=None)
                    stop_worker_lease(worker_id, boot_id)
                    runtime["registered"] = False
                try:
                    await asyncio.wait_for(
                        shutdown_requested.wait(),
                        timeout=max(0.25, float(settings.TASK_WORKER_POLL_INTERVAL or 0.25)),
                    )
                except asyncio.TimeoutError:
                    pass
                continue

            if not runtime["registered"]:
                register_worker_lease(
                    worker_id,
                    boot_id,
                    version=settings.APP_VERSION,
                    capacity=1,
                )
                runtime["registered"] = True
                print(f"GankAIGC worker slot started: {worker_id} boot={boot_id}", flush=True)

            runtime.update(state="idle", session_id=None)
            update_worker_lease(worker_id, boot_id, state="idle")

            def on_claimed(session) -> None:
                runtime["state"] = "draining" if shutdown_requested.is_set() else "busy"
                runtime["session_id"] = session.id
                update_worker_lease(
                    worker_id,
                    boot_id,
                    state=str(runtime["state"]),
                    current_session_id=session.id,
                )

            processed = await process_next_queued_session(
                worker_id,
                on_claimed=on_claimed,
            )
            runtime["session_id"] = None
            if shutdown_requested.is_set():
                break
            runtime["state"] = "idle"
            update_worker_lease(worker_id, boot_id, state="idle")

            if not processed:
                try:
                    await asyncio.wait_for(
                        shutdown_requested.wait(),
                        timeout=max(0.1, float(settings.TASK_WORKER_POLL_INTERVAL or 0.1)),
                    )
                except asyncio.TimeoutError:
                    pass
    finally:
        heartbeat_stop.set()
        heartbeat_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat_task
        if runtime["registered"]:
            stop_worker_lease(worker_id, boot_id)
        print(f"GankAIGC worker slot stopped: {worker_id} boot={boot_id}", flush=True)


async def worker_loop() -> None:
    shutdown_requested = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(signum, shutdown_requested.set)

    base_worker_id = build_worker_base_id()
    max_slots = max(1, int(settings.TASK_WORKER_MAX_CONCURRENCY or 1))
    print(
        f"GankAIGC worker supervisor started: {base_worker_id} "
        f"capacity={configured_worker_capacity()} max={max_slots}",
        flush=True,
    )

    tasks = [
        asyncio.create_task(
            _worker_slot_loop(
                base_worker_id=base_worker_id,
                slot_index=slot_index,
                shutdown_requested=shutdown_requested,
            )
        )
        for slot_index in range(max_slots)
    ]
    reload_task = asyncio.create_task(_reload_settings_loop(shutdown_requested))
    try:
        await asyncio.gather(*tasks)
    finally:
        shutdown_requested.set()
        reload_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await reload_task
        for task in tasks:
            if not task.done():
                task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        print(f"GankAIGC worker supervisor stopped: {base_worker_id}", flush=True)


def main() -> None:
    prepare_database()
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()
