<!--
@File    : ReportView.vue
@Desc    : 报告页。场景报告和用例报告两个列表，布局对齐 MeterSphere
@Author  : xuetang-api
@Date    : 2026-11-12
@Update  : 2026-11-13 按 MeterSphere 报告列表重做
-->
<script setup lang="ts">
import { computed, ref } from "vue";

interface ReportRow {
  name: string;
  type: string;
  result: "成功" | "失败";
  trigger: string;
  creator: string;
  created_at: string;
}

const pageTab = ref("场景报告");
const scope = ref("全部");
const keyword = ref("");
const reports = ref<ReportRow[]>([]);

const visible = computed(() => {
  const text = keyword.value.trim().toLowerCase();
  return reports.value.filter((item) => {
    const inScope = scope.value === "全部" || item.type === scope.value;
    const matched = !text || item.name.toLowerCase().includes(text);
    return inScope && matched;
  });
});
</script>

<template>
  <div class="ms-page ms-report">
    <section class="ms-main">
      <el-tabs v-model="pageTab">
        <el-tab-pane label="场景报告" name="场景报告" />
        <el-tab-pane label="用例报告" name="用例报告" />
      </el-tabs>
      <div class="ms-toolbar">
        <el-radio-group v-model="scope">
          <el-radio-button label="全部" value="全部" />
          <el-radio-button label="独立报告" value="独立报告" />
          <el-radio-button label="集合报告" value="集合报告" />
        </el-radio-group>
        <span class="doc-bar-gap" />
        <el-input v-model="keyword" clearable placeholder="通过名称搜索" style="width: 240px" />
      </div>
      <el-table :data="visible" height="100%">
        <el-table-column type="selection" width="48" />
        <el-table-column prop="name" label="报告名称" min-width="220" />
        <el-table-column prop="type" label="报告类型" width="140" />
        <el-table-column label="执行结果" width="120">
          <template #default="{ row }">
            <span :class="row.result === '成功' ? 'result-ok' : 'result-fail'">{{ row.result }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="trigger" label="触发方式" width="120" />
        <el-table-column prop="creator" label="创建人" width="140" />
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="140">
          <template #default>
            <el-button link type="primary">删除</el-button>
            <el-button link type="primary">导出</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!visible.length" :description="`${pageTab}还没有数据，执行场景后会出现在这里`" />
      <div class="ms-count">共 {{ visible.length }} 条</div>
    </section>
  </div>
</template>
