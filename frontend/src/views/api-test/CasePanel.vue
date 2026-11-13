<!--
@File    : CasePanel.vue
@Desc    : 定义页的用例抽屉。支持新建、批量操作、版本对比和接口变更说明
@Author  : xuetang-api
@Date    : 2026-11-13
@Update  : 2026-11-13 初始化用例维护
-->
<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { http, type ApiBody } from "@/api/http";

interface ApiOption {
  id: number;
  name: string;
  method: string;
  path: string;
  request?: { query?: unknown[]; headers?: unknown[]; path_params?: unknown[]; body?: { type?: string; content?: unknown } };
}
interface CaseRow {
  id: number;
  name: string;
  api_id: number | null;
  api_name: string;
  priority: string;
  tags: string;
  description: string;
  request: Record<string, unknown>;
  processors: {
    assertions?: Record<string, unknown>[];
    extractors?: Record<string, unknown>[];
    pre?: Record<string, unknown>[];
    post?: Record<string, unknown>[];
  };
  api_changed: boolean;
  change: { items?: { field: string; before: unknown; after: unknown }[] };
}
interface VersionRow {
  id: number;
  version_no: number;
  remark: string;
  tagged: boolean;
  operator: string;
  created_at: string;
}
interface DiffRow {
  field: string;
  label: string;
  change: string;
  left: unknown;
  right: unknown;
}

const props = defineProps<{ modelValue: boolean; projectId: string; apiId: number | null; apis: ApiOption[] }>();
const emit = defineEmits<{ "update:modelValue": [boolean]; changed: [] }>();
const router = useRouter();
const rows = ref<CaseRow[]>([]);
const selected = ref<CaseRow[]>([]);
const editorVisible = ref(false);
const editingId = ref<number | null>(null);
const versionVisible = ref(false);
const versionCaseId = ref(0);
const versions = ref<VersionRow[]>([]);
const leftVersion = ref<number | null>(null);
const rightVersion = ref<number | null>(null);
const diffs = ref<DiffRow[]>([]);
const changeVisible = ref(false);
const changeItems = ref<CaseRow["change"]["items"]>([]);
const priority = ref("P2");
const tags = ref("");
const moveApiId = ref<number | null>(null);
const form = reactive({
  name: "",
  api_id: null as number | null,
  priority: "P2",
  tags: "",
  description: "",
  method: "",
  path: "",
  bodyType: "none",
  bodyText: "",
  remark: "",
});
const assertions = ref<{ type: string; name: string; expression: string; expect: string; script: string; sql: string; datasource_id: string }[]>([]);
const extractors = ref<{ type: string; name: string; expression: string }[]>([]);
const pres = ref<{ type: string; name: string; value: string; ms: string; datasource_id: string; script_id: string }[]>([]);
const posts = ref<{ type: string; name: string; value: string; datasource_id: string }[]>([]);
const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit("update:modelValue", value),
});

function showError(error: unknown): void {
  if (error === "cancel" || error === "close") {
    return;
  }
  ElMessage.error(error instanceof Error ? error.message : "操作失败");
}

async function load(): Promise<void> {
  const query = props.apiId ? `?api_id=${props.apiId}` : "";
  const response = await http.get<ApiBody<CaseRow[]>>(`/api/v1/projects/${props.projectId}/cases${query}`);
  rows.value = response.data.data;
}

watch(
  () => `${props.modelValue}:${props.apiId ?? ""}:${props.projectId}`,
  () => {
    if (props.modelValue) {
      load().catch(showError);
    }
  },
);

function textOf(content: unknown): string {
  if (typeof content === "string") {
    return content;
  }
  if (content == null) {
    return "";
  }
  return JSON.stringify(content, null, 2);
}

