import asyncio
import httpx


async def get_with_retry(
    url: str,
    headers: dict,
    params: dict | None = None,
    timeout: int = 30,
    max_retries: int = 3,
) -> httpx.Response:
    """GET request that retries on 429 with progressive backoff.

    On a 429 response, waits for the Retry-After header value if present,
    otherwise uses an exponential backoff: 10s, 30s, 60s.
    """
    backoff = [10, 30, 60]

    for attempt in range(max_retries + 1):
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, headers=headers, params=params)

        if resp.status_code != 429:
            return resp

        if attempt == max_retries:
            resp.raise_for_status()

        # Honour Retry-After if the server sends it, else use backoff
        wait = backoff[min(attempt, len(backoff) - 1)]
        try:
            wait = max(wait, int(resp.headers.get("retry-after", wait)))
        except (ValueError, TypeError):
            pass

        await asyncio.sleep(wait)

    resp.raise_for_status()  # unreachable but satisfies type checkers
    return resp  # type: ignore[return-value]
