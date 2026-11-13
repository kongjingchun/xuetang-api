<!--
@File    : DebugView.vue
@Desc    : 调试页。左侧请求树，右侧多页签请求编辑和响应区
@Author  : xuetang-api
@Date    : 2026-11-12
@Update  : 2026-11-13 按 MeterSphere 调试页布局重做
-->
<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { http, type ApiBody } from "@/api/http";
import { parseCurl } from "@/utils/curl";
import DebugTree from "@/views/api-test/DebugTree.vue";

interface ModuleRow {
  id: number;
  parent_id: number | null;
  name: string;
  sort: number;
}
interface ApiRow {
  id: number;
  module_id: number | null;
  name: string;
  method: string;
  path: string;
  sort: number;
  description: string;
  request: { query?: ParamRow[]; headers?: ParamRow[]; path_params?: ParamRow[]; body?: { type: string; content: unknown } };
}
interface ParamRow {
  name: string;
  value: string;
  description?: string;
  enabled?: boolean;
  required?: boolean;
}
interface DocTab {
  key: string;
  apiId: number | null;
  caseId: number | null;
  title: string;
  method: string;
  url: string;
  bodyType: string;
  bodyText: string;
  query: ParamRow[];
  headers: ParamRow[];
  rest: ParamRow[];
  responseText: string;
  responseMeta: string;
  assertions: { type: string; passed: boolean; message: string }[];
}
interface EnvOption {
  id: number;
  name: string;
  base_url: string;
}
interface HistoryRow {
  id: number;
  method: string;
  url: string;
  status: number;
  elapsed_ms: number;
  created_at: string;
}

const route = useRoute();
const projectId = computed(() => String(route.params.projectId || ""));
const modules = ref<ModuleRow[]>([]);
const apis = ref<ApiRow[]>([]);
const keyword = ref("");
const expanded = ref<Record<string, boolean>>({});
const draggingId = ref<number | null>(null);
const dropHint = ref<{ key: string; place: "before" | "after" | "into" } | null>(null);
const addName = ref("");
const tabs = ref<DocTab[]>([]);
const activeKey = ref("");
const section = ref("请求体");
const layout = ref("上下");
const batchVisible = ref(false);
const batchText = ref("");
const batchTarget = ref<"headers" | "query">("headers");
const environments = ref<EnvOption[]>([]);
const envId = ref<number | null>(null);
const historyVisible = ref(false);
const histories = ref<HistoryRow[]>([]);
let draftSeq = 1;
const sections = ["请求头", "请求体", "Query", "REST", "前置", "后置", "认证", "设置"];
const bodyTypes = ["none", "form-data", "x-www-form-urlencoded", "json", "xml", "raw", "binary"];
const activeTab = computed(() => tabs.value.find((item) => item.key === activeKey.value) || null);
const filteredApis = computed(() => {
  const text = keyword.value.trim().toLowerCase();
  if (!text) {
    return apis.value;
  }
  return apis.value.filter((item) => `${item.name} ${item.method} ${item.path}`.toLowerCase().includes(text));
});

function showError(error: unknown): void {
  if (error === "cancel" || error === "close") {
    return;
  }
  ElMessage.error(error instanceof Error ? error.message : "操作失败");
}

function blankTab(partial?: Partial<DocTab>): DocTab {
  const key = `draft-${draftSeq}`;
  draftSeq += 1;
  return {
    apiId: null,
    caseId: null,
    title: "新建请求",
    method: "GET",
    url: "",
    bodyType: "none",
    bodyText: "",
    query: [emptyHeader()],
    headers: [emptyHeader()],
    rest: [emptyHeader()],
    responseText: "",
    responseMeta: "",
    assertions: [],
    ...partial,
    key,
  };
}

function openDraft(): void {
  const tab = blankTab();
  tabs.value.push(tab);
  activeKey.value = tab.key;
}

function textOf(content: unknown): string {
  if (typeof content === "string") {
    return content;
  }
  if (content == null) {
    return "";
  }
  return JSON.stringify(content, null, 2);
}

