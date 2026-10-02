"""Bot spot BTC/USDC su Binance. Strategia default: ema_cross 10/200 su candele 4h.

SICUREZZA
- Di default gira in DRY-RUN (simula, non invia ordini) e sulla TESTNET di Binance.
- Solo spot, nessuna leva. Chiave API senza permesso di prelievo + whitelist IP.

USO
    pip install ccxt pandas
    export BINANCE_KEY=...  BINANCE_SECRET=...      # chiavi testnet: https://testnet.binance.vision
    python bot.py                 # un controllo e basta (da lanciare con cron ogni 4h)
    python bot.py --loop          # resta acceso e controlla a ogni chiusura di candela
    python bot.py --live          # ordini veri sulla testnet
    python bot.py --live --mainnet  # SOLDI VERI: solo dopo settimane di test
"""
import argparse
import os
import time
from datetime import datetime, timezone

import pandas as pd

from strategies import STRATEGIES

SYMBOL = "BTC/USDC"
TIMEFRAME = "4h"
STRATEGY, PARAMS = "ema_cross", {"fast": 10, "slow": 200}
ALLOCATION = 0.95   # quota del saldo USDC usata a ogni acquisto
MIN_ORDER = 10      # Binance rifiuta ordini sotto ~5-10 USDC


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} | {msg}"
    print(line, flush=True)
    with open(os.path.join(os.path.dirname(__file__), "bot.log"), "a") as f:
        f.write(line + "\n")


def make_exchange(mainnet: bool):
    import ccxt
    ex = ccxt.binance({
        "apiKey": os.getenv("BINANCE_KEY"),
        "secret": os.getenv("BINANCE_SECRET"),
        "enableRateLimit": True,
        "options": {"defaultType": "spot"},
    })
    if not mainnet:
        ex.set_sandbox_mode(True)
    return ex


def candles(ex) -> pd.DataFrame:
    raw = ex.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=1000)  # tanta storia = EMA lente stabili come nel backtest
    df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
    df.index = pd.to_datetime(df.pop("ts"), unit="ms", utc=True)
    return df.iloc[:-1]  # scarta la candela ancora aperta


def decide(df: pd.DataFrame) -> int:
    fn = STRATEGIES[STRATEGY][0]
    return int(fn(df, **PARAMS).iloc[-1])


def step(ex, live: bool) -> None:
    df = candles(ex)
    target = decide(df)
    price = df.close.iloc[-1]
    base, quote = SYMBOL.split("/")
    bal = ex.fetch_balance() if ex.apiKey else {"free": {base: 0, quote: 1000}}
    have_btc = bal["free"].get(base, 0) or 0
    have_usd = bal["free"].get(quote, 0) or 0
    in_position = have_btc * price > MIN_ORDER
    log(f"prezzo {price:,.2f} | segnale {'LONG' if target else 'FLAT'} | "
        f"{base} {have_btc:.6f} | {quote} {have_usd:,.2f}")

    if target and not in_position and have_usd * ALLOCATION > MIN_ORDER:
        amount = float(ex.amount_to_precision(SYMBOL, have_usd * ALLOCATION / price))
        log(f"COMPRA {amount} {base}" + ("" if live else " (dry-run)"))
        if live:
            log(str(ex.create_market_buy_order(SYMBOL, amount)["id"]))
    elif not target and in_position:
        amount = float(ex.amount_to_precision(SYMBOL, have_btc))
        log(f"VENDI {amount} {base}" + ("" if live else " (dry-run)"))
        if live:
            log(str(ex.create_market_sell_order(SYMBOL, amount)["id"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="invia ordini veri")
    ap.add_argument("--mainnet", action="store_true", help="usa Binance reale invece della testnet")
    ap.add_argument("--loop", action="store_true", help="resta acceso")
    a = ap.parse_args()
    if a.mainnet and input("Ordini con SOLDI VERI. Scrivi 'confermo': ") != "confermo":
        return
    ex = make_exchange(a.mainnet)
    log(f"avvio | {STRATEGY} {PARAMS} | {'MAINNET' if a.mainnet else 'testnet'} | "
        f"{'LIVE' if a.live else 'dry-run'}")
    while True:
        try:
            step(ex, a.live)
        except Exception as e:  # rete/exchange: logga e riprova al giro dopo
            log(f"errore: {e!r}")
        if not a.loop:
            break
        period = ex.parse_timeframe(TIMEFRAME)
        time.sleep(period - time.time() % period + 30)  # 30s dopo la chiusura candela


if __name__ == "__main__":
    main()
