from datetime import UTC, datetime


def utcnow() -> datetime:
    """返回数据库兼容的 UTC naive 时间。"""
    return datetime.now(UTC).replace(tzinfo=None)
