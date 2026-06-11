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
  const [user, setUser] = useState<User | null>(getStoredUser);
  const [loading, setLoading] = useState(!getStoredUser());

  const fetchMe = useCallback(async () => {
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

  const logout = useCallback(() => {
    clearAuth();
    setUser(null);
  }, []);

  return { user, loading, login, logout, refresh: fetchMe };
}
