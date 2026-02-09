<script setup lang="ts">
import { ref } from 'vue'
import AppSidebar from './AppSidebar.vue'
import AppHeader from './AppHeader.vue'
import PageContainer from './PageContainer.vue'

// 侧边栏折叠状态
const sidebarCollapsed = ref(false)

// 移动端侧边栏显示状态
const mobileMenuOpen = ref(false)

const handleToggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

const handleToggleMobileMenu = () => {
  mobileMenuOpen.value = !mobileMenuOpen.value
}

// 点击遮罩层关闭移动端菜单
const handleCloseMobileMenu = () => {
  mobileMenuOpen.value = false
}
</script>

<template>
  <div class="h-screen flex overflow-hidden bg-bg-page font-display">
    <!-- 桌面端侧边栏 -->
    <div class="hidden lg:block">
      <AppSidebar :collapsed="sidebarCollapsed" @toggle="handleToggleSidebar" />
    </div>

    <!-- 移动端侧边栏遮罩 -->
    <Transition name="fade">
      <div
        v-if="mobileMenuOpen"
        class="lg:hidden fixed inset-0 bg-black/50 z-40"
        @click="handleCloseMobileMenu"
      />
    </Transition>

    <!-- 移动端侧边栏 -->
    <Transition name="slide">
      <div
        v-if="mobileMenuOpen"
        class="lg:hidden fixed inset-y-0 left-0 z-50 w-sidebar"
      >
        <AppSidebar :collapsed="false" @toggle="handleCloseMobileMenu" />
      </div>
    </Transition>

    <!-- 主内容区 -->
    <main class="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
      <!-- 顶部栏 -->
      <AppHeader
        @toggle-sidebar="handleToggleMobileMenu"
      />

      <!-- 页面内容 -->
      <PageContainer>
        <slot />
      </PageContainer>
    </main>
  </div>
</template>

<style scoped>
/* 遮罩层淡入淡出 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* 侧边栏滑入滑出 */
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(-100%);
}
</style>
