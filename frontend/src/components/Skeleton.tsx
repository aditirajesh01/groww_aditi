const bar = "animate-pulse rounded-md bg-gray-200 dark:bg-gray-800";

/** Loading state that holds the layout it is about to become, so nothing jumps. */
export function DigestSkeleton() {
  return (
    <div className="mx-auto max-w-5xl px-6 py-8" aria-busy="true" aria-label="Loading your digest">
      <div className="rounded-2xl border border-gray-200 bg-white p-8 dark:border-gray-800 dark:bg-gray-900">
        <div className={`${bar} h-8 w-[min(22ch,100%)]`} />
        <div className={`${bar} mt-2 h-8 w-[min(16ch,80%)]`} />
        <div className={`${bar} mt-5 h-4 w-[min(46ch,100%)]`} />
        <div className="mt-6 flex gap-10">
          {[0, 1, 2].map((i) => (
            <div key={i}>
              <div className={`${bar} h-6 w-12`} />
              <div className={`${bar} mt-1.5 h-3 w-20`} />
            </div>
          ))}
        </div>
      </div>
      <ul className="mt-6 flex flex-col gap-4">
        {[0, 1, 2].map((i) => (
          <li key={i} style={{ opacity: 1 - i * 0.22 }}>
            <div className="grid grid-cols-[4rem_1fr] overflow-hidden rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
              <div className="flex flex-col items-center gap-2 border-r border-gray-100 p-4 dark:border-gray-800">
                <div className={`${bar} h-4 w-6`} />
                <div className={`${bar} h-12 w-1.5`} />
              </div>
              <div className="p-5">
                <div className={`${bar} h-4 w-36`} />
                <div className={`${bar} mt-4 h-6 w-[min(38ch,100%)]`} />
                <div className={`${bar} mt-1.5 h-6 w-[min(28ch,80%)]`} />
                <div className={`${bar} mt-4 h-3 w-[min(52ch,100%)]`} />
                <div className={`${bar} mt-1.5 h-3 w-[min(44ch,90%)]`} />
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
