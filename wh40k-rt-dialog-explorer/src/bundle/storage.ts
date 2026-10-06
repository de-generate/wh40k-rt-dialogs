import { del, get, set } from "idb-keyval";

// The user's bundle, kept in IndexedDB between visits.
const KEY = "bundle";

export async function loadStoredBundle(): Promise<Blob | undefined> {
  return get<Blob>(KEY);
}

export async function storeBundle(blob: Blob): Promise<void> {
  await set(KEY, blob);
  // Best effort: without persistence the browser may evict the bundle under storage pressure.
  await navigator.storage?.persist?.().catch(() => false);
}

export async function clearStoredBundle(): Promise<void> {
  await del(KEY);
}
