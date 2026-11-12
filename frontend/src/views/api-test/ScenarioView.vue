<!--
@File    : ScenarioView.vue
@Desc    : 场景页。左侧场景目录，右侧场景表格
@Author  : xuetang-api
@Date    : 2026-11-12
@Update  : 2026-11-13 按 MeterSphere 场景列表重做
-->
<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { ElMessage } from "element-plus";
import { http, type ApiBody } from "@/api/http";

interface ModuleRow {
  id: number;
  name: string;
}
interface SceneRow {
  id: number;
  name: string;
  level: string;
  status: string;
  tags: string;
  module_id: number | null;
  module: string;
  env_name: string;
  result: string;
}

const route = useRoute();
const projectId = computed(() => String(route.params.projectId || ""));
const modules = ref<ModuleRow[]>([]);
const items = ref<SceneRow[]>([]);
const keyword = ref("");
const folderKey = ref("all");

const visible = computed(() => {
  const text = keyword.value.trim().toLowerCase();
  return items.value.filter((item) => {
    const inFolder =
      folderKey.value === "all" ||
      (folderKey.value === "none" && item.module_id == null) ||
      folderKey.value === `m-${item.module_id}`;
    const matched = !text || `${item.name} ${item.tags} ${item.level}`.toLowerCase().includes(text);
    return inFolder && matched;
  });
});

function countOf(id: number | null): number {
  return items.value.filter((item) => (item.module_id ?? null) === id).length;
}

async function load(): Promise<void> {
  const response = await http.get<ApiBody<{ modules: ModuleRow[]; items: SceneRow[] }>>(
    `/api/v1/projects/${projectId.value}/scenarios`,
  );
  modules.value = response.data.data.modules;
  items.value = response.data.data.items;
}

function createHint(): void {
  ElMessage.info("场景编排会在阶段 4 接入，当前可以查看已有场景");
}

onMounted(() => {
  load().catch((error: unknown) => ElMessage.error(error instanceof Error ? error.message : "加载失败"));
});
watch(projectId, () => load());
</script>

<template>
  <div class="ms-page">
    <aside class="ms-side">
      <div class="ms-side-pad">
        <el-input v-model="keyword" clearable placeholder="请输入模块名称进行搜索" />
        <div class="ms-side-actions">
          <el-button type="primary" @click="createHint">新建场景</el-button>
          <el-button @click="createHint">导入场景</el-button>
        </div>
        <div class="ms-folder" :class="{ active: folderKey === 'all' }" @click="folderKey = 'all'">
          <span>全部场景</span>
          <span class="ms-count">{{ items.length }}</span>
        </div>
        <div class="ms-folder" :class="{ active: folderKey === 'none' }" @click="folderKey = 'none'">
          <span>未规划场景</span>
          <span class="ms-count">{{ countOf(null) }}</span>
        </div>
        <div
          v-for="folder in modules"
          :key="folder.id"
          class="ms-folder"
          :class="{ active: folderKey === `m-${folder.id}` }"
          @click="folderKey = `m-${folder.id}`"
        >
          <span>{{ folder.name }}</span>
          <span class="ms-count">{{ countOf(folder.id) }}</span>
        </div>
      </div>
    </aside>
    <section class="ms-main">
      <div class="ms-toolbar">
        <el-tag type="primary" effect="plain">全部场景</el-tag>
        <span class="doc-bar-gap" />
        <el-input v-model="keyword" clearable placeholder="通过 ID/名称/标签搜索" style="width: 240px" />
      </div>
      <el-table :data="visible" height="100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="场景名称" min-width="160" />
        <el-table-column prop="level" label="场景等级" width="110" />
        <el-table-column prop="status" label="状态" width="110" />
        <el-table-column label="执行结果" width="120">
          <template #default="{ row }">{{ row.result || "-" }}</template>
        </el-table-column>
        <el-table-column prop="tags" label="标签" width="120" />
        <el-table-column prop="env_name" label="场景环境" width="140" />
        <el-table-column label="操作" width="120">
          <template #default>
            <el-button link type="primary" @click="createHint">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!visible.length" description="暂无数据，请新建场景" />
    </section>
  </div>
</template>
