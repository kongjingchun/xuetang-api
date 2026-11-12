<!--
@File    : ScenarioView.vue
@Desc    : 场景 Tab 空壳。左侧场景树，右侧展示一条示例步骤
@Author  : xuetang-api
@Date    : 2026-11-12
@Update  : 2026-11-12 初始化场景页
-->
<script setup lang="ts">
import SplitPane from "@/components/SplitPane.vue";

const tree = [
  {
    label: "用户端",
    children: [{ label: "用户登录" }],
  },
];
</script>

<template>
  <SplitPane side-title="场景目录">
    <template #side>
      <el-tree :data="tree" default-expand-all />
    </template>
    <el-table :data="[{ name: '登录成功', type: '引用用例', order: 1 }]" border>
      <el-table-column prop="order" label="#" width="60" />
      <el-table-column prop="name" label="步骤" />
      <el-table-column prop="type" label="类型" />
    </el-table>
    <p class="hint">拖拽编排、逻辑控制器和执行会在阶段 4 实现。当前只展示种子场景的步骤结构。</p>
  </SplitPane>
</template>
