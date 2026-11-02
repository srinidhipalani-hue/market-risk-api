import os

import yfinance as yf
from redis import Redis
from rq import Queue

from app.cache import clear_risk_cache
from app.db import get_conn

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

redis_conn = Redis.from_url(REDIS_URL)
refresh_queue = Queue("refresh", connection=redis_conn)

def refresh_job(symbol: str, period: str) -> dict:
    data = yf.Ticker(symbol).history(period=period)
    if data.empty:
        raise ValueError(f"No data found for {symbol}")

    rows = [(symbol, date.date(), float(close)) for date, close in data["Close"].items()]

    with get_conn() as conn:
        before = conn.execute(
            "SELECT COUNT(*) FROM prices WHERE ticker = %s", (symbol,)
        ).fetchone()[0]

        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO prices (ticker, date, close)
                VALUES (%s, %s, %s)
                ON CONFLICT (ticker, date) DO UPDATE SET close = EXCLUDED.close
                """,
                rows,
            )

        after = conn.execute(
            "SELECT COUNT(*) FROM prices WHERE ticker = %s", (symbol,)
        ).fetchone()[0]

    cleared = clear_risk_cache()
    return {
        "ticker": symbol,
        "downloaded": len(rows),
        "new_rows": after - before,
        "cache_entries_cleared": cleared,
    }
