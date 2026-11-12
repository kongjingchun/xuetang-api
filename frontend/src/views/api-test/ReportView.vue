<!--
@File    : ReportView.vue
@Desc    : 报告 Tab 空壳。左侧筛选，右侧列出计划中的列表字段
@Author  : xuetang-api
@Date    : 2026-11-12
@Update  : 2026-11-12 初始化报告页
-->
<script setup lang="ts">
import { reactive } from "vue";
import SplitPane from "@/components/SplitPane.vue";

const filters = reactive({
  status: "",
});
</script>

<template>
  <SplitPane side-title="筛选">
    <template #side>
      <div style="padding: 12px">
        <el-form label-position="top">
          <el-form-item label="状态">
            <el-select v-model="filters.status" clearable placeholder="全部" style="width: 100%">
              <el-option label="成功" value="success" />
              <el-option label="失败" value="failed" />
            </el-select>
          </el-form-item>
        </el-form>
      </div>
    </template>
    <el-table :data="[]" border>
      <el-table-column prop="started_at" label="执行时间" />
      <el-table-column prop="task_type" label="执行类型" />
      <el-table-column prop="executor" label="执行人" />
      <el-table-column prop="env" label="环境" />
      <el-table-column prop="status" label="状态" />
      <el-table-column prop="pass_rate" label="通过率" />
      <el-table-column prop="elapsed" label="执行时长" />
    </el-table>
    <el-empty description="报告列表和详情在阶段 5 实现" />
  </SplitPane>
</template>
