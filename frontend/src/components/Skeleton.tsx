/** Loading state that holds the layout it is about to become, so nothing jumps. */
export function DigestSkeleton() {
  return (
    <div className="wrap" aria-busy="true" aria-label="Loading your digest">
      <div className="digest-head">
        <div className="skel" style={{ height: "2.2rem", width: "min(22ch, 100%)" }} />
        <div className="skel" style={{ height: "2.2rem", width: "min(16ch, 80%)", marginTop: "0.5rem" }} />
        <div className="skel" style={{ height: "1rem", width: "min(46ch, 100%)", marginTop: "1.25rem" }} />
        <div className="stat-row">
          {[0, 1, 2].map((i) => (
            <div className="stat" key={i}>
              <div className="skel" style={{ height: "1.2rem", width: "3rem" }} />
              <div className="skel" style={{ height: "0.7rem", width: "5rem", marginTop: "0.35rem" }} />
            </div>
          ))}
        </div>
      </div>
      <div className="section">
        <ul className="stack">
          {[0, 1, 2].map((i) => (
            <li key={i}>
              <div className="card" style={{ opacity: 1 - i * 0.22 }}>
                <div className="rail">
                  <div className="skel" style={{ height: "1rem", width: "1.6rem" }} />
                  <div className="skel" style={{ flex: 1, width: "4px", minHeight: "3rem" }} />
                </div>
                <div className="card__body">
                  <div className="skel" style={{ height: "0.9rem", width: "9rem" }} />
                  <div className="skel" style={{ height: "1.4rem", width: "min(38ch, 100%)", marginTop: "1rem" }} />
                  <div className="skel" style={{ height: "1.4rem", width: "min(28ch, 80%)", marginTop: "0.4rem" }} />
                  <div className="skel" style={{ height: "0.8rem", width: "min(52ch, 100%)", marginTop: "1rem" }} />
                  <div className="skel" style={{ height: "0.8rem", width: "min(44ch, 90%)", marginTop: "0.35rem" }} />
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
