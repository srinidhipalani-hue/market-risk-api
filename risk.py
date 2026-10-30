import numpy as np
import pandas as pd

trading_days = 252
z_95 = 1.645

def daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.pct_change().dropna()

def portfolio_risk(returns: pd.DataFrame, weights: np.ndarray, value: float) -> dict:
    cov = returns.cov()
    corr = returns.corr()

    daily_var = weights @ cov.values @ weights
    daily_vol = np.sqrt(daily_var)
    annual_vol = daily_vol * np.sqrt(trading_days)

    portfolio_returns = returns.values @ weights
    parametric_var = z_95 * daily_vol * value
    historical_var = -np.percentile(portfolio_returns, 5) * value

    marginal = cov.values @ weights
    contribution = weights * marginal / daily_vol
    contribution_pct = contribution / daily_vol

    tickers = list(returns.columns)
    return {
        "annual_volatility": round(float(annual_vol), 4),
        "var_95_parametric": round(float(parametric_var), 2),
        "var_95_historical": round(float(historical_var), 2),
        "risk_contribution": {
            t: round(float(p), 4) for t, p in zip(tickers, contribution_pct)
        },
        "correlation": {
            a: {b: round(float(corr.loc[a, b]), 4) for b in tickers} for a in tickers
        },
    }