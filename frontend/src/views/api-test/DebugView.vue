<!--
@File    : DebugView.vue
@Desc    : 调试 Tab 空壳。上半部分预留请求，下半部分预留响应
@Author  : xuetang-api
@Date    : 2026-11-12
@Update  : 2026-11-12 初始化调试页
-->
<script setup lang="ts">
import SplitPane from "@/components/SplitPane.vue";

const history = [{ label: "调试历史（阶段 3 写入）" }];
</script>

<template>
  <SplitPane side-title="调试">
    <template #side>
      <el-tree :data="history" />
    </template>
    <el-row :gutter="16">
      <el-col :span="24">
        <el-card shadow="never">
          <template #header>请求</template>
          <el-empty description="选择环境并发送请求将在阶段 3 实现" />
        </el-card>
      </el-col>
      <el-col :span="24" style="margin-top: 16px">
        <el-card shadow="never">
          <template #header>响应</template>
          <el-empty description="状态码、耗时、响应头和格式化响应体会显示在这里" />
        </el-card>
      </el-col>
    </el-row>
  </SplitPane>
</template>
