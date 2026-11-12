<!--
@File    : LoginView.vue
@Desc    : 账号密码登录。口令错误停在本页，首次登录去改密页
@Author  : xuetang-api
@Date    : 2026-11-12
@Update  : 2026-11-13 调整登录页版式
-->
<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { http, type ApiBody } from "@/api/http";
import { DEMO_PROJECT_ID } from "@/constants/project";
import { useSessionStore } from "@/stores/session";

const router = useRouter();
const session = useSessionStore();
const ssoEnabled = ref(false);
const form = reactive({
  username: "admin",
  password: "",
});

onMounted(async () => {
  try {
    const response = await http.get<ApiBody<unknown[]>>("/api/v1/auth/sso/providers");
    ssoEnabled.value = response.data.data.length > 0;
  } catch {
    ssoEnabled.value = false;
  }
});

async function enter(): Promise<void> {
  if (!form.username.trim() || !form.password) {
    ElMessage.warning("请输入用户名和密码");
    return;
  }
  try {
    await session.login(form.username.trim(), form.password);
    if (session.mustChangePassword) {
      router.push("/change-password");
      return;
    }
    router.push(`/p/${DEMO_PROJECT_ID}/dashboard`);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "登录失败");
  }
}

async function startSso(): Promise<void> {
  ElMessage.info("企业 SSO 尚未接入");
}
</script>

<template>
  <div class="login-page">
    <section class="login-brand">
      <span class="login-mark">学堂</span>
      <h1>学堂在线</h1>
      <p>接口自动化测试平台。使用管理员账号登录，首次进入需要修改初始密码。</p>
      <ul class="login-points">
        <li>接口定义、调试、场景和报告</li>
        <li>项目环境、变量和数据源</li>
        <li>用户角色与操作审计</li>
      </ul>
    </section>
    <section class="login-panel">
      <el-card class="login-card" shadow="never">
        <template #header>账号密码登录</template>
        <el-form label-position="top" size="large" @submit.prevent="enter">
          <el-form-item label="用户名">
            <el-input v-model="form.username" autocomplete="username" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="form.password" type="password" show-password autocomplete="current-password" />
          </el-form-item>
          <el-button type="primary" size="large" style="width: 100%" @click="enter">登录</el-button>
          <p class="hint">种子管理员为 admin，初始密码见 .env.example。首次登录必须修改密码。</p>
          <el-button style="width: 100%; margin-top: 12px" :disabled="!ssoEnabled" @click="startSso">企业 SSO 登录</el-button>
          <p class="hint">没有启用的身份源时，企业 SSO 保持不可用。</p>
        </el-form>
      </el-card>
    </section>
  </div>
</template>
