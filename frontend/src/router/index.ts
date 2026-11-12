/**
 * @File    : index.ts
 * @Desc    : 路由。接口测试固定四个子路径：定义、调试、场景、报告
 * @Author  : xuetang-api
 * @Date    : 2026-11-12
 * @Update  : 2026-11-12 初始化阶段 0 页面路由
 */

import { createRouter, createWebHistory } from "vue-router";
import { readAuth } from "@/api/http";
import { DEMO_PROJECT_ID } from "@/constants/project";
import MainLayout from "@/layouts/MainLayout.vue";
import ApiTestLayout from "@/views/api-test/ApiTestLayout.vue";
import DebugView from "@/views/api-test/DebugView.vue";
import DefinitionView from "@/views/api-test/DefinitionView.vue";
import ReportView from "@/views/api-test/ReportView.vue";
import ScenarioView from "@/views/api-test/ScenarioView.vue";
import PlaceholderView from "@/views/common/PlaceholderView.vue";
import DashboardView from "@/views/dashboard/DashboardView.vue";
import ChangePasswordView from "@/views/login/ChangePasswordView.vue";
import LoginView from "@/views/login/LoginView.vue";
import ProjectSettingsView from "@/views/settings/ProjectSettingsView.vue";
import SettingsView from "@/views/settings/SettingsView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: LoginView },
    { path: "/change-password", name: "change-password", component: ChangePasswordView },
    {
      path: "/",
      component: MainLayout,
      children: [
        { path: "", redirect: `/p/${DEMO_PROJECT_ID}/dashboard` },
        {
          path: "p/:projectId/dashboard",
          name: "dashboard",
          component: DashboardView,
        },
        {
          path: "p/:projectId/api-test",
          component: ApiTestLayout,
          children: [
            { path: "", redirect: (to) => `/p/${to.params.projectId}/api-test/definition` },
            { path: "definition", name: "api-definition", component: DefinitionView },
            { path: "debug", name: "api-debug", component: DebugView },
            { path: "scenario", name: "api-scenario", component: ScenarioView },
            { path: "report", name: "api-report", component: ReportView },
          ],
        },
        {
          path: "p/:projectId/test-plan",
          component: PlaceholderView,
          meta: { title: "测试计划", phase: 7 },
        },
        {
          path: "p/:projectId/review",
          component: PlaceholderView,
          meta: { title: "用例评审", phase: 7 },
        },
        {
          path: "p/:projectId/traffic",
          component: PlaceholderView,
          meta: { title: "流量录制", phase: 8 },
        },
        {
          path: "p/:projectId/data-factory",
          component: PlaceholderView,
          meta: { title: "数据工厂", phase: 9 },
        },
        {
          path: "p/:projectId/statistics",
          component: PlaceholderView,
          meta: { title: "统计看板", phase: 7 },
        },
        { path: "settings", name: "settings", component: SettingsView },
        { path: "p/:projectId/project-settings", name: "project-settings", component: ProjectSettingsView },
      ],
    },
  ],
});

router.beforeEach((to) => {
  const auth = readAuth();
  if (to.path === "/login") {
    if (!auth?.accessToken) {
      return true;
    }
    return auth.mustChangePassword ? "/change-password" : `/p/${DEMO_PROJECT_ID}/dashboard`;
  }
  if (!auth?.accessToken) {
    return "/login";
  }
  // 未改密时只能停留在改密页，避免绕过首次登录限制
  if (auth.mustChangePassword && to.path !== "/change-password") {
    return "/change-password";
  }
  if (!auth.mustChangePassword && to.path === "/change-password") {
    return `/p/${DEMO_PROJECT_ID}/dashboard`;
  }
  return true;
});

export default router;
