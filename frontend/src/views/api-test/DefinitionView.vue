<!--
@File    : DefinitionView.vue
@Desc    : 定义页。左侧模块树，右侧接口表格，对齐 MeterSphere
@Author  : xuetang-api
@Date    : 2026-11-12
@Update  : 2026-11-13 改为接口列表布局
-->
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { http, type ApiBody } from "@/api/http";
import CasePanel from "@/views/api-test/CasePanel.vue";
import DebugTree from "@/views/api-test/DebugTree.vue";
import RequestWorkbench from "@/views/api-test/RequestWorkbench.vue";

interface ModuleRow {
  id: number;
  parent_id: number | null;
  name: string;
  sort: number;
}
interface ParamRow {
  name: string;
  value: string;
  description?: string;
  enabled?: boolean;
  required?: boolean;
}
interface ApiRow {
  id: number;
  public_id: string;
  module_id: number | null;
  module: string;
  name: string;
  method: string;
  path: string;
  sort: number;
  description: string;
  request: { query?: ParamRow[]; headers?: ParamRow[]; path_params?: ParamRow[]; body?: { type: string; content: unknown } };
  case_count?: number;
  api_changed?: boolean;
  creator?: string;
  created_at?: string;
  updated_at?: string;
}
interface WorkTab {
  key: string;
  apiId: number | null;
  caseId: number | null;
  title: string;
  method: string;
  url: string;
  moduleId: number | null;
  bodyType: string;
  bodyText: string;
  headers: ParamRow[];
  query: ParamRow[];
  rest: ParamRow[];
  responseText: string;
  responseMeta: string;
  responseHeaders: { name: string; value: string }[];
  actualRequest: string;
  consoleText: string;
  bodyBase64: string;
  bodyFormat: string;
  bodyEncoding: string;
  assertions: { type: string; passed: boolean; message: string }[];
}
interface ExportPack {
  filename: string;
  content_base64: string;
}

const route = useRoute();
const projectId = computed(() => String(route.params.projectId || ""));
const modules = ref<ModuleRow[]>([]);
const apis = ref<ApiRow[]>([]);
const keyword = ref("");
const folderKey = ref("all");
const expanded = ref<Record<string, boolean>>({});
const addName = ref("");
const addRootOpen = ref(false);
const selected = ref<ApiRow[]>([]);
const tableRef = ref();
const listRef = ref<HTMLElement | null>(null);
const batchRef = ref<HTMLElement | null>(null);
const countRef = ref<HTMLElement | null>(null);
const tableMaxHeight = ref(420);
let tableObserver: ResizeObserver | null = null;
const moveVisible = ref(false);
const moveTarget = ref<number | null>(null);
const draggingId = ref<number | null>(null);
const dropHint = ref<{ key: string; place: "before" | "after" | "into" } | null>(null);
const apiVisible = ref(false);
const importVisible = ref(false);
const importFile = ref<File | null>(null);
const caseVisible = ref(false);
const caseApiId = ref<number | null>(null);
const editingId = ref<number | null>(null);
const workTabs = ref<WorkTab[]>([]);
const activeWork = ref("");
const currentWork = computed(() => workTabs.value.find((item) => item.key === activeWork.value) || null);
const apiForm = reactive({ name: "", method: "GET", path: "/", module_id: null as number | null, description: "" });

const visibleApis = computed(() => {
  const text = keyword.value.trim().toLowerCase();
  return apis.value.filter((item) => {
    const inFolder =
      folderKey.value === "all" ||
      (folderKey.value === "none" && item.module_id == null) ||
      folderKey.value === `m-${item.module_id}`;
    const matched = !text || `${item.public_id} ${item.name} ${item.path}`.toLowerCase().includes(text);
    return inFolder && matched;
  });
});

function countOf(id: number | null): number {
  return apis.value.filter((item) => (item.module_id ?? null) === id).length;
}

