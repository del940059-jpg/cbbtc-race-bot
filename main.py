"""Dip-buy and hold bot for the make.fun BTC race (agent-fun/bars-replay/v1).

Strategy, in one paragraph: the pool's 1-minute bars are very quiet (about
6 bps of per-bar noise) and a full-size round trip costs roughly 30 bps, so
anything that trades often bleeds out in fees, slippage and impact. This bot
therefore trades at most once. It waits for a real dip -- the close at least
100 bps below the highest close of the last 240 bars (4 hours) with the
10-bar momentum already turning back up -- and then buys with all its cash
and holds to the end of the window. If no dip ever comes it buys once at
batch 720 (halfway) so it still holds a position for the second half. While
it holds, the only exit is a wide hard stop: the position is sold if its
value at the latest close falls 100 bps below what it cost (fees included),
crash insurance only. There is no trailing exit and no re-entry: every extra
round trip tested on the dev window cost more than it earned.

All decisions use integer arithmetic on the raw price units the hello and
batch messages carry, in the order the bars arrive, so the same bars give
the same orders on every run: no clock, no network, no files, no random
numbers anywhere.

One safety net: a buy the market refuses (a fill past the slippage cap, a
bar missing at the next open) leaves the bot flat, so the entry is not
counted as used and the bot may try again on the next bar that signals it.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"
# A dip counts when the close sits this many bps under the 240-bar high.
DIP_BPS = 100
# Bars of history a dip is measured against (4 hours of 1-minute bars).
LOOKBACK_BARS = 240
# The bounce confirmation: the close must be above the close this many bars ago.
MOMENTUM_BARS = 10
# The hard stop, in bps under the position's cost (fees included).
HARD_STOP_BPS = 100
# If no dip has fired by this batch, buy once anyway so the bot always trades.
FORCE_BUY_BAR = 720
# At most one entry per run, so at most one round trip of costs.
MAX_ENTRIES = 1
# Fills move at most a few tens of bps from the close they were decided on;
# 100 bps leaves ample room while refusing a fill into a liquidity gap.
MAX_SLIPPAGE_BPS = 100

_closes = []
_entries = 0
_pending_buy = False


def _on_hello(state):
    del _closes[:]
    global _entries, _pending_buy
    _entries = 0
    _pending_buy = False


def _on_batch(state, batch):
    global _entries, _pending_buy
    if state.warming_up:
        return []
    bar = None
    for b in batch["bars"]:
        if b["symbol"] == SYMBOL:
            bar = b
            break
    if bar is None:
        # No bar for this symbol on this batch: nothing new to decide on.
        return []
    close = int(bar["c"])
    _closes.append(close)

    holding = state.positions.get(SYMBOL)
    if _pending_buy:
        if holding is None:
            # The buy decided on the last bar never filled: it was refused,
            # so it does not count as the one entry and the bot may retry.
            _pending_buy = False
            _entries = 0
        else:
            _pending_buy = False
    if holding is not None:
        # Held: the only exit is the wide hard stop, measured against the
        # position's true cost (fees included) at the latest close.
        value = state.value(SYMBOL, holding.qty)
        if value * 10000 <= holding.cost * (10000 - HARD_STOP_BPS):
            return [{
                "side": "sell",
                "symbol": SYMBOL,
                "qty": holding.qty,
                "max_slippage_bps": MAX_SLIPPAGE_BPS,
            }]
        return []

    if _entries >= MAX_ENTRIES:
        return []
    if len(_closes) < LOOKBACK_BARS + 2:
        return []
    if state.seq < 0:
        return []

    # Dip: the highest close of the last LOOKBACK_BARS bars before this one,
    # compared with this bar's close, in whole bps (integer cross-multiply).
    high = max(_closes[-LOOKBACK_BARS - 1:-1])
    dipped = high * 10000 >= close * (10000 + DIP_BPS)
    # Bounce: the close is above the close MOMENTUM_BARS bars ago.
    bouncing = close > _closes[-MOMENTUM_BARS - 1]
    forced = state.seq >= FORCE_BUY_BAR
    if (dipped and bouncing) or forced:
        _entries += 1
        _pending_buy = True
        return [{
            "side": "buy",
            "symbol": SYMBOL,
            "notional_quote_units": state.cash,
            "max_slippage_bps": MAX_SLIPPAGE_BPS,
        }]
    return []


makefun_bars.run(_on_batch, on_hello=_on_hello)
