/**
 * @File    : http.ts
 * @Desc    : 统一请求。自动带访问令牌，业务 code 非 0 时抛出后端文案
 * @Author  : xuetang-api
 * @Date    : 2026-11-13
 * @Update  : 2026-11-13 接入登录态
 */

import axios, { type AxiosRequestConfig } from "axios";

const STORAGE_KEY = "xt_auth";

export interface AuthBag {
  accessToken: string;
  refreshToken: string;
  username: string;
  mustChangePassword: boolean;
  permissions: string[];
}

export interface ApiBody<T> {
  code: number;
  message: string;
  data: T;
}

/** 读取本地会话。刷新页面后仍然保留，直到关闭浏览器。 */
export function readAuth(): AuthBag | null {
  const raw = sessionStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as AuthBag;
  } catch {
    return null;
  }
}

/** 写入或清除本地会话。 */
export function writeAuth(bag: AuthBag | null): void {
  if (!bag) {
    sessionStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem("xt_session");
    return;
  }
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(bag));
}

export const http = axios.create({
  // 401 也要把 JSON 交给拦截器，登录失败才能显示后端文案
  validateStatus: () => true,
});

http.interceptors.request.use((config) => {
  const auth = readAuth();
  if (auth?.accessToken) {
    config.headers.Authorization = `Bearer ${auth.accessToken}`;
  }
  return config;
});

http.interceptors.response.use(async (response) => {
  const body = response.data as ApiBody<unknown> | string;
  if (!body || typeof body !== "object" || typeof body.code !== "number") {
    throw new Error("主服务没有返回 JSON");
  }
  if (body.code === 0) {
    return response;
  }
  const config = response.config as AxiosRequestConfig & { retried?: boolean };
  const url = config.url || "";
  const canRefresh = body.code === 4010 && !config.retried && !url.includes("/auth/login") && !url.includes("/auth/refresh");
  const auth = readAuth();
  if (canRefresh && auth?.refreshToken) {
    config.retried = true;
    const refreshed = await http.post<ApiBody<{ access_token: string; refresh_token: string }>>("/api/v1/auth/refresh", {
      refresh_token: auth.refreshToken,
    });
    const next = refreshed.data.data;
    writeAuth({ ...auth, accessToken: next.access_token, refreshToken: next.refresh_token });
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${next.access_token}`;
    return http.request(config);
  }
  throw new Error(body.message || "请求失败");
});
