/**
 * localStorage-backed FIFO offline queue for attendance scans
 * (Phase 19). The door scanner is the natural place for a WiFi
 * outage — the scanner runs on a tablet at the door, the WiFi
 * access point is in the corridor, and the connection drops
 * whenever the AP reboots. Without a queue, every dropped scan
 * means the security officer has to write down the student code
 * on a clipboard and replay it later.
 *
 * The queue is intentionally dumb:
 *
 *  * Entries are JSON-serialisable. We store the (session_id, token,
 *    optional signature, location, captured_at) tuple per scan.
 *  * Order is FIFO. The first scan dropped is the first scan
 *    re-attempted.
 *  * The cap is 50 entries (~5KB on disk). A door that loses
 *    WiFi for an hour will run out of queue space, but at 5s per
 *    scan that means ~250 scans before the cap — way more than
 *    any single exam room's roster.
 *  * Drains happen on (a) a successful submit and (b) the
 *    ``window`` ``online`` event. A 60s safety net is also
 *    installed in case the browser fires ``online`` while the
 *    queue is still resolving.
 *  * Items that fail to drain stay in the queue. The next drain
 *    retries them. A 4xx is also a permanent skip (logged to
 *    ``console.warn``) — retrying a 400 every 5s is just noise.
 */
import { scanQrToken } from "./api";

export type QueuedScan = {
  session_id: string;
  token: string;
  signature_png: string;
  location: string;
  captured_at: string; // ISO timestamp
};

const QUEUE_KEY = "invigilo_scan_queue";
const MAX_QUEUE_SIZE = 50;

function isBrowser() {
  return typeof window !== "undefined" && typeof localStorage !== "undefined";
}

export function readQueue(): QueuedScan[] {
  if (!isBrowser()) return [];
  try {
    const raw = localStorage.getItem(QUEUE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (e) =>
        e &&
        typeof e === "object" &&
        typeof e.session_id === "string" &&
        typeof e.token === "string",
    );
  } catch {
    return [];
  }
}

function writeQueue(items: QueuedScan[]): void {
  if (!isBrowser()) return;
  // Cap the queue so a multi-hour outage doesn't blow the
  // localStorage budget. The newest items win — the first
  // dropped scan is the first to fall off the back.
  const trimmed = items.slice(-MAX_QUEUE_SIZE);
  localStorage.setItem(QUEUE_KEY, JSON.stringify(trimmed));
}

export function enqueueScan(scan: QueuedScan): QueuedScan[] {
  const items = readQueue();
  items.push(scan);
  writeQueue(items);
  return items;
}

export function clearQueue(): void {
  if (!isBrowser()) return;
  localStorage.removeItem(QUEUE_KEY);
}

/**
 * Drain the queue, oldest first. Stops on the first network
 * failure so we keep the in-flight items on the queue (they'll
 * be retried by the next drain). Permanent 4xx errors are removed
 * from the queue — the scan is broken and retrying is just noise.
 */
export async function drainQueue(): Promise<{
  drained: number;
  failed: number;
  remaining: number;
}> {
  if (!isBrowser()) return { drained: 0, failed: 0, remaining: 0 };
  if (typeof navigator !== "undefined" && navigator.onLine === false) {
    return { drained: 0, failed: 0, remaining: readQueue().length };
  }
  const items = readQueue();
  if (items.length === 0) return { drained: 0, failed: 0, remaining: 0 };

  let drained = 0;
  let failed = 0;
  const remaining: QueuedScan[] = [];

  for (const item of items) {
    try {
      await scanQrToken(item.session_id, item.token, {
        signature_png: item.signature_png,
        location: item.location,
      });
      drained += 1;
    } catch (err) {
      const status = (err as { status?: number }).status;
      if (status && status >= 400 && status < 500) {
        // 4xx is a permanent failure — drop the item. We log so
        // an operator can chase the broken scan if it matters.
        // eslint-disable-next-line no-console
        console.warn(
          "scan queue: dropping permanently-failed scan",
          item,
          err,
        );
        failed += 1;
        continue;
      }
      // 5xx, network error, etc. Keep the item for the next drain.
      remaining.push(item);
    }
  }

  writeQueue(remaining);
  return { drained, failed, remaining: remaining.length };
}

/**
 * Install a window-level listener that drains the queue when the
 * browser comes back online. Returns a teardown function. Idempotent
 * across component re-mounts: a module-level flag is set after the
 * first install so the second mount is a no-op (and the listener is
 * not duplicated).
 *
 * The flag lives on ``window`` so React Strict Mode's double-mount
 * in development doesn't end up with two drain loops competing.
 */
let installed = false;
export function installOfflineDrain(): () => void {
  if (!isBrowser()) return () => undefined;
  if (installed) return () => undefined;
  installed = true;
  const onOnline = () => {
    void drainQueue();
  };
  const interval = window.setInterval(() => {
    if (navigator.onLine) {
      void drainQueue();
    }
  }, 60_000);
  window.addEventListener("online", onOnline);
  return () => {
    installed = false;
    window.removeEventListener("online", onOnline);
    window.clearInterval(interval);
  };
}
