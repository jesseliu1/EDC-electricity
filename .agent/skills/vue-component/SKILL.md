---
name: vue-component
description: 当用户要求创建新 Vue 组件、页面或布局时使用。自动遵循项目 Vue 3 + Element Plus + Tailwind CSS 规范生成组件模板。
---

# Vue 组件生成技能

## 目标
按照项目规范自动生成 Vue 3 组件，确保代码风格一致。

## 使用场景
- 用户说"创建一个 XX 组件"
- 用户说"新增一个 XX 页面"
- 需要从 UI 原型生成组件代码

## 生成规范

### 组件结构
```vue
<script setup lang="ts">
// 中文注释说明组件用途
import { ref, computed, onMounted } from 'vue'

// Props 定义（使用 TypeScript 接口）
interface Props {
  // 属性说明
}

const props = withDefaults(defineProps<Props>(), {
  // 默认值
})

// Emits 定义
const emit = defineEmits<{
  // 事件说明
}>()

// 响应式状态
// 计算属性
// 方法
// 生命周期
</script>

<template>
  <!-- 使用 Element Plus 组件 + Tailwind CSS 类 -->
</template>
```

### 命名规范
- 文件名：**PascalCase**（如 `DashboardCard.vue`）
- 组件目录：按功能模块分组（如 `components/dashboard/`、`components/baseline/`）

### 样式规范
- **禁止** `<style>` 标签中写大量自定义 CSS
- **禁止**内联样式（`:style="..."`）
- 使用 **Tailwind CSS** 原子类
- 使用 **Element Plus** 组件自带样式
- 如需少量自定义样式，使用 `<style scoped>` + BEM 命名

### 状态管理
- 组件内部状态用 `ref` / `reactive`
- 跨组件共享状态用 **Pinia** store
- API 调用通过 composables 或 store actions

## 约束
- 生成前先检查 `material/UI/stitch_dashboard/` 中是否有对应 UI 设计稿
- 必须使用 TypeScript（`lang="ts"`）
- 必须导出明确的 Props 和 Emits 接口
