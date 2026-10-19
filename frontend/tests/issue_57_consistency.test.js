import test from 'node:test'
import assert from 'node:assert/strict'
import {
  validateQuestionEdit,
  adaptAnswerOnTypeChange,
  adaptOptionsOnTypeChange,
  sanitizeAnswerOnOptionRemove,
} from '../src/domain/bankManage.js'
import { ApiError } from '../src/api/client.js'
import { setLocale } from '../src/composables/useLocale.js'

test('Defect 1: validateQuestionEdit rejects MULTI with only 1 correct answer', () => {
  const options = [
    { key: 'A', content: 'Option A' },
    { key: 'B', content: 'Option B' },
    { key: 'C', content: 'Option C' },
  ]
  const res = validateQuestionEdit('MULTI', options, 'A')
  assert.equal(res.valid, false, 'MULTI question must require at least 2 distinct correct answers')
  assert.equal(res.error, 'invalid_answer')
})

test('Defect 1 & Risk 8: validateQuestionEdit rejects MULTI with duplicate answer keys resulting in 1 unique answer', () => {
  const options = [
    { key: 'A', content: 'Option A' },
    { key: 'B', content: 'Option B' },
  ]
  const res = validateQuestionEdit('MULTI', options, 'A,A')
  assert.equal(res.valid, false, 'MULTI question with duplicate identical answer keys should not count as 2 answers')
})

test('Risk 8: validateQuestionEdit rejects options with duplicate option keys', () => {
  const options = [
    { key: 'A', content: 'Option 1' },
    { key: 'A', content: 'Option 2' },
    { key: 'B', content: 'Option 3' },
  ]
  const res = validateQuestionEdit('SINGLE', options, 'A')
  assert.equal(res.valid, false, 'Options with duplicate keys must be rejected')

  const resMulti = validateQuestionEdit('MULTI', options, 'A,B')
  assert.equal(resMulti.valid, false, 'Options with duplicate keys must be rejected for MULTI')
})

test('Defect 1: validateQuestionEdit accepts MULTI with 2 or more distinct valid options', () => {
  const options = [
    { key: 'A', content: 'Option A' },
    { key: 'B', content: 'Option B' },
    { key: 'C', content: 'Option C' },
  ]
  const res = validateQuestionEdit('MULTI', options, 'A,B')
  assert.equal(res.valid, true)
})

test('Defect 1 & 2: validateQuestionEdit rejects single answer for MULTI while adapt allows staging', () => {
  const options = [
    { key: 'A', content: 'Option A' },
    { key: 'B', content: 'Option B' },
    { key: 'C', content: 'Option C' },
  ]
  const valRes = validateQuestionEdit('MULTI', options, 'A')
  assert.equal(valRes.valid, false, 'Saving MULTI with 1 answer must be rejected')

  // When switching type, non-T/F option may be staged in modal, but cannot be saved until second is picked
  const adaptRes = adaptAnswerOnTypeChange('MULTI', 'A', options)
  assert.equal(adaptRes, 'A')
})

test('Defect 2: adaptAnswerOnTypeChange clears T/F when converting JUDGE to SINGLE or MULTI', () => {
  const options = [
    { key: 'A', content: 'Option A' },
    { key: 'B', content: 'Option B' },
  ]
  const resSingle = adaptAnswerOnTypeChange('SINGLE', 'T', options)
  assert.equal(resSingle, '', 'T should not be kept as answer for SINGLE with A/B options')

  const resMulti = adaptAnswerOnTypeChange('MULTI', 'T', options)
  assert.equal(resMulti, '', 'T should not be kept as answer for MULTI with A/B options')
})

test('Review Finding 2: adaptOptionsOnTypeChange produces standard options on type conversion', () => {
  // JUDGE produces T/F options
  const judgeOpts = adaptOptionsOnTypeChange('JUDGE', [])
  assert.equal(judgeOpts.length, 2)
  assert.equal(judgeOpts[0].key, 'T')
  assert.equal(judgeOpts[1].key, 'F')

  // Switching from JUDGE to SINGLE resets to standard A, B, C, D
  const singleOpts = adaptOptionsOnTypeChange('SINGLE', judgeOpts)
  assert.equal(singleOpts.length, 4)
  assert.deepEqual(singleOpts.map(o => o.key), ['A', 'B', 'C', 'D'])

  // Switching from SINGLE to MULTI preserves existing options
  const existingSingle = [
    { key: 'A', content: 'Apple' },
    { key: 'B', content: 'Banana' },
    { key: 'C', content: 'Cherry' },
  ]
  const multiOpts = adaptOptionsOnTypeChange('MULTI', existingSingle)
  assert.equal(multiOpts.length, 3)
  assert.equal(multiOpts[0].content, 'Apple')

  // ESSAY produces empty options
  const essayOpts = adaptOptionsOnTypeChange('ESSAY', existingSingle)
  assert.equal(essayOpts.length, 0)
})

test('Review Finding 4: ApiError resolves EXAM_ACTIVE_PROTECTED and rawDetail fallback', () => {
  setLocale('zh-CN')
  const errActiveZh = new ApiError(403, 'EXAM_ACTIVE_PROTECTED')
  assert.match(errActiveZh.message, /存在活动模拟考试/)

  setLocale('en-US')
  const errActiveEn = new ApiError(403, 'EXAM_ACTIVE_PROTECTED')
  assert.match(errActiveEn.message, /Mock exam in progress/)

  // Reset locale back to zh-CN
  setLocale('zh-CN')

  // When error code is unknown, fall back to rawDetail if present
  const errFallback = new ApiError(400, 'UNKNOWN_ERROR', {}, null, 'Custom backend error')
  assert.equal(errFallback.message, 'Custom backend error')
})