function openApi(row: ApiRow): void {
  const existing = tabs.value.find((item) => item.apiId === row.id);
  if (existing) {
    activeKey.value = existing.key;
    return;
  }
  const bodyType = row.request.body?.type || "none";
  const tab = blankTab({
    apiId: row.id,
    title: row.name,
    method: row.method,
    url: row.path,
    bodyType: bodyType === "form" ? "form-data" : bodyType === "urlencoded" ? "x-www-form-urlencoded" : bodyType,
    bodyText: textOf(row.request.body?.content),
    query: withBlankHeader(row.request.query || []),
    headers: withBlankHeader(row.request.headers || []),
    rest: withBlankHeader(row.request.path_params || []),
  });
  tabs.value.push(tab);
  activeKey.value = tab.key;
}

function closeTab(key: string): void {
  const index = tabs.value.findIndex((item) => item.key === key);
  if (index < 0) {
    return;
  }
  const wasActive = activeKey.value === key;
  tabs.value.splice(index, 1);
  if (wasActive) {
    const next = tabs.value[index] || tabs.value[index - 1];
    activeKey.value = next?.key || "";
  }
}

async function load(): Promise<void> {
  const base = `/api/v1/projects/${projectId.value}`;
  const [moduleBody, apiBody, envBody] = await Promise.all([
    http.get<ApiBody<ModuleRow[]>>(`${base}/modules`),
    http.get<ApiBody<ApiRow[]>>(`${base}/definitions`),
    http.get<ApiBody<EnvOption[]>>(`${base}/debug/environments`),
  ]);
  modules.value = moduleBody.data.data;
  apis.value = apiBody.data.data;
  environments.value = envBody.data.data;
  if (envId.value == null && environments.value.length) {
    envId.value = environments.value[0].id;
  }
  const caseId = Number(route.query.caseId || 0);
  const focus = Number(route.query.apiId || 0);
  if (caseId) {
    await openCase(caseId);
  } else {
    const row = apis.value.find((item) => item.id === focus);
    if (row) {
      openApi(row);
    } else if (!tabs.value.length) {
      openDraft();
    }
  }
}

async function openCase(caseId: number): Promise<void> {
  const response = await http.get<ApiBody<{ id: number; name: string; api_id: number | null; request: ApiRow["request"] & { method?: string; path?: string } }>>(
    `/api/v1/projects/${projectId.value}/cases/${caseId}`,
  );
  const item = response.data.data;
  const api = apis.value.find((row) => row.id === item.api_id);
  const request = item.request || {};
  const body = request.body || api?.request.body;
  const bodyType = body?.type || "none";
  const tab = blankTab({
    caseId: item.id,
    apiId: item.api_id,
    title: item.name,
    method: request.method || api?.method || "GET",
    url: request.path || api?.path || "",
    bodyType: bodyType === "form" ? "form-data" : bodyType === "urlencoded" ? "x-www-form-urlencoded" : bodyType || "none",
    bodyText: textOf(body?.content),
    query: withBlankHeader((request.query as ParamRow[]) || api?.request.query || []),
    headers: withBlankHeader((request.headers as ParamRow[]) || api?.request.headers || []),
    rest: withBlankHeader((request.path_params as ParamRow[]) || api?.request.path_params || []),
  });
  tabs.value.push(tab);
  activeKey.value = tab.key;
}

function filledCount(rows: ParamRow[]): number {
  return rows.filter((item) => item.name.trim() || item.value.trim()).length;
}

function sectionCount(name: string): number {
  const tab = activeTab.value;
  if (!tab) {
    return 0;
  }
  if (name === "请求头") {
    return filledCount(tab.headers);
  }
  if (name === "Query") {
    return filledCount(tab.query);
  }
  if (name === "REST") {
    return filledCount(tab.rest);
  }
  return 0;
}

function moduleApis(moduleId: number | null): ApiRow[] {
  return apis.value
    .filter((item) => (item.module_id ?? null) === moduleId)
    .sort((left, right) => (left.sort ?? 0) - (right.sort ?? 0) || left.id - right.id);
}

function hintClass(key: string): string {
  if (dropHint.value?.key !== key) {
    return "";
  }
  if (dropHint.value.place === "before") {
    return "drop-before";
  }
  if (dropHint.value.place === "after") {
    return "drop-after";
  }
  return "drop-into";
}

