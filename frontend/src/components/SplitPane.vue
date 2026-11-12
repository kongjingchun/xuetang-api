<!--
@File    : SplitPane.vue
@Desc    : 接口测试页左侧目录与右侧内容的可拖拽分栏，默认宽度 260
@Author  : xuetang-api
@Date    : 2026-11-12
@Update  : 2026-11-12 初始化分栏
-->
<script setup lang="ts">
import { onBeforeUnmount, ref } from "vue";

defineProps<{
  sideTitle: string;
}>();

const width = ref(260);
const dragging = ref(false);

/** 按鼠标位置调整左栏宽度，限制在 200 到 480 之间。 */
function onMove(event: MouseEvent): void {
  if (!dragging.value) {
    return;
  }
  const pane = document.querySelector(".split");
  if (!pane) {
    return;
  }
  const next = event.clientX - pane.getBoundingClientRect().left;
  width.value = Math.min(480, Math.max(200, next));
}

function stop(): void {
  dragging.value = false;
  window.removeEventListener("mousemove", onMove);
  window.removeEventListener("mouseup", stop);
}

function start(): void {
  dragging.value = true;
  window.addEventListener("mousemove", onMove);
  window.addEventListener("mouseup", stop);
}

onBeforeUnmount(stop);
</script>

<template>
  <div class="split">
    <aside class="split-side" :style="{ width: `${width}px` }">
      <div class="split-title">{{ sideTitle }}</div>
      <slot name="side" />
    </aside>
    <div class="split-resizer" @mousedown="start" />
    <section class="split-main">
      <slot />
    </section>
  </div>
</template>
