import axios, { AxiosError } from "axios";

export const TOKEN_KEY = "dedupe.token";

export const api = axios.create({ baseURL: "/api/v1", timeout: 60_000 });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (error: AxiosError) => {
    const isAuthCall = error.config?.url?.startsWith("/auth/login");
    if (error.response?.status === 401 && !isAuthCall) {
      // Session expired: clear it and let the router send the user to sign in.
      localStorage.removeItem(TOKEN_KEY);
      window.dispatchEvent(new Event("dedupe:logout"));
    }
    return Promise.reject(error);
  },
);

interface ApiErrorBody {
  error?: { code: string; message: string; details?: unknown };
}

export function errorMessage(err: unknown, fallback = "Something went wrong. Try again."): string {
  if (axios.isAxiosError(err)) {
    const body = err.response?.data as ApiErrorBody | undefined;
    if (body?.error?.message) return body.error.message;
    if (err.code === "ERR_NETWORK") return "Can't reach the server. Check your connection.";
    if (err.code === "ECONNABORTED") return "The request took too long. Try again.";
  }
  return fallback;
}

export function errorDetails<T = unknown>(err: unknown): T | undefined {
  if (axios.isAxiosError(err)) return (err.response?.data as ApiErrorBody | undefined)?.error?.details as T | undefined;
  return undefined;
}