function beginDrag(event: DragEvent, id: number): void {
  draggingId.value = id;
  event.dataTransfer?.setData("text/plain", String(id));
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = "move";
  }
}

function endDrag(): void {
  draggingId.value = null;
  dropHint.value = null;
}

function overApiRow(event: DragEvent, item: ApiRow): void {
  event.preventDefault();
  if (draggingId.value === item.id) {
    dropHint.value = null;
    return;
  }
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
  dropHint.value = {
    key: `api-${item.id}`,
    place: event.clientY < rect.top + rect.height / 2 ? "before" : "after",
  };
}

async function moveApi(payload: { id: number; moduleId: number | null; beforeId: number | null; place: "before" | "after" | "into" }): Promise<void> {
  endDrag();
  if (!payload.id || payload.id === payload.beforeId) {
    return;
  }
  const dragging = apis.value.find((item) => item.id === payload.id);
  if (!dragging) {
    return;
  }
  const moduleId = payload.moduleId;
  const siblings = apis.value
    .filter((item) => item.id !== dragging.id && (item.module_id ?? null) === moduleId)
    .sort((left, right) => (left.sort ?? 0) - (right.sort ?? 0) || left.id - right.id);
  const found = payload.beforeId ? siblings.findIndex((item) => item.id === payload.beforeId) : siblings.length;
  const index = payload.place === "after" ? (found < 0 ? siblings.length : found + 1) : (found < 0 ? siblings.length : found);
  siblings.splice(index, 0, dragging);
  const placed = new Map(siblings.map((item, order) => [item.id, order]));
  await http.put(`/api/v1/projects/${projectId.value}/definitions/layout`, {
    modules: [],
    apis: apis.value.map((item) => ({
      id: item.id,
      module_id: item.id === dragging.id ? moduleId : item.module_id,
      sort: placed.has(item.id) ? placed.get(item.id) : item.sort ?? 0,
    })),
  });
  await load();
}

function isOpen(key: string): boolean {
  if (keyword.value.trim()) {
    return true;
  }
  return expanded.value[key] !== false;
}

function toggleNode(key: string): void {
  expanded.value[key] = !isOpen(key);
}

function childModules(parentId: number | null): ModuleRow[] {
  return modules.value
    .filter((item) => (item.parent_id ?? null) === parentId)
    .sort((left, right) => left.sort - right.sort || left.id - right.id);
}

function matchesText(value: string): boolean {
  const text = keyword.value.trim().toLowerCase();
  return !text || value.toLowerCase().includes(text);
}

function moduleVisibleInTree(moduleId: number): boolean {
  const folder = modules.value.find((item) => item.id === moduleId);
  if (!folder) {
    return false;
  }
  if (matchesText(folder.name) || moduleApis(moduleId).some((item) => matchesText(`${item.name} ${item.method} ${item.path}`))) {
    return true;
  }
  return childModules(moduleId).some((item) => moduleVisibleInTree(item.id));
}

async function execute(): Promise<void> {
  const tab = activeTab.value;
  if (!tab) {
    return;
  }
  if (!tab.url.trim()) {
    tab.responseMeta = "";
    tab.responseText = "请填写路径，或包含 http/https 的完整 URL";
    tab.assertions = [];
    return;
  }
  const kind = tab.bodyType === "form-data" ? "form" : tab.bodyType === "x-www-form-urlencoded" ? "urlencoded" : tab.bodyType === "json" ? "json" : tab.bodyType === "none" ? "none" : "raw";
  const response = await http.post<ApiBody<{ status: number; elapsed_ms: number; body: string; error: string; assertions: DocTab["assertions"]; passed: boolean }>>(
    `/api/v1/projects/${projectId.value}/debug/send`,
    {
      env_id: envId.value,
      method: tab.method,
      url: tab.url,
      headers: tab.headers,
      query: tab.query,
      rest: tab.rest,
      body_type: kind,
      body_text: tab.bodyText,
      target_type: tab.caseId ? "case" : "api",
      target_id: tab.apiId || 0,
      case_id: tab.caseId,
    },
  );
  const data = response.data.data;
  tab.assertions = data.assertions || [];
  tab.responseMeta = data.error
    ? `请求失败 ${data.error} · ${data.elapsed_ms} ms`
    : `${data.status} · ${data.elapsed_ms} ms${tab.caseId ? (data.passed ? " · 断言通过" : " · 断言失败") : ""}`;
  tab.responseText = data.body || (data.error ? data.error : "响应体为空");
}