function resetForm(row?: CaseRow, fromApi?: ApiOption): void {
  const request = (row?.request || {}) as { method?: string; path?: string; body?: { type?: string; content?: unknown } };
  const source = fromApi?.request;
  editingId.value = row?.id || null;
  form.name = row?.name || (fromApi ? `${fromApi.name} 用例` : "");
  form.api_id = row?.api_id ?? fromApi?.id ?? props.apiId;
  form.priority = row?.priority || "P2";
  form.tags = row?.tags || "";
  form.description = row?.description || "";
  form.method = request.method || fromApi?.method || "";
  form.path = request.path || fromApi?.path || "";
  form.bodyType = request.body?.type || source?.body?.type || "none";
  form.bodyText = textOf(request.body?.content ?? source?.body?.content ?? "");
  form.remark = "";
  assertions.value = (row?.processors.assertions || [{ type: "status_code", expect: "200" }]).map((item) => ({
    type: String(item.type || "status_code"),
    name: String(item.name || ""),
    expression: String(item.expression || item.name || item.script || item.sql || ""),
    expect: item.expect == null ? "" : String(item.expect),
    script: String(item.script || ""),
    sql: String(item.sql || ""),
    datasource_id: item.datasource_id == null ? "" : String(item.datasource_id),
  }));
  extractors.value = (row?.processors.extractors || []).map((item) => ({
    type: String(item.type || "jsonpath"),
    name: String(item.name || ""),
    expression: String(item.expression || item.name || ""),
  }));
  pres.value = (row?.processors.pre || []).map((item) => ({
    type: String(item.type || "assign"),
    name: String(item.name || ""),
    value: String(item.value || item.script || item.sql || ""),
    ms: item.ms == null ? "0" : String(item.ms),
    datasource_id: item.datasource_id == null ? "" : String(item.datasource_id),
    script_id: item.script_id == null ? "" : String(item.script_id),
  }));
  posts.value = (row?.processors.post || []).map((item) => ({
    type: String(item.type || "script"),
    name: String(item.name || ""),
    value: String(item.value || item.script || item.sql || ""),
    datasource_id: item.datasource_id == null ? "" : String(item.datasource_id),
  }));
  editorVisible.value = true;
}

function payload(): Record<string, unknown> {
  return {
    name: form.name.trim(),
    api_id: form.api_id,
    priority: form.priority,
    tags: form.tags,
    description: form.description,
    remark: form.remark,
    request_json: {
      method: form.method,
      path: form.path,
      query: [],
      headers: [],
      path_params: [],
      body: form.bodyType && form.bodyType !== "none" ? { type: form.bodyType, content: form.bodyText } : {},
    },
    processors_json: {
      assertions: assertions.value.filter((item) => item.type).map((item) => ({
        type: item.type,
        name: item.type === "header" ? item.expression : item.name,
        expression: item.expression,
        expect: item.type === "status_code" || item.type === "time" ? Number(item.expect || 0) : item.expect,
        script: item.type === "script" ? item.expression : item.script,
        sql: item.type === "database" ? item.expression : item.sql,
        datasource_id: item.datasource_id ? Number(item.datasource_id) : undefined,
      })),
      extractors: extractors.value.filter((item) => item.name || item.expression).map((item) => ({
        type: item.type,
        name: item.type === "header" ? item.name : item.name,
        expression: item.expression,
      })),
      pre: pres.value.filter((item) => item.type).map((item) => ({
        type: item.type,
        name: item.name,
        value: item.value,
        ms: item.type === "wait" ? Number(item.value || 0) : 0,
        script: item.type === "script" ? item.value : "",
        sql: item.type === "sql" ? item.value : "",
        datasource_id: item.datasource_id ? Number(item.datasource_id) : undefined,
        script_id: item.type === "script_ref" ? Number(item.value || 0) : undefined,
      })),
      post: posts.value.filter((item) => item.type).map((item) => ({
        type: item.type,
        name: item.name,
        value: item.value,
        script: item.type === "script" ? item.value : "",
        sql: item.type === "sql" ? item.value : "",
        expression: item.value,
        datasource_id: item.datasource_id ? Number(item.datasource_id) : undefined,
      })),
    },
  };
}

async function save(): Promise<void> {
  if (!form.name.trim()) {
    ElMessage.warning("请填写用例名称");
    return;
  }
  const body = payload();
  if (editingId.value) {
    await http.put(`/api/v1/projects/${props.projectId}/cases/${editingId.value}`, body);
  } else {
    await http.post(`/api/v1/projects/${props.projectId}/cases`, body);
  }
  editorVisible.value = false;
  ElMessage.success("用例已保存");
  await load();
  emit("changed");
}

