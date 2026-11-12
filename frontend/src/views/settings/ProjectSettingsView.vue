<!--
@File    : ProjectSettingsView.vue
@Desc    : 项目配置。成员、环境、变量、脚本和数据源的添加都在弹窗中完成
@Author  : xuetang-api
@Date    : 2026-11-13
@Update  : 2026-11-13 五个列表增加修改弹窗
-->
<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { http, type ApiBody } from "@/api/http";
import { useSessionStore } from "@/stores/session";

interface MemberRow {
  user_id: number;
  username: string;
  real_name: string;
  role_code: string;
  role_name: string;
}
interface EnvRow {
  id: number;
  name: string;
  code: string;
  base_url: string;
  enabled: boolean;
  headers_json: Record<string, unknown>;
  pre_script: string;
  description: string;
}
interface VarRow {
  id: number;
  scope: string;
  scope_id: number;
  name: string;
  var_type: string;
  value: string;
  encrypted: boolean;
  description: string;
}
interface ScriptRow {
  id: number;
  name: string;
  category: string;
  params_json: Record<string, unknown>;
  content: string;
}
interface SourceRow {
  id: number;
  name: string;
  db_type: string;
  host: string;
  port: number;
  database: string;
  username: string;
}
interface UserOption {
  id: number;
  username: string;
}

const route = useRoute();
const session = useSessionStore();
const projectId = computed(() => String(route.params.projectId || ""));
const members = ref<MemberRow[]>([]);
const envs = ref<EnvRow[]>([]);
const variables = ref<VarRow[]>([]);
const scripts = ref<ScriptRow[]>([]);
const sources = ref<SourceRow[]>([]);
const users = ref<UserOption[]>([]);
const memberKeyword = ref("");
const envKeyword = ref("");
const varKeyword = ref("");
const scriptKeyword = ref("");
const sourceKeyword = ref("");
const memberVisible = ref(false);
const envVisible = ref(false);
const varVisible = ref(false);
const scriptVisible = ref(false);
const sourceVisible = ref(false);
const editingMember = ref(false);
const editingEnvId = ref<number | null>(null);
const editingVarId = ref<number | null>(null);
const editingScriptId = ref<number | null>(null);
const editingSourceId = ref<number | null>(null);
const envExtras = reactive({ enabled: true, headers_json: {} as Record<string, unknown>, pre_script: "", description: "" });
const varExtras = reactive({ scope: "project", scope_id: 0, var_type: "string", description: "" });
const scriptExtras = reactive({ category: "default", params_json: {} as Record<string, unknown> });
const memberForm = reactive({ user_id: undefined as number | undefined, role_code: "tester" });
const envForm = reactive({ name: "", code: "", base_url: "" });
const varForm = reactive({ name: "", value: "", encrypted: false });
const scriptForm = reactive({ name: "", content: "result = params.get('n', 0)" });
const sourceForm = reactive({ name: "", db_type: "sqlite", host: "", port: 0, database: "", username: "", password: "" });
const previewText = ref("${app_name}");
const previewResult = ref("");

function matchKeyword(keyword: string, values: string[]): boolean {
  const text = keyword.trim().toLowerCase();
  if (!text) {
    return true;
  }
  return values.some((value) => (value || "").toLowerCase().includes(text));
}

const filteredMembers = computed(() => members.value.filter((item) => matchKeyword(memberKeyword.value, [item.username, item.real_name, item.role_name, item.role_code])));
const filteredEnvs = computed(() => envs.value.filter((item) => matchKeyword(envKeyword.value, [item.name, item.code, item.base_url])));
const filteredVars = computed(() => variables.value.filter((item) => matchKeyword(varKeyword.value, [item.name, item.scope, item.value])));
const filteredScripts = computed(() => scripts.value.filter((item) => matchKeyword(scriptKeyword.value, [item.name, item.content])));
const filteredSources = computed(() => sources.value.filter((item) => matchKeyword(sourceKeyword.value, [item.name, item.db_type, item.database])));