async function openHistory(): Promise<void> {
  const response = await http.get<ApiBody<HistoryRow[]>>(`/api/v1/projects/${projectId.value}/debug/history`);
  histories.value = response.data.data;
  historyVisible.value = true;
}

function onHistory(row: HistoryRow): void {
  restoreHistory(row).catch(showError);
}

async function restoreHistory(row: HistoryRow): Promise<void> {
  const response = await http.get<ApiBody<{ request: { method: string; url: string; headers: Record<string, string>; body_type: string; body: string } }>>(
    `/api/v1/projects/${projectId.value}/debug/history/${row.id}`,
  );
  const request = response.data.data.request;
  const tab = activeTab.value || blankTab();
  if (!activeTab.value) {
    tabs.value.push(tab);
    activeKey.value = tab.key;
  }
  tab.method = request.method || "GET";
  tab.url = request.url || "";
  tab.bodyType = request.body_type === "form" ? "form-data" : request.body_type === "urlencoded" ? "x-www-form-urlencoded" : request.body_type || "raw";
  tab.bodyText = request.body || "";
  tab.headers = withBlankHeader(Object.entries(request.headers || {}).map(([name, value]) => ({ name, value, enabled: true, description: "" })));
  historyVisible.value = false;
}

async function save(): Promise<void> {
  const tab = activeTab.value;
  if (!tab) {
    return;
  }
  if (!tab.title.trim() || tab.title === "新建请求") {
    ElMessage.warning("请先把请求名称改成要保存的接口名");
    return;
  }
  const kind = tab.bodyType === "form-data" ? "form" : tab.bodyType === "x-www-form-urlencoded" ? "urlencoded" : tab.bodyType === "none" ? "none" : "raw";
  const payload = {
    name: tab.title.trim(),
    method: tab.method,
    path: tab.url.trim() || "/",
    module_id: null,
    description: "",
    request_json: {
      query: tab.query.filter((item) => item.name.trim() || item.value.trim()),
      headers: tab.headers.filter((item) => item.name.trim() || item.value.trim()),
      path_params: tab.rest.filter((item) => item.name.trim() || item.value.trim()),
      body: { type: kind, content: kind === "none" ? "" : tab.bodyText },
    },
    examples: [],
  };
  if (tab.apiId) {
    await http.put(`/api/v1/projects/${projectId.value}/definitions/${tab.apiId}`, payload);
  } else {
    const response = await http.post<ApiBody<{ id: number }>>(`/api/v1/projects/${projectId.value}/definitions`, payload);
    tab.apiId = response.data.data.id;
  }
  ElMessage.success("请求已保存到接口定义");
  await load();
}

onMounted(() => {
  load().catch(showError);
});
function emptyHeader(): ParamRow {
  return { name: "", value: "", description: "", enabled: true };
}

function withBlankHeader(rows: ParamRow[]): ParamRow[] {
  const next: ParamRow[] = rows.map((item) => ({
    name: item.name || "",
    value: item.value || "",
    description: item.description || "",
    enabled: item.enabled !== false,
  }));
  const last = next[next.length - 1];
  if (!last || last.name.trim() || last.value.trim()) {
    next.push(emptyHeader());
  }
  return next;
}

function onHeaderInput(rows: ParamRow[]): void {
  const last = rows[rows.length - 1];
  if (last && (last.name.trim() || last.value.trim())) {
    rows.push(emptyHeader());
  }
}

function removeHeader(rows: ParamRow[], index: number): void {
  rows.splice(index, 1);
  if (!rows.length || rows[rows.length - 1].name.trim() || rows[rows.length - 1].value.trim()) {
    rows.push(emptyHeader());
  }
}

