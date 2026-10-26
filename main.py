from fastapi import FastAPI, HTTPException
import yfinance as yf

app = FastAPI(title = "Market Risk API")

@app.get("/health")
def health():
    return {"status" : "ok", "project": "market-risk-api"}


@app.get("/prices/{ticker}")
def get_prices(ticker: str, period: str = "1mo"):
    data = yf.Ticker(ticker.upper()).history(period=period)

    if data.empty:
        raise HTTPException(status_code=404, detail = f"No data found for {ticker}")

    prices = [
        {"date": date.strftime("%Y-%m-%d"), "close": round(float(close), 2)}
        for date, close in data["Close"].items()
    ]

    return {"ticket": ticker.upper(), "period": period, "prices": prices}
