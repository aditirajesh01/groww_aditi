import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  type ReactNode,
} from "react";
import { API_MODE, getClient } from "@/api/client";
import type { AddWatchInput, PatchWatchInput } from "@/api/client";
import type {
  ChangeItem,
  DigestResponse,
  HealthResponse,
  SignalKind,
  WatchlistResponse,
} from "@/api/types";

export interface Toast {
  id: number;
  text: string;
  detail?: string;
  undo?: () => void;
  tone: "neutral" | "warn";
}

interface State {
  status: "loading" | "ready" | "error";
  error: string | null;
  digest: DigestResponse | null;
  /** Working copy of the ranked list. Ack and dismiss mutate this optimistically. */
  items: ChangeItem[];
  corrections: ChangeItem[];
  /** Cards cleared in this session — the number that makes inbox zero feel earned. */
  cleared: number;
  /** Locally dismissed items, added to budget.suppressed as it happens. */
  suppressedDelta: number;
  watchlist: WatchlistResponse | null;
  health: HealthResponse | null;
  toasts: Toast[];
  busy: boolean;
}

type Action =
  | { type: "load/start" }
  | { type: "load/ok"; digest: DigestResponse; watchlist: WatchlistResponse; health: HealthResponse }
  | { type: "load/fail"; error: string }
  | { type: "item/ack"; eventId: string }
  | { type: "item/dismiss"; eventId: string }
  | { type: "item/restore"; item: ChangeItem; wasDismissal: boolean }
  | { type: "watchlist/set"; watchlist: WatchlistResponse }
  | { type: "toast/push"; toast: Toast }
  | { type: "toast/pop"; id: number }
  | { type: "busy"; busy: boolean };

const initial: State = {
  status: "loading",
  error: null,
  digest: null,
  items: [],
  corrections: [],
  cleared: 0,
  suppressedDelta: 0,
  watchlist: null,
  health: null,
  toasts: [],
  busy: false,
};

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "load/start":
      return { ...state, status: "loading", error: null };
    case "load/ok":
      return {
        ...state,
        status: "ready",
        error: null,
        digest: action.digest,
        items: action.digest.items,
        corrections: action.digest.corrections,
        watchlist: action.watchlist,
        health: action.health,
        cleared: 0,
        suppressedDelta: 0,
      };
    case "load/fail":
      return { ...state, status: "error", error: action.error };
    case "item/ack":
      return {
        ...state,
        items: state.items.filter((i) => i.event_id !== action.eventId),
        corrections: state.corrections.filter((i) => i.event_id !== action.eventId),
        cleared: state.cleared + 1,
      };
    case "item/dismiss":
      return {
        ...state,
        items: state.items.filter((i) => i.event_id !== action.eventId),
        cleared: state.cleared + 1,
        suppressedDelta: state.suppressedDelta + 1,
      };
    case "item/restore": {
      const isCorrection = action.item.signals.some((s) => s.kind === "CORRECTION");
      const list = isCorrection ? state.corrections : state.items;
      if (list.some((i) => i.event_id === action.item.event_id)) return state;
      const next = [...list, action.item].sort((a, b) => b.attention - a.attention);
      return {
        ...state,
        items: isCorrection ? state.items : next,
        corrections: isCorrection ? next : state.corrections,
        cleared: Math.max(0, state.cleared - 1),
        suppressedDelta: Math.max(0, state.suppressedDelta - (action.wasDismissal ? 1 : 0)),
      };
    }
    case "watchlist/set":
      return { ...state, watchlist: action.watchlist };
    case "toast/push":
      return { ...state, toasts: [...state.toasts.slice(-2), action.toast] };
    case "toast/pop":
      return { ...state, toasts: state.toasts.filter((t) => t.id !== action.id) };
    case "busy":
      return { ...state, busy: action.busy };
    default:
      return state;
  }
}

interface Store extends State {
  mode: typeof API_MODE;
  /** Everything the header needs about the attention budget, post-interaction. */
  budget: { cap: number; shown: number; suppressed: number };
  unread: number;
  inboxZero: boolean;
  refresh: () => Promise<void>;
  ack: (item: ChangeItem) => Promise<void>;
  ackAll: () => Promise<void>;
  dismiss: (item: ChangeItem, kind: SignalKind) => Promise<void>;
  addWatch: (input: AddWatchInput) => Promise<void>;
  patchWatch: (symbol: string, patch: PatchWatchInput) => Promise<void>;
  removeWatch: (symbol: string) => Promise<void>;
  advanceSim: (hours: number) => Promise<void>;
  dismissToast: (id: number) => void;
}

const Ctx = createContext<Store | null>(null);

let toastSeq = 0;