function showError(error: unknown): void {
  if (error === "cancel" || error === "close") {
    return;
  }
  ElMessage.error(error instanceof Error ? error.message : "操作失败");
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

function moduleApis(moduleId: number | null): ApiRow[] {
  return apis.value
    .filter((item) => (item.module_id ?? null) === moduleId)
    .sort((left, right) => (left.sort ?? 0) - (right.sort ?? 0) || left.id - right.id);
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

function selectModule(moduleId: number): void {
  folderKey.value = `m-${moduleId}`;
}

function hintClass(key: string): string {
  if (dropHint.value?.key !== key) {
    return "";
  }
  return dropHint.value.place === "into" ? "drop-into" : dropHint.value.place === "before" ? "drop-before" : "drop-after";
}

function endDrag(): void {
  draggingId.value = null;
  dropHint.value = null;
}

function beginDrag(event: DragEvent, id: number): void {
  draggingId.value = id;
  event.dataTransfer?.setData("text/plain", String(id));
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = "move";
  }
}

function overApiRow(event: DragEvent, item: ApiRow): void {
  event.preventDefault();
  if (draggingId.value === item.id) {
    dropHint.value = null;
    return;
  }
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
  dropHint.value = { key: `api-${item.id}`, place: event.clientY < rect.top + rect.height / 2 ? "before" : "after" };
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

async function createModule(parentId: number | null, name: string): Promise<void> {
  if (!name.trim()) {
    ElMessage.warning("请填写目录名称");
    return;
  }
  await http.post(`/api/v1/projects/${projectId.value}/modules`, { name: name.trim(), parent_id: parentId });
  addName.value = "";
  if (parentId == null) {
    addRootOpen.value = false;
  }
  await load();
}

async function renameModule(folder: ModuleRow): Promise<void> {
  const { value } = await ElMessageBox.prompt("请输入名称", "重命名", {
    inputValue: folder.name,
    inputPattern: /\S+/,
    inputErrorMessage: "请填写名称",
  });
  await http.put(`/api/v1/projects/${projectId.value}/modules/${folder.id}`, { name: value.trim(), parent_id: folder.parent_id });
  await load();
}

async function deleteModule(folder: ModuleRow): Promise<void> {
  await ElMessageBox.confirm(`确定删除目录 ${folder.name}？`, "删除确认", { type: "warning" });
  await http.delete(`/api/v1/projects/${projectId.value}/modules/${folder.id}`);
  if (folderKey.value === `m-${folder.id}`) {
    folderKey.value = "all";
  }
  await load();
}

async function renameApi(row: Pick<ApiRow, "id" | "name" | "method" | "path" | "module_id" | "description" | "request">): Promise<void> {
  const { value } = await ElMessageBox.prompt("请输入名称", "重命名", {
    inputValue: row.name,
    inputPattern: /\S+/,
    inputErrorMessage: "请填写名称",
  });
  await http.put(`/api/v1/projects/${projectId.value}/definitions/${row.id}`, {
    name: value.trim(),
    method: row.method,
    path: row.path,
    module_id: row.module_id,
    description: row.description || "",
    request_json: row.request || { query: [], headers: [], path_params: [], body: { type: "none", content: "" } },
    examples: [],
  });
  await load();
}

async function load(): Promise<void> {
  const base = `/api/v1/projects/${projectId.value}`;
  const [moduleBody, apiBody] = await Promise.all([
    http.get<ApiBody<ModuleRow[]>>(`${base}/modules`),
    http.get<ApiBody<ApiRow[]>>(`${base}/definitions`),
  ]);
  modules.value = moduleBody.data.data;
  apis.value = apiBody.data.data;
}

function openCreate(): void {
  editingId.value = null;
  apiForm.name = "";
  apiForm.method = "GET";
  apiForm.path = "/";
  apiForm.module_id = folderKey.value.startsWith("m-") ? Number(folderKey.value.slice(2)) : null;
  apiForm.description = "";
  apiVisible.value = true;
}

async function openEdit(row: ApiRow): Promise<void> {
  editingId.value = row.id;
  apiForm.name = row.name;
  apiForm.method = row.method;
  apiForm.path = row.path;
  apiForm.module_id = row.module_id;
  apiForm.description = row.description || "";
  apiVisible.value = true;
}

async function saveApi(): Promise<void> {
  if (!apiForm.name.trim() || !apiForm.path.trim()) {
    ElMessage.warning("请填写接口名称和路径");
    return;
  }
  const payload = {
    name: apiForm.name.trim(),
    method: apiForm.method,
    path: apiForm.path.trim(),
    module_id: apiForm.module_id,
    description: apiForm.description,
    request_json: { query: [], headers: [], path_params: [], body: { type: "none", content: "" } },
    examples: [],
  };
  if (editingId.value) {
    await http.put(`/api/v1/projects/${projectId.value}/definitions/${editingId.value}`, payload);
  } else {
    await http.post(`/api/v1/projects/${projectId.value}/definitions`, payload);
  }
  apiVisible.value = false;
  ElMessage.success("接口已保存");
  await load();
}

async function copyApi(row: ApiRow): Promise<void> {
  await http.post(`/api/v1/projects/${projectId.value}/definitions`, {
    name: `${row.name} 副本`,
    method: row.method,
    path: row.path,
    module_id: row.module_id,
    description: row.description,
    request_json: { query: [], headers: [], path_params: [], body: { type: "none", content: "" } },
    examples: [],
  });
  ElMessage.success("已复制接口");
  await load();
}

function openCases(apiId: number | null): void {
  caseApiId.value = apiId;
  caseVisible.value = true;
}

function focusApi(row: Pick<ApiRow, "module_id">): void {
  folderKey.value = row.module_id == null ? "none" : `m-${row.module_id}`;
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

function displayUrl(path: string): string {
  const text = (path || "").trim();
  const absolute = text.replace(/^\/+/, "");
  if (/^https?:\/\//i.test(absolute)) {
    return absolute;
  }
  return text;
}

function withBlank(rows: ParamRow[] | undefined): ParamRow[] {
  const items = (rows || []).map((item) => ({
    name: item.name || "",
    value: item.value || "",
    description: item.description || "",
    enabled: item.enabled !== false,
  }));
  const last = items[items.length - 1];
  if (!last || last.name.trim() || last.value.trim()) {
    items.push({ name: "", value: "", description: "", enabled: true });
  }
  return items;
}

function blankWork(partial: Partial<WorkTab> & Pick<WorkTab, "key" | "title" | "method" | "url">): WorkTab {
  return {
    apiId: null,
    caseId: null,
    moduleId: null,
    bodyType: "none",
    bodyText: "",
    query: withBlank([]),
    headers: withBlank([]),
    rest: withBlank([]),
    responseText: "",
    responseMeta: "",
    responseHeaders: [],
    actualRequest: "",
    consoleText: "",
    bodyBase64: "",
    bodyFormat: "预览",
    bodyEncoding: "UTF-8",
    assertions: [],
    ...partial,
  };
}

function runApi(row: ApiRow): void {
  const existing = workTabs.value.find((item) => item.apiId === row.id && !item.caseId);
  if (existing) {
    activeWork.value = existing.key;
    return;
  }
  const bodyType = row.request?.body?.type || "none";
  const key = `api-${row.id}`;
  workTabs.value.push(blankWork({
    key,
    apiId: row.id,
    title: row.name,
    method: row.method,
    url: displayUrl(row.path),
    moduleId: row.module_id,
    bodyType: bodyType === "form" ? "form-data" : bodyType === "urlencoded" ? "x-www-form-urlencoded" : bodyType,
    bodyText: textOf(row.request?.body?.content),
    query: withBlank(row.request?.query),
    headers: withBlank(row.request?.headers),
    rest: withBlank(row.request?.path_params),
  }));
  activeWork.value = key;
}

function onExecuteCase(row: { id: number; name: string; api_id: number | null }): void {
  runCase(row).catch(showError);
}

async function runCase(row: { id: number; name: string; api_id: number | null }): Promise<void> {
  caseVisible.value = false;
  const existing = workTabs.value.find((item) => item.caseId === row.id);
  if (existing) {
    activeWork.value = existing.key;
    return;
  }
  const response = await http.get<ApiBody<{ id: number; name: string; api_id: number | null; request: ApiRow["request"] & { method?: string; path?: string } }>>(
    `/api/v1/projects/${projectId.value}/cases/${row.id}`,
  );
  const item = response.data.data;
  const api = apis.value.find((entry) => entry.id === item.api_id);
  const request = item.request || {};
  const body = request.body || api?.request.body;
  const bodyType = body?.type || "none";
  const key = `case-${item.id}`;
  workTabs.value.push(blankWork({
    key,
    apiId: item.api_id,
    caseId: item.id,
    title: item.name,
    method: request.method || api?.method || "GET",
    url: displayUrl(request.path || api?.path || ""),
    moduleId: api?.module_id ?? null,
    bodyType: bodyType === "form" ? "form-data" : bodyType === "urlencoded" ? "x-www-form-urlencoded" : bodyType || "none",
    bodyText: textOf(body?.content),
    query: withBlank((request.query as ParamRow[] | undefined) || api?.request.query),
    headers: withBlank((request.headers as ParamRow[] | undefined) || api?.request.headers),
    rest: withBlank((request.path_params as ParamRow[] | undefined) || api?.request.path_params),
  }));
  activeWork.value = key;
}

function closeWork(key: string): void {
  const index = workTabs.value.findIndex((item) => item.key === key);
  if (index < 0) {
    return;
  }
  workTabs.value.splice(index, 1);
  if (activeWork.value === key) {
    activeWork.value = workTabs.value[index]?.key || workTabs.value[index - 1]?.key || "";
  }
}

async function removeApi(row: Pick<ApiRow, "id" | "name">): Promise<void> {
  await ElMessageBox.confirm(`确定删除接口 ${row.name}？`, "删除确认", { type: "warning" });
  await http.delete(`/api/v1/projects/${projectId.value}/definitions/${row.id}`);
  await load();
}

function onFile(event: Event): void {
  importFile.value = (event.target as HTMLInputElement).files?.[0] || null;
}

async function saveImport(): Promise<void> {
  if (!importFile.value) {
    ElMessage.warning("请选择文件");
    return;
  }
  const form = new FormData();
  form.append("file", importFile.value);
  const response = await http.post<ApiBody<{ created: number; updated: number }>>(
    `/api/v1/projects/${projectId.value}/definitions/import`,
    form,
  );
  ElMessage.success(`新增 ${response.data.data.created}，更新 ${response.data.data.updated}`);
  importVisible.value = false;
  await load();
}

async function download(format: "json" | "xlsx", rows: ApiRow[] = selected.value): Promise<void> {
  const response = await http.get<ApiBody<ExportPack>>(`/api/v1/projects/${projectId.value}/definitions/export`, {
    params: { format, ids: rows.map((item) => item.id).join(",") },
  });
  const binary = atob(response.data.data.content_base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  const url = URL.createObjectURL(new Blob([bytes]));
  const link = document.createElement("a");
  link.href = url;
  link.download = response.data.data.filename;
  link.click();
  URL.revokeObjectURL(url);
}

function editSelected(): void {
  if (selected.value.length !== 1) {
    ElMessage.warning("请选择一条接口再编辑");
    return;
  }
  openEdit(selected.value[0]).catch(showError);
}

async function confirmMove(): Promise<void> {
  if (!selected.value.length) {
    return;
  }
  const ids = new Set(selected.value.map((item) => item.id));
  await http.put(`/api/v1/projects/${projectId.value}/definitions/layout`, {
    modules: [],
    apis: apis.value.map((item) => ({
      id: item.id,
      module_id: ids.has(item.id) ? moveTarget.value : item.module_id,
      sort: item.sort ?? 0,
    })),
  });
  moveVisible.value = false;
  ElMessage.success("已移动");
  await load();
}

async function deleteSelected(): Promise<void> {
  if (!selected.value.length) {
    return;
  }
  await ElMessageBox.confirm(`确定删除选中的 ${selected.value.length} 个接口？`, "删除确认", { type: "warning" });
  for (const row of selected.value) {
    await http.delete(`/api/v1/projects/${projectId.value}/definitions/${row.id}`);
  }
  selected.value = [];
  ElMessage.success("已删除");
  await load();
}

function clearSelected(): void {
  selected.value = [];
  tableRef.value?.clearSelection();
}

function syncTableHeight(): void {
  const list = listRef.value;
  if (!list) {
    return;
  }
  const batch = batchRef.value?.offsetHeight ?? 0;
  const count = countRef.value?.offsetHeight ?? 0;
  const gap = (batch > 0 ? 8 : 0) + (count > 0 ? 8 : 0);
  const height = list.clientHeight - batch - count - gap;
  if (height > 80) {
    tableMaxHeight.value = height;
  }
}

watch(listRef, (element) => {
  tableObserver?.disconnect();
  tableObserver = null;
  if (!element) {
    return;
  }
  tableObserver = new ResizeObserver(() => syncTableHeight());
  tableObserver.observe(element);
  syncTableHeight();
});

watch(() => selected.value.length, () => nextTick(syncTableHeight));

onMounted(() => load().catch(showError));
onBeforeUnmount(() => tableObserver?.disconnect());
watch(projectId, () => load().catch(showError));
</script>

<template>
  <div class="ms-page">
    <aside class="ms-side">
      <div class="ms-side-pad">
        <div class="ms-side-search">
          <el-input v-model="keyword" clearable placeholder="请输入模块/接口名称" />
          <el-button type="primary" @click="openCreate">新建接口</el-button>
        </div>
        <div class="tree-row" :class="{ active: folderKey === 'all' }" @click="folderKey = 'all'">
          <span class="tree-main">
            <span class="tree-icon">
              <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1.5 3.5A1.5 1.5 0 0 1 3 2h3.2a1.5 1.5 0 0 1 1.2.6L8.2 4H13a1.5 1.5 0 0 1 1.5 1.5v7A1.5 1.5 0 0 1 13 14H3a1.5 1.5 0 0 1-1.5-1.5v-9z" /></svg>
            </span>
            <span>全部接口 ({{ apis.length }})</span>
          </span>
          <span class="tree-ops" @click.stop>
            <el-popover v-model:visible="addRootOpen" trigger="click" placement="bottom" :width="280">
              <template #reference>
                <button type="button" class="tree-op">+</button>
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
        <div
          class="tree-row"
          :class="[{ active: folderKey === 'none' }, hintClass('mod-unplanned')]"
          @dragover.prevent="dropHint = { key: 'mod-unplanned', place: 'into' }"
          @drop="moveApi({ id: Number(($event as DragEvent).dataTransfer?.getData('text/plain') || draggingId || 0), moduleId: null, beforeId: null, place: 'into' }).catch(showError)"
        >
          <button type="button" class="tree-main" @click="folderKey = 'none'; toggleNode('unplanned')">
            <span class="tree-arrow" :class="{ open: isOpen('unplanned') }">▸</span>
            <span class="tree-icon">
              <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1.5 3.5A1.5 1.5 0 0 1 3 2h3.2a1.5 1.5 0 0 1 1.2.6L8.2 4H13a1.5 1.5 0 0 1 1.5 1.5v7A1.5 1.5 0 0 1 13 14H3a1.5 1.5 0 0 1-1.5-1.5v-9z" /></svg>
            </span>
            <span>未规划接口</span>
            <span class="ms-count">{{ countOf(null) }}</span>
          </button>
        </div>
        <template v-if="isOpen('unplanned')">
          <button
            v-for="item in moduleApis(null).filter((row) => matchesText(`${row.name} ${row.method} ${row.path}`))"
            :key="`top-${item.id}`"
            type="button"
            class="tree-row request-row"
            :class="[hintClass(`api-${item.id}`), { 'is-dragging': draggingId === item.id }]"
            draggable="true"
            @click="focusApi(item)"
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
                    <el-dropdown-item @click="removeApi(item).catch(showError)">删除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </span>
          </button>
        </template>
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
          @select-module="selectModule"
          @open-api="focusApi"
          @create-module="(parentId, name) => createModule(parentId, name).catch(showError)"
          @rename-module="(folder) => renameModule(folder).catch(showError)"
          @delete-module="(folder) => deleteModule(folder).catch(showError)"
          @rename-api="(row) => renameApi(row).catch(showError)"
          @delete-api="(row) => removeApi(row).catch(showError)"
          @move-api="(payload) => moveApi(payload).catch(showError)"
          @hint="dropHint = $event"
          @drag-start="draggingId = $event"
          @drag-end="endDrag"
        />
      </div>
    </aside>
    <section class="ms-main def-main" :class="{ 'is-running': currentWork }">
      <div class="doc-bar">
        <button type="button" class="doc-tab" :class="{ active: !activeWork }" @click="activeWork = ''">全部接口</button>
        <button
          v-for="tab in workTabs"
          :key="tab.key"
          type="button"
          class="doc-tab"
          :class="{ active: activeWork === tab.key }"
          @click="activeWork = tab.key"
        >
          <span :class="['method-text', tab.method.toLowerCase()]">{{ tab.method }}</span>
          <span class="doc-tab-title">{{ tab.title }}</span>
          <span class="doc-tab-close" @click.stop="closeWork(tab.key)">×</span>
        </button>
      </div>
      <RequestWorkbench
        v-if="currentWork"
        :project-id="projectId"
        :tab="currentWork"
        :save-mode="currentWork.caseId ? 'case' : 'definition'"
        @saved="load().catch(showError)"
      />
      <template v-else>
      <div class="req-line">
        <el-button @click="openCases(null)">新建用例</el-button>
        <el-button @click="importVisible = true">导入接口</el-button>
        <span class="doc-bar-gap" />
        <span class="def-folder">{{ folderKey === 'all' ? '全部接口' : folderKey === 'none' ? '未规划接口' : modules.find((item) => folderKey === `m-${item.id}`)?.name || '接口' }}</span>
      </div>
      <div ref="listRef" class="def-list">
      <div class="def-table-wrap">
      <el-table ref="tableRef" :data="visibleApis" :max-height="tableMaxHeight" scrollbar-always-on @selection-change="selected = $event">
        <el-table-column type="selection" width="48" />
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="接口名称" min-width="180">
          <template #default="{ row }">
            <span>{{ row.name }}</span>
            <el-tag v-if="row.api_changed" class="case-flag" size="small" type="warning">接口已变更</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="协议" width="90">
          <template #default>HTTP</template>
        </el-table-column>
        <el-table-column label="请求类型" width="110">
          <template #default="{ row }">
            <span :class="['method-text', row.method.toLowerCase()]">{{ row.method }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="path" label="路径" min-width="220" show-overflow-tooltip />
        <el-table-column label="状态" width="100">
          <template #default><el-tag size="small">进行中</el-tag></template>
        </el-table-column>
        <el-table-column prop="module" label="所属模块" width="120" />
        <el-table-column label="用例数" width="90">
          <template #default="{ row }">
            <el-button link type="primary" @click="openCases(row.id)">{{ row.case_count || 0 }}</el-button>
          </template>
        </el-table-column>
        <el-table-column label="创建人" width="110" show-overflow-tooltip>
          <template #default="{ row }">{{ row.creator || "—" }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170" />
        <el-table-column prop="updated_at" label="更新时间" width="170" />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="primary" @click="runApi(row)">执行</el-button>
            <el-button link type="primary" @click="copyApi(row).catch(showError)">复制</el-button>
            <el-button link type="danger" @click="removeApi(row).catch(showError)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      </div>
      <div v-if="selected.length" ref="batchRef" class="batch-bar">
        <span>已选择 {{ selected.length }} 条</span>
        <el-dropdown>
          <el-button>导出</el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="download('json').catch(showError)">导出 JSON</el-dropdown-item>
              <el-dropdown-item @click="download('xlsx').catch(showError)">导出 Excel</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button @click="editSelected">编辑</el-button>
        <el-button @click="moveTarget = null; moveVisible = true">移动</el-button>
        <el-dropdown>
          <el-button>...</el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="deleteSelected().catch(showError)">删除</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button link type="primary" @click="clearSelected">清空</el-button>
      </div>
      <div ref="countRef" class="ms-count">共 {{ visibleApis.length }} 条</div>
      </div>
      </template>
    </section>
    <el-dialog v-model="apiVisible" :title="editingId ? '编辑接口' : '新建接口'" width="520px">
      <el-form label-position="top">
        <el-form-item label="接口名称"><el-input v-model="apiForm.name" /></el-form-item>
        <el-form-item label="请求类型">
          <el-select v-model="apiForm.method" style="width: 100%">
            <el-option v-for="item in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="路径"><el-input v-model="apiForm.path" /></el-form-item>
        <el-form-item label="所属模块">
          <el-select v-model="apiForm.module_id" clearable placeholder="未规划接口" style="width: 100%">
            <el-option v-for="item in modules" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明"><el-input v-model="apiForm.description" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="apiVisible = false">取消</el-button>
        <el-button type="primary" @click="saveApi().catch(showError)">确定</el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="moveVisible" title="移动到" width="420px">
      <el-select v-model="moveTarget" placeholder="未规划接口" style="width: 100%">
        <el-option label="未规划接口" :value="null" />
        <el-option v-for="item in modules" :key="item.id" :label="item.name" :value="item.id" />
      </el-select>
      <template #footer>
        <el-button @click="moveVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmMove().catch(showError)">确定</el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="importVisible" title="导入接口" width="480px">
      <p class="hint">支持 OpenAPI 2、OpenAPI 3、Postman v2.1 和 HAR。</p>
      <input type="file" accept=".json,.yaml,.yml,.har" @change="onFile" />
      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button type="primary" @click="saveImport().catch(showError)">导入</el-button>
      </template>
    </el-dialog>
    <CasePanel v-model="caseVisible" :project-id="projectId" :api-id="caseApiId" :apis="apis" @changed="load().catch(showError)" @execute="onExecuteCase" />
  </div>
</template>
