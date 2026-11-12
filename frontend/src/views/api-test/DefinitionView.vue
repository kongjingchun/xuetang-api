<!--
@File    : DefinitionView.vue
@Desc    : 定义 Tab 空壳。左侧目录，右侧保留方法色块和详情占位
@Author  : xuetang-api
@Date    : 2026-11-12
@Update  : 2026-11-12 初始化定义页
-->
<script setup lang="ts">
import SplitPane from "@/components/SplitPane.vue";

const tree = [
  {
    label: "用户端",
    children: [{ label: "用户登录  POST /api/v1/u/login" }],
  },
  {
    label: "管理端",
    children: [],
  },
];
</script>

<template>
  <SplitPane side-title="接口目录">
    <template #side>
      <el-tree :data="tree" default-expand-all />
    </template>
    <div>
      <p>
        <span class="method get">GET</span>
        <span class="method post">POST</span>
        <span class="method put">PUT</span>
        <span class="method delete">DELETE</span>
      </p>
      <el-tabs>
        <el-tab-pane label="请求参数" />
        <el-tab-pane label="请求体" />
        <el-tab-pane label="请求头" />
        <el-tab-pane label="前置" />
        <el-tab-pane label="后置" />
        <el-tab-pane label="断言" />
        <el-tab-pane label="Mock" />
      </el-tabs>
      <el-empty description="接口详情在阶段 2 实现。种子数据已包含用户登录示例。" />
    </div>
  </SplitPane>
</template>
