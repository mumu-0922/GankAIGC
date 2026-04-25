from collections import defaultdict, deque
from datetime import datetime, timedelta


class SlidingWindowLimiter:
    def __init__(self):
        self._hits = defaultdict(deque)

    def check(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=window_seconds)
        bucket = self._hits[key]
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True
