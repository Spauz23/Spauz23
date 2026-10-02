"""Strategie: ognuna restituisce la posizione desiderata (0 = flat, 1 = long) a fine candela."""
import numpy as np
import pandas as pd


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def hold_until(entry: pd.Series, exit_: pd.Series) -> pd.Series:
    """1 da un segnale di entrata fino al primo segnale di uscita."""
    state = np.where(entry, 1.0, np.where(exit_, 0.0, np.nan))
    return pd.Series(state, index=entry.index).ffill().fillna(0)


def buy_hold(df):
    return pd.Series(1.0, index=df.index)


def ema_cross(df, fast=20, slow=100):
    """Trend following: long finché la media veloce è sopra la lenta."""
    return (ema(df.close, fast) > ema(df.close, slow)).astype(float)


def donchian(df, entry=55, exit=20):
    """Breakout 'Turtle': compra sul massimo di N candele, esce sul minimo di M."""
    hi = df.high.rolling(entry).max().shift(1)
    lo = df.low.rolling(exit).min().shift(1)
    return hold_until(df.close > hi, df.close < lo)


def rsi_dip(df, n=14, buy=30, sell=60, trend=200):
    """Mean reversion: compra l'ipervenduto solo se il trend di fondo è rialzista."""
    r, t = rsi(df.close, n), ema(df.close, trend)
    return hold_until((r < buy) & (df.close > t), (r > sell) | (df.close < t * 0.95))


STRATEGIES = {
    "ema_cross": (ema_cross, {"fast": [10, 20, 50], "slow": [50, 100, 200]}),
    "donchian": (donchian, {"entry": [20, 55, 100], "exit": [10, 20, 50]}),
    "rsi_dip": (rsi_dip, {"buy": [25, 30, 35], "sell": [55, 60, 70], "trend": [100, 200]}),
}
