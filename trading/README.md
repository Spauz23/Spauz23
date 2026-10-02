# Trading bot BTC – backtest e bot spot

| File | Cosa fa |
|---|---|
| `data.py` | Scarica lo storico BTC/USD 2018→oggi (Bitstamp, 1 min) e crea candele 1h/4h/1d |
| `strategies.py` | Strategie: `ema_cross`, `donchian`, `rsi_dip` (+ buy & hold come riferimento) |
| `backtest.py` | Backtester: commissioni, slippage, leva, funding, liquidazione |
| `run_tests.py` | Ottimizza su 2018-2023, verifica su 2024→oggi → `RISULTATI.md` + `equity.png` |
| `bot.py` | Bot Binance spot (ccxt), default **testnet + dry-run** |

```bash
pip install pandas numpy matplotlib ccxt
python data.py        # dati
python run_tests.py   # test
python bot.py         # bot in simulazione
```

Il bot va lanciato ogni 4h (cron o `--loop`) su un server sempre acceso (VPS).
Passare a `--live --mainnet` solo dopo settimane di testnet, con chiave API **senza prelievo**.
