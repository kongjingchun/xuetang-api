<!--
@File    : SettingsView.vue
@Desc    : 系统设置。用户、角色和审计
@Author  : xuetang-api
@Date    : 2026-11-13
@Update  : 2026-11-13 角色创建改为弹窗，列表顶部增加搜索
-->
<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { http, type ApiBody } from "@/api/http";
import { useSessionStore } from "@/stores/session";

interface UserRow {
  id: number;
  username: string;
  email: string | null;
  real_name: string;
  status: string;
  role_code: string;
  role_name: string;
  protected: boolean;
}
interface RoleRow {
  id: number;
  name: string;
  code: string;
  builtin: boolean;
  data_scope: string;
  description: string;
  permission_codes: string[];
}
interface PermRow {
  code: string;
  name: string;
  type: string;
}
interface AuditRow {
  id: number;
  username: string;
  module: string;
  action: string;
  content: string;
  created_at: string;
}

const session = useSessionStore();
const users = ref<UserRow[]>([]);
const roles = ref<RoleRow[]>([]);
const permissions = ref<PermRow[]>([]);
const audits = ref<AuditRow[]>([]);
const userKeyword = ref("");
const createVisible = ref(false);
const editingUserId = ref<number | null>(null);
const editingUserProtected = ref(false);
const userForm = reactive({ username: "", password: "", email: "", real_name: "", role_code: "tester", status: "enabled" });
const roleKeyword = ref("");
const roleVisible = ref(false);
const editingRoleId = ref<number | null>(null);
const editingRoleBuiltin = ref(false);
const roleForm = reactive({ name: "", code: "", data_scope: "project", description: "", permission_codes: [] as string[] });
const auditFilter = reactive({ module: "", action: "" });

const filteredRoles = computed(() => {
  const keyword = roleKeyword.value.trim().toLowerCase();
  if (!keyword) {
    return roles.value;
  }
  return roles.value.filter((item) =>
    [item.name, item.code, item.data_scope].some((value) => (value || "").toLowerCase().includes(keyword)),
  );
});

const filteredUsers = computed(() => {
  const keyword = userKeyword.value.trim().toLowerCase();
  if (!keyword) {
    return users.value;
  }
  return users.value.filter((item) =>
    [item.username, item.real_name, item.role_name, item.role_code].some((value) => (value || "").toLowerCase().includes(keyword)),
  );
});

async function load(): Promise<void> {
  if (session.has("user:manage") || session.has("role:manage")) {
    roles.value = (await http.get<ApiBody<RoleRow[]>>("/api/v1/roles")).data.data;
  }
  if (session.has("user:manage")) {
    users.value = (await http.get<ApiBody<UserRow[]>>("/api/v1/users")).data.data;
  }
  if (session.has("role:manage")) {
    permissions.value = (await http.get<ApiBody<PermRow[]>>("/api/v1/permissions")).data.data;
  }
  if (session.has("audit:read")) {
    await loadAudit();
  }
}

async function loadAudit(): Promise<void> {
  const response = await http.get<ApiBody<AuditRow[]>>("/api/v1/audit", { params: auditFilter });
  audits.value = response.data.data;
}

const allPermissionsSelected = computed(
  () => permissions.value.length > 0 && permissions.value.every((item) => roleForm.permission_codes.includes(item.code)),
);

function toggleAllPermissions(): void {
  roleForm.permission_codes = allPermissionsSelected.value ? [] : permissions.value.map((item) => item.code);
}

function openCreate(): void {
  editingUserId.value = null;
  editingUserProtected.value = false;
  userForm.username = "";
  userForm.password = "";
  userForm.email = "";
  userForm.real_name = "";
  userForm.role_code = roles.value.find((item) => item.code === "tester")?.code || roles.value[0]?.code || "tester";
  userForm.status = "enabled";
  createVisible.value = true;
}

function openEditUser(row: UserRow): void {
  editingUserId.value = row.id;
  editingUserProtected.value = row.protected;
  userForm.username = row.username;
  userForm.password = "";
  userForm.email = row.email || "";
  userForm.real_name = row.real_name;
  userForm.role_code = row.role_code;
  userForm.status = row.status;
  createVisible.value = true;
}

