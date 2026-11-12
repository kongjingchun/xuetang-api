<!--
@File    : DashboardView.vue
@Desc    : 工作台。展示依赖健康状态和当前项目的真实计数
@Author  : xuetang-api
@Date    : 2026-11-12
@Update  : 2026-11-13 概览改为指标卡片
-->
<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { fetchHealth, type HealthData } from "@/api/health";
import { http, type ApiBody } from "@/api/http";

interface Overview {
  api_count: number;
  case_count: number;
  scenario_count: number;
  week_exec_count: number;
  week_pass_rate: number;
}

const route = useRoute();
const loading = ref(false);
const message = ref("");
const health = ref<HealthData | null>(null);
const overview = ref<Overview | null>(null);

async function load(): Promise<void> {
  loading.value = true;
  try {
    const body = await fetchHealth();
    health.value = body.data;
    message.value = body.message;
    const projectId = String(route.params.projectId || "");
    if (projectId) {
      const response = await http.get<ApiBody<Overview>>(`/api/v1/projects/${projectId}/overview`);
      overview.value = response.data.data;
    }
  } catch (error) {
    health.value = health.value;
    message.value = error instanceof Error ? error.message : "无法连接主服务";
  } finally {
    loading.value = false;
  }
}

function statusText(value: string | undefined): string {
  if (!value) {
    return "-";
  }
  if (value === "ok" || value === "success") {
    return "正常";
  }
  return value;
}

function statusType(value: string | undefined): "success" | "danger" | "info" {
  if (value === "ok" || value === "success") {
    return "success";
  }
  if (!value) {
    return "info";
  }
  return "danger";
}

onMounted(load);
watch(() => route.params.projectId, load);
</script>

<template>
  <div class="page" v-loading="loading">
    <div class="stat-grid">
      <article class="stat-card">
        <span class="stat-label">接口</span>
        <strong class="stat-value">{{ overview?.api_count ?? "-" }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">用例</span>
        <strong class="stat-value">{{ overview?.case_count ?? "-" }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">场景</span>
        <strong class="stat-value">{{ overview?.scenario_count ?? "-" }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">本周执行</span>
        <strong class="stat-value">{{ overview?.week_exec_count ?? "-" }}</strong>
        <span class="stat-extra">通过率 {{ overview?.week_pass_rate ?? "-" }}%</span>
      </article>
    </div>
    <el-card class="panel" shadow="never">
      <template #header>
        <div class="user-toolbar" style="margin: 0">
          <span>运行状态</span>
          <el-button @click="load">重新检查</el-button>
        </div>
      </template>
      <el-descriptions v-if="health" :column="2" border>
        <el-descriptions-item label="总体"><el-tag :type="statusType(health.status)">{{ statusText(health.status) }}</el-tag></el-descriptions-item>
        <el-descriptions-item label="说明">{{ message === "success" ? "服务可用" : message }}</el-descriptions-item>
        <el-descriptions-item label="MySQL"><el-tag :type="statusType(health.mysql)">{{ statusText(health.mysql) }}</el-tag></el-descriptions-item>
        <el-descriptions-item label="Redis"><el-tag :type="statusType(health.redis)">{{ statusText(health.redis) }}</el-tag></el-descriptions-item>
        <el-descriptions-item label="Python">{{ health.python }}</el-descriptions-item>
        <el-descriptions-item label="版本">{{ health.version }} / 阶段 {{ health.phase }}</el-descriptions-item>
      </el-descriptions>
      <el-empty v-else :description="message || '尚未获取状态'" />
    </el-card>
  </div>
</template>
