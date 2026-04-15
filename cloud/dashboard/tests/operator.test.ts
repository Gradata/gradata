import { describe, it, expect } from 'vitest'
import { isOperatorEmail } from '@/lib/operator'

describe('isOperatorEmail', () => {
  it('returns true for @gradata.ai emails', () => {
    expect(isOperatorEmail('oliver@gradata.ai')).toBe(true)
  })

  it('returns true for @sprites.ai emails', () => {
    expect(isOperatorEmail('founder@sprites.ai')).toBe(true)
  })

  it('is case-insensitive on domain', () => {
    expect(isOperatorEmail('oliver@GRADATA.AI')).toBe(true)
    expect(isOperatorEmail('Oliver@Gradata.Ai')).toBe(true)
  })

  it('returns false for outside domains', () => {
    expect(isOperatorEmail('user@example.com')).toBe(false)
    expect(isOperatorEmail('user@gradata.com')).toBe(false)
    expect(isOperatorEmail('user@gradata.ai.evil.com')).toBe(false)
  })

  it('returns false for null, undefined, empty', () => {
    expect(isOperatorEmail(null)).toBe(false)
    expect(isOperatorEmail(undefined)).toBe(false)
    expect(isOperatorEmail('')).toBe(false)
  })

  it('returns false for malformed emails without @', () => {
    expect(isOperatorEmail('gradata.ai')).toBe(false)
    expect(isOperatorEmail('oliver')).toBe(false)
  })

  it('trims whitespace on domain', () => {
    expect(isOperatorEmail('oliver@gradata.ai ')).toBe(true)
  })
})