export function StoreProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initial);
  const timers = useRef<number[]>([]);

  const pushToast = useCallback((toast: Omit<Toast, "id">) => {
    const id = ++toastSeq;
    dispatch({ type: "toast/push", toast: { ...toast, id } });
    const handle = window.setTimeout(() => dispatch({ type: "toast/pop", id }), 6000);
    timers.current.push(handle);
  }, []);

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  const refresh = useCallback(async () => {
    dispatch({ type: "load/start" });
    try {
      const api = await getClient();
      const [digest, watchlist, health] = await Promise.all([
        api.getDigest(),
        api.getWatchlist(),
        api.getHealth(),
      ]);
      dispatch({ type: "load/ok", digest, watchlist, health });
    } catch (err) {
      dispatch({ type: "load/fail", error: err instanceof Error ? err.message : String(err) });
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const ack = useCallback(
    async (item: ChangeItem) => {
      dispatch({ type: "item/ack", eventId: item.event_id });
      try {
        const api = await getClient();
        await api.ackDigest([item.event_id]);
      } catch {
        dispatch({ type: "item/restore", item, wasDismissal: false });
        pushToast({ text: `Could not mark ${item.symbol} as read`, tone: "warn" });
      }
    },
    [pushToast],
  );

  const ackAll = useCallback(async () => {
    const all = [...state.items, ...state.corrections];
    if (all.length === 0) return;
    for (const item of all) dispatch({ type: "item/ack", eventId: item.event_id });
    try {
      const api = await getClient();
      await api.ackDigest(all.map((i) => i.event_id));
    } catch {
      for (const item of all) dispatch({ type: "item/restore", item, wasDismissal: false });
      pushToast({ text: "Could not advance the read cursor", tone: "warn" });
    }
  }, [state.items, state.corrections, pushToast]);

  const dismiss = useCallback(
    async (item: ChangeItem, kind: SignalKind) => {
      dispatch({ type: "item/dismiss", eventId: item.event_id });
      pushToast({
        text: `Fewer ${kind.toLowerCase().replace(/_/g, " ")} signals for ${item.symbol}`,
        detail: "Dismissal teaches a personal threshold. It does not hide corrections or thesis contradictions.",
        tone: "neutral",
        undo: () => dispatch({ type: "item/restore", item, wasDismissal: true }),
      });
      try {
        const api = await getClient();
        await api.dismiss(item.event_id, kind);
      } catch {
        dispatch({ type: "item/restore", item, wasDismissal: true });
        pushToast({ text: `Could not dismiss ${item.symbol}`, tone: "warn" });
      }
    },
    [pushToast],
  );

  const reloadWatchlist = useCallback(async () => {
    const api = await getClient();
    dispatch({ type: "watchlist/set", watchlist: await api.getWatchlist() });
  }, []);

  const addWatch = useCallback(
    async (input: AddWatchInput) => {
      dispatch({ type: "busy", busy: true });
      try {
        const api = await getClient();
        const entry = await api.addWatch(input);
        await reloadWatchlist();
        pushToast({
          text: `${entry.symbol} added`,
          detail: entry.thesis
            ? `We will check "${entry.thesis}" against dated evidence.`
            : "No thesis written — contradiction checks are off for this one.",
          tone: "neutral",
        });
      } catch (err) {
        pushToast({ text: err instanceof Error ? err.message : "Could not add", tone: "warn" });
        throw err;
      } finally {
        dispatch({ type: "busy", busy: false });
      }
    },
    [pushToast, reloadWatchlist],
  );

  const patchWatch = useCallback(
    async (symbol: string, patch: PatchWatchInput) => {
      const api = await getClient();
      await api.patchWatch(symbol, patch);
      await reloadWatchlist();
      if (patch.thesis !== undefined) {
        pushToast({
          text: patch.thesis ? `Thesis saved for ${symbol}` : `Thesis cleared for ${symbol}`,
          tone: "neutral",
        });
      }
    },
    [pushToast, reloadWatchlist],
  );

  const removeWatch = useCallback(
    async (symbol: string) => {
      const api = await getClient();
      await api.removeWatch(symbol);
      await reloadWatchlist();
      pushToast({ text: `${symbol} removed from your watchlist`, tone: "neutral" });
    },
    [pushToast, reloadWatchlist],
  );

  const advanceSim = useCallback(
    async (hours: number) => {
      dispatch({ type: "busy", busy: true });
      try {
        const api = await getClient();
        await api.advanceSim(hours);
        await refresh();
        pushToast({ text: `Replay clock advanced ${hours}h`, tone: "neutral" });
      } finally {
        dispatch({ type: "busy", busy: false });
      }
    },
    [refresh, pushToast],
  );

  const value = useMemo<Store>(() => {
    const cap = state.digest?.budget.cap ?? 0;
    const baseSuppressed = state.digest?.budget.suppressed ?? 0;
    const unread = [...state.items, ...state.corrections].filter((i) => i.is_unread).length;
    return {
      ...state,
      mode: API_MODE,
      budget: {
        cap,
        shown: state.items.length,
        suppressed: baseSuppressed + state.suppressedDelta,
      },
      unread,
      inboxZero:
        state.status === "ready" && state.items.length === 0 && state.corrections.length === 0,
      refresh,
      ack,
      ackAll,
      dismiss,
      addWatch,
      patchWatch,
      removeWatch,
      advanceSim,
      dismissToast: (id: number) => dispatch({ type: "toast/pop", id }),
    };
  }, [state, refresh, ack, ackAll, dismiss, addWatch, patchWatch, removeWatch, advanceSim]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useStore(): Store {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useStore must be used inside <StoreProvider>");
  return ctx;
}
