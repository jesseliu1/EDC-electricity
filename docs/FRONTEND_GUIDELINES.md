# 前端开发规范 (FRONTEND_GUIDELINES)

## 1. 设计令牌

### 1.1 颜色系统

```scss
// 主色
$primary: #409EFF;        // Element Plus 主蓝
$primary-light: #79BBFF;
$primary-dark: #337ECC;

// 功能色
$success: #67C23A;        // 正常/通过
$warning: #E6A23C;        // 警告/注意
$danger: #F56C6C;         // 异常/错误
$info: #909399;           // 信息/禁用

// 中性色
$text-primary: #303133;
$text-regular: #606266;
$text-secondary: #909399;
$text-placeholder: #C0C4CC;

$border-base: #DCDFE6;
$border-light: #E4E7ED;

$bg-page: #F5F7FA;
$bg-card: #FFFFFF;
```

### 1.2 间距系统

```scss
// 基于 4px 的间距系统
$spacing-xs: 4px;
$spacing-sm: 8px;
$spacing-md: 16px;
$spacing-lg: 24px;
$spacing-xl: 32px;

// Tailwind 等效
// p-1 = 4px, p-2 = 8px, p-4 = 16px, p-6 = 24px, p-8 = 32px
```

### 1.3 字体系统

```scss
// 字号
$font-xs: 12px;
$font-sm: 13px;
$font-base: 14px;
$font-lg: 16px;
$font-xl: 18px;
$font-2xl: 20px;
$font-3xl: 24px;

// 行高
$leading-tight: 1.25;
$leading-normal: 1.5;
$leading-relaxed: 1.75;
```

### 1.4 阴影

```scss
$shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
$shadow-base: 0 2px 4px rgba(0, 0, 0, 0.12);
$shadow-lg: 0 4px 12px rgba(0, 0, 0, 0.15);
```

## 2. 组件规范

### 2.1 文件命名

```
components/
├── common/              # 通用组件
│   ├── AppHeader.vue
│   ├── AppSidebar.vue
│   └── PageContainer.vue
├── dashboard/           # 仪表盘相关
│   ├── StatCard.vue
│   ├── RealtimeChart.vue
│   └── HeatList.vue
├── baseline/            # 基线相关
│   ├── BaselineCard.vue
│   ├── BaselineWizard.vue
│   └── CurveCompare.vue
└── task/                # 任务相关
    ├── TaskCard.vue
    └── TaskForm.vue
```

**命名规则**：
- 组件文件：`PascalCase.vue`
- 组合式函数：`useCamelCase.ts`
- 工具函数：`camelCase.ts`

### 2.2 组件结构

```vue
<script setup lang="ts">
// 1. 类型导入
import type { Baseline } from '@/types'

// 2. 组件导入
import { ElButton, ElCard } from 'element-plus'
import StatCard from './StatCard.vue'

// 3. 组合式函数
import { useBaseline } from '@/composables/useBaseline'

// 4. Props 定义
interface Props {
  baseline: Baseline
  editable?: boolean
}
const props = withDefaults(defineProps<Props>(), {
  editable: false
})

// 5. Emits 定义
interface Emits {
  (e: 'update', value: Baseline): void
  (e: 'delete', id: string): void
}
const emit = defineEmits<Emits>()

// 6. 响应式状态
const { loading, data, refresh } = useBaseline()

// 7. 计算属性
const isActive = computed(() => props.baseline.status === 'active')

// 8. 方法
function handleUpdate() {
  emit('update', props.baseline)
}

// 9. 生命周期
onMounted(() => {
  refresh()
})
</script>

<template>
  <!-- 单一根元素 -->
  <div class="baseline-card">
    <!-- 内容 -->
  </div>
</template>

<style scoped>
/* 使用 scoped 样式 */
.baseline-card {
  @apply rounded-lg bg-white shadow-sm p-4;
}
</style>
```

### 2.3 样式规范

**优先级**：
1. Element Plus 组件样式（不覆盖）
2. Tailwind CSS 原子类
3. Scoped CSS（仅用于复杂样式）

**禁止**：
- 内联样式 `style="..."`
- 全局 CSS（除了 `src/styles/` 目录）
- `!important`（除非覆盖第三方库）

**Tailwind 使用示例**：
```vue
<template>
  <!-- 推荐：使用 Tailwind -->
  <div class="flex items-center gap-4 p-4 bg-white rounded-lg shadow-sm">
    <span class="text-sm text-gray-500">标签</span>
    <span class="text-lg font-semibold text-gray-900">值</span>
  </div>
</template>
```

## 3. 图表规范

