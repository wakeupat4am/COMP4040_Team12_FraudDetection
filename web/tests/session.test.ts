import assert from "node:assert/strict";
import test from "node:test";

import { clearSession, persistSession, readSession } from "../lib/session.ts";

function createStorage() {
  const values = new Map<string, string>();

  return {
    getItem(key: string) {
      return values.get(key) ?? null;
    },
    setItem(key: string, value: string) {
      values.set(key, value);
    },
    removeItem(key: string) {
      values.delete(key);
    },
  };
}

test("persistSession and readSession round trip", () => {
  const storage = createStorage();
  persistSession(storage, {
    accessToken: "token-123",
    role: "analyst",
    tokenType: "bearer",
    username: "analyst",
  });

  const session = readSession(storage);
  assert.deepEqual(session, {
    accessToken: "token-123",
    role: "analyst",
    tokenType: "bearer",
    username: "analyst",
  });
});

test("clearSession removes persisted auth state", () => {
  const storage = createStorage();
  persistSession(storage, {
    accessToken: "token-123",
    role: "manager_admin",
    tokenType: "bearer",
    username: "admin",
  });

  clearSession(storage);
  assert.equal(readSession(storage), null);
});
