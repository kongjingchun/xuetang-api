<!--
@File    : ChangePasswordView.vue
@Desc    : 首次登录或自行修改密码。成功后进入工作台
@Author  : xuetang-api
@Date    : 2026-11-13
@Update  : 2026-11-13 改密页与登录页使用同一版式
-->
<script setup lang="ts">
import { reactive } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { DEMO_PROJECT_ID } from "@/constants/project";
import { useSessionStore } from "@/stores/session";

const router = useRouter();
const session = useSessionStore();
const form = reactive({
  oldPassword: "",
  newPassword: "",
});

async function submit(): Promise<void> {
  if (form.newPassword.length < 8) {
    ElMessage.warning("新密码至少 8 位");
    return;
  }
  try {
    await session.changePassword(form.oldPassword, form.newPassword);
    ElMessage.success("密码已更新");
    router.push(`/p/${DEMO_PROJECT_ID}/dashboard`);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "修改失败");
  }
}
</script>

<template>
  <div class="login-page">
    <section class="login-brand">
      <span class="login-mark">学堂</span>
      <h1>修改密码</h1>
      <p>设置新的登录密码后进入工作台。</p>
    </section>
    <section class="login-panel">
      <el-card class="login-card" shadow="never">
        <template #header>修改密码</template>
        <el-form label-position="top" size="large" @submit.prevent="submit">
          <el-form-item label="原密码">
            <el-input v-model="form.oldPassword" type="password" show-password />
          </el-form-item>
          <el-form-item label="新密码">
            <el-input v-model="form.newPassword" type="password" show-password />
          </el-form-item>
          <el-button type="primary" size="large" style="width: 100%" @click="submit">保存并进入工作台</el-button>
        </el-form>
      </el-card>
    </section>
  </div>
</template>
