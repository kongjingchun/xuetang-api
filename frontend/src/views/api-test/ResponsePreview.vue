<!--
@File    : ResponsePreview.vue
@Desc    : 把 JSON 或 XML 响应显示成可展开的层级
@Author  : xuetang-api
@Date    : 2026-11-13
-->
<script setup lang="ts">
import { computed } from "vue";
import { parsePreview } from "@/utils/responseBody";
import PreviewNode from "@/views/api-test/PreviewNode.vue";

const props = defineProps<{ text: string }>();
const tree = computed(() => parsePreview(props.text));
</script>

<template>
  <div v-if="tree" class="resp-body preview-body">
    <PreviewNode :node="tree" :depth="0" />
  </div>
  <div v-else class="resp-body">{{ text }}</div>
</template>
