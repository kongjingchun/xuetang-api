<!--
@File    : RequestWorkbench.vue
@Desc    : 调试页和定义页共用的请求编辑器，展示和参数保持一致
@Author  : xuetang-api
@Date    : 2026-11-13
-->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { http, type ApiBody } from "@/api/http";
import { parseCurl } from "@/utils/curl";
import { BODY_ENCODINGS, BODY_FORMATS, bytesFromBase64, contentTypeOf, detectEncoding, detectFormat, presentBody } from "@/utils/responseBody";
import ResponsePreview from "@/views/api-test/ResponsePreview.vue";

interface ParamRow {
  name: string;
  value: string;
  description?: string;
  enabled?: boolean;
}
export interface RequestTab {
  apiId: number | null;
  caseId: number | null;
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
}
interface HistoryRow {
  id: number;
  method: string;
  url: string;
  status: number;
  elapsed_ms: number;
  created_at: string;
}
interface ModuleOption {
  id: number;
  name: string;
}

const props = defineProps<{ projectId: string; tab: RequestTab; saveMode: "debug" | "definition" | "case" }>();
const emit = defineEmits<{ saved: [] }>();
const section = ref("请求体");
const respTab = ref("响应体");
const respTabs = ["响应体", "响应头", "实际请求", "控制台"];
const layout = ref("上下");
const sections = ["请求头", "请求体", "Query", "REST", "前置", "后置", "认证", "设置"];
const bodyTypes = ["none", "form-data", "x-www-form-urlencoded", "json", "xml", "raw", "binary"];
const environments = ref<EnvOption[]>([]);
const envId = ref<number | null>(null);
const historyVisible = ref(false);
const histories = ref<HistoryRow[]>([]);
const batchVisible = ref(false);
const batchText = ref("");
const batchTarget = ref<"headers" | "query">("headers");
const saveAsVisible = ref(false);
const saveAsForm = reactive({ name: "", url: "", moduleId: null as number | null });
const modules = ref<ModuleOption[]>([]);
const shortcutLabel = /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘+S" : "Ctrl+S";

const decodedBody = computed(() => {
  const tab = props.tab;
  if (!tab.bodyBase64) {
    return tab.responseText || "";
  }
  return presentBody(tab.bodyBase64, tab.bodyEncoding, "Text");
});
const displayBody = computed(() => {
  const tab = props.tab;
  if (!tab.bodyBase64) {
    return tab.responseText || "";
  }
  return presentBody(tab.bodyBase64, tab.bodyEncoding, tab.bodyFormat === "预览" ? "JSON" : tab.bodyFormat);
});

watch(
  () => [props.tab.bodyFormat, decodedBody.value] as const,
  () => {
    if (props.tab.bodyFormat !== "预览" || !decodedBody.value.trim()) {
      return;
    }
    const next = detectFormat(decodedBody.value, contentTypeOf(props.tab.responseHeaders));
    if (next !== "预览") {
      props.tab.bodyFormat = next;
    }
  },
);

function showError(error: unknown): void {
  ElMessage.error(error instanceof Error ? error.message : "操作失败");
}

function emptyHeader(): ParamRow {
  return { name: "", value: "", description: "", enabled: true };
}

function filledCount(rows: ParamRow[]): number {
  return rows.filter((item) => item.name.trim() || item.value.trim()).length;
}

