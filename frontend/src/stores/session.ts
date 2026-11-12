/**
 * @File    : session.ts
 * @Desc    : 登录会话。令牌放在 sessionStorage，密码不落本地
 * @Author  : xuetang-api
 * @Date    : 2026-11-13
 * @Update  : 2026-11-13 改为调用登录接口
 */

import { defineStore } from "pinia";
import { http, readAuth, writeAuth, type ApiBody, type AuthBag } from "@/api/http";

interface LoginData {
  access_token: string;
  refresh_token: string;
  must_change_password: boolean;
  user: {
    username: string;
    permissions: string[];
    must_change_password: boolean;
  };
}

export const useSessionStore = defineStore("session", {
  state: () => ({
    username: "",
    accessToken: "",
    refreshToken: "",
    mustChangePassword: false,
    permissions: [] as string[],
  }),
  actions: {
    /** 从 sessionStorage 恢复。没有记录时保持未登录。 */
    restore(): void {
      const bag = readAuth();
      this.applyBag(bag);
    },
    applyBag(bag: AuthBag | null): void {
      this.username = bag?.username || "";
      this.accessToken = bag?.accessToken || "";
      this.refreshToken = bag?.refreshToken || "";
      this.mustChangePassword = Boolean(bag?.mustChangePassword);
      this.permissions = bag?.permissions || [];
    },
    /** 账号密码登录。失败时由调用方展示错误，不写入会话。 */
    async login(username: string, password: string): Promise<void> {
      const response = await http.post<ApiBody<LoginData>>("/api/v1/auth/login", { username, password });
      const data = response.data.data;
      const bag: AuthBag = {
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
        username: data.user.username,
        mustChangePassword: data.must_change_password,
        permissions: data.user.permissions,
      };
      writeAuth(bag);
      this.applyBag(bag);
    },
    /** 修改自己的密码后解除首次登录限制。 */
    async changePassword(oldPassword: string, newPassword: string): Promise<void> {
      await http.put("/api/v1/auth/password", { old_password: oldPassword, new_password: newPassword });
      const bag = readAuth();
      if (bag) {
        bag.mustChangePassword = false;
        writeAuth(bag);
        this.applyBag(bag);
      }
    },
    /** 通知服务端拉黑令牌，然后清除本地会话。 */
    async logout(): Promise<void> {
      try {
        await http.post("/api/v1/auth/logout");
      } catch {
        // 网络失败也要清掉本地令牌，避免页面还以为已登录
      }
      writeAuth(null);
      this.applyBag(null);
    },
    has(code: string): boolean {
      return this.permissions.includes(code);
    },
  },
});
