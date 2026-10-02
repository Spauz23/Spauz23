"""Esegue i test e scrive RISULTATI.md + grafico equity.

Metodo anti-autoinganno:
1. ottimizza i parametri SOLO sul periodo 2018-2023 (in-sample);
2. valuta gli stessi parametri, senza ritocchi, sul 2024-oggi (out-of-sample);
3. confronta sempre con il semplice buy & hold;
4. ripete la strategia migliore con leva 3x/10x/20x per vedere cosa succede "stile reel".
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from backtest import optimize, run
from data import load
from strategies import STRATEGIES, buy_hold

TF = "4h"
SPLIT = "2024-01-01"
OUT = Path(__file__).parent


def table(rows: list[dict]) -> str:
    cols = list(rows[0])
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in rows]
    return "\n".join(lines)


def main():
    df = load(TF)
    ins, oos = df[:SPLIT].iloc[:-1], df[SPLIT:]
    rows_in, rows_out, curves = [], [], {}

    curves["buy & hold"] = run(oos, buy_hold(oos)).equity
    rows_in.append({"strategia": "buy & hold", "parametri": "-", **run(ins, buy_hold(ins)).stats()})
    rows_out.append({"strategia": "buy & hold", "parametri": "-", **run(oos, buy_hold(oos)).stats()})

    best_name, best_sharpe = None, -1e9
    for name, (fn, grid) in STRATEGIES.items():
        params, s_in = optimize(ins, fn, grid)
        r_out = run(oos, fn(oos, **params))
        p = ", ".join(f"{k}={v}" for k, v in params.items())
        rows_in.append({"strategia": name, "parametri": p, **s_in})
        rows_out.append({"strategia": name, "parametri": p, **r_out.stats()})
        curves[name] = r_out.equity
        if s_in["Sharpe"] > best_sharpe:  # scelta fatta sull'in-sample, non sul risultato futuro
            best_name, best_sharpe, best_params = name, s_in["Sharpe"], params

    fn = STRATEGIES[best_name][0]
    rows_lev = []
    for lev in (1, 3, 10, 20):
        r = run(oos, fn(oos, **best_params), leverage=lev)
        rows_lev.append({"leva": f"{lev}x", **r.stats()})

    fig, ax = plt.subplots(figsize=(11, 5.5))
    for name, eq in curves.items():
        ax.plot(eq.index, eq * 1000, label=name, lw=2.2 if name == best_name else 1.3)
    ax.set_title(f"BTC/USD {TF} – 1.000 $ investiti dal {SPLIT} (out-of-sample, commissioni incluse)")
    ax.set_ylabel("$")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "equity.png", dpi=110)

    period = lambda d: f"{d.index[0]:%d/%m/%Y} → {d.index[-1]:%d/%m/%Y}"
    report = f"""# Risultati backtest BTC/USD ({TF})

Commissioni 0,10% + slippage 0,05% per lato. Operazione alla candela successiva al segnale.

## 1. Ottimizzazione – in-sample ({period(ins)})
{table(rows_in)}

## 2. Verifica – out-of-sample ({period(oos)}), stessi parametri, nessun ritocco
{table(rows_out)}

![equity](equity.png)

## 3. Strategia scelta ({best_name}) con leva – out-of-sample
Funding 0,01%/8h, liquidazione se il minimo della candela brucia il margine.

{table(rows_lev)}
"""
    (OUT / "RISULTATI.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
