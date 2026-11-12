/**
 * @File    : project.ts
 * @Desc    : 阶段 0 固定演示项目的对外 ID，和种子数据 PRJ_XUETANG 对齐
 * @Author  : xuetang-api
 * @Date    : 2026-11-12
 * @Update  : 2026-11-12 初始化阶段 0 前端常量
 */

/** 演示项目对外 ID。阶段 1 会改成从项目列表选择。 */
export const DEMO_PROJECT_ID = "PRJ_XUETANG";

/** 接口测试四个顶部 Tab，顺序和文案固定，不允许页面里再增减。 */
export const API_TEST_TABS = [
  { name: "definition", label: "定义" },
  { name: "debug", label: "调试" },
  { name: "scenario", label: "场景" },
  { name: "report", label: "报告" },
] as const;
