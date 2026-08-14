"use client";

import { useEffect, useState, useCallback } from "react";
import { authApi, storeTokens, clearTokens, getAccessToken, AUTH_EXPIRED_EVENT, type User } from "./api";

const USER_KEY = "gka_user";

export function getStoredUser(): User | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function clearStoredUser() {
  localStorage.removeItem(USER_KEY);
}

export function clearAuth() {
  clearTokens();
  clearStoredUser();
}

export function useAuth() {
  // Both start SSR-safe (null / loading) so the first render is identical on
  // server and client — getStoredUser() reads localStorage, which doesn't
  // exist during SSR, so calling it in a useState initializer previously
  // made the client's first render diverge from the server's and triggered
  // a hydration mismatch. The cached-user check now happens inside fetchMe,
  // which only ever runs client-side inside a useEffect.
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchMe = useCallback(async () => {
    // Optimistically show the cached user immediately (avoids a loading
    // flash for returning users) while still validating against the API below.
    const cached = getStoredUser();
    if (cached) {
      setUser(cached);
      setLoading(false);
    }
    if (!getAccessToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await authApi.me();
      localStorage.setItem(USER_KEY, JSON.stringify(me));
      setUser(me);
    } catch {
      clearAuth();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMe();
  }, [fetchMe]);

  // Force-logout when the refresh token is exhausted
  useEffect(() => {
    const handler = () => {
      clearStoredUser();
      setUser(null);
    };
    window.addEventListener(AUTH_EXPIRED_EVENT, handler);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, handler);
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const tokens = await authApi.login(email, password);
      storeTokens(tokens.access_token, tokens.refresh_token);
      await fetchMe();
    },
    [fetchMe]
  );

  const loginWithTokens = useCallback(
    async (accessToken: string, refreshToken: string) => {
      storeTokens(accessToken, refreshToken);
      await fetchMe();
    },
    [fetchMe]
  );

  const logout = useCallback(() => {
    clearAuth();
    setUser(null);
  }, []);

  return { user, loading, login, loginWithTokens, logout, refresh: fetchMe };
}