async function load(): Promise<void> {
  const id = projectId.value;
  if (!id) {
    return;
  }
  if (session.has("member:manage")) {
    members.value = (await http.get<ApiBody<MemberRow[]>>(`/api/v1/projects/${id}/members`)).data.data;
    users.value = (await http.get<ApiBody<UserOption[]>>("/api/v1/users")).data.data;
  }
  if (session.has("env:manage")) {
    envs.value = (await http.get<ApiBody<EnvRow[]>>(`/api/v1/projects/${id}/environments`)).data.data;
  }
  if (session.has("variable:manage")) {
    variables.value = (await http.get<ApiBody<VarRow[]>>(`/api/v1/projects/${id}/variables`)).data.data;
  }
  if (session.has("script:manage")) {
    scripts.value = (await http.get<ApiBody<ScriptRow[]>>(`/api/v1/projects/${id}/scripts`)).data.data;
  }
  if (session.has("datasource:manage")) {
    sources.value = (await http.get<ApiBody<SourceRow[]>>(`/api/v1/projects/${id}/datasources`)).data.data;
  }
}

function openMember(): void {
  editingMember.value = false;
  memberForm.user_id = undefined;
  memberForm.role_code = "tester";
  memberVisible.value = true;
}

function openEditMember(row: MemberRow): void {
  editingMember.value = true;
  memberForm.user_id = row.user_id;
  memberForm.role_code = row.role_code;
  memberVisible.value = true;
}

function openEnv(): void {
  editingEnvId.value = null;
  envForm.name = "";
  envForm.code = "";
  envForm.base_url = "";
  envExtras.enabled = true;
  envExtras.headers_json = {};
  envExtras.pre_script = "";
  envExtras.description = "";
  envVisible.value = true;
}

function openEditEnv(row: EnvRow): void {
  editingEnvId.value = row.id;
  envForm.name = row.name;
  envForm.code = row.code;
  envForm.base_url = row.base_url;
  envExtras.enabled = row.enabled;
  envExtras.headers_json = row.headers_json || {};
  envExtras.pre_script = row.pre_script || "";
  envExtras.description = row.description || "";
  envVisible.value = true;
}

function openVar(): void {
  editingVarId.value = null;
  varForm.name = "";
  varForm.value = "";
  varForm.encrypted = false;
  varExtras.scope = "project";
  varExtras.scope_id = 0;
  varExtras.var_type = "string";
  varExtras.description = "";
  varVisible.value = true;
}

function openEditVar(row: VarRow): void {
  editingVarId.value = row.id;
  varForm.name = row.name;
  varForm.value = row.value;
  varForm.encrypted = row.encrypted;
  varExtras.scope = row.scope;
  varExtras.scope_id = row.scope_id;
  varExtras.var_type = row.var_type || "string";
  varExtras.description = row.description || "";
  varVisible.value = true;
}

function openScript(): void {
  editingScriptId.value = null;
  scriptForm.name = "";
  scriptForm.content = "result = params.get('n', 0)";
  scriptExtras.category = "default";
  scriptExtras.params_json = {};
  scriptVisible.value = true;
}

function openEditScript(row: ScriptRow): void {
  editingScriptId.value = row.id;
  scriptForm.name = row.name;
  scriptForm.content = row.content;
  scriptExtras.category = row.category || "default";
  scriptExtras.params_json = row.params_json || {};
  scriptVisible.value = true;
}

function openSource(): void {
  editingSourceId.value = null;
  sourceForm.name = "";
  sourceForm.db_type = "sqlite";
  sourceForm.host = "";
  sourceForm.port = 0;
  sourceForm.database = "";
  sourceForm.username = "";
  sourceForm.password = "";
  sourceVisible.value = true;
}

function openEditSource(row: SourceRow): void {
  editingSourceId.value = row.id;
  sourceForm.name = row.name;
  sourceForm.db_type = row.db_type;
  sourceForm.host = row.host || "";
  sourceForm.port = row.port || 0;
  sourceForm.database = row.database || "";
  sourceForm.username = row.username || "";
  sourceForm.password = "";
  sourceVisible.value = true;
}

async function addMember(): Promise<void> {
  if (!memberForm.user_id) {
    ElMessage.warning("请选择用户");
    return;
  }
  await http.post(`/api/v1/projects/${projectId.value}/members`, memberForm);
  memberVisible.value = false;
  ElMessage.success(editingMember.value ? "成员角色已更新" : "成员已添加");
  await load();
}