async function createUser(): Promise<void> {
  if (!editingUserId.value && !userForm.username.trim()) {
    ElMessage.warning("请填写用户名。姓名只是显示名，不能代替登录名");
    return;
  }
  if (!editingUserId.value && userForm.password.length < 8) {
    ElMessage.warning("初始密码至少 8 位");
    return;
  }
  if (editingUserId.value && userForm.password && userForm.password.length < 8) {
    ElMessage.warning("新密码至少 8 位，留空则不修改密码");
    return;
  }
  try {
    if (editingUserId.value) {
      await http.put(`/api/v1/users/${editingUserId.value}`, {
        email: userForm.email || null,
        real_name: userForm.real_name,
        role_code: userForm.role_code,
        status: userForm.status,
      });
      if (userForm.password) {
        await http.post(`/api/v1/users/${editingUserId.value}/reset-password`, { password: userForm.password });
      }
      ElMessage.success("用户已更新");
    } else {
      await http.post("/api/v1/users", { ...userForm, username: userForm.username.trim() });
      ElMessage.success("用户已创建");
    }
    createVisible.value = false;
    await load();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "保存失败");
  }
}

function scopeLabel(scope: string): string {
  if (scope === "all") {
    return "全部";
  }
  if (scope === "self") {
    return "仅本人";
  }
  return "所在项目";
}

function openRole(): void {
  editingRoleId.value = null;
  editingRoleBuiltin.value = false;
  roleForm.name = "";
  roleForm.code = "";
  roleForm.data_scope = "project";
  roleForm.description = "";
  roleForm.permission_codes = [];
  roleVisible.value = true;
}

function openEditRole(row: RoleRow): void {
  editingRoleId.value = row.id;
  editingRoleBuiltin.value = row.builtin;
  roleForm.name = row.name;
  roleForm.code = row.code;
  roleForm.data_scope = row.data_scope;
  roleForm.description = row.description || "";
  roleForm.permission_codes = [...row.permission_codes];
  roleVisible.value = true;
}

async function createRole(): Promise<void> {
  if (!roleForm.name.trim() || !roleForm.code.trim()) {
    ElMessage.warning("请填写角色名称和编码");
    return;
  }
  const payload = { ...roleForm, name: roleForm.name.trim(), code: roleForm.code.trim() };
  try {
    if (editingRoleId.value) {
      await http.put(`/api/v1/roles/${editingRoleId.value}`, payload);
      ElMessage.success("角色已更新");
    } else {
      await http.post("/api/v1/roles", payload);
      ElMessage.success("角色已创建");
    }
    roleVisible.value = false;
    await load();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "保存失败");
  }
}

async function removeRole(row: RoleRow): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定删除角色 ${row.name}？删除后不能恢复。`, "删除确认", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }
  try {
    await http.delete(`/api/v1/roles/${row.id}`);
    ElMessage.success("角色已删除");
    await load();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "删除失败");
  }
}

async function disableUser(row: UserRow): Promise<void> {
  try {
    await http.post(`/api/v1/users/${row.id}/disable`);
    ElMessage.success("用户已禁用");
    await load();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "操作失败");
  }
}

async function removeUser(row: UserRow): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定删除用户 ${row.username}？删除后不能恢复。`, "删除确认", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }
  try {
    await http.delete(`/api/v1/users/${row.id}`);
    ElMessage.success("用户已删除");
    await load();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "删除失败");
  }
}

onMounted(() => {
  session.restore();
  load().catch((error: unknown) => {
    ElMessage.error(error instanceof Error ? error.message : "加载失败");
  });
});
</script>

