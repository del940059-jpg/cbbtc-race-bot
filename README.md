# Dip-buy BTC bot — make.fun `btc-race-24h-20261117-0603`

A Python 3.13 (stdlib only) bot for the make.fun BTC race. It trades one
asset, CBBTC (Coinbase Wrapped BTC) vs USDC, on 1-minute bars, starting with
$1,000 of paper money, long only. It speaks `agent-fun/bars-replay/v1`: the
`hello` message arrives first, then one `batch` per bar, and it answers every
batch with exactly one reply echoing its `seq` with its `orders`.

## Strategy

1-minute cbBTC bars are very quiet (about 6 bps of noise per bar) while a
full-size round trip costs roughly 30 bps in fees, slippage and pool impact,
so frequent trading bleeds out. This bot therefore trades at most once:

- **Entry** — buy with all cash when the close is at least 100 bps below
  the highest close of the last 240 bars (4 hours) **and** the close is
  above the close 10 bars ago (the dip is already bouncing). If no dip ever
  comes, it buys once at batch 720 (halfway) so it always holds a position
  for the second half of the window.
- **Exit** — none, except a wide hard stop: sell everything if the position
  is worth 100 bps less than it cost (fees included) at the latest close.
  No trailing exit, no re-entry. Everything else is held to the end of the
  window and flattened by the replay.

All decisions are integer arithmetic on the raw price units from the `hello`
and `batch` messages, in bar order: fully deterministic, no clock, no
network, no files, no randomness.

## Files

- `main.py` — the bot (entrypoint, run as `python3 -P -s /bot/main.py`)
- `vendor/makefun_bars.py` — byte-identical copy of the kit's Python shim
- `LICENSE` — MIT
- `.makefun/owner.json` — account claim file

## Grade locally

From inside the competition kit directory:

```sh
node cli/makefun.mjs grade-local --kit . --bot /home/hatch/workspace/btc-race-bot --driver docker
```

It runs the bot twice on the frozen 24-hour dev window and reports net PnL,
return, max drawdown, Sharpe and trades; the two runs must match.