async function addEnv(): Promise<void> {
  if (!envForm.name.trim() || !envForm.code.trim()) {
    ElMessage.warning("请填写环境名称和编码");
    return;
  }
  const payload = {
    ...envForm,
    name: envForm.name.trim(),
    code: envForm.code.trim(),
    enabled: envExtras.enabled,
    headers_json: envExtras.headers_json,
    pre_script: envExtras.pre_script,
    description: envExtras.description,
  };
  if (editingEnvId.value) {
    await http.put(`/api/v1/projects/${projectId.value}/environments/${editingEnvId.value}`, payload);
  } else {
    await http.post(`/api/v1/projects/${projectId.value}/environments`, payload);
  }
  envVisible.value = false;
  ElMessage.success(editingEnvId.value ? "环境已更新" : "环境已添加");
  await load();
}

async function addVar(): Promise<void> {
  if (!varForm.name.trim()) {
    ElMessage.warning("请填写变量名");
    return;
  }
  const payload = {
    scope: editingVarId.value ? varExtras.scope : "project",
    scope_id: editingVarId.value ? varExtras.scope_id : 0,
    name: varForm.name.trim(),
    var_type: varExtras.var_type,
    encrypted: varForm.encrypted,
    value: varForm.value,
    description: varExtras.description,
  };
  if (editingVarId.value) {
    await http.put(`/api/v1/projects/${projectId.value}/variables/${editingVarId.value}`, payload);
  } else {
    await http.post(`/api/v1/projects/${projectId.value}/variables`, payload);
  }
  varVisible.value = false;
  ElMessage.success(editingVarId.value ? "变量已更新" : "变量已添加");
  await load();
}

async function preview(): Promise<void> {
  const response = await http.post<ApiBody<{ text: string }>>(`/api/v1/projects/${projectId.value}/variables/preview`, {
    text: previewText.value,
    runtime: {},
  });
  previewResult.value = response.data.data.text;
}

async function addScript(): Promise<void> {
  if (!scriptForm.name.trim()) {
    ElMessage.warning("请填写脚本名称");
    return;
  }
  const payload = {
    name: scriptForm.name.trim(),
    category: scriptExtras.category,
    params_json: scriptExtras.params_json,
    content: scriptForm.content,
  };
  if (editingScriptId.value) {
    await http.put(`/api/v1/projects/${projectId.value}/scripts/${editingScriptId.value}`, payload);
  } else {
    await http.post(`/api/v1/projects/${projectId.value}/scripts`, payload);
  }
  scriptVisible.value = false;
  ElMessage.success(editingScriptId.value ? "脚本已更新" : "脚本已保存");
  await load();
}

async function debugScript(row: ScriptRow): Promise<void> {
  const response = await http.post<ApiBody<{ ok: boolean; result: unknown; error?: string }>>(
    `/api/v1/projects/${projectId.value}/scripts/${row.id}/debug`,
    { params: { n: 1 }, timeout: 5 },
  );
  ElMessage.success(JSON.stringify(response.data.data));
}

async function addSource(): Promise<void> {
  if (!sourceForm.name.trim()) {
    ElMessage.warning("请填写数据源名称");
    return;
  }
  const payload = { ...sourceForm, name: sourceForm.name.trim() };
  if (editingSourceId.value) {
    await http.put(`/api/v1/projects/${projectId.value}/datasources/${editingSourceId.value}`, payload);
  } else {
    await http.post(`/api/v1/projects/${projectId.value}/datasources`, payload);
  }
  sourceVisible.value = false;
  ElMessage.success(editingSourceId.value ? "数据源已更新" : "数据源已保存");
  await load();
}

async function pingSource(): Promise<void> {
  const response = await http.post<ApiBody<{ message: string }>>(`/api/v1/projects/${projectId.value}/datasources/ping`, sourceForm);
  ElMessage.success(response.data.data.message);
}

function showError(error: unknown): void {
  ElMessage.error(error instanceof Error ? error.message : "操作失败");
}

async function confirmRemove(message: string): Promise<boolean> {
  try {
    await ElMessageBox.confirm(message, "删除确认", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    });
    return true;
  } catch {
    return false;
  }
}

async function removeMember(row: MemberRow): Promise<void> {
  if (!(await confirmRemove(`确定移除成员 ${row.username}？`))) {
    return;
  }
  await http.delete(`/api/v1/projects/${projectId.value}/members/${row.user_id}`);
  ElMessage.success("成员已移除");
  await load();
}

async function removeEnv(row: EnvRow): Promise<void> {
  if (!(await confirmRemove(`确定删除环境 ${row.name}？`))) {
    return;
  }
  await http.delete(`/api/v1/projects/${projectId.value}/environments/${row.id}`);
  ElMessage.success("环境已删除");
  await load();
}

