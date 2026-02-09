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
        // 主色 - Element Plus 风格
        primary: {
          DEFAULT: '#409EFF',
          light: '#79BBFF',
          dark: '#337ECC',
        },
        // 功能色
        success: '#67C23A',
        warning: '#E6A23C',
        danger: '#F56C6C',
        info: '#909399',
        // 背景色
        'bg-page': '#F5F7FA',
        'bg-card': '#FFFFFF',
        // 边框色
        'border-base': '#DCDFE6',
        'border-light': '#E4E7ED',
        // 文字色
        'text-primary': '#303133',
        'text-regular': '#606266',
        'text-secondary': '#909399',
        'text-placeholder': '#C0C4CC',
        // 侧边栏专用色
        sidebar: {
          bg: '#FFFFFF',
          border: '#E4E7ED',
        },
      },
      fontFamily: {
        display: ['Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        'sm': '0 1px 2px rgba(0, 0, 0, 0.05)',
        'base': '0 2px 4px rgba(0, 0, 0, 0.12)',
        'lg': '0 4px 12px rgba(0, 0, 0, 0.15)',
      },
      spacing: {
        'sidebar': '240px',
        'sidebar-collapsed': '64px',
        'header': '64px',
      },
    },
  },
  plugins: [],
}

