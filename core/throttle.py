"""Persistent authentication throttle; raw identifiers are not stored."""

import hashlib
from django.core.cache import cache


def rate_limited(request, scope, limit=10, seconds=900):
    # Never trust client-supplied X-Forwarded-For.
    value = f"{scope}:{request.META.get('REMOTE_ADDR', '')}"
    key = "rate:" + hashlib.sha256(value.encode()).hexdigest()
    if cache.add(key, 1, seconds):
        return False
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, seconds)
        count = 1
    return count > limit
