"""Creates book ids in the catalog service.

This is currently a mock: the real catalog service assigns the id and is called
without a request body. Replace the body of ``create_book`` with an ``httpx``
call that returns the id from the response once that endpoint exists.
"""
import random


async def create_book() -> int:
    """Reserve a numeric id for a new book.

    The real call will be an HTTP request to the catalog service that takes no
    payload and responds with the freshly created id.
    """
    return random.randint(100000, 999999)
