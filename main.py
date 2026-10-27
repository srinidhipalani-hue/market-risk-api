from fastapi import FastAPI, HTTPException
import yfinance as yf

from db import get_conn

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

    return {"ticker": symbol, "downloaded": len(rows), "new_rows": after - before}


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
