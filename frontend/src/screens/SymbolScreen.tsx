import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { getClient } from "@/api/client";
import type { SymbolDetail } from "@/api/types";
import { ChangeCard } from "@/components/ChangeCard";
import { FreshnessChip } from "@/components/FreshnessChip";
import { Sparkline } from "@/components/Sparkline";
import { Ticker } from "@/components/Ticker";
import { asOf, day } from "@/lib/format";
import { listVariants, cardVariants } from "@/lib/motion";
import { href } from "@/state/router";
import { useStore } from "@/state/store";

export function SymbolScreen({ symbol }: { symbol: string }) {
  const store = useStore();
  const reduced = useReducedMotion();
  const [detail, setDetail] = useState<SymbolDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setDetail(null);
    setError(null);
    void (async () => {
      try {
        const api = await getClient();
        const d = await api.getSymbol(symbol);
        if (live) setDetail(d);
      } catch (err) {
        if (live) setError(err instanceof Error ? err.message : "Could not load this symbol.");
      }
    })();
    return () => {
      live = false;
    };
  }, [symbol]);

  const entry = store.watchlist?.entries.find((e) => e.symbol === symbol);

  if (error) {
    return (
      <div className="wrap section">
        <div className="empty-note">{error}</div>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="wrap section" aria-busy="true">
        <div className="skel" style={{ height: "2.4rem", width: "14rem" }} />
        <div className="skel" style={{ height: "84px", width: "100%", marginTop: "1.5rem" }} />
        <div className="skel" style={{ height: "10rem", width: "100%", marginTop: "1.5rem" }} />
      </div>
    );
  }

  const p = detail.price;

  return (
    <div className="wrap">
      <header className="detail-head">
        <div>
          <a className="eyebrow" href={href({ name: "digest" })} style={{ textDecoration: "none" }}>
            ← back to digest
          </a>
          <div className="sym__row" style={{ marginTop: "0.6rem" }}>
            <span className="sym__ticker" style={{ fontSize: "0.875rem" }}>
              {detail.symbol}
            </span>
            <FreshnessChip provenance={detail.provenance} />
          </div>
          <h1 className="detail-title">{detail.name}</h1>
        </div>
        <div className="price">
          <div className="price__last" style={{ fontSize: "1.5rem" }}>
            <span className="cur">₹</span>
            <Ticker value={p.last} grouped />
          </div>
          <div className="price__delta">
            <span className="price__label">today</span>
            <span className={p.change_pct > 0 ? "up" : p.change_pct < 0 ? "down" : "neutral"}>
              <Ticker value={p.change_pct} signed suffix="%" from={0} />
            </span>
          </div>
          {p.idiosyncratic_pct != null && (
            <div className="price__delta" style={{ marginTop: "0.15rem" }}>
              <span className="price__label">idiosyncratic</span>
              <span className={p.idiosyncratic_pct > 0 ? "up" : p.idiosyncratic_pct < 0 ? "down" : "neutral"}>
                <Ticker value={p.idiosyncratic_pct} signed suffix="%" from={0} />
              </span>
            </div>
          )}
          <div className="price__delta" style={{ marginTop: "0.15rem" }}>
            <span className="price__label">volume z</span>
            <span className="num">{p.vol_z.toFixed(1)}σ</span>
          </div>
        </div>
      </header>

      <section className="section">
        <Sparkline points={detail.sparkline} />
      </section>

      {detail.thesis && (
        <section className="section">
          <div className="section__head">
            <h2 className="section__title">Your thesis</h2>
          </div>
          <motion.blockquote
            className="wl__thesis-quote"
            style={{ fontSize: "1.25rem", maxWidth: "44ch" }}
            initial={reduced ? false : { opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={reduced ? { duration: 0 } : { duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
          >
            {detail.thesis}
          </motion.blockquote>
          {entry?.thesis_added_at && (
            <span className="confront__when">written {day(entry.thesis_added_at)}</span>
          )}
        </section>
      )}

      <section className="section">
        <div className="section__head">
          <h2 className="section__title">Timeline</h2>
          <span className="section__note">
            {detail.timeline.length === 0
              ? "Nothing has cleared the gate for this symbol yet."
              : `${detail.timeline.length} recorded ${detail.timeline.length === 1 ? "change" : "changes"}, newest first. Append-only — corrections are added, never edited over.`}
          </span>
        </div>

        {detail.timeline.length === 0 ? (
          <div className="empty-note">
            Checked as of {asOf(detail.provenance.as_of)}. Nothing here is an absence of data — it is
            an absence of anything that passed two independent confirming factors.
          </div>
        ) : (
          <motion.ul
            className="stack timeline"
            variants={listVariants(!!reduced)}
            initial="hidden"
            animate="shown"
          >
            {detail.timeline.map((item, i) => (
              <motion.li key={item.event_id} variants={cardVariants(!!reduced)}>
                <ChangeCard item={item} rank={i + 1} readOnly thesisAddedAt={entry?.thesis_added_at} />
              </motion.li>
            ))}
          </motion.ul>
        )}
      </section>
    </div>
  );
}
