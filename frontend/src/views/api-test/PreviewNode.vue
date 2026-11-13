<!--
@File    : PreviewNode.vue
@Desc    : 响应预览里的一层节点，点击后展开或收起子节点
@Author  : xuetang-api
@Date    : 2026-11-13
-->
<script setup lang="ts">
import { ref } from "vue";
import type { PreviewNode } from "@/utils/responseBody";

const props = defineProps<{ node: PreviewNode; depth: number }>();
const open = ref(props.depth < 2);
const hasChildren = props.node.children.length > 0;

function toggle(): void {
  if (hasChildren) {
    open.value = !open.value;
  }
}

function summary(): string {
  return props.node.kind === "array" ? `[${props.node.value}]` : `{${props.node.value}}`;
}
</script>

<template>
  <div class="preview-node">
    <button type="button" class="preview-row" :class="{ foldable: hasChildren }" :style="{ paddingLeft: `${depth * 16}px` }" @click="toggle">
      <span class="preview-arrow" :class="{ open, empty: !hasChildren }">▸</span>
      <span class="preview-key">{{ node.label || "根" }}</span>
      <span v-if="hasChildren" class="preview-meta">{{ summary() }}</span>
      <span v-else :class="`preview-${node.kind}`">{{ node.kind === "string" ? `"${node.value}"` : node.value }}</span>
    </button>
    <template v-if="hasChildren && open">
      <PreviewNode v-for="child in node.children" :key="child.id" :node="child" :depth="depth + 1" />
    </template>
  </div>
</template>

<script lang="ts">
export default { name: "PreviewNode" };
</script>