<template>
  <div class="page">
    <el-tabs>
      <el-tab-pane v-if="session.has('user:manage')" label="用户">
        <div class="user-toolbar">
          <el-input v-model="userKeyword" clearable placeholder="搜索用户名、姓名或角色" style="width: 280px" />
          <el-button type="primary" @click="openCreate">创建</el-button>
        </div>
        <el-table :data="filteredUsers" border>
          <el-table-column prop="username" label="用户名" />
          <el-table-column prop="real_name" label="姓名" />
          <el-table-column prop="role_name" label="角色" />
          <el-table-column label="状态">
            <template #default="{ row }">{{ row.status === "enabled" ? "启用" : "禁用" }}</template>
          </el-table-column>
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEditUser(row)">修改</el-button>
              <el-button v-if="!row.protected" link type="warning" @click="disableUser(row)">禁用</el-button>
              <el-button v-if="!row.protected" link type="danger" @click="removeUser(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-dialog v-model="createVisible" :title="editingUserId ? '修改用户' : '创建用户'" width="480px">
          <el-form label-position="top">
            <el-form-item label="用户名">
              <el-input v-model="userForm.username" placeholder="登录名，例如 tester01" :disabled="Boolean(editingUserId)" />
            </el-form-item>
            <el-form-item label="姓名">
              <el-input v-model="userForm.real_name" placeholder="显示名称，可与用户名不同" />
            </el-form-item>
            <el-form-item :label="editingUserId ? '新密码' : '初始密码'">
              <el-input v-model="userForm.password" type="password" show-password :placeholder="editingUserId ? '留空则不修改密码' : ''" />
            </el-form-item>
            <el-form-item v-if="!editingUserProtected" label="状态">
              <el-select v-model="userForm.status" style="width: 100%">
                <el-option label="启用" value="enabled" />
                <el-option label="禁用" value="disabled" />
              </el-select>
            </el-form-item>
            <el-form-item label="角色">
              <el-select v-model="userForm.role_code" style="width: 100%">
                <el-option v-for="role in roles" :key="role.code" :label="role.name" :value="role.code" />
              </el-select>
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="createVisible = false">取消</el-button>
            <el-button type="primary" @click="createUser">确定</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>
      <el-tab-pane v-if="session.has('role:manage')" label="角色">
        <div class="user-toolbar">
          <el-input v-model="roleKeyword" clearable placeholder="搜索角色名称、编码或数据范围" style="width: 280px" />
          <el-button type="primary" @click="openRole">创建</el-button>
        </div>
        <el-table :data="filteredRoles" border>
          <el-table-column prop="name" label="名称" />
          <el-table-column label="数据范围">
            <template #default="{ row }">{{ scopeLabel(row.data_scope) }}</template>
          </el-table-column>
          <el-table-column label="内置">
            <template #default="{ row }">{{ row.builtin ? "是" : "否" }}</template>
          </el-table-column>
          <el-table-column label="操作" width="140">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEditRole(row)">修改</el-button>
              <el-button v-if="!row.builtin" link type="danger" @click="removeRole(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-dialog v-model="roleVisible" :title="editingRoleId ? '修改角色' : '创建角色'" width="560px">
          <el-form label-position="top">
            <el-form-item label="名称"><el-input v-model="roleForm.name" /></el-form-item>
            <el-form-item label="编码"><el-input v-model="roleForm.code" :disabled="editingRoleBuiltin" /></el-form-item>
            <el-form-item label="数据范围">
              <el-select v-model="roleForm.data_scope" style="width: 100%">
                <el-option label="全部" value="all" />
                <el-option label="所在项目" value="project" />
                <el-option label="仅本人" value="self" />
              </el-select>
            </el-form-item>
            <el-form-item label="权限">
              <el-button link type="primary" @click="toggleAllPermissions">{{ allPermissionsSelected ? "取消全选" : "全选" }}</el-button>
              <el-checkbox-group v-model="roleForm.permission_codes">
                <el-checkbox v-for="item in permissions" :key="item.code" :value="item.code">{{ item.name }}</el-checkbox>
              </el-checkbox-group>
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="roleVisible = false">取消</el-button>
            <el-button type="primary" @click="createRole">确定</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>
      <el-tab-pane v-if="session.has('audit:read')" label="审计">
        <el-form class="filter-bar" inline>
          <el-form-item label="模块"><el-input v-model="auditFilter.module" /></el-form-item>
          <el-form-item label="类型"><el-input v-model="auditFilter.action" /></el-form-item>
          <el-button @click="loadAudit">查询</el-button>
        </el-form>
        <el-table :data="audits" border>
          <el-table-column prop="created_at" label="时间" width="180" />
          <el-table-column prop="username" label="用户" width="120" />
          <el-table-column prop="module" label="模块" width="120" />
          <el-table-column prop="action" label="类型" width="140" />
          <el-table-column prop="content" label="内容" />
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>
