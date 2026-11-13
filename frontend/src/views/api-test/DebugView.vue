<!--
@File    : DebugView.vue
@Desc    : 调试页。左侧请求树，右侧多页签请求编辑和响应区
@Author  : xuetang-api
@Date    : 2026-11-12
@Update  : 2026-11-13 按 MeterSphere 调试页布局重做
-->
<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { http, type ApiBody } from "@/api/http";
import DebugTree from "@/views/api-test/DebugTree.vue";
import RequestWorkbench from "@/views/api-test/RequestWorkbench.vue";

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
  draftId: string | null;
  moduleId: number | null;
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
  responseHeaders: { name: string; value: string }[];
  bodyBase64: string;
  bodyFormat: string;
  bodyEncoding: string;
  actualRequest: string;
  consoleText: string;
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
const addRootOpen = ref(false);
const tabs = ref<DocTab[]>([]);
const activeKey = ref("");
const environments = ref<EnvOption[]>([]);
const envId = ref<number | null>(null);
const drafts = ref<DraftRow[]>([]);
const selectedKey = ref("all");

interface DraftRow {
  id: string;
  title: string;
  method: string;
  url: string;
  bodyType: string;
  bodyText: string;
  query: ParamRow[];
  headers: ParamRow[];
  rest: ParamRow[];
}
let draftSeq = 1;
const activeTab = computed(() => tabs.value.find((item) => item.key === activeKey.value) || null);
const filteredApis = computed(() => {
  const text = keyword.value.trim().toLowerCase();
  if (!text) {
    return apis.value;
  }
  return apis.value.filter((item) => `${item.name} ${item.method} ${item.path}`.toLowerCase().includes(text));
});
const filteredDrafts = computed(() => {
  const text = keyword.value.trim().toLowerCase();
  if (!text) {
    return drafts.value;
  }
  return drafts.value.filter((item) => `${item.title} ${item.method} ${item.url}`.toLowerCase().includes(text));
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
    draftId: null,
    moduleId: null,
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
    responseHeaders: [],
    bodyBase64: "",
    bodyFormat: "预览",
    bodyEncoding: "UTF-8",
    actualRequest: "",
    consoleText: "",
    assertions: [],
    ...partial,
    key,
  };
}

function chosenModuleId(): number | null {
  if (selectedKey.value.startsWith("m-")) {
    return Number(selectedKey.value.slice(2));
  }
  if (selectedKey.value.startsWith("api-")) {
    const api = apis.value.find((item) => item.id === Number(selectedKey.value.slice(4)));
    return api?.module_id ?? null;
  }
  return null;
}

function selectDebugModule(moduleId: number): void {
  selectedKey.value = `m-${moduleId}`;
}

