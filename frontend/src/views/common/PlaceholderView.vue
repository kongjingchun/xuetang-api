<!--
@File    : PlaceholderView.vue
@Desc    : 尚未实现的菜单页，只说明计划中的阶段，避免做成可操作的假功能
@Author  : xuetang-api
@Date    : 2026-11-12
@Update  : 2026-11-13 占位页改为阶段说明卡片
-->
<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";

const route = useRoute();
const title = computed(() => String(route.meta.title || "功能"));
const phase = computed(() => Number(route.meta.phase || 0));
</script>

<template>
  <div class="page">
    <section class="empty-stage">
      <span class="phase-badge">阶段 {{ phase }}</span>
      <h2>{{ title }}</h2>
      <p>{{ title }}将在阶段 {{ phase }} 实现，当前还不能操作。</p>
    </section>
  </div>
</template>
