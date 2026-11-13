<!--
@File    : DefinitionView.vue
@Desc    : 定义页。左侧模块树，右侧接口表格，对齐 MeterSphere
@Author  : xuetang-api
@Date    : 2026-11-12
@Update  : 2026-11-13 改为接口列表布局
-->
<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { http, type ApiBody } from "@/api/http";
import CasePanel from "@/views/api-test/CasePanel.vue";

interface ModuleRow {
  id: number;
  parent_id: number | null;
  name: string;
}
interface ApiRow {
  id: number;
  public_id: string;
  module_id: number | null;
  module: string;
  name: string;
  method: string;
  path: string;
  description: string;
  request?: { query?: unknown[]; headers?: unknown[]; path_params?: unknown[]; body?: { type?: string; content?: unknown } };
  case_count?: number;
  api_changed?: boolean;
}
interface ExportPack {
  filename: string;
  content_base64: string;
}

const route = useRoute();
const router = useRouter();
const projectId = computed(() => String(route.params.projectId || ""));
const modules = ref<ModuleRow[]>([]);
const apis = ref<ApiRow[]>([]);
const keyword = ref("");
const folderKey = ref("all");
const moduleVisible = ref(false);
const apiVisible = ref(false);
const importVisible = ref(false);
const importFile = ref<File | null>(null);
const caseVisible = ref(false);
const caseApiId = ref<number | null>(null);
const editingId = ref<number | null>(null);
const moduleForm = reactive({ name: "", parent_id: null as number | null });
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
  ElMessage.error(error instanceof Error ? error.message : "操作失败");
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

function runApi(row: ApiRow): void {
  router.push({ path: `/p/${projectId.value}/api-test/debug`, query: { apiId: String(row.id) } });
}

async function removeApi(row: ApiRow): Promise<void> {
  await ElMessageBox.confirm(`确定删除接口 ${row.name}？`, "删除确认", { type: "warning" });
  await http.delete(`/api/v1/projects/${projectId.value}/definitions/${row.id}`);
  await load();
}

async function saveModule(): Promise<void> {
  if (!moduleForm.name.trim()) {
    ElMessage.warning("请填写目录名称");
    return;
  }
  await http.post(`/api/v1/projects/${projectId.value}/modules`, {
    name: moduleForm.name.trim(),
    parent_id: moduleForm.parent_id,
  });
  moduleVisible.value = false;
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

async function download(format: "json" | "xlsx"): Promise<void> {
  const response = await http.get<ApiBody<ExportPack>>(`/api/v1/projects/${projectId.value}/definitions/export`, {
    params: { format },
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

onMounted(() => load().catch(showError));
watch(projectId, () => load().catch(showError));
</script>

<template>
  <div class="ms-page">
    <aside class="ms-side">
      <div class="ms-side-pad">
        <el-input v-model="keyword" clearable placeholder="请输入模块/接口名称" />
        <div class="ms-side-actions">
          <el-button type="primary" @click="openCreate">新建接口</el-button>
          <el-button @click="openCases(null)">新建用例</el-button>
          <el-button @click="importVisible = true">导入接口</el-button>
        </div>
        <div class="ms-folder" :class="{ active: folderKey === 'all' }" @click="folderKey = 'all'">
          <span>全部接口</span>
          <span class="ms-count">{{ apis.length }}</span>
        </div>
        <div class="ms-folder" :class="{ active: folderKey === 'none' }" @click="folderKey = 'none'">
          <span>未规划接口</span>
          <span class="ms-count">{{ countOf(null) }}</span>
        </div>
        <div
          v-for="folder in modules"
          :key="folder.id"
          class="ms-folder"
          :class="{ active: folderKey === `m-${folder.id}` }"
          @click="folderKey = `m-${folder.id}`"
        >
          <span>{{ folder.name }}</span>
          <span class="ms-count">{{ countOf(folder.id) }}</span>
        </div>
      </div>
      <div class="ms-side-pad">
        <el-button link @click="moduleVisible = true">新建目录</el-button>
      </div>
    </aside>
    <section class="ms-main">
      <div class="ms-toolbar">
        <el-tag type="primary" effect="plain">全部接口</el-tag>
        <span class="doc-bar-gap" />
        <el-input v-model="keyword" clearable placeholder="输入 ID/名称/api 路径搜索" style="width: 240px" />
        <el-button @click="download('json').catch(showError)">导出 JSON</el-button>
        <el-button @click="download('xlsx').catch(showError)">导出 Excel</el-button>
      </div>
      <el-table :data="visibleApis" height="100%">
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
            <span :class="['method', row.method.toLowerCase()]">{{ row.method }}</span>
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
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="primary" @click="runApi(row)">执行</el-button>
            <el-button link type="primary" @click="copyApi(row).catch(showError)">复制</el-button>
            <el-button link type="danger" @click="removeApi(row).catch(showError)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="ms-count">共 {{ visibleApis.length }} 条</div>
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
    <el-dialog v-model="moduleVisible" title="新建目录" width="420px">
      <el-form label-position="top">
        <el-form-item label="名称"><el-input v-model="moduleForm.name" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="moduleVisible = false">取消</el-button>
        <el-button type="primary" @click="saveModule().catch(showError)">确定</el-button>
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
    <CasePanel v-model="caseVisible" :project-id="projectId" :api-id="caseApiId" :apis="apis" @changed="load().catch(showError)" />
  </div>
</template>
