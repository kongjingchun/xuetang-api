<!--
@File    : MainLayout.vue
@Desc    : 后台主框架。按权限显示菜单，顶部可切换项目
@Author  : xuetang-api
@Date    : 2026-11-12
@Update  : 2026-11-13 侧栏图标和顶栏用户信息
-->
<script setup lang="ts">
import { computed, onMounted, ref, watch, type Component } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  Box,
  Calendar,
  Connection,
  DocumentChecked,
  FolderOpened,
  Odometer,
  Setting,
  TrendCharts,
  VideoCamera,
} from "@element-plus/icons-vue";
import { http, type ApiBody } from "@/api/http";
import { useSessionStore } from "@/stores/session";

interface ProjectItem {
  public_id: string;
  name: string;
  status: string;
}

const route = useRoute();
const router = useRouter();
const session = useSessionStore();
const projects = ref<ProjectItem[]>([]);
const selectedId = ref("");

const projectId = computed(() => String(route.params.projectId || selectedId.value || ""));

const activeMenu = computed(() => {
  if (route.path.includes("/api-test")) {
    return `/p/${projectId.value}/api-test/definition`;
  }
  if (route.path.startsWith("/settings")) {
    return "/settings";
  }
  return route.path;
});

const menuIcons: Record<string, Component> = {
  "menu:dashboard": Odometer,
  "menu:api-test": Connection,
  "menu:test-plan": Calendar,
  "menu:review": DocumentChecked,
  "menu:traffic": VideoCamera,
  "menu:data-factory": Box,
  "menu:statistics": TrendCharts,
  "menu:settings": Setting,
  "project-settings": FolderOpened,
};

const menus = computed(() => {
  const id = projectId.value;
  const items = [
    { code: "menu:dashboard", index: `/p/${id}/dashboard`, label: "工作台" },
    { code: "menu:api-test", index: `/p/${id}/api-test/definition`, label: "接口测试" },
    { code: "menu:test-plan", index: `/p/${id}/test-plan`, label: "测试计划" },
    { code: "menu:review", index: `/p/${id}/review`, label: "用例评审" },
    { code: "menu:traffic", index: `/p/${id}/traffic`, label: "流量录制" },
    { code: "menu:data-factory", index: `/p/${id}/data-factory`, label: "数据工厂" },
    { code: "menu:statistics", index: `/p/${id}/statistics`, label: "统计看板" },
    { code: "menu:settings", index: "/settings", label: "系统设置" },
  ];
  const canConfig = ["member:manage", "env:manage", "variable:manage", "script:manage", "datasource:manage"].some((code) =>
    session.has(code),
  );
  const visible = items.filter((item) => session.has(item.code));
  if (canConfig && id) {
    visible.push({ code: "project-settings", index: `/p/${id}/project-settings`, label: "项目配置" });
  }
  return visible;
});

const pageTitle = computed(() => menus.value.find((item) => item.index === activeMenu.value)?.label || "学堂在线");
const initial = computed(() => (session.username || "用").slice(0, 1).toUpperCase());

async function loadProjects(): Promise<void> {
  const response = await http.get<ApiBody<ProjectItem[]>>("/api/v1/projects");
  projects.value = response.data.data;
  if (!selectedId.value && projects.value.length > 0) {
    selectedId.value = String(route.params.projectId || projects.value[0].public_id);
  }
}

function onProjectChange(id: string): void {
  selectedId.value = id;
  if (route.path.startsWith("/p/")) {
    router.push(route.path.replace(/^\/p\/[^/]+/, `/p/${id}`));
  }
}

async function logout(): Promise<void> {
  await session.logout();
  router.push("/login");
}

onMounted(async () => {
  session.restore();
  selectedId.value = String(route.params.projectId || "");
  try {
    await loadProjects();
  } catch {
    projects.value = [];
  }
});

watch(
  () => route.params.projectId,
  (value) => {
    if (value) {
      selectedId.value = String(value);
    }
  },
);
</script>

<template>
  <el-container class="shell">
    <el-aside class="sidebar" width="232px">
      <div class="brand">
        <span class="brand-mark">学堂</span>
        <span>
          <strong>学堂在线</strong>
          <small>接口测试平台</small>
        </span>
      </div>
      <el-menu class="sidebar-menu" :key="activeMenu" :default-active="activeMenu" :router="true">
        <el-menu-item v-for="item in menus" :key="item.index" :index="item.index">
          <el-icon><component :is="menuIcons[item.code]" /></el-icon>
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <div class="header-title">
          <h1>{{ pageTitle }}</h1>
        </div>
        <div class="header-actions">
          <el-select class="project-select" :model-value="selectedId" placeholder="选择项目" @change="onProjectChange">
            <el-option v-for="item in projects" :key="item.public_id" :label="item.name" :value="item.public_id" />
          </el-select>
          <el-dropdown trigger="click">
            <span class="user-chip">
              <span class="avatar">{{ initial }}</span>
              {{ session.username || "未登录" }}
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="logout">退出</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main class="content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>