function openDraft(): void {
  const tab = blankTab({ moduleId: chosenModuleId() });
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

function displayUrl(path: string): string {
  const text = (path || "").trim();
  const absolute = text.replace(/^\/+/, "");
  if (/^https?:\/\//i.test(absolute)) {
    return absolute;
  }
  return text;
}

function openApi(row: ApiRow): void {
  selectedKey.value = `api-${row.id}`;
  const existing = tabs.value.find((item) => item.apiId === row.id);
  if (existing) {
    activeKey.value = existing.key;
    return;
  }
  const bodyType = row.request.body?.type || "none";
  const tab = blankTab({
    apiId: row.id,
    moduleId: row.module_id,
    title: row.name,
    method: row.method,
    url: displayUrl(row.path),
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
  drafts.value = readDrafts();
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
    apiId: null,
    title: item.name,
    method: request.method || api?.method || "GET",
    url: displayUrl(request.path || api?.path || ""),
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


function draftStorageKey(): string {
  return `xt_debug_drafts_${projectId.value}`;
}

function readDrafts(): DraftRow[] {
  try {
    const raw = localStorage.getItem(draftStorageKey());
    return raw ? (JSON.parse(raw) as DraftRow[]) : [];
  } catch {
    return [];
  }
}

function writeDrafts(rows: DraftRow[]): void {
  localStorage.setItem(draftStorageKey(), JSON.stringify(rows));
  drafts.value = rows;
}

function requestPayload(tab: DocTab): Record<string, unknown> {
  const kind = tab.bodyType === "form-data" ? "form" : tab.bodyType === "x-www-form-urlencoded" ? "urlencoded" : tab.bodyType === "json" ? "json" : tab.bodyType === "none" ? "none" : "raw";
  return {
    query: tab.query.filter((item) => item.name.trim() || item.value.trim()),
    headers: tab.headers.filter((item) => item.name.trim() || item.value.trim()),
    path_params: tab.rest.filter((item) => item.name.trim() || item.value.trim()),
    body: { type: kind, content: kind === "none" ? "" : tab.bodyText },
  };
}

function saveDraft(): void {
  const tab = activeTab.value;
  if (!tab) {
    return;
  }
  if (!tab.draftId) {
    tab.draftId = `draft-${Date.now()}`;
  }
  const row: DraftRow = {
    id: tab.draftId,
    title: tab.title.trim() || "未命名请求",
    method: tab.method,
    url: tab.url,
    bodyType: tab.bodyType,
    bodyText: tab.bodyText,
    query: tab.query,
    headers: tab.headers,
    rest: tab.rest,
  };
  writeDrafts([row, ...readDrafts().filter((item) => item.id !== row.id)]);
  ElMessage.success("调试请求已保存，未写入接口定义");
}

function openDraftRow(row: DraftRow): void {
  const existing = tabs.value.find((item) => item.draftId === row.id);
  if (existing) {
    activeKey.value = existing.key;
    return;
  }
  const tab = blankTab({
    draftId: row.id,
    title: row.title,
    method: row.method,
    url: row.url,
    bodyType: row.bodyType,
    bodyText: row.bodyText,
    query: withBlankHeader(row.query || []),
    headers: withBlankHeader(row.headers || []),
    rest: withBlankHeader(row.rest || []),
  });
  tabs.value.push(tab);
  activeKey.value = tab.key;
}

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

async function createModule(parentId: number | null, name: string): Promise<void> {
  const title = name.trim();
  if (!title) {
    ElMessage.warning("请填写名称");
    return;
  }
  await http.post(`/api/v1/projects/${projectId.value}/modules`, { name: title, parent_id: parentId });
  addName.value = "";
  if (parentId == null) {
    addRootOpen.value = false;
  }
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

onMounted(() => {
  load().catch(showError);
});

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
        <div class="tree-row" :class="{ active: selectedKey === 'all' }" @click="selectedKey = 'all'">
          <span class="tree-main">
            <span class="tree-icon">
              <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1.5 3.5A1.5 1.5 0 0 1 3 2h3.2a1.5 1.5 0 0 1 1.2.6L8.2 4H13a1.5 1.5 0 0 1 1.5 1.5v7A1.5 1.5 0 0 1 13 14H3a1.5 1.5 0 0 1-1.5-1.5v-9z" /></svg>
            </span>
            <span>全部接口 ({{ filteredApis.length }})</span>
          </span>
          <span class="tree-ops">
            <el-popover v-model:visible="addRootOpen" trigger="click" placement="bottom" :width="280">
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
        <div
          class="tree-row"
          :class="[{ active: selectedKey === 'none' }, hintClass('mod-unplanned')]"
          @dragover.prevent="dropHint = { key: 'mod-unplanned', place: 'into' }"
          @drop="moveApi({ id: Number(($event as DragEvent).dataTransfer?.getData('text/plain') || draggingId || 0), moduleId: null, beforeId: null, place: 'into' }).catch(showError)"
        >
          <button type="button" class="tree-main" @click="selectedKey = 'none'; toggleNode('unplanned')">
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
            :class="[hintClass(`api-${item.id}`), { 'is-dragging': draggingId === item.id, active: selectedKey === `api-${item.id}` }]"
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
          :selected-module-id="selectedKey.startsWith('m-') ? Number(selectedKey.slice(2)) : null"
          :selected-api-id="selectedKey.startsWith('api-') ? Number(selectedKey.slice(4)) : null"
          @toggle="toggleNode"
          @select-module="selectDebugModule"
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
      </div>
    </aside>
    <section class="ms-main debug-main">
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
      <RequestWorkbench v-if="activeTab" :project-id="projectId" :tab="activeTab" save-mode="debug" @saved="load().catch(showError)" />
    </section>
  </div>
</template>
