/**
 * @File    : health.ts
 * @Desc    : 健康检查接口封装。地址为 GET /api/v1/health
 * @Author  : xuetang-api
 * @Date    : 2026-11-12
 * @Update  : 2026-11-12 初始化阶段 0 前端请求
 */

import axios from "axios";

/** 后端统一响应。code 为 0 表示成功。 */
export interface ApiBody<T> {
  code: number;
  message: string;
  data: T;
}

/** 健康检查 data 字段。mysql 与 redis 只有 ok 或 unavailable。 */
export interface HealthData {
  status: string;
  mysql: string;
  redis: string;
  python: string;
  version: string;
  phase: number;
}

/**
 * 读取主服务健康状态。
 * 依赖不可用时 HTTP 为 503，axios 会抛错，调用方需要读 response.data。
 */
export async function fetchHealth(): Promise<ApiBody<HealthData>> {
  const response = await axios.get<ApiBody<HealthData>>("/api/v1/health", {
    // 503 也要把 JSON 交给页面，用来显示是 MySQL 还是 Redis 不可用
    validateStatus: () => true,
  });
  const body = response.data;
  if (!body || typeof body !== "object" || typeof body.code !== "number") {
    throw new Error("主服务没有返回 JSON");
  }
  return body;
}
