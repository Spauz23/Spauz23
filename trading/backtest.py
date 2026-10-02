"""Backtester vettoriale con commissioni, slippage, leva e liquidazione.

Regole di esecuzione (prudenti):
- il segnale si calcola a chiusura candela e si opera alla candela successiva (niente "sbirciate" nel futuro);
- commissione + slippage pagati su ogni cambio di posizione;
- con leva: funding dei perpetual e liquidazione se il minimo della candela brucia il margine.
"""
from dataclasses import dataclass
from itertools import product

import numpy as np
import pandas as pd

FEE = 0.001        # 0,10% per lato (Binance spot, tier base)
SLIPPAGE = 0.0005  # 0,05% per lato
FUNDING_8H = 0.0001  # 0,01% ogni 8h sul nozionale (solo con leva)


@dataclass
class Result:
    equity: pd.Series
    trades: int
    liquidated: bool
    liq_date: pd.Timestamp | None = None

    def stats(self) -> dict:
        eq = self.equity
        rets = eq.pct_change().fillna(0)
        bars_year = pd.Timedelta(days=365) / (eq.index[1] - eq.index[0])
        years = (eq.index[-1] - eq.index[0]).days / 365
        dd = eq / eq.cummax() - 1
        cagr = eq.iloc[-1] ** (1 / years) - 1 if eq.iloc[-1] > 0 else -1.0
        sharpe = rets.mean() / rets.std() * np.sqrt(bars_year) if rets.std() > 0 else 0
        return {
            "rendimento %": round((eq.iloc[-1] - 1) * 100, 1),
            "CAGR %": round(cagr * 100, 1),
            "max drawdown %": round(dd.min() * 100, 1),
            "Sharpe": "n/d" if self.liquidated else round(sharpe, 2),
            "trade": self.trades,
            "liquidato": f"SÌ ({self.liq_date:%d/%m/%Y})" if self.liquidated else "no",
        }


def run(df: pd.DataFrame, position: pd.Series, leverage: float = 1.0) -> Result:
    pos = position.shift(1).fillna(0) * leverage  # si opera alla candela dopo il segnale
    prev = df.close.shift(1)
    ret = (df.close / prev - 1).fillna(0)
    worst = (df.low / prev - 1).fillna(0)  # peggior movimento intra-candela per un long

    turnover = pos.diff().abs().fillna(pos.abs())
    hours = (df.index[1] - df.index[0]) / pd.Timedelta(hours=1)
    funding = pos.abs() * FUNDING_8H * hours / 8 if leverage > 1 else 0
    growth = 1 + pos * ret - turnover * (FEE + SLIPPAGE) - funding

    liquidated, liq_date = False, None
    if leverage > 1:
        hit = (1 + pos * worst) <= 0.005 * leverage  # margine di mantenimento ~0,5%
        if hit.any():
            liquidated, liq_date = True, hit.idxmax()
            growth[liq_date:] = 0  # conto azzerato alla prima liquidazione

    equity = growth.clip(lower=0).cumprod()
    trades = int((position.diff() > 0).sum())
    return Result(equity, trades, liquidated, liq_date)


def optimize(df, fn, grid: dict, min_trades: int = 10):
    """Prova tutte le combinazioni e tiene quella con lo Sharpe migliore."""
    best, best_params = None, None
    for values in product(*grid.values()):
        params = dict(zip(grid, values))
        if params.get("fast", 0) >= params.get("slow", 1e9):
            continue
        r = run(df, fn(df, **params))
        s = r.stats()
        if r.trades >= min_trades and (best is None or s["Sharpe"] > best["Sharpe"]):
            best, best_params = s, params
    return best_params, best