async function removeVar(row: VarRow): Promise<void> {
  if (!(await confirmRemove(`确定删除变量 ${row.name}？`))) {
    return;
  }
  await http.delete(`/api/v1/projects/${projectId.value}/variables/${row.id}`);
  ElMessage.success("变量已删除");
  await load();
}

async function removeScript(row: ScriptRow): Promise<void> {
  if (!(await confirmRemove(`确定删除脚本 ${row.name}？`))) {
    return;
  }
  await http.delete(`/api/v1/projects/${projectId.value}/scripts/${row.id}`);
  ElMessage.success("脚本已删除");
  await load();
}

async function removeSource(row: SourceRow): Promise<void> {
  if (!(await confirmRemove(`确定删除数据源 ${row.name}？`))) {
    return;
  }
  await http.delete(`/api/v1/projects/${projectId.value}/datasources/${row.id}`);
  ElMessage.success("数据源已删除");
  await load();
}

onMounted(() => {
  session.restore();
  load().catch(showError);
});
watch(() => route.params.projectId, () => load().catch(showError));
</script>

<template>
  <div class="page">
    <el-tabs>
      <el-tab-pane v-if="session.has('member:manage')" label="成员">
        <div class="user-toolbar">
          <el-input v-model="memberKeyword" clearable placeholder="搜索用户、姓名或角色" style="width: 280px" />
          <el-button type="primary" @click="openMember">添加</el-button>
        </div>
        <el-table :data="filteredMembers" border>
          <el-table-column prop="username" label="用户" />
          <el-table-column prop="real_name" label="姓名" />
          <el-table-column prop="role_name" label="项目角色" />
          <el-table-column label="操作" width="140">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEditMember(row)">修改</el-button>
              <el-button link type="danger" @click="removeMember(row).catch(showError)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-dialog v-model="memberVisible" :title="editingMember ? '修改成员' : '添加成员'" width="480px">
          <el-form label-position="top">
            <el-form-item label="用户">
              <el-select v-model="memberForm.user_id" placeholder="选择用户" style="width: 100%" :disabled="editingMember">
                <el-option v-for="item in users" :key="item.id" :label="item.username" :value="item.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="项目角色">
              <el-select v-model="memberForm.role_code" style="width: 100%">
                <el-option label="项目管理员" value="project_admin" />
                <el-option label="测试工程师" value="tester" />
                <el-option label="访客" value="guest" />
              </el-select>
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="memberVisible = false">取消</el-button>
            <el-button type="primary" @click="addMember().catch(showError)">确定</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>
      <el-tab-pane v-if="session.has('env:manage')" label="环境">
        <div class="user-toolbar">
          <el-input v-model="envKeyword" clearable placeholder="搜索环境名称、编码或地址" style="width: 280px" />
          <el-button type="primary" @click="openEnv">添加</el-button>
        </div>
        <el-table :data="filteredEnvs" border>
          <el-table-column prop="name" label="名称" />
          <el-table-column prop="code" label="编码" />
          <el-table-column prop="base_url" label="Base URL" />
          <el-table-column label="操作" width="140">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEditEnv(row)">修改</el-button>
              <el-button link type="danger" @click="removeEnv(row).catch(showError)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-dialog v-model="envVisible" :title="editingEnvId ? '修改环境' : '添加环境'" width="480px">
          <el-form label-position="top">
            <el-form-item label="名称"><el-input v-model="envForm.name" /></el-form-item>
            <el-form-item label="编码"><el-input v-model="envForm.code" placeholder="例如 staging" /></el-form-item>
            <el-form-item label="Base URL"><el-input v-model="envForm.base_url" placeholder="http://example.com" /></el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="envVisible = false">取消</el-button>
            <el-button type="primary" @click="addEnv().catch(showError)">确定</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>
      <el-tab-pane v-if="session.has('variable:manage')" label="变量">
        <div class="user-toolbar">
          <el-input v-model="varKeyword" clearable placeholder="搜索变量名或值" style="width: 280px" />
          <el-button type="primary" @click="openVar">添加</el-button>
        </div>
        <el-form class="preview-bar" inline>
          <el-input v-model="previewText" placeholder="预览模板，例如 ${app_name}" style="width: 280px" />
          <el-button style="margin-left: 8px" @click="preview().catch(showError)">预览</el-button>
          <span style="margin-left: 8px">{{ previewResult }}</span>
        </el-form>
        <el-table :data="filteredVars" border>
          <el-table-column prop="scope" label="作用域" width="100" />
          <el-table-column prop="name" label="名称" />
          <el-table-column prop="value" label="值" />
          <el-table-column prop="encrypted" label="加密" width="80" />
          <el-table-column label="操作" width="140">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEditVar(row)">修改</el-button>
              <el-button link type="danger" @click="removeVar(row).catch(showError)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-dialog v-model="varVisible" :title="editingVarId ? '修改变量' : '添加变量'" width="480px">
          <el-form label-position="top">
            <el-form-item label="变量名"><el-input v-model="varForm.name" placeholder="例如 course_id" /></el-form-item>
            <el-form-item label="值">
              <el-input v-model="varForm.value" :placeholder="editingVarId && varForm.encrypted ? '保持 ****** 则不修改密文' : ''" />
            </el-form-item>
            <el-form-item label="加密"><el-checkbox v-model="varForm.encrypted">加密保存，列表中只显示掩码</el-checkbox></el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="varVisible = false">取消</el-button>
            <el-button type="primary" @click="addVar().catch(showError)">确定</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>
      <el-tab-pane v-if="session.has('script:manage')" label="脚本">
        <div class="user-toolbar">
          <el-input v-model="scriptKeyword" clearable placeholder="搜索脚本名称或内容" style="width: 280px" />
          <el-button type="primary" @click="openScript">添加</el-button>
        </div>
        <el-table :data="filteredScripts" border>
          <el-table-column prop="name" label="名称" />
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEditScript(row)">修改</el-button>
              <el-button link type="primary" @click="debugScript(row).catch(showError)">调试</el-button>
              <el-button link type="danger" @click="removeScript(row).catch(showError)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-dialog v-model="scriptVisible" :title="editingScriptId ? '修改脚本' : '添加脚本'" width="560px">
          <el-form label-position="top">
            <el-form-item label="名称"><el-input v-model="scriptForm.name" /></el-form-item>
            <el-form-item label="内容"><el-input v-model="scriptForm.content" type="textarea" :rows="6" /></el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="scriptVisible = false">取消</el-button>
            <el-button type="primary" @click="addScript().catch(showError)">确定</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>
      <el-tab-pane v-if="session.has('datasource:manage')" label="数据源">
        <div class="user-toolbar">
          <el-input v-model="sourceKeyword" clearable placeholder="搜索数据源名称、类型或库名" style="width: 280px" />
          <el-button type="primary" @click="openSource">添加</el-button>
        </div>
        <el-table :data="filteredSources" border>
          <el-table-column prop="name" label="名称" />
          <el-table-column prop="db_type" label="类型" />
          <el-table-column prop="database" label="库" />
          <el-table-column label="操作" width="140">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEditSource(row)">修改</el-button>
              <el-button link type="danger" @click="removeSource(row).catch(showError)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-dialog v-model="sourceVisible" :title="editingSourceId ? '修改数据源' : '添加数据源'" width="520px">
          <el-form label-position="top">
            <el-form-item label="名称"><el-input v-model="sourceForm.name" /></el-form-item>
            <el-form-item label="类型">
              <el-select v-model="sourceForm.db_type" style="width: 100%">
                <el-option label="MySQL" value="mysql" />
                <el-option label="PostgreSQL" value="postgresql" />
                <el-option label="SQLite" value="sqlite" />
              </el-select>
            </el-form-item>
            <el-form-item label="主机"><el-input v-model="sourceForm.host" /></el-form-item>
            <el-form-item label="端口"><el-input v-model.number="sourceForm.port" /></el-form-item>
            <el-form-item label="库名或 SQLite 路径"><el-input v-model="sourceForm.database" /></el-form-item>
            <el-form-item label="用户名"><el-input v-model="sourceForm.username" /></el-form-item>
            <el-form-item label="密码">
              <el-input v-model="sourceForm.password" type="password" show-password :placeholder="editingSourceId ? '留空则不修改密码' : ''" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="pingSource().catch(showError)">测试连接</el-button>
            <el-button @click="sourceVisible = false">取消</el-button>
            <el-button type="primary" @click="addSource().catch(showError)">确定</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>
