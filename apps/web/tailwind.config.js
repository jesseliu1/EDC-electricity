/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // 主色 — 深工业蓝 (对齐 stitch_dashboard 原型)
        primary: {
          DEFAULT: '#1152d4',
          light: '#79BBFF',
          dark: '#0a365c',
        },
        // 强调色 — 工业青
        accent: '#00d4ff',
        // 功能色
        success: '#10B981',
        warning: '#F59E0B',
        danger: '#EF4444',
        info: '#909399',
        // 背景色
        'background-light': '#f6f6f8',
        'background-dark': '#101622',
        'bg-page': '#f6f6f8',
        'bg-card': '#FFFFFF',
        // 表面色
        'surface-light': '#ffffff',
        'surface-dark': '#1a2234',
        // 边框色
        'border-light': '#e2e8f0',
        'border-dark': '#2d3748',
        'border-base': '#DCDFE6',
        // 文字色
        'text-primary': '#303133',
        'text-main': '#0F172A',
        'text-regular': '#606266',
        'text-secondary': '#64748B',
        'text-placeholder': '#C0C4CC',
        // 侧边栏专用色
        sidebar: {
          bg: '#FFFFFF',
          border: '#E4E7ED',
        },
      },
      fontFamily: {
        display: ['Inter', 'Noto Sans SC', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        industrial: '12px',
      },
      boxShadow: {
        sm: '0 1px 2px rgba(0, 0, 0, 0.05)',
        subtle: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        base: '0 2px 4px rgba(0, 0, 0, 0.12)',
        card: '0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03)',
        lg: '0 4px 12px rgba(0, 0, 0, 0.15)',
      },
      spacing: {
        sidebar: '240px',
        'sidebar-collapsed': '64px',
        header: '64px',
      },
    },
  },
  plugins: [],
}


