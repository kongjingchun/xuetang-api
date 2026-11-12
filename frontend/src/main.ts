/**
 * @File    : main.ts
 * @Desc    : 前端入口。挂载路由、Pinia 和 Element Plus 中文语言包
 * @Author  : xuetang-api
 * @Date    : 2026-11-12
 * @Update  : 2026-11-12 初始化阶段 0 前端
 */

import { createPinia } from "pinia";
import { createApp } from "vue";
import ElementPlus from "element-plus";
import zhCn from "element-plus/es/locale/lang/zh-cn";
import "element-plus/dist/index.css";
import App from "./App.vue";
import router from "./router";
import "./styles/index.css";

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.use(ElementPlus, { locale: zhCn });
app.mount("#app");