async function copyRow(row: CaseRow): Promise<void> {
  await http.post(`/api/v1/projects/${props.projectId}/cases/${row.id}/copy`);
  await load();
  emit("changed");
}

async function removeRow(row: CaseRow): Promise<void> {
  await ElMessageBox.confirm(`确定删除用例 ${row.name}？`, "删除确认", { type: "warning" });
  await http.delete(`/api/v1/projects/${props.projectId}/cases/${row.id}`);
  await load();
  emit("changed");
}

async function batch(action: string): Promise<void> {
  if (!selected.value.length) {
    ElMessage.warning("请先选择用例");
    return;
  }
  await http.post(`/api/v1/projects/${props.projectId}/cases/batch`, {
    action,
    ids: selected.value.map((item) => item.id),
    priority: priority.value,
    tags: tags.value,
    api_id: moveApiId.value,
  });
  ElMessage.success("已更新");
  await load();
  emit("changed");
}

async function openVersions(row: CaseRow): Promise<void> {
  versionCaseId.value = row.id;
  const response = await http.get<ApiBody<VersionRow[]>>(`/api/v1/projects/${props.projectId}/cases/${row.id}/versions`);
  versions.value = response.data.data;
  leftVersion.value = versions.value[1]?.id || versions.value[0]?.id || null;
  rightVersion.value = versions.value[0]?.id || null;
  diffs.value = [];
  versionVisible.value = true;
}

async function compare(): Promise<void> {
  if (!leftVersion.value || !rightVersion.value) {
    return;
  }
  const response = await http.get<ApiBody<{ items: DiffRow[] }>>(
    `/api/v1/projects/${props.projectId}/cases/${versionCaseId.value}/diff`,
    { params: { left: leftVersion.value, right: rightVersion.value } },
  );
  diffs.value = response.data.data.items;
}

async function toggleTag(row: VersionRow): Promise<void> {
  await http.post(`/api/v1/projects/${props.projectId}/cases/${versionCaseId.value}/versions/${row.id}/tag`);
  const response = await http.get<ApiBody<VersionRow[]>>(`/api/v1/projects/${props.projectId}/cases/${versionCaseId.value}/versions`);
  versions.value = response.data.data;
}

async function rollback(row: VersionRow): Promise<void> {
  await http.post(`/api/v1/projects/${props.projectId}/cases/${versionCaseId.value}/versions/${row.id}/rollback`);
  ElMessage.success(`已回滚到版本 ${row.version_no}`);
  versionVisible.value = false;
  await load();
  emit("changed");
}

function showChange(row: CaseRow): void {
  changeItems.value = row.change?.items || [];
  changeVisible.value = true;
}

function debugCase(row: CaseRow): void {
  router.push({ path: `/p/${props.projectId}/api-test/debug`, query: { caseId: String(row.id) } });
}

function showValue(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value ?? "", null, 0);
}
</script>

