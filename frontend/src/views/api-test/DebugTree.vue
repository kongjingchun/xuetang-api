<!--
@File    : DebugTree.vue
@Desc    : 调试页左侧目录树。文件夹可展开，悬停后可添加、重命名和删除
@Author  : xuetang-api
@Date    : 2026-11-13
@Update  : 2026-11-13 拖动时显示插入线或放入模块的高亮
-->
<script setup lang="ts">
import { ref } from "vue";

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
  module_id: number | null;
  name: string;
  method: string;
  path: string;
  sort: number;
  description: string;
  request: { query?: ParamRow[]; headers?: ParamRow[]; path_params?: ParamRow[]; body?: { type: string; content: unknown } };
}

const props = defineProps<{
  modules: ModuleRow[];
  depth: number;
  keyword: string;
  isOpen: (key: string) => boolean;
  moduleApis: (moduleId: number | null) => ApiRow[];
  childModules: (parentId: number | null) => ModuleRow[];
  moduleVisible: (moduleId: number) => boolean;
  matchesText: (value: string) => boolean;
  dropHint: { key: string; place: "before" | "after" | "into" } | null;
  draggingId: number | null;
}>();

const emit = defineEmits<{
  toggle: [key: string];
  openApi: [row: ApiRow];
  createModule: [parentId: number | null, name: string];
  renameModule: [folder: ModuleRow];
  deleteModule: [folder: ModuleRow];
  renameApi: [row: ApiRow];
  deleteApi: [row: ApiRow];
  moveApi: [payload: { id: number; moduleId: number | null; beforeId: number | null; place: "before" | "after" | "into" }];
  hint: [payload: { key: string; place: "before" | "after" | "into" } | null];
  dragStart: [id: number];
  dragEnd: [];
}>();

const names = ref<Record<number, string>>({});

function submit(folderId: number): void {
  emit("createModule", folderId, names.value[folderId] || "");
  names.value[folderId] = "";
}

function dragId(event: DragEvent): number {
  return Number(event.dataTransfer?.getData("text/plain") || props.draggingId || 0);
}

function hintClass(key: string): string {
  if (props.dropHint?.key !== key) {
    return "";
  }
  if (props.dropHint.place === "before") {
    return "drop-before";
  }
  if (props.dropHint.place === "after") {
    return "drop-after";
  }
  return "drop-into";
}

function allowDrop(event: DragEvent): void {
  event.preventDefault();
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = "move";
  }
}

function beginDrag(event: DragEvent, id: number): void {
  event.dataTransfer?.setData("text/plain", String(id));
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = "move";
  }
  emit("dragStart", id);
}

function overFolder(event: DragEvent, folderId: number): void {
  allowDrop(event);
  emit("hint", { key: `mod-${folderId}`, place: "into" });
}

function overApi(event: DragEvent, item: ApiRow): void {
  allowDrop(event);
  if (props.draggingId === item.id) {
    emit("hint", null);
    return;
  }
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
  const place = event.clientY < rect.top + rect.height / 2 ? "before" : "after";
  emit("hint", { key: `api-${item.id}`, place });
}

function dropApi(event: DragEvent, item: ApiRow): void {
  const place = props.dropHint?.key === `api-${item.id}` && props.dropHint.place !== "into"
    ? props.dropHint.place
    : "before";
  emit("hint", null);
  emit("moveApi", { id: dragId(event), moduleId: item.module_id, beforeId: item.id, place });
}
</script>

<template>
  <template v-for="folder in modules" :key="folder.id">
    <div
      v-if="moduleVisible(folder.id)"
      class="tree-row"
      :class="hintClass(`mod-${folder.id}`)"
      :style="{ paddingLeft: `${depth * 16}px` }"
      @dragover="overFolder($event, folder.id)"
      @drop.stop="emit('moveApi', { id: dragId($event), moduleId: folder.id, beforeId: null, place: 'into' })"
    >
      <button type="button" class="tree-main" @click="emit('toggle', `m-${folder.id}`)">
        <span class="tree-arrow" :class="{ open: isOpen(`m-${folder.id}`) }">▸</span>
        <span class="tree-icon">
          <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1.5 3.5A1.5 1.5 0 0 1 3 2h3.2a1.5 1.5 0 0 1 1.2.6L8.2 4H13a1.5 1.5 0 0 1 1.5 1.5v7A1.5 1.5 0 0 1 13 14H3a1.5 1.5 0 0 1-1.5-1.5v-9z" /></svg>
        </span>
        <span class="tree-label">{{ folder.name }}</span>
        <span class="ms-count">{{ moduleApis(folder.id).length }}</span>
      </button>
      <span class="tree-ops" @click.stop>
        <el-popover trigger="click" placement="bottom" :width="280">
          <template #reference>
            <button type="button" class="tree-op">+</button>
          </template>
          <div class="add-module">
            <div class="add-module-title">添加子模块</div>
            <el-input v-model="names[folder.id]" placeholder="请输入名称，按回车键保存" @keyup.enter="submit(folder.id)" />
            <div class="add-module-actions">
              <el-button @click="names[folder.id] = ''">取消</el-button>
              <el-button type="primary" @click="submit(folder.id)">确定</el-button>
            </div>
          </div>
        </el-popover>
        <el-dropdown trigger="click">
          <button type="button" class="tree-op">...</button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="emit('renameModule', folder)">重命名</el-dropdown-item>
              <el-dropdown-item @click="emit('deleteModule', folder)">删除</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </span>
    </div>
    <DebugTree
      v-if="moduleVisible(folder.id) && isOpen(`m-${folder.id}`)"
      :modules="childModules(folder.id)"
      :depth="depth + 1"
      :keyword="keyword"
      :is-open="isOpen"
      :module-apis="moduleApis"
      :child-modules="childModules"
      :module-visible="moduleVisible"
      :matches-text="matchesText"
      :drop-hint="dropHint"
      :dragging-id="draggingId"
      @toggle="emit('toggle', $event)"
      @open-api="emit('openApi', $event)"
      @create-module="(parentId, name) => emit('createModule', parentId, name)"
      @rename-module="emit('renameModule', $event)"
      @delete-module="emit('deleteModule', $event)"
      @rename-api="emit('renameApi', $event)"
      @delete-api="emit('deleteApi', $event)"
      @move-api="emit('moveApi', $event)"
      @hint="emit('hint', $event)"
      @drag-start="emit('dragStart', $event)"
      @drag-end="emit('dragEnd')"
    />
    <template v-if="moduleVisible(folder.id) && isOpen(`m-${folder.id}`)">
      <button
        v-for="item in moduleApis(folder.id).filter((row) => matchesText(`${row.name} ${row.method} ${row.path}`))"
        :key="item.id"
        type="button"
        class="tree-row request-row"
        :class="[hintClass(`api-${item.id}`), { 'is-dragging': draggingId === item.id }]"
        draggable="true"
        :style="{ paddingLeft: `${(depth + 1) * 16}px` }"
        @click="emit('openApi', item)"
        @dragstart="beginDrag($event, item.id)"
        @dragend="emit('dragEnd')"
        @dragover="overApi($event, item)"
        @drop.stop="dropApi($event, item)"
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
                <el-dropdown-item @click="emit('renameApi', item)">重命名</el-dropdown-item>
                <el-dropdown-item @click="emit('deleteApi', item)">删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </span>
      </button>
    </template>
  </template>
</template>

<script lang="ts">
export default { name: "DebugTree" };
</script>
