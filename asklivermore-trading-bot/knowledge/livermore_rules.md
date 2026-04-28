# Livermore's Trading Rules — Reference

These are the rules the ConfluenceValidatorAgent and ReasoningAgent treat as canonical.
If a chat instruction contradicts what's here, this file wins (per CLAUDE.md §10).

## The 5-step pivotal point method

1. **Identify the pivot.** A clear prior high, prior low, or sideways congestion ceiling. No pivot, no trade.
2. **Trade the line of least resistance.** Only enter in the direction the market is already inclined to move. Do not anticipate reversals.
3. **Volume must confirm.** Breakouts on weak volume are suspect. Demand at least 1.5x the 30-day average on the breakout bar.
4. **No overhead supply.** Stock should not be entering a thicket of recent prior congestion. If it is, the supply will likely cap the move.
5. **Market tone must support.** Don't trade longs in a tape that's broadly distributing. Indices in confirmed uptrend, not fighting downside breadth.

## Money rules

- Never average down. Add only to winners that prove themselves above the pivot.
- Cut losses fast at the predetermined stop. No exceptions, no "give it room."
- Risk a fixed small fraction per trade (this bot uses 2% — CLAUDE.md hard rule).
- Sit on hands when conditions are wrong. The best position is sometimes cash.

## Behavioral

- The market is always right; your opinion is not.
- Suspicion of one's own analysis is healthy; revisit the data, not the position.
- Journal every trade, win or loss, with the reasoning prior to entry — not after exit.

## What this bot does NOT do

- No shorting. (Long-only by design; less ruin risk for retail-scale automation.)
- No options. (Reserved for future extension; gates and risk math would change.)
- No leverage above broker margin defaults.
- No revenge trading: 3 consecutive losses on a ticker triggers a cooldown via MemoryGraphAgent.
