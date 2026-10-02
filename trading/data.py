"""Scarica lo storico BTC/USD (Bitstamp, 1 minuto) e lo ricampiona in candele 1h/4h/1d.

Fonte: https://github.com/ff137/bitstamp-btcusd-minute-data (dataset pubblico, aggiornato ogni giorno).
Uso:  python data.py            -> crea data/btcusd_1h.csv, data/btcusd_4h.csv, data/btcusd_1d.csv
"""
from pathlib import Path
import urllib.request

import pandas as pd

BASE = "https://raw.githubusercontent.com/ff137/bitstamp-btcusd-minute-data/main/data"
SOURCES = {
    "hist.csv.gz": f"{BASE}/historical/btcusd_bitstamp_1min_2012-2025.csv.gz",
    "latest.csv": f"{BASE}/updates/btcusd_bitstamp_1min_latest.csv",
}
DATA = Path(__file__).parent / "data"
START = "2018-01-01"
AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def download(cache: Path) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        if not (cache / name).exists():
            print("scarico", url)
            urllib.request.urlretrieve(url, cache / name)


def build(cache: Path = DATA / "raw") -> None:
    download(cache)
    df = pd.concat(pd.read_csv(cache / n) for n in SOURCES)
    df = df.drop_duplicates("timestamp").sort_values("timestamp")
    df.index = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    df = df.loc[START:, list(AGG)]
    for tf in ("1h", "4h", "1D"):
        out = df.resample(tf).agg(AGG).dropna()
        out.to_csv(DATA / f"btcusd_{tf.lower()}.csv")
        print(tf, len(out), out.index[0], "->", out.index[-1])


def load(tf: str = "4h") -> pd.DataFrame:
    return pd.read_csv(DATA / f"btcusd_{tf}.csv", index_col=0, parse_dates=True)


if __name__ == "__main__":
    build()