function sectionCount(name: string): number {
  if (name === "请求头") {
    return filledCount(props.tab.headers);
  }
  if (name === "Query") {
    return filledCount(props.tab.query);
  }
  if (name === "REST") {
    return filledCount(props.tab.rest);
  }
  return 0;
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

function bodyKind(bodyType: string): string {
  if (bodyType === "form-data") {
    return "form";
  }
  if (bodyType === "x-www-form-urlencoded") {
    return "urlencoded";
  }
  if (bodyType === "json" || bodyType === "none") {
    return bodyType;
  }
  return "raw";
}

function requestPayload(): Record<string, unknown> {
  const tab = props.tab;
  const kind = bodyKind(tab.bodyType);
  return {
    query: tab.query.filter((item) => item.name.trim() || item.value.trim()),
    headers: tab.headers.filter((item) => item.name.trim() || item.value.trim()),
    path_params: tab.rest.filter((item) => item.name.trim() || item.value.trim()),
    body: { type: kind, content: kind === "none" ? "" : tab.bodyText },
  };
}

onMounted(async () => {
  window.addEventListener("keydown", onSaveKey);
  const response = await http.get<ApiBody<EnvOption[]>>(`/api/v1/projects/${props.projectId}/debug/environments`);
  environments.value = response.data.data;
  envId.value = environments.value[0]?.id ?? null;
});
onBeforeUnmount(() => window.removeEventListener("keydown", onSaveKey));

async function execute(): Promise<void> {
  const tab = props.tab;
  if (!tab.url.trim()) {
    tab.responseMeta = "";
    tab.responseText = "请填写路径，或包含 http/https 的完整 URL";
    tab.responseHeaders = [];
    tab.bodyBase64 = "";
    tab.actualRequest = "";
    tab.consoleText = "";
    tab.assertions = [];
    return;
  }
  const response = await http.post<ApiBody<{
    status: number;
    elapsed_ms: number;
    body: string;
    body_base64: string;
    error: string;
    headers: Record<string, string>;
    request: { method: string; url: string; headers: Record<string, string>; body: string };
    console: string[];
    assertions: RequestTab["assertions"];
    passed: boolean;
  }>>(`/api/v1/projects/${props.projectId}/debug/send`, {
    env_id: envId.value,
    method: tab.method,
    url: tab.url,
    headers: tab.headers,
    query: tab.query,
    rest: tab.rest,
    body_type: bodyKind(tab.bodyType),
    body_text: tab.bodyText,
    target_type: tab.caseId ? "case" : "api",
    target_id: tab.apiId || 0,
    case_id: tab.caseId,
  });
  const data = response.data.data;
  const sent = data.request || { method: tab.method, url: tab.url, headers: {}, body: "" };
  tab.assertions = data.assertions || [];
  tab.responseHeaders = Object.entries(data.headers || {}).map(([name, value]) => ({ name, value }));
  tab.bodyBase64 = data.body_base64 || "";
  if (tab.bodyBase64) {
    const bytes = bytesFromBase64(tab.bodyBase64);
    const media = contentTypeOf(data.headers || {});
    tab.bodyEncoding = detectEncoding(bytes, media);
    tab.bodyFormat = detectFormat(presentBody(tab.bodyBase64, tab.bodyEncoding, "Text"), media);
  }
  tab.actualRequest = [sent.method, sent.url, "", ...Object.entries(sent.headers || {}).map(([name, value]) => `${name}: ${value}`), "", sent.body || ""].join("\n");
  tab.consoleText = (data.console || []).join("\n");
  tab.responseMeta = data.error
    ? `请求失败 ${data.error} · ${data.elapsed_ms} ms`
    : `${data.status} · ${data.elapsed_ms} ms${tab.caseId ? (data.passed ? " · 断言通过" : " · 断言失败") : ""}`;
  tab.responseText = data.body || (data.error ? data.error : "响应体为空");
}

async function openHistory(): Promise<void> {
  const response = await http.get<ApiBody<HistoryRow[]>>(`/api/v1/projects/${props.projectId}/debug/history`);
  histories.value = response.data.data;
  historyVisible.value = true;
}

function onHistory(row: HistoryRow): void {
  restoreHistory(row).catch(showError);
}

async function restoreHistory(row: HistoryRow): Promise<void> {
  const response = await http.get<ApiBody<{ request: { method: string; url: string; headers: Record<string, string>; body_type: string; body: string } }>>(
    `/api/v1/projects/${props.projectId}/debug/history/${row.id}`,
  );
  const request = response.data.data.request;
  const tab = props.tab;
  tab.method = request.method || "GET";
  tab.url = request.url || "";
  tab.bodyType = request.body_type === "form" ? "form-data" : request.body_type === "urlencoded" ? "x-www-form-urlencoded" : request.body_type || "raw";
  tab.bodyText = request.body || "";
  tab.headers = withBlank(Object.entries(request.headers || {}).map(([name, value]) => ({ name, value, enabled: true, description: "" })));
  historyVisible.value = false;
}

function withBlank(rows: ParamRow[]): ParamRow[] {
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

function applyParsedCurl(text: string): boolean {
  const parsed = parseCurl(text);
  if (!parsed) {
    return false;
  }
  const tab = props.tab;
  tab.method = parsed.method;
  tab.url = parsed.url;
  tab.headers = withBlank(parsed.headers);
  tab.query = withBlank(parsed.query);
  tab.rest = withBlank(parsed.rest);
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

function openBatch(target: "headers" | "query"): void {
  batchTarget.value = target;
  batchText.value = "";
  batchVisible.value = true;
}

function applyBatch(): void {
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
    parsed.push({ name: text.slice(0, splitAt).trim(), value: text.slice(splitAt + 1).trim(), description: "", enabled: true });
  }
  const label = batchTarget.value === "headers" ? "请求头" : "Query";
  if (!parsed.length) {
    ElMessage.warning(`请填写要添加的${label}`);
    return;
  }
  const rows = batchTarget.value === "headers" ? props.tab.headers : props.tab.query;
  const filled = rows.filter((item) => item.name.trim() || item.value.trim());
  rows.splice(0, rows.length, ...filled, ...parsed, emptyHeader());
  batchText.value = "";
  batchVisible.value = false;
}

async function openSaveDialog(): Promise<void> {
  if (props.saveMode === "definition" && props.tab.apiId) {
    await saveDefinition();
    return;
  }
  if (props.saveMode === "case" && props.tab.caseId) {
    await saveCase();
    return;
  }
  await openSaveAs();
}

async function openSaveAs(): Promise<void> {
  const tab = props.tab;
  if (!tab.url.trim()) {
    ElMessage.warning("请先填写请求 URL");
    return;
  }
  const response = await http.get<ApiBody<ModuleOption[]>>(`/api/v1/projects/${props.projectId}/modules`);
  modules.value = response.data.data;
  saveAsForm.name = tab.title === "新建请求" ? "" : tab.title;
  saveAsForm.url = tab.url;
  saveAsForm.moduleId = tab.moduleId;
  saveAsVisible.value = true;
}

async function confirmSaveAs(): Promise<void> {
  const tab = props.tab;
  if (!saveAsForm.name.trim() || !saveAsForm.url.trim()) {
    ElMessage.warning("请填写请求名称和请求 URL");
    return;
  }
  const payload = {
    name: saveAsForm.name.trim(),
    method: tab.method,
    path: saveAsForm.url.trim(),
    module_id: saveAsForm.moduleId,
    description: "",
    request_json: requestPayload(),
    examples: [],
  };
  const created = tab.apiId
    ? await http.put<ApiBody<{ id: number }>>(`/api/v1/projects/${props.projectId}/definitions/${tab.apiId}`, payload)
    : await http.post<ApiBody<{ id: number }>>(`/api/v1/projects/${props.projectId}/definitions`, payload);
  tab.apiId = created.data.data.id;
  tab.title = saveAsForm.name.trim();
  tab.url = saveAsForm.url.trim();
  tab.moduleId = saveAsForm.moduleId;
  saveAsVisible.value = false;
  ElMessage.success("接口已保存");
  emit("saved");
}

async function saveDefinition(): Promise<void> {
  const tab = props.tab;
  if (!tab.apiId) {
    await openSaveAs();
    return;
  }
  const current = await http.get<ApiBody<{ tags?: string; description?: string; examples?: { name: string; status_code: number; headers_json: Record<string, string>; body: string; description: string }[] }>>(
    `/api/v1/projects/${props.projectId}/definitions/${tab.apiId}`,
  );
  const detail = current.data.data;
  await http.put(`/api/v1/projects/${props.projectId}/definitions/${tab.apiId}`, {
    name: tab.title,
    method: tab.method,
    path: tab.url.trim() || "/",
    module_id: tab.moduleId,
    tags: detail.tags || "",
    description: detail.description || "",
    request_json: requestPayload(),
    examples: (detail.examples || []).map((item) => ({
      name: item.name,
      status_code: item.status_code,
      headers_json: item.headers_json || {},
      body: item.body || "",
      description: item.description || "",
    })),
  });
  ElMessage.success("接口已保存");
  emit("saved");
}

async function saveCase(): Promise<void> {
  const tab = props.tab;
  if (!tab.caseId) {
    return;
  }
  const current = await http.get<ApiBody<{ name: string; api_id: number | null; priority: string; tags: string; description: string; processors: Record<string, unknown> }>>(
    `/api/v1/projects/${props.projectId}/cases/${tab.caseId}`,
  );
  const detail = current.data.data;
  await http.put(`/api/v1/projects/${props.projectId}/cases/${tab.caseId}`, {
    name: detail.name,
    api_id: detail.api_id,
    priority: detail.priority,
    tags: detail.tags,
    description: detail.description,
    remark: "从执行窗口保存",
    request_json: { method: tab.method, path: tab.url.trim(), ...requestPayload() },
    processors_json: detail.processors || {},
  });
  ElMessage.success("用例已保存");
  emit("saved");
}

function onSaveKey(event: KeyboardEvent): void {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
    event.preventDefault();
    openSaveDialog().catch(showError);
  }
}
</script>

<template>
  <div class="req-line">
    <el-select model-value="HTTP" style="width: 110px" disabled>
      <el-option label="HTTP" value="HTTP" />
    </el-select>
    <el-select v-model="tab.method" style="width: 110px">
      <el-option v-for="item in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']" :key="item" :label="item" :value="item" />
    </el-select>
    <el-select v-model="envId" clearable placeholder="选择环境" style="width: 140px">
      <el-option v-for="item in environments" :key="item.id" :label="item.name" :value="item.id" />
    </el-select>
    <el-input v-model="tab.url" placeholder="路径或完整 URL，也可粘贴 curl" @paste="onPasteUrl" />
    <el-button type="primary" @click="execute().catch(showError)">服务端执行</el-button>
    <el-button @click="openHistory().catch(showError)">历史</el-button>
    <el-button v-if="saveMode !== 'debug'" @click="openSaveDialog().catch(showError)">保存</el-button>
    <el-dropdown v-else split-button trigger="click" @click="openSaveDialog().catch(showError)" @command="() => openSaveAs().catch(showError)">
      保存({{ shortcutLabel }})
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item command="save-as">另存为接口</el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
  <div class="body-types">
    <button v-for="item in sections" :key="item" type="button" class="section-tab" :class="{ active: section === item }" @click="section = item">
      {{ item }}
      <span v-if="sectionCount(item)" class="section-count">{{ sectionCount(item) }}</span>
    </button>
  </div>
  <div v-if="section === '请求体'" class="body-types">
    <button v-for="item in bodyTypes" :key="item" type="button" :class="{ active: tab.bodyType === item }" @click="tab.bodyType = item">{{ item }}</button>
  </div>
  <div v-if="section === '请求体' && tab.bodyType === 'none'" class="body-empty">请求没有 Body</div>
  <el-input v-else-if="section === '请求体'" v-model="tab.bodyText" type="textarea" :rows="8" placeholder="请求体" />
  <div v-else-if="section === '请求头'" class="header-table">
    <div class="header-row header-row-title">
      <span />
      <span>参数名称</span>
      <span>参数值</span>
      <span>描述</span>
      <el-button link type="primary" @click="openBatch('headers')">批量添加</el-button>
    </div>
    <div v-for="(param, index) in tab.headers" :key="index" class="header-row">
      <el-checkbox v-model="param.enabled" />
      <el-input v-model="param.name" placeholder="参数名称" @input="onHeaderInput(tab.headers)" />
      <el-input v-model="param.value" placeholder="参数值" @input="onHeaderInput(tab.headers)" />
      <el-input v-model="param.description" placeholder="描述" />
      <el-button link type="danger" @click="removeHeader(tab.headers, index)">－</el-button>
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
    <div v-for="(param, index) in tab.rest" :key="index" class="header-row">
      <el-checkbox v-model="param.enabled" />
      <el-input v-model="param.name" placeholder="参数名称" @input="onHeaderInput(tab.rest)" />
      <el-input v-model="param.value" placeholder="参数值" @input="onHeaderInput(tab.rest)" />
      <el-input v-model="param.description" placeholder="描述" />
      <el-button link type="danger" @click="removeHeader(tab.rest, index)">－</el-button>
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
    <div v-for="(param, index) in tab.query" :key="index" class="header-row">
      <el-checkbox v-model="param.enabled" />
      <el-input v-model="param.name" placeholder="参数名称" @input="onHeaderInput(tab.query)" />
      <el-input v-model="param.value" placeholder="参数值" @input="onHeaderInput(tab.query)" />
      <el-input v-model="param.description" placeholder="描述" />
      <el-button link type="danger" @click="removeHeader(tab.query, index)">－</el-button>
    </div>
  </div>
  <div v-else class="body-empty">{{ section }}将在后续阶段接入</div>
  <div class="resp-pane" :class="{ side: layout === '左右' }">
    <div class="resp-head">
      <div class="resp-tabs">
        <button v-for="name in respTabs" :key="name" type="button" class="resp-tab" :class="{ active: respTab === name }" @click="respTab = name">{{ name }}</button>
      </div>
      <span class="doc-bar-gap" />
      <div v-if="respTab === '响应体'" class="resp-tools">
        <el-select v-model="tab.bodyFormat" class="resp-select" size="small">
          <el-option v-for="item in BODY_FORMATS" :key="item" :label="item" :value="item" />
        </el-select>
        <el-select v-model="tab.bodyEncoding" class="resp-select resp-select-wide" size="small">
          <el-option v-for="item in BODY_ENCODINGS" :key="item" :label="item" :value="item" />
        </el-select>
      </div>
      <el-button-group>
        <el-button size="small" :type="layout === '上下' ? 'primary' : 'default'" @click="layout = '上下'">上下</el-button>
        <el-button size="small" :type="layout === '左右' ? 'primary' : 'default'" @click="layout = '左右'">左右</el-button>
      </el-button-group>
      <span v-if="tab.responseMeta">{{ tab.responseMeta }}</span>
    </div>
    <template v-if="respTab === '响应体'">
      <ResponsePreview v-if="tab.bodyFormat === '预览' && decodedBody" :text="decodedBody" />
      <div v-else class="resp-body">{{ displayBody || "点击 服务端执行 获取响应内容" }}</div>
    </template>
    <div v-else-if="respTab === '响应头'" class="resp-body">
      <div v-if="!tab.responseHeaders.length">暂无响应头</div>
      <div v-for="item in tab.responseHeaders" :key="item.name" class="resp-line">
        <span>{{ item.name }}</span>
        <span>{{ item.value }}</span>
      </div>
    </div>
    <div v-else-if="respTab === '实际请求'" class="resp-body">{{ tab.actualRequest || "执行后显示实际发出的请求" }}</div>
    <div v-else class="resp-body">{{ tab.consoleText || "执行后显示控制台日志" }}</div>
  </div>
  <el-dialog v-model="saveAsVisible" title="保存" width="560px">
    <el-form label-position="top">
      <el-form-item label="请求名称" required>
        <el-input v-model="saveAsForm.name" placeholder="请输入请求名称" />
      </el-form-item>
      <el-form-item label="请求 URL" required>
        <el-input v-model="saveAsForm.url" />
      </el-form-item>
      <el-form-item label="请求所属模块">
        <el-select v-model="saveAsForm.moduleId" placeholder="未规划请求" style="width: 100%">
          <el-option label="未规划请求" :value="null" />
          <el-option v-for="item in modules" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="saveAsVisible = false">取消</el-button>
      <el-button type="primary" @click="confirmSaveAs().catch(showError)">确定</el-button>
    </template>
  </el-dialog>
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
    <el-input v-model="batchText" type="textarea" :rows="8" :placeholder="batchTarget === 'headers' ? 'Content-Type:application/json' : 'page:1'" />
    <template #footer>
      <el-button @click="batchVisible = false">取消</el-button>
      <el-button type="primary" @click="applyBatch">添加</el-button>
    </template>
  </el-dialog>
</template>
