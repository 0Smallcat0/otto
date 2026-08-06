import { describe, expect, it } from "vitest";

import { rankHeadlines, sessionSpan, sessionStamp, staleCandles } from "../../src/ui/api";
import { runProvenance, sampleCaveat } from "../../src/ui/readers";
import { deleveragingLine, isTwSymbol } from "../../src/ui/wall";

// Five defects fixed on 2026-07-27 were all the same shape: the backend had
// computed the qualifying fact, put it in the payload, and the render step
// dropped it. Nothing failed — the API was right and only the screen was
// wrong. The Playwright suite runs against a deliberately fresh terminal with
// no positions, no judgments and no quote cache, so it cannot see any of it.
// These are the guards for the decisions themselves.

describe("rankHeadlines", () => {
  it("puts his holdings above anything merely fresher", () => {
    const feed = [
      { id: "lottery", relevance: "noise", age_minutes: 1 },
      { id: "wire", relevance: "global", age_minutes: 5 },
      { id: "his", relevance: "mine", age_minutes: 600 },
      { id: "tw", relevance: "tw", age_minutes: 30 }
    ];

    // In the live feed 4 of 120 items were "mine" and freshness alone put
    // none of them in the top ten.
    expect(rankHeadlines(feed).map((item) => item.id)).toEqual(["his", "wire", "tw", "lottery"]);
  });

  it("sinks noise without dropping it", () => {
    const feed = [
      { id: "lottery", relevance: "noise", age_minutes: 1 },
      { id: "forum", relevance: "noise", age_minutes: 2 }
    ];

    expect(rankHeadlines(feed)).toHaveLength(2);
  });

  it("treats an untagged item as ordinary rather than as junk", () => {
    const feed = [
      { id: "noise", relevance: "noise", age_minutes: 1 },
      { id: "untagged", age_minutes: 90 }
    ];

    expect(rankHeadlines(feed)[0].id).toBe("untagged");
  });

  it("does not mutate the caller's array", () => {
    const feed = [
      { id: "a", relevance: "noise", age_minutes: 1 },
      { id: "b", relevance: "mine", age_minutes: 2 }
    ];
    rankHeadlines(feed);

    expect(feed.map((item) => item.id)).toEqual(["a", "b"]);
  });
});

describe("sessionStamp", () => {
  it("reads a TWSE ROC date", () => {
    expect(sessionStamp({ symbol: "2834", date: "1150724" })).toBe("07/24");
  });

  it("reads Finnhub epoch seconds in UTC, not local time", () => {
    // 1784923200 is Friday 2026-07-24 20:00Z, the US close. Local getters in
    // UTC+8 rolled it to Saturday 07/25 and stamped the rows with a day the
    // market was shut — caught on screen, invisible in the payload.
    expect(sessionStamp({ symbol: "AAPL", latest_trading_day: "1784923200" })).toBe("07/24");
  });

  it("reads an ISO trading day without going through a timezone", () => {
    expect(sessionStamp({ symbol: "EUR/USD", latest_trading_day: "2026-07-26" })).toBe("07/26");
  });

  it("says nothing rather than guessing when the row names no session", () => {
    // Crypto never closes, so there is no session to name and the caller
    // falls back to fetch age. Returning a wrong date here would be worse
    // than returning none.
    expect(sessionStamp({ symbol: "BTCUSDT", retrieved_at: "2026-07-27T00:00:00Z" })).toBe("");
    expect(sessionStamp(undefined)).toBe("");
    expect(sessionStamp({ symbol: "X", latest_trading_day: "not a date" })).toBe("");
  });
});

describe("sessionSpan", () => {
  it("never certifies a group as fresher than its oldest row", () => {
    // TWSE publishes its daily file per symbol. On 2026-07-28 the same five
    // rows carried two dates, and stamping the group from rows[0] put three
    // rows holding 07/27 prices under a header reading 07/28 — on a session
    // where 0050 had fallen 4.24% and the wall showed +0.15%.
    const rows = [
      { symbol: "2330", date: "1150728" },
      { symbol: "0050", date: "1150727" },
      { symbol: "00982A", date: "1150727" }
    ];

    expect(sessionSpan(rows)).toEqual({ stamp: "07/27", mixed: true });
  });

  it("does not cry mixed when the group agrees", () => {
    const rows = [
      { symbol: "2330", date: "1150728" },
      { symbol: "0050", date: "1150728" }
    ];

    expect(sessionSpan(rows)).toEqual({ stamp: "07/28", mixed: false });
  });

  it("picks December over January across a year boundary", () => {
    const rows = [
      { symbol: "A", latest_trading_day: "2027-01-02" },
      { symbol: "B", latest_trading_day: "2026-12-31" }
    ];

    expect(sessionSpan(rows).stamp).toBe("12/31");
  });

  it("says nothing when no row names a session", () => {
    expect(sessionSpan([{ symbol: "BTCUSDT" }])).toEqual({ stamp: "", mixed: false });
    expect(sessionSpan([])).toEqual({ stamp: "", mixed: false });
  });

  it("ignores rows with no session rather than treating them as oldest", () => {
    const rows = [{ symbol: "A", date: "1150728" }, { symbol: "B" }];

    expect(sessionSpan(rows)).toEqual({ stamp: "07/28", mixed: false });
  });
});

