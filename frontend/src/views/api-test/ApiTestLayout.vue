<!--
@File    : ApiTestLayout.vue
@Desc    : 接口测试固定四个顶部 Tab：定义、调试、场景、报告
@Author  : xuetang-api
@Date    : 2026-11-12
@Update  : 2026-11-12 初始化四 Tab 布局
-->
<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { API_TEST_TABS } from "@/constants/project";

const route = useRoute();
const router = useRouter();

const active = computed(() => {
  const part = route.path.split("/").pop() || "definition";
  return API_TEST_TABS.some((item) => item.name === part) ? part : "definition";
});

function changeTab(name: string | number): void {
  const projectId = route.params.projectId;
  router.push(`/p/${projectId}/api-test/${name}`);
}
</script>

<template>
  <div class="api-test">
    <el-tabs class="api-tabs" :model-value="active" @tab-change="changeTab">
      <el-tab-pane v-for="tab in API_TEST_TABS" :key="tab.name" :label="tab.label" :name="tab.name" />
    </el-tabs>
    <router-view />
  </div>
</template>