<template>
  <el-drawer v-model="visible" :title="apiId ? '接口用例' : '全部用例'" size="720px">
    <div class="case-toolbar">
      <el-button type="primary" @click="resetForm()">新建用例</el-button>
      <el-button v-if="apiId" @click="resetForm(undefined, apis.find((item) => item.id === apiId))">从接口生成</el-button>
      <el-select v-model="priority" style="width: 90px">
        <el-option v-for="item in ['P0', 'P1', 'P2', 'P3']" :key="item" :label="item" :value="item" />
      </el-select>
      <el-button @click="batch('priority').catch(showError)">改优先级</el-button>
      <el-input v-model="tags" placeholder="标签" style="width: 120px" />
      <el-button @click="batch('tags').catch(showError)">改标签</el-button>
      <el-select v-model="moveApiId" clearable placeholder="移动到" style="width: 140px">
        <el-option v-for="item in apis" :key="item.id" :label="item.name" :value="item.id" />
      </el-select>
      <el-button @click="batch('move').catch(showError)">移动</el-button>
      <el-button type="danger" plain @click="batch('delete').catch(showError)">删除</el-button>
    </div>
    <el-table :data="rows" @selection-change="selected = $event">
      <el-table-column type="selection" width="42" />
      <el-table-column prop="name" label="用例" min-width="140" />
      <el-table-column prop="priority" label="等级" width="70" />
      <el-table-column prop="tags" label="标签" width="90" />
      <el-table-column label="变更" width="110">
        <template #default="{ row }">
          <el-button v-if="row.api_changed" link type="warning" @click="showChange(row)">接口已变更</el-button>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220">
        <template #default="{ row }">
          <el-button link type="primary" @click="resetForm(row)">编辑</el-button>
          <el-button link type="primary" @click="debugCase(row)">调试</el-button>
          <el-button link type="primary" @click="openVersions(row).catch(showError)">版本</el-button>
          <el-button link @click="copyRow(row).catch(showError)">复制</el-button>
          <el-button link type="danger" @click="removeRow(row).catch(showError)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-drawer>
  <el-dialog v-model="editorVisible" :title="editingId ? '编辑用例' : '新建用例'" width="640px">
    <el-form label-position="top">
      <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
      <el-form-item label="所属接口">
        <el-select v-model="form.api_id" clearable placeholder="空白用例" style="width: 100%">
          <el-option v-for="item in apis" :key="item.id" :label="`${item.method} ${item.name}`" :value="item.id" />
        </el-select>
      </el-form-item>
      <div class="case-grid">
        <el-form-item label="优先级">
          <el-select v-model="form.priority" style="width: 100%">
            <el-option v-for="item in ['P0', 'P1', 'P2', 'P3']" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="标签"><el-input v-model="form.tags" /></el-form-item>
      </div>
      <div class="case-grid">
        <el-form-item label="方法"><el-input v-model="form.method" placeholder="空则沿用接口" /></el-form-item>
        <el-form-item label="路径"><el-input v-model="form.path" placeholder="空则沿用接口" /></el-form-item>
      </div>
      <el-form-item label="请求体">
        <el-select v-model="form.bodyType" style="width: 160px">
          <el-option v-for="item in ['none', 'json', 'raw', 'form', 'urlencoded']" :key="item" :label="item" :value="item" />
        </el-select>
        <el-input v-if="form.bodyType !== 'none'" v-model="form.bodyText" type="textarea" :rows="4" />
      </el-form-item>
      <el-form-item label="断言">
        <div v-for="(item, index) in assertions" :key="index" class="case-assert">
          <el-select v-model="item.type" style="width: 130px">
            <el-option v-for="kind in ['status_code', 'header', 'jsonpath', 'regex', 'xpath', 'time', 'script', 'database']" :key="kind" :label="kind" :value="kind" />
          </el-select>
          <el-input v-model="item.expression" :placeholder="item.type === 'database' ? 'SQL' : item.type === 'script' ? '脚本，用 result 返回' : '表达式或头名称'" />
          <el-input v-if="item.type === 'database'" v-model="item.datasource_id" placeholder="数据源 ID" />
          <el-input v-model="item.expect" placeholder="期望值" />
          <el-button link type="danger" @click="assertions.splice(index, 1)">删除</el-button>
        </div>
        <el-button link type="primary" @click="assertions.push({ type: 'status_code', name: '', expression: '', expect: '200', script: '', sql: '', datasource_id: '' })">添加断言</el-button>
      </el-form-item>
      <el-form-item label="前置">
        <div v-for="(item, index) in pres" :key="index" class="case-assert">
          <el-select v-model="item.type" style="width: 130px">
            <el-option v-for="kind in ['assign', 'wait', 'script', 'sql', 'script_ref']" :key="kind" :label="kind" :value="kind" />
          </el-select>
          <el-input v-model="item.name" placeholder="变量名" />
          <el-input v-model="item.value" placeholder="值、毫秒、脚本、SQL 或脚本 ID" />
          <el-input v-if="item.type === 'sql'" v-model="item.datasource_id" placeholder="数据源 ID" />
          <el-button link type="danger" @click="pres.splice(index, 1)">删除</el-button>
        </div>
        <el-button link type="primary" @click="pres.push({ type: 'assign', name: '', value: '', ms: '0', datasource_id: '', script_id: '' })">添加前置</el-button>
      </el-form-item>
      <el-form-item label="后置">
        <div v-for="(item, index) in posts" :key="index" class="case-assert">
          <el-select v-model="item.type" style="width: 130px">
            <el-option v-for="kind in ['extract', 'script', 'sql', 'clear']" :key="kind" :label="kind" :value="kind" />
          </el-select>
          <el-input v-model="item.name" placeholder="变量名" />
          <el-input v-model="item.value" placeholder="表达式、脚本或 SQL" />
          <el-input v-if="item.type === 'sql'" v-model="item.datasource_id" placeholder="数据源 ID" />
          <el-button link type="danger" @click="posts.splice(index, 1)">删除</el-button>
        </div>
        <el-button link type="primary" @click="posts.push({ type: 'clear', name: '', value: '', datasource_id: '' })">添加后置</el-button>
      </el-form-item>
      <el-form-item label="提取">
        <div v-for="(item, index) in extractors" :key="index" class="case-assert">
          <el-select v-model="item.type" style="width: 130px">
            <el-option v-for="kind in ['jsonpath', 'regex', 'header']" :key="kind" :label="kind" :value="kind" />
          </el-select>
          <el-input v-model="item.expression" placeholder="表达式" />
          <el-input v-model="item.name" placeholder="变量名" />
          <el-button link type="danger" @click="extractors.splice(index, 1)">删除</el-button>
        </div>
        <el-button link type="primary" @click="extractors.push({ type: 'jsonpath', name: '', expression: '' })">添加提取</el-button>
      </el-form-item>
      <el-form-item label="说明"><el-input v-model="form.description" type="textarea" :rows="2" /></el-form-item>
      <el-form-item label="版本备注"><el-input v-model="form.remark" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="editorVisible = false">取消</el-button>
      <el-button type="primary" @click="save().catch(showError)">保存</el-button>
    </template>
  </el-dialog>
  <el-dialog v-model="versionVisible" title="版本对比" width="760px">
    <el-table :data="versions" size="small">
      <el-table-column prop="version_no" label="版本" width="70" />
      <el-table-column prop="remark" label="备注" />
      <el-table-column prop="operator" label="修改人" width="100" />
      <el-table-column prop="created_at" label="时间" width="170" />
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button link @click="toggleTag(row).catch(showError)">{{ row.tagged ? "取消标签" : "打标签" }}</el-button>
          <el-button link type="primary" @click="rollback(row).catch(showError)">回滚</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="case-toolbar">
      <el-select v-model="leftVersion" placeholder="旧版本" style="width: 140px">
        <el-option v-for="item in versions" :key="item.id" :label="`v${item.version_no}`" :value="item.id" />
      </el-select>
      <el-select v-model="rightVersion" placeholder="新版本" style="width: 140px">
        <el-option v-for="item in versions" :key="item.id" :label="`v${item.version_no}`" :value="item.id" />
      </el-select>
      <el-button type="primary" @click="compare().catch(showError)">对比</el-button>
    </div>
    <div v-for="item in diffs" :key="item.field" class="diff-row" :class="`diff-${item.change}`">
      <strong>{{ item.label }}</strong>
      <span>{{ item.change === "same" ? "相同" : item.change === "added" ? "新增" : item.change === "removed" ? "删除" : "修改" }}</span>
      <pre>{{ showValue(item.left) }}</pre>
      <pre>{{ showValue(item.right) }}</pre>
    </div>
  </el-dialog>
  <el-dialog v-model="changeVisible" title="接口变更" width="560px">
    <div v-for="item in changeItems" :key="item.field" class="diff-row diff-modified">
      <strong>{{ item.field }}</strong>
      <pre>{{ showValue(item.before) }}</pre>
      <pre>{{ showValue(item.after) }}</pre>
    </div>
    <p v-if="!changeItems?.length" class="hint">保存用例后会清除这个标记。</p>
  </el-dialog>
</template>