describe("staleCandles", () => {
  const now = new Date("2026-07-28T14:00:00Z");

  it("catches the three-week gap that drew a 23.83 bar under a 20.09 price", () => {
    expect(staleCandles("2026-07-08", now)).toBe(true);
  });

  it("does not accuse Friday's close on a Monday", () => {
    // A weekend plus a holiday either side must not read as a dead source.
    expect(staleCandles("2026-07-24", now)).toBe(false);
    expect(staleCandles("2026-07-28", now)).toBe(false);
  });

  it("says nothing when the series names no last close", () => {
    // Crypto series and anything that omits the field must not be branded
    // stale on the strength of a missing value.
    expect(staleCandles(undefined, now)).toBe(false);
    expect(staleCandles("", now)).toBe(false);
    expect(staleCandles("not a date", now)).toBe(false);
  });

describe("sampleCaveat", () => {
  // Same shape as the five defects above, committed one round ago and by me:
  // the engine computed whether a backtest's sample could carry a verdict, put
  // it in the payload, and the render step dropped it. On screen, 11 round
  // trips over twenty hours produced a win rate and a Sharpe that looked
  // exactly like a run of 400 trades over three years.
  it("qualifies a run too small to be a verdict", () => {
    const caveat = sampleCaveat({
      sample: {
        verdict: "not_a_verdict",
        round_trip_count: 11,
        floor_round_trips: 30,
        fragile_metrics: ["sharpe_ratio", "win_rate_pct"]
      }
    });

    expect(caveat).not.toBeNull();
    expect(caveat?.round_trip_count).toBe(11);
    // The KPI row shows a win rate; naming it is what connects the two.
    expect(caveat?.fragile_metrics).toContain("win_rate_pct");
  });

  it("stays quiet only when the sample can actually carry a conclusion", () => {
    expect(sampleCaveat({ sample: { verdict: "defensible" } })).toBeNull();
    expect(sampleCaveat({ sample: { verdict: "reliable" } })).not.toBeNull();
    expect(sampleCaveat({ sample: { verdict: "directional_only" } })).not.toBeNull();
  });

  it("says nothing when the engine said nothing", () => {
    expect(sampleCaveat(undefined)).toBeNull();
    expect(sampleCaveat({})).toBeNull();
    expect(sampleCaveat({ sample: {} })).toBeNull();
  });
});

  it("reads a full timestamp, not just a bare date", () => {
    expect(staleCandles("2026-07-08T13:30:00+08:00", now)).toBe(true);
  });
});

describe("runProvenance", () => {
  it("refuses to dress a synthetic run as a result", () => {
    // Three of eight runs were computed on locally generated candles because
    // market data could not be fetched, and they were the best-looking rows
    // in the table, styled exactly like the one live run.
    const synthetic = runProvenance({ data_state: "offline_fallback" });

    expect(synthetic.trusted).toBe(false);
    expect(synthetic.label).toBe("合成資料");
  });

  it("keeps a stale run trusted — an old cache is still real market data", () => {
    const stale = runProvenance({ data_state: "stale" });

    expect(stale.trusted).toBe(true);
    expect(stale.label).toBe("過期快取");
  });

  it("treats an unknown state as trusted but labels it verbatim", () => {
    // Inventing a reassuring label for a state we do not recognise would be
    // the same failure as dropping it.
    expect(runProvenance({ data_state: "something_new" })).toMatchObject({
      label: "something_new",
      trusted: true
    });
    expect(runProvenance({}).label).toBe("—");
  });
});

// The margin series shipped one round before this one and reached no screen at
// all: /api/research/tw-margin had zero references in the whole frontend. The
// number it put on the wall first was also the wrong one — a streak counts
// days, and Taiwan desks compare distance (index -12.86% vs margin -9.93% on
// 2026-07-28, https://www.setn.com/news/1880517).

describe("deleveragingLine", () => {
  const incomplete = {
    verdict: "incomplete",
    margin_decline_pct: "-9.93",
    index_decline_pct: "-12.86",
    index_symbol: "0050"
  };

  it("says the tape has fallen further than the leverage behind it", () => {
    const line = deleveragingLine(incomplete, 2);
    expect(line?.labelKey).toBe("去槓桿未完成");
    expect(line?.detail).toBe("-9.93% vs 0050 -12.86%");
    expect(line?.cls).toBe("ft-down");
  });

  it("colours the other answer the other way", () => {
    const line = deleveragingLine({ ...incomplete, verdict: "margin_led" }, 1);
    expect(line?.labelKey).toBe("融資已先跌過大盤");
    expect(line?.cls).toBe("ft-up");
  });

  it("stays silent for a book with nothing on that exchange", () => {
    expect(deleveragingLine(incomplete, 0)).toBeNull();
  });

  it("shows why it cannot answer rather than a blank", () => {
    const line = deleveragingLine(
      { verdict: "unknown", reason: "0050 history ends 2026-07-28" },
      1
    );
    expect(line?.cls).toBe("ft-dim");
    expect(line?.detail).toContain("2026-07-28");
  });

  it("renders nothing when the backend sent no verdict", () => {
    expect(deleveragingLine(null, 3)).toBeNull();
    expect(deleveragingLine({ verdict: "" }, 3)).toBeNull();
  });
});

describe("isTwSymbol", () => {
  it("counts the shapes the book actually stores", () => {
    expect(["2834", "0050", "00982A", "2317.TW", "6488.TWO"].every(isTwSymbol)).toBe(true);
    expect(["AAPL", "BTCUSDT", "SPY", ""].some(isTwSymbol)).toBe(false);
  });
});
