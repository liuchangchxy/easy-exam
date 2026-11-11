import { describe, it, expect, vi } from 'vitest'

vi.mock('../../src/api/questions', () => ({
  getQuestion: vi.fn(),
}))

import { buildVariantRequestBody } from '../../src/api/ai'

describe('variant request contract', () => {
  it('normalizes the legacy practice payload into the API contract', () => {
    const body = buildVariantRequestBody(
      { question_id: 'q1', prompt: '改为同考点题' },
      { bank_id: 'bank-1' },
    )
    expect(body).toEqual({
      original_question_id: 'q1',
      target_bank_id: 'bank-1',
      prompt_hint: '改为同考点题',
    })
  })

  it('keeps explicit contract fields', () => {
    const body = buildVariantRequestBody({
      original_question_id: 'q2',
      target_bank_id: 'bank-2',
      prompt_hint: 'hint',
      prompt: 'ignored',
    })
    expect(body).toEqual({
      original_question_id: 'q2',
      target_bank_id: 'bank-2',
      prompt_hint: 'hint',
    })
  })

  it('refuses to send a request without an original question or target bank', () => {
    expect(() => buildVariantRequestBody({ prompt: 'x' })).toThrow('original_question_id')
    expect(() => buildVariantRequestBody({ question_id: 'q1' })).toThrow('target_bank_id')
  })
})
