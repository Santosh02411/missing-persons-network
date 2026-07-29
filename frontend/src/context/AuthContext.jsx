import { createContext, useContext, useEffect, useState } from "react";
import * as authApi from "../api/auth";
import { clearTokens, getAccessToken, setTokens } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // On reload we have a token but no in-memory user -- fetch who it belongs
    // to. If the token's stale (expired refresh, revoked session, etc.) the
    // api client's interceptor already tried refreshing before this fails.
    const token = getAccessToken();
    if (!token) {
      setIsLoading(false);
      return;
    }
    authApi
      .fetchCurrentUser()
      .then(({ data }) => setUser(data))
      .catch(() => clearTokens())
      .finally(() => setIsLoading(false));
  }, []);

  async function login(credentials) {
    const { data: tokens } = await authApi.login(credentials);
    setTokens(tokens);
    const { data: currentUser } = await authApi.fetchCurrentUser();
    setUser(currentUser);
    return currentUser;
  }

  async function register(payload) {
    await authApi.registerAccount(payload);
    // Registration doesn't log the user in automatically -- authority
    // accounts start unverified, so surfacing that distinction on the
    // login screen (rather than silently signing them in) is clearer.
    return login({ email: payload.email, password: payload.password });
  }

  async function logout() {
    try {
      await authApi.logout();
    } catch {
      // Even if the network call fails, still clear local session state --
      // the person asked to log out and shouldn't stay "stuck" logged in.
    }
    clearTokens();
    setUser(null);
  }

  const value = {
    user,
    isLoading,
    isAuthenticated: Boolean(user),
    login,
    register,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
