"""Tiny in-memory sliding-window rate limiter (per user, per action).
Good enough for a single-process demo; swap for Redis if the API is scaled out."""
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, status

from app.dependencies import get_current_user

_hits: dict = defaultdict(deque)


def reset() -> None:
    _hits.clear()


def limit(action: str, max_calls: int, per_seconds: int):
    async def dependency(current_user=Depends(get_current_user)):
        now = time.monotonic()
        window = _hits[(action, current_user.id)]
        while window and now - window[0] > per_seconds:
            window.popleft()
        if len(window) >= max_calls:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts. Please wait a few minutes and try again.",
            )
        window.append(now)
        return current_user

    return dependency