function applyParsedCurl(text: string): boolean {
  const parsed = parseCurl(text);
  const tab = activeTab.value;
  if (!parsed || !tab) {
    return false;
  }
  tab.method = parsed.method;
  tab.url = parsed.url;
  tab.headers = withBlankHeader(parsed.headers);
  tab.query = withBlankHeader(parsed.query);
  tab.rest = withBlankHeader(parsed.rest);
  tab.bodyType = parsed.bodyType;
  tab.bodyText = parsed.bodyText;
  ElMessage.success("已从 curl 填入请求信息");
  return true;
}

function onPasteUrl(event: ClipboardEvent): void {
  const text = event.clipboardData?.getData("text") || "";
  if (!text.trim().toLowerCase().startsWith("curl")) {
    return;
  }
  event.preventDefault();
  if (!applyParsedCurl(text)) {
    ElMessage.warning("没有识别出 curl 里的请求地址");
  }
}

async function createModule(parentId: number | null, name: string): Promise<void> {
  const title = name.trim();
  if (!title) {
    ElMessage.warning("请填写名称");
    return;
  }
  await http.post(`/api/v1/projects/${projectId.value}/modules`, { name: title, parent_id: parentId });
  addName.value = "";
  if (parentId) {
    expanded.value[`m-${parentId}`] = true;
  }
  await load();
}

async function renameModule(folder: ModuleRow): Promise<void> {
  const { value } = await ElMessageBox.prompt("请输入名称", "重命名", {
    inputValue: folder.name,
    inputPattern: /\S+/,
    inputErrorMessage: "请填写名称",
  });
  await http.put(`/api/v1/projects/${projectId.value}/modules/${folder.id}`, {
    name: value.trim(),
    parent_id: folder.parent_id,
  });
  await load();
}

async function deleteModule(folder: ModuleRow): Promise<void> {
  await ElMessageBox.confirm(`确定删除目录 ${folder.name}？`, "删除确认", { type: "warning" });
  await http.delete(`/api/v1/projects/${projectId.value}/modules/${folder.id}`);
  await load();
}

async function renameApi(row: ApiRow): Promise<void> {
  const { value } = await ElMessageBox.prompt("请输入名称", "重命名", {
    inputValue: row.name,
    inputPattern: /\S+/,
    inputErrorMessage: "请填写名称",
  });
  const response = await http.get<ApiBody<ApiRow & { description?: string; examples?: unknown[] }>>(
    `/api/v1/projects/${projectId.value}/definitions/${row.id}`,
  );
  const data = response.data.data;
  await http.put(`/api/v1/projects/${projectId.value}/definitions/${row.id}`, {
    name: value.trim(),
    method: data.method,
    path: data.path,
    module_id: data.module_id,
    description: data.description || "",
    request_json: data.request,
    examples: data.examples || [],
  });
  const tab = tabs.value.find((item) => item.apiId === row.id);
  if (tab) {
    tab.title = value.trim();
  }
  await load();
}

async function deleteApi(row: ApiRow): Promise<void> {
  await ElMessageBox.confirm(`确定删除接口 ${row.name}？`, "删除确认", { type: "warning" });
  await http.delete(`/api/v1/projects/${projectId.value}/definitions/${row.id}`);
  const tab = tabs.value.find((item) => item.apiId === row.id);
  if (tab) {
    closeTab(tab.key);
  }
  await load();
}

function openBatch(target: "headers" | "query"): void {
  batchTarget.value = target;
  batchText.value = "";
  batchVisible.value = true;
}

function applyBatch(): void {
  const tab = activeTab.value;
  if (!tab) {
    return;
  }
  const parsed: ParamRow[] = [];
  for (const line of batchText.value.split(/\r?\n/)) {
    const text = line.trim();
    if (!text) {
      continue;
    }
    const splitAt = text.includes(":") ? text.indexOf(":") : text.indexOf("：");
    if (splitAt <= 0) {
      ElMessage.warning(`无法识别「${text}」，请使用 名称:值`);
      return;
    }
    parsed.push({
      name: text.slice(0, splitAt).trim(),
      value: text.slice(splitAt + 1).trim(),
      description: "",
      enabled: true,
    });
  }
  const label = batchTarget.value === "headers" ? "请求头" : "Query";
  if (!parsed.length) {
    ElMessage.warning(`请填写要添加的${label}`);
    return;
  }
  const rows = batchTarget.value === "headers" ? tab.headers : tab.query;
  const filled = rows.filter((item) => item.name.trim() || item.value.trim());
  rows.splice(0, rows.length, ...filled, ...parsed, emptyHeader());
  batchText.value = "";
  batchVisible.value = false;
}

