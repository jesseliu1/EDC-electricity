import { describe, it, expect } from 'vitest'
import tailwindConfig from '../../tailwind.config.js'

const colors = tailwindConfig.theme?.extend?.colors ?? {}
const fontFamily = tailwindConfig.theme?.extend?.fontFamily ?? {}
const borderRadius = tailwindConfig.theme?.extend?.borderRadius ?? {}
const boxShadow = tailwindConfig.theme?.extend?.boxShadow ?? {}

describe('Design Tokens — 色值', () => {
  it('primary 应为深工业蓝 #1152d4', () => {
    const primary =
      typeof colors.primary === 'string'
        ? colors.primary
        : colors.primary?.DEFAULT
    expect(primary).toBe('#1152d4')
  })

  it('accent 应为工业青 #00d4ff', () => {
    expect(colors.accent).toBe('#00d4ff')
  })

  it('background-light 应为 #f6f6f8', () => {
    expect(colors['background-light']).toBe('#f6f6f8')
  })

  it('surface-light 应为 #ffffff', () => {
    expect(colors['surface-light']).toBe('#ffffff')
  })

  it('border-light 应为 #e2e8f0', () => {
    expect(colors['border-light']).toBe('#e2e8f0')
  })
})

describe('Design Tokens — 字体', () => {
  it('display 字体系列包含 Inter', () => {
    expect(fontFamily.display).toContain('Inter')
  })

  it('display 字体系列包含 Noto Sans SC', () => {
    expect(fontFamily.display).toContain('Noto Sans SC')
  })
})

describe('Design Tokens — 圆角', () => {
  it('包含 industrial 圆角 12px', () => {
    expect(borderRadius.industrial).toBe('12px')
  })
})

describe('Design Tokens — 阴影', () => {
  it('包含 card 阴影', () => {
    expect(boxShadow.card).toBeDefined()
  })

  it('包含 subtle 阴影', () => {
    expect(boxShadow.subtle).toBeDefined()
  })
})
