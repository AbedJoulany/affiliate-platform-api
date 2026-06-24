import asyncio
from typing import TypeVar

T = TypeVar("T")


def run_async(coro) -> T:
    return asyncio.run(coro)
