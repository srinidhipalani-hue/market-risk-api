import logging
import time

from fastapi import FastAPI, HTTPException
import numpy as np
import pandas as pd
import yfinance as yf

from app.cache import clear_risk_cache, get_json, set_json
from app.db import get_conn
from app.risk import daily_returns, portfolio_risk

log = logging.getLogger("uvicorn.error")

app = FastAPI(title = "Market Risk API")

@app.get("/health")
def health():
    return {"status" : "ok", "project": "market-risk-api"}


@app.post("/tickers/{ticker}/refresh")
def refresh_ticker(ticker: str, period: str = "1y"):
    symbol = ticker.upper()
    data = yf.Ticker(symbol).history(period=period)

    if data.empty:
        raise HTTPException(status_code=404, detail = f"No data found for {ticker}")

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
                ON CONFLICT (ticker, date) DO NOTHING
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


@app.get("/prices/{ticker}")
def get_prices(ticker: str, limit: int = 30):
    symbol = ticker.upper()

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT date, close FROM prices
            WHERE ticker = %s
            ORDER BY date DESC
            LIMIT %s
            """,
            (symbol, limit),
        ).fetchall()
 
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No stored prices for {symbol}. Call POST /tickers/{symbol}/refresh first.",
        )
 
    prices = [{"date": d.isoformat(), "close": float(c)} for d, c in reversed(rows)]
    return {"ticker": symbol, "count": len(prices), "prices": prices}

@app.get("/risk")
def get_risk(tickers: str, weights: str | None = None, value: float = 10_000):
    """Portfolio risk from stored prices. Example: ?tickers=XOM,CVX,NVDA,MSFT&weights=0.25,0.25,0.25,0.25"""
    start = time.perf_counter()

    symbols = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if len(symbols) < 2:
        raise HTTPException(status_code=400, detail="Give at least two tickers, separated by commas.")

    if weights:
        try:
            w = np.array([float(x) for x in weights.split(",")])
        except ValueError:
            raise HTTPException(status_code=400, detail="Weights must be numbers, separated by commas.")
        if len(w) != len(symbols):
            raise HTTPException(status_code=400, detail="Give one weight per ticker.")
        if abs(w.sum() - 1) > 1e-6:
            raise HTTPException(status_code=400, detail=f"Weights must add up to 1 (they add up to {w.sum():.4f}).")
    else:
        w = np.full(len(symbols), 1 / len(symbols))

    cache_key = f"risk:{','.join(symbols)}:{','.join(f'{x:.4f}' for x in w)}:{value}"
    cached = get_json(cache_key)
    if cached is not None:
        elapsed = (time.perf_counter() - start) * 1000
        log.info("Cache HIT %s (%.1f ms)", cache_key, elapsed)
        return {**cached, "cache": "hit", "elapsed_ms": round(elapsed, 1)}

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT ticker, date, close FROM prices WHERE ticker = ANY(%s) ORDER BY date",
            (symbols,),
        ).fetchall()

    df = pd.DataFrame(rows, columns=["ticker", "date", "close"])
    missing = sorted(set(symbols) - set(df["ticker"]))
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"No stored prices for {', '.join(missing)}. Refresh them first.",
        )

    prices = df.pivot(index="date", columns="ticker", values="close").astype(float)[symbols].dropna()
    returns = daily_returns(prices)
    if len(returns) < 30:
        raise HTTPException(status_code=400, detail="Need at least 30 overlapping days of prices.")

    response = {
        "tickers": symbols,
        "weights": [round(float(x), 4) for x in w],
        "portfolio_value": value,
        "days_used": len(returns),
        **portfolio_risk(returns, w, value),
    }
    set_json(cache_key, response)

    elapsed = (time.perf_counter() - start) * 1000
    log.info("Cache MISS %s (%.1f ms)", cache_key, elapsed)
    return {**response, "cache": "miss", "elapsed_ms": round(elapsed, 1)}
