import type { AuthSession } from "./types";

export const SESSION_STORAGE_KEY = "fraud-ops.session";

type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export function readSession(storage: StorageLike | null | undefined): AuthSession | null {
  if (!storage) {
    return null;
  }

  const rawValue = storage.getItem(SESSION_STORAGE_KEY);
  if (!rawValue) {
    return null;
  }

  try {
    const parsed = JSON.parse(rawValue) as Partial<AuthSession>;
    if (!parsed.accessToken || !parsed.role || !parsed.tokenType || !parsed.username) {
      return null;
    }
    return parsed as AuthSession;
  } catch {
    return null;
  }
}

export function persistSession(storage: StorageLike | null | undefined, session: AuthSession): void {
  storage?.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
}

export function clearSession(storage: StorageLike | null | undefined): void {
  storage?.removeItem(SESSION_STORAGE_KEY);
}
