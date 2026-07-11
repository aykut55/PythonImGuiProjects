import json
import os
from datetime import datetime, timedelta

import numpy as np


def ema(values, period):
    alpha = 2.0 / (period + 1.0)
    out = np.empty(len(values), dtype=np.float64)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1.0 - alpha) * out[i - 1]
    return out


def main():
    project_dir = os.path.dirname(os.path.dirname(__file__))
    out_dir = os.path.join(project_dir, "inputs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "latest_bundle.npz")

    n = 1500
    xs = np.arange(n, dtype=np.float64)
    base = 100.0 + 0.02 * xs + 4.0 * np.sin(xs / 45.0) + 1.2 * np.sin(xs / 11.0)
    close = base
    open_ = close + 0.35 * np.sin(xs / 7.0)
    high = np.maximum(open_, close) + 0.8 + 0.2 * np.sin(xs / 13.0)
    low = np.minimum(open_, close) - 0.8 - 0.2 * np.cos(xs / 17.0)
    volume = (100_000 + 20_000 * (1.0 + np.sin(xs / 30.0))).astype(np.float64)
    size = np.full(n, 1, dtype=np.int32)

    ema50 = ema(close, 50)
    ema100 = ema(close, 100)
    ema200 = ema(close, 200)
    indicator_names = np.array(["EMA50", "EMA100", "EMA200"], dtype="<U32")
    indicator_values = np.vstack([ema50, ema100, ema200])

    signal_codes = np.zeros(n, dtype=np.int32)
    signal_steps = np.zeros(n, dtype=np.int32)
    details = []
    position = 0
    entry_price = None
    entry_index = None
    take_profit_pct = 0.03
    stop_loss_pct = 0.015

    for i in range(1, n):
        if position != 0 and entry_price is not None:
            if position == 1:
                stop_price = entry_price * (1.0 - stop_loss_pct)
                take_price = entry_price * (1.0 + take_profit_pct)
                stop_hit = low[i] <= stop_price
                take_hit = high[i] >= take_price
                if stop_hit or take_hit:
                    exit_price = stop_price if stop_hit else take_price
                    reason = "STOP_LOSS" if stop_hit else "TAKE_PROFIT"
                    signal_codes[i] = 2
                    details.append({
                        "index": i,
                        "signal": "FLAT",
                        "state": 0,
                        "position": "AL",
                        "entryIndex": entry_index,
                        "entryPrice": float(entry_price),
                        "exitPrice": float(exit_price),
                        "exitReason": reason,
                        "pnl": float(exit_price - entry_price),
                        "pnlPct": float((exit_price - entry_price) / entry_price),
                    })
                    position = 0
                    entry_price = None
                    entry_index = None
                    signal_steps[i] = position
                    continue
            else:
                stop_price = entry_price * (1.0 + stop_loss_pct)
                take_price = entry_price * (1.0 - take_profit_pct)
                stop_hit = high[i] >= stop_price
                take_hit = low[i] <= take_price
                if stop_hit or take_hit:
                    exit_price = stop_price if stop_hit else take_price
                    reason = "STOP_LOSS" if stop_hit else "TAKE_PROFIT"
                    signal_codes[i] = 2
                    details.append({
                        "index": i,
                        "signal": "FLAT",
                        "state": 0,
                        "position": "SAT",
                        "entryIndex": entry_index,
                        "entryPrice": float(entry_price),
                        "exitPrice": float(exit_price),
                        "exitReason": reason,
                        "pnl": float(entry_price - exit_price),
                        "pnlPct": float((entry_price - exit_price) / entry_price),
                    })
                    position = 0
                    entry_price = None
                    entry_index = None
                    signal_steps[i] = position
                    continue

        prev_diff = ema50[i - 1] - ema100[i - 1]
        cur_diff = ema50[i] - ema100[i]
        candidate = 0
        if prev_diff <= 0.0 < cur_diff:
            candidate = 1
        elif prev_diff >= 0.0 > cur_diff:
            candidate = -1

        if candidate and position != 0:
            details.append({
                "index": i,
                "signal": "SKIP",
                "state": position,
                "candidateSignal": "AL" if candidate == 1 else "SAT",
                "position": "AL" if position == 1 else "SAT",
                "entryIndex": entry_index,
                "entryPrice": float(entry_price),
                "reason": "POSITION_OPEN",
            })
        elif candidate == 1:
            signal_codes[i] = 1
            position = 1
            entry_price = close[i]
            entry_index = i
            details.append({
                "index": i,
                "signal": "AL",
                "state": 1,
                "position": "AL",
                "entryIndex": i,
                "entryPrice": float(entry_price),
                "takeProfitPrice": float(entry_price * (1.0 + take_profit_pct)),
                "stopLossPrice": float(entry_price * (1.0 - stop_loss_pct)),
                "reason": "EMA_CROSS_UP",
            })
        elif candidate == -1:
            signal_codes[i] = -1
            position = -1
            entry_price = close[i]
            entry_index = i
            details.append({
                "index": i,
                "signal": "SAT",
                "state": -1,
                "position": "SAT",
                "entryIndex": i,
                "entryPrice": float(entry_price),
                "takeProfitPrice": float(entry_price * (1.0 - take_profit_pct)),
                "stopLossPrice": float(entry_price * (1.0 + stop_loss_pct)),
                "reason": "EMA_CROSS_DOWN",
            })

        signal_steps[i] = position

    start = datetime(2026, 1, 2, 10, 0)
    timestamps = np.array([(start + timedelta(minutes=5 * i)).isoformat() for i in range(n)], dtype="<U32")
    meta = {
        "symbol": "TEST",
        "market": "SIM",
        "period": "05",
        "intraday": True,
        "barCount": n,
    }
    signal_details_json = np.array([json.dumps(item, ensure_ascii=False) for item in details], dtype="<U1024")

    np.savez(
        out_path,
        meta_json=np.array(json.dumps(meta, ensure_ascii=False)),
        timestamps=timestamps,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        size=size,
        indicator_names=indicator_names,
        indicator_values=indicator_values,
        signal_codes=signal_codes,
        signal_steps=signal_steps,
        signal_details_json=signal_details_json,
    )
    view_path = os.path.join(out_dir, "latest_bundle.view.json")
    view = {
        "panels": [
            {
                "id": "ohlc",
                "name": "OHLC",
                "caption": "TEST OHLC",
                "height": 420,
                "ySyncId": 0,
                "series": [
                    {"type": "candle", "source": "ohlc", "dataId": 0, "name": "TEST"},
                    {"type": "line", "source": "indicator", "name": "EMA50"},
                    {"type": "line", "source": "indicator", "name": "EMA100"},
                ],
                "tradeOverlay": {
                    "enabled": True,
                    "showSignals": False,
                    "showLevelLines": True,
                    "colorBars": True,
                },
            },
            {
                "id": "signals",
                "name": "Signals",
                "caption": "Signal Steps",
                "height": 160,
                "ySyncId": 1,
                "series": [
                    {"type": "line", "source": "signalSteps", "dataId": 1, "name": "Signal Step"}
                ],
            },
            {
                "id": "indicators",
                "name": "Indicators",
                "caption": "Indicators",
                "height": 260,
                "ySyncId": 2,
                "series": [
                    {"type": "line", "source": "indicator", "name": "EMA200"}
                ],
            },
        ]
    }
    with open(view_path, "w", encoding="utf-8") as f:
        json.dump(view, f, ensure_ascii=False, indent=2)

    input_config_path = os.path.join(out_dir, "input.json")
    with open(input_config_path, "w", encoding="utf-8") as f:
        json.dump({"bundle": out_path, "view": view_path}, f, ensure_ascii=False, indent=2)
    print(f"Yazildi: {out_path}")
    print(f"View config: {view_path}")
    print(f"Input config: {input_config_path}")
    print(f"Bar count: {n}")
    print(f"Signal events: {int(np.count_nonzero(signal_codes))}")
    print(f"Details: {len(details)}")


if __name__ == "__main__":
    main()