watch(projectId, () => {
  tabs.value = [];
  load().catch(showError);
});
</script>

<template>
  <div class="ms-page">
    <aside class="ms-side">
      <div class="ms-side-pad">
        <div class="ms-side-search">
          <el-input v-model="keyword" clearable placeholder="请输入模块/请求名称" />
          <el-button type="primary" @click="openDraft">新建请求</el-button>
        </div>
        <div class="tree-row">
          <span class="tree-main">
            <span class="tree-icon">
              <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1.5 3.5A1.5 1.5 0 0 1 3 2h3.2a1.5 1.5 0 0 1 1.2.6L8.2 4H13a1.5 1.5 0 0 1 1.5 1.5v7A1.5 1.5 0 0 1 13 14H3a1.5 1.5 0 0 1-1.5-1.5v-9z" /></svg>
            </span>
            <span>全部请求 ({{ filteredApis.length }})</span>
          </span>
          <span class="tree-ops">
            <el-popover trigger="click" placement="bottom" :width="280">
              <template #reference>
                <button type="button" class="tree-op" @click.stop>+</button>
              </template>
              <div class="add-module">
                <div class="add-module-title">添加模块</div>
                <el-input v-model="addName" placeholder="请输入名称，按回车键保存" @keyup.enter="createModule(null, addName).catch(showError)" />
                <div class="add-module-actions">
                  <el-button @click="addName = ''">取消</el-button>
                  <el-button type="primary" @click="createModule(null, addName).catch(showError)">确定</el-button>
                </div>
              </div>
            </el-popover>
          </span>
        </div>
        <DebugTree
          :modules="childModules(null)"
          :depth="0"
          :keyword="keyword"
          :is-open="isOpen"
          :module-apis="moduleApis"
          :child-modules="childModules"
          :module-visible="moduleVisibleInTree"
          :matches-text="matchesText"
          :drop-hint="dropHint"
          :dragging-id="draggingId"
          @toggle="toggleNode"
          @open-api="openApi"
          @create-module="(parentId, name) => createModule(parentId, name).catch(showError)"
          @rename-module="(folder) => renameModule(folder).catch(showError)"
          @delete-module="(folder) => deleteModule(folder).catch(showError)"
          @rename-api="(row) => renameApi(row).catch(showError)"
          @delete-api="(row) => deleteApi(row).catch(showError)"
          @move-api="(payload) => moveApi(payload).catch(showError)"
          @hint="dropHint = $event"
          @drag-start="draggingId = $event"
          @drag-end="endDrag"
        />
        <div
          class="tree-row"
          :class="hintClass('mod-unplanned')"
          @dragover.prevent="dropHint = { key: 'mod-unplanned', place: 'into' }"
          @drop="moveApi({ id: Number(($event as DragEvent).dataTransfer?.getData('text/plain') || draggingId || 0), moduleId: null, beforeId: null, place: 'into' }).catch(showError)"
        >
          <button type="button" class="tree-main" @click="toggleNode('unplanned')">
            <span class="tree-arrow" :class="{ open: isOpen('unplanned') }">▸</span>
            <span class="tree-icon">
              <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1.5 3.5A1.5 1.5 0 0 1 3 2h3.2a1.5 1.5 0 0 1 1.2.6L8.2 4H13a1.5 1.5 0 0 1 1.5 1.5v7A1.5 1.5 0 0 1 13 14H3a1.5 1.5 0 0 1-1.5-1.5v-9z" /></svg>
            </span>
            <span>未规划请求</span>
            <span class="ms-count">{{ moduleApis(null).length }}</span>
          </button>
        </div>
        <template v-if="isOpen('unplanned')">
          <button
            v-for="item in moduleApis(null).filter((row) => matchesText(`${row.name} ${row.method} ${row.path}`))"
            :key="item.id"
            type="button"
            class="tree-row request-row"
            :class="[hintClass(`api-${item.id}`), { 'is-dragging': draggingId === item.id }]"
            draggable="true"
            @click="openApi(item)"
            @dragstart="beginDrag($event, item.id)"
            @dragend="endDrag"
            @dragover="overApiRow($event, item)"
            @drop.stop="moveApi({ id: Number(($event as DragEvent).dataTransfer?.getData('text/plain') || draggingId || 0), moduleId: null, beforeId: item.id, place: dropHint?.key === `api-${item.id}` && dropHint.place !== 'into' ? dropHint.place : 'before' }).catch(showError)"
          >
            <span class="tree-main">
              <span class="tree-arrow placeholder" />
              <span :class="['method-text', item.method.toLowerCase()]">{{ item.method }}</span>
              <span class="tree-label">{{ item.name }}</span>
            </span>
            <span class="tree-ops" @click.stop>
              <el-dropdown trigger="click">
                <button type="button" class="tree-op">...</button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item @click="renameApi(item).catch(showError)">重命名</el-dropdown-item>
                    <el-dropdown-item @click="deleteApi(item).catch(showError)">删除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </span>
          </button>
        </template>
      </div>
    </aside>
    <section class="ms-main">
      <div class="doc-bar">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          type="button"
          class="doc-tab"
          :class="{ active: tab.key === activeKey }"
          @click="activeKey = tab.key"
        >
          <span :class="['method-text', tab.method.toLowerCase()]">{{ tab.method }}</span>
          <span class="doc-tab-title">{{ tab.title }}</span>
          <span class="doc-tab-close" @click.stop="closeTab(tab.key)">×</span>
        </button>
        <el-button circle @click="openDraft">+</el-button>
      </div>
      <template v-if="activeTab">
        <div class="req-line">
          <el-select model-value="HTTP" style="width: 110px" disabled>
            <el-option label="HTTP" value="HTTP" />
          </el-select>
          <el-select v-model="activeTab.method" style="width: 110px">
            <el-option v-for="item in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']" :key="item" :label="item" :value="item" />
          </el-select>
          <el-select v-model="envId" clearable placeholder="选择环境" style="width: 140px">
            <el-option v-for="item in environments" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
          <el-input v-model="activeTab.url" placeholder="路径或完整 URL，也可粘贴 curl" @paste="onPasteUrl" />
          <el-button type="primary" plain @click="execute().catch(showError)">服务端执行</el-button>
          <el-button @click="openHistory().catch(showError)">历史</el-button>
          <el-button @click="save().catch(showError)">保存</el-button>
        </div>
        <div class="body-types">
          <button v-for="item in sections" :key="item" type="button" class="section-tab" :class="{ active: section === item }" @click="section = item">
            {{ item }}
            <span v-if="sectionCount(item)" class="section-count">{{ sectionCount(item) }}</span>
          </button>
        </div>
        <div v-if="section === '请求体'" class="body-types">
          <button
            v-for="item in bodyTypes"
            :key="item"
            type="button"
            :class="{ active: activeTab.bodyType === item }"
            @click="activeTab.bodyType = item"
          >
            {{ item }}
          </button>
        </div>
        <div v-if="section === '请求体' && activeTab.bodyType === 'none'" class="body-empty">请求没有 Body</div>
        <el-input
          v-else-if="section === '请求体'"
          v-model="activeTab.bodyText"
          type="textarea"
          :rows="8"
          placeholder="请求体"
        />
        <div v-else-if="section === '请求头'" class="header-table">
          <div class="header-row header-row-title">
            <span />
            <span>参数名称</span>
            <span>参数值</span>
            <span>描述</span>
            <el-button link type="primary" @click="openBatch('headers')">批量添加</el-button>
          </div>
          <div v-for="(param, index) in activeTab.headers" :key="index" class="header-row">
            <el-checkbox v-model="param.enabled" />
            <el-input v-model="param.name" placeholder="参数名称" @input="onHeaderInput(activeTab.headers)" />
            <el-input v-model="param.value" placeholder="参数值" @input="onHeaderInput(activeTab.headers)" />
            <el-input v-model="param.description" placeholder="描述" />
            <el-button link type="danger" @click="removeHeader(activeTab.headers, index)">－</el-button>
          </div>
        </div>
        <div v-else-if="section === 'REST'" class="header-table">
          <div class="header-row header-row-title">
            <span />
            <span>参数名称</span>
            <span>参数值</span>
            <span>描述</span>
            <span />
          </div>
          <div v-for="(param, index) in activeTab.rest" :key="index" class="header-row">
            <el-checkbox v-model="param.enabled" />
            <el-input v-model="param.name" placeholder="参数名称" @input="onHeaderInput(activeTab.rest)" />
            <el-input v-model="param.value" placeholder="参数值" @input="onHeaderInput(activeTab.rest)" />
            <el-input v-model="param.description" placeholder="描述" />
            <el-button link type="danger" @click="removeHeader(activeTab.rest, index)">－</el-button>
          </div>
        </div>
        <div v-else-if="section === 'Query'" class="header-table">
          <div class="header-row header-row-title">
            <span />
            <span>参数名称</span>
            <span>参数值</span>
            <span>描述</span>
            <el-button link type="primary" @click="openBatch('query')">批量添加</el-button>
          </div>
          <div v-for="(param, index) in activeTab.query" :key="index" class="header-row">
            <el-checkbox v-model="param.enabled" />
            <el-input v-model="param.name" placeholder="参数名称" @input="onHeaderInput(activeTab.query)" />
            <el-input v-model="param.value" placeholder="参数值" @input="onHeaderInput(activeTab.query)" />
            <el-input v-model="param.description" placeholder="描述" />
            <el-button link type="danger" @click="removeHeader(activeTab.query, index)">－</el-button>
          </div>
        </div>
        <div v-else class="body-empty">{{ section }}将在后续阶段接入</div>
        <div class="resp-pane" :class="{ side: layout === '左右' }">
          <div class="resp-head">
            <span>响应内容</span>
            <el-button-group>
              <el-button size="small" :type="layout === '上下' ? 'primary' : 'default'" @click="layout = '上下'">上下</el-button>
              <el-button size="small" :type="layout === '左右' ? 'primary' : 'default'" @click="layout = '左右'">左右</el-button>
            </el-button-group>
            <span v-if="activeTab.responseMeta">{{ activeTab.responseMeta }}</span>
          </div>
          <div class="resp-body">{{ activeTab.responseText || "点击 服务端执行 获取响应内容" }}</div>
          <div v-if="activeTab.assertions.length" class="assert-list">
            <div v-for="(item, index) in activeTab.assertions" :key="index" :class="item.passed ? 'assert-pass' : 'assert-fail'">
              {{ item.type }} · {{ item.message }}
            </div>
          </div>
        </div>
      </template>
    </section>
    <el-dialog v-model="historyVisible" title="调试历史" width="720px">
      <el-table :data="histories" size="small" @row-click="onHistory">
        <el-table-column prop="created_at" label="时间" width="170" />
        <el-table-column prop="method" label="方法" width="80" />
        <el-table-column prop="url" label="地址" min-width="220" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="70" />
        <el-table-column prop="elapsed_ms" label="耗时" width="80" />
      </el-table>
      <p class="hint">点击一行可把当时的请求填回当前页签。</p>
    </el-dialog>
    <el-dialog v-model="batchVisible" :title="batchTarget === 'headers' ? '批量添加请求头' : '批量添加 Query'" width="520px">
      <p class="hint">每行一个参数，格式为 名称:值。添加后默认勾选，会随请求发送。</p>
      <el-input
        v-model="batchText"
        type="textarea"
        :rows="8"
        :placeholder="batchTarget === 'headers' ? 'Content-Type:application/json' : 'page:1'"
      />
      <template #footer>
        <el-button @click="batchVisible = false">取消</el-button>
        <el-button type="primary" @click="applyBatch">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>