### 3.1 ECharts 配置基础

```typescript
// composables/useChartOptions.ts
export function useChartOptions() {
  const baseOptions: EChartsOption = {
    grid: {
      left: 60,
      right: 20,
      top: 40,
      bottom: 40
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#DCDFE6',
      textStyle: {
        color: '#303133'
      }
    },
    legend: {
      top: 10,
      textStyle: {
        color: '#606266'
      }
    }
  }

  return { baseOptions }
}
```

### 3.2 曲线对比图标准

```typescript
// 黄金基线曲线
const goldenLine = {
  name: '黄金基线',
  type: 'line',
  smooth: true,
  lineStyle: {
    width: 2,
    type: 'dashed',
    color: '#67C23A'  // 绿色
  },
  showSymbol: false
}

// 当前生产曲线
const currentLine = {
  name: '当前生产',
  type: 'line',
  smooth: true,
  lineStyle: {
    width: 2,
    color: '#409EFF'  // 蓝色
  },
  showSymbol: false
}

// 异常区域标记
const markArea = {
  itemStyle: {
    color: 'rgba(245, 108, 108, 0.2)'  // 半透明红色
  },
  data: [
    [{ xAxis: startTime }, { xAxis: endTime }]
  ]
}
```

## 4. 响应式设计

### 4.1 断点

```scss
// Tailwind 默认断点
sm: 640px   // 手机横屏
md: 768px   // 平板
lg: 1024px  // 小屏笔记本
xl: 1280px  // 标准桌面
2xl: 1536px // 大屏桌面
```

### 4.2 布局适配

```vue
<template>
  <!-- 响应式网格 -->
  <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
    <StatCard v-for="stat in stats" :key="stat.id" :stat="stat" />
  </div>

  <!-- 侧边栏响应式 -->
  <aside class="w-64 lg:w-72 shrink-0">
    <!-- 侧边栏内容 -->
  </aside>
</template>
```

## 5. 状态管理

### 5.1 Store 结构

```typescript
// stores/baseline.ts
import { defineStore } from 'pinia'
import type { Baseline } from '@/types'

interface BaselineState {
  list: Baseline[]
  current: Baseline | null
  loading: boolean
}

export const useBaselineStore = defineStore('baseline', {
  state: (): BaselineState => ({
    list: [],
    current: null,
    loading: false
  }),

  getters: {
    activeBaseline: (state) => state.list.find(b => b.status === 'active'),
    hasBaseline: (state) => state.list.length > 0
  },

  actions: {
    async fetchList() {
      this.loading = true
      try {
        this.list = await api.baseline.list()
      } finally {
        this.loading = false
      }
    }
  }
})
```

## 6. API 调用

### 6.1 API 客户端

```typescript
// api/client.ts
import axios from 'axios'
import { ElMessage } from 'element-plus'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 10000
})

client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    ElMessage.error(error.response?.data?.message || '请求失败')
    return Promise.reject(error)
  }
)

export { client }
```

### 6.2 API 模块

```typescript
// api/baseline.ts
import { client } from './client'
import type { Baseline, CreateBaselineDto } from '@/types'

export const baselineApi = {
  list: () => client.get<Baseline[]>('/baselines'),
  get: (id: string) => client.get<Baseline>(`/baselines/${id}`),
  create: (data: CreateBaselineDto) => client.post<Baseline>('/baselines', data),
  update: (id: string, data: Partial<Baseline>) => client.patch(`/baselines/${id}`, data),
  delete: (id: string) => client.delete(`/baselines/${id}`)
}
```

## 7. 多语言规范

### 7.1 设计原则

- 所有 UI 文案使用 i18n key，不直接写死中文
- 默认语言为中文（zh-CN），预留英文（en-US）、繁体中文（zh-TW）、日语（ja-JP）占位
- 文案集中管理，避免分散在组件内

### 7.2 目录结构建议

```
src/locales/
├── zh-CN.json
├── en-US.json
├── zh-TW.json
└── ja-JP.json
```

### 7.3 使用示例

```vue
<template>
  <span>{{ t('dashboard.todayHeats') }}</span>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>
```

## 8. 禁止事项

| 禁止 | 原因 | 替代方案 |
|------|------|----------|
| `any` 类型 | 类型不安全 | 定义明确类型 |
| 内联样式 | 难以维护 | Tailwind / scoped CSS |
| `var` 声明 | 作用域问题 | `const` / `let` |
| `==` 比较 | 类型转换问题 | `===` |
| 魔法数字 | 难以理解 | 命名常量 |
| 中文变量名 | 编码问题 | 英文变量名 |
