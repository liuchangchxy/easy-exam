import { beforeEach, describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { reactive } from 'vue'
import ImportView from '../../src/views/ImportView.vue'
import { t } from '../../src/composables/useLocale.js'
import { listBanks } from '../../src/api/banks'
import {
  previewImport,
  previewFileImport,
  startImportJob,
  getImportJob,
  cancelImportJob,
  createImportDraft,
  listImportDrafts,
  getImportDraft,
  updateImportDraft,
  deleteImportDraft,
} from '../../src/api/imports'

const push = vi.fn()
const replace = vi.fn()
const routeState = reactive({ query: { bankId: 'b1' } })
const captured = vi.hoisted(() => ({ leaveGuard: null }))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push, replace }),
  useRoute: () => routeState,
  onBeforeRouteLeave: (guard) => { captured.leaveGuard = guard },
}))

vi.mock('../../src/api/banks', () => ({
  listBanks: vi.fn(),
}))

vi.mock('../../src/api/imports', () => ({
  previewImport: vi.fn(),
  previewFileImport: vi.fn(),
  uploadImport: vi.fn(),
  previewPdfImport: vi.fn(),
  confirmPdfImport: vi.fn(),
  createImportDraft: vi.fn(),
  listImportDrafts: vi.fn(),
  getImportDraft: vi.fn(),
  updateImportDraft: vi.fn(),
  deleteImportDraft: vi.fn(),
  startImportJob: vi.fn(),
  getImportJob: vi.fn(),
  cancelImportJob: vi.fn(),
}))

const flush = () => new Promise(resolve => setTimeout(resolve, 0))
const wait = ms => new Promise(resolve => setTimeout(resolve, ms))

const BANKS = [
  { id: 'b1', name: 'Bank One', question_count: 3, role: 'ADMIN' },
  { id: 'b2', name: 'Bank Two', question_count: 5, role: 'ADMIN' },
]

const SPREADSHEET_PREVIEW = {
  accepted: true,
  headers: ['Stem', 'Answer'],
  preview_rows: [],
  missing: [],
  question_count: 1,
  duplicates: [],
  mapping: { stem: 0, answer: 1 },
}

function markdownFile() {
  const file = new File(['# questions'], 'questions.md', { type: 'text/markdown' })
  if (typeof file.text !== 'function') file.text = () => Promise.resolve('# questions')
  return file
}

function spreadsheetFile() {
  return new File(['a,b'], 'questions.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
}

async function mountView() {
  const wrapper = mount(ImportView, { props: { token: 't1' }, attachTo: document.body })
  await flush()
  await flush()
  return wrapper
}

async function chooseFile(wrapper, file) {
  await wrapper.find('.file-drop').trigger('drop', { dataTransfer: { files: [file] } })
  await flush()
}

function stepItems(wrapper) {
  return wrapper.findAll('li.import-step')
}

function activeStepIndex(wrapper) {
  return stepItems(wrapper).findIndex(item => item.attributes('aria-current') === 'step') + 1
}

function nextButton(wrapper) {
  return wrapper.find('.import-actions .btn-primary')
}

function unmount(wrapper) {
  wrapper.unmount()
  document.body.innerHTML = ''
}

beforeEach(() => {
  vi.resetAllMocks()
  routeState.query = { bankId: 'b1' }
  captured.leaveGuard = null
  listBanks.mockResolvedValue(BANKS)
  listImportDrafts.mockResolvedValue([])
  getImportDraft.mockResolvedValue({ id: 'draft-1', bank_id: 'b1', step: 1, status: 'OPEN', state: {} })
  createImportDraft.mockResolvedValue({ id: 'draft-1', bank_id: 'b1', step: 1, status: 'OPEN' })
  updateImportDraft.mockResolvedValue({ id: 'draft-1', bank_id: 'b1', step: 2, status: 'OPEN' })
  deleteImportDraft.mockResolvedValue(null)
  startImportJob.mockResolvedValue(null)
  getImportJob.mockResolvedValue(null)
  cancelImportJob.mockResolvedValue(null)
})

describe('ImportView wizard navigation', () => {
  it('advances to the check step and keeps the step in the URL in both directions', async () => {
    previewFileImport.mockResolvedValue(SPREADSHEET_PREVIEW)
    const wrapper = await mountView()

    await chooseFile(wrapper, spreadsheetFile())
    await nextButton(wrapper).trigger('click')
    await flush()

    expect(activeStepIndex(wrapper)).toBe(2)
    expect(wrapper.find('.import-progress').attributes('aria-valuenow')).toBe('2')
    expect(wrapper.find('.mapping-grid').exists()).toBe(true)
    expect(push.mock.calls.some(([arg]) => arg?.query?.step === '2' && arg.query.bankId === 'b1')).toBe(true)

    await wrapper.find('.import-actions .btn-quiet').trigger('click')
    await flush()

    expect(activeStepIndex(wrapper)).toBe(1)
    expect(wrapper.find('.import-progress').attributes('aria-valuenow')).toBe('1')
    expect(push.mock.calls.some(([arg]) => arg?.query?.bankId === 'b1' && !arg.query.step)).toBe(true)

    unmount(wrapper)
  })

  it('opens at the step stored in the URL when a draft is loaded on reload', async () => {
    routeState.query = { bankId: 'b1', step: '2', draft: 'draft-9' }
    getImportDraft.mockResolvedValue({
      id: 'draft-9',
      bank_id: 'b1',
      filename: 'reload.xlsx',
      source_kind: 'spreadsheet',
      step: 2,
      status: 'OPEN',
      state: {
        spreadsheet_preview: SPREADSHEET_PREVIEW,
        mapping: { stem: 0, answer: 1 },
        option_slots: [],
        duplicate_strategy: 'skip',
      },
    })

    const wrapper = await mountView()

    expect(getImportDraft).toHaveBeenCalledWith('t1', 'draft-9')
    expect(activeStepIndex(wrapper)).toBe(2)
    expect(wrapper.find('.import-progress').attributes('aria-valuenow')).toBe('2')
    expect(wrapper.find('.mapping-grid').exists()).toBe(true)

    unmount(wrapper)
  })
})

describe('ImportView draft autosave', () => {
  it('creates a draft when the step changes and updates it after a debounced edit', async () => {
    previewFileImport.mockResolvedValue(SPREADSHEET_PREVIEW)
    const wrapper = await mountView()

    await chooseFile(wrapper, spreadsheetFile())
    await nextButton(wrapper).trigger('click')
    await flush()

    const created = createImportDraft.mock.calls.find(([, bank, payload]) => bank === 'b1' && payload?.step === 2)
    expect(created).toBeTruthy()
    expect(created[2].source_kind).toBe('spreadsheet')
    expect(created[2].filename).toBe('questions.xlsx')
    expect(created[2].state.mapping).toMatchObject({ stem: 0, answer: 1 })

    await wrapper.findAll('.mapping-grid select')[0].setValue('1')
    await wait(650)

    const updated = updateImportDraft.mock.calls.find(([, id, payload]) => id === 'draft-1' && payload?.state?.mapping?.stem === 1)
    expect(updated).toBeTruthy()
    expect(updated[2].step).toBe(2)

    unmount(wrapper)
  })

  it('lists open drafts, resumes one, and deletes another', async () => {
    listImportDrafts.mockResolvedValue([
      { id: 'd1', filename: 'old.xlsx', source_kind: 'spreadsheet', step: 2, updated_at: '2026-11-12T10:00:00Z' },
      { id: 'd2', filename: 'old.md', source_kind: 'text', step: 3, updated_at: '2026-11-12T11:00:00Z' },
    ])
    getImportDraft.mockResolvedValue({
      id: 'd1',
      bank_id: 'b1',
      filename: 'old.xlsx',
      source_kind: 'spreadsheet',
      step: 2,
      status: 'OPEN',
      state: {
        spreadsheet_preview: SPREADSHEET_PREVIEW,
        mapping: { stem: 0, answer: 1 },
        option_slots: [],
        duplicate_strategy: 'skip',
      },
    })

    const wrapper = await mountView()

    const banner = wrapper.find('[data-testid="import-resume"]')
    expect(banner.exists()).toBe(true)
    expect(banner.text()).toContain('old.xlsx')
    expect(banner.findAll('[data-testid="draft-row"]')).toHaveLength(2)

    await banner.findAll('[data-testid="draft-resume"]')[0].trigger('click')
    await flush()

    expect(getImportDraft).toHaveBeenCalledWith('t1', 'd1')
    expect(activeStepIndex(wrapper)).toBe(2)
    expect(push.mock.calls.some(([arg]) => arg?.query?.draft === 'd1' && arg.query.step === '2')).toBe(true)
    expect(wrapper.findAll('[data-testid="draft-row"]')).toHaveLength(1)

    await wrapper.find('[data-testid="draft-delete"]').trigger('click')
    await flush()

    expect(deleteImportDraft).toHaveBeenCalledWith('t1', 'd2')
    expect(wrapper.find('[data-testid="import-resume"]').exists()).toBe(false)

    unmount(wrapper)
  })
})

describe('ImportView leave guard', () => {
  it('leaves without a prompt when the wizard is clean', async () => {
    const wrapper = await mountView()
    const next = vi.fn()

    captured.leaveGuard({}, {}, next)
    await flush()

    expect(next).toHaveBeenCalledTimes(1)
    expect(document.body.querySelector('[data-testid="leave-dialog"]')).toBeNull()

    unmount(wrapper)
  })

  it('asks before abandoning a mid-way wizard and offers "continue later"', async () => {
    previewImport.mockResolvedValue({ question_count: 1, duplicates: [] })
    const wrapper = await mountView()

    await chooseFile(wrapper, markdownFile())
    await nextButton(wrapper).trigger('click')
    await flush()
    expect(activeStepIndex(wrapper)).toBe(3)

    const stayNext = vi.fn()
    captured.leaveGuard({}, {}, stayNext)
    await flush()

    const dialog = document.body.querySelector('[data-testid="leave-dialog"]')
    expect(dialog).toBeTruthy()
    expect(dialog.textContent).toContain(t('ep.imports.leave_later'))

    document.body.querySelector('.leave-stay').click()
    await flush()
    expect(stayNext).toHaveBeenCalledWith(false)

    const laterNext = vi.fn()
    captured.leaveGuard({}, {}, laterNext)
    await flush()
    document.body.querySelector('.leave-later').click()
    await flush()

    expect(laterNext).toHaveBeenCalledTimes(1)
    expect(laterNext.mock.calls[0]).toEqual([])

    unmount(wrapper)
  })

  it('does not prompt while a job is running because the job belongs to the server', async () => {
    previewImport.mockResolvedValue({ question_count: 1, duplicates: [] })
    startImportJob.mockResolvedValue({ job_id: 'job-leave', status: 'RUNNING' })
    getImportJob.mockResolvedValue({ status: 'RUNNING', imported_count: 0, total: 1 })
    const wrapper = await mountView()

    await chooseFile(wrapper, markdownFile())
    await nextButton(wrapper).trigger('click')
    await flush()
    await nextButton(wrapper).trigger('click')
    await flush()

    const next = vi.fn()
    captured.leaveGuard({}, {}, next)
    await flush()

    expect(next).toHaveBeenCalledTimes(1)
    expect(document.body.querySelector('[data-testid="leave-dialog"]')).toBeNull()

    unmount(wrapper)
  })
})

describe('ImportView import job', () => {
  async function startTextJob() {
    previewImport.mockResolvedValue({ question_count: 3, duplicates: [] })
    const wrapper = await mountView()
    await chooseFile(wrapper, markdownFile())
    await nextButton(wrapper).trigger('click')
    await flush()
    await nextButton(wrapper).trigger('click')
    await flush()
    return wrapper
  }

  it('starts a job, reports progress, then reports the final count', async () => {
    startImportJob.mockResolvedValue({ job_id: 'job-1', status: 'RUNNING' })
    getImportJob
      .mockResolvedValueOnce({ status: 'RUNNING', imported_count: 1, total: 3 })
      .mockResolvedValueOnce({ status: 'COMPLETED', imported_count: 3, total: 3 })
    const wrapper = await startTextJob()

    expect(startImportJob).toHaveBeenCalledWith('t1', 'b1', expect.objectContaining({
      format: 'markdown',
      content: '# questions',
      duplicate_strategy: 'skip',
    }))
    expect(activeStepIndex(wrapper)).toBe(4)
    expect(wrapper.find('[data-testid="job-progress"]').exists()).toBe(true)

    await wrapper.vm.pollJobOnce()
    await flush()
    expect(wrapper.find('[data-testid="job-progress"]').text()).toContain(t('ep.imports.job_progress', { done: 1, total: 3 }))

    await wrapper.vm.pollJobOnce()
    await flush()

    const result = wrapper.find('[data-testid="import-result"]')
    expect(result.find('[data-testid="result-bank"]').text()).toBe('Bank One')
    expect(result.text()).toContain(t('ep.imports.result_desc', { count: 3 }))
    expect(wrapper.find('[data-testid="job-progress"]').exists()).toBe(false)

    unmount(wrapper)
  })

  it('cancels a running job and stops polling', async () => {
    startImportJob.mockResolvedValue({ job_id: 'job-cancel', status: 'RUNNING' })
    getImportJob.mockResolvedValue({ status: 'RUNNING', imported_count: 0, total: 3 })
    const wrapper = await startTextJob()

    await wrapper.find('[data-testid="job-cancel"]').trigger('click')
    await flush()

    expect(cancelImportJob).toHaveBeenCalledWith('t1', 'job-cancel')
    expect(wrapper.find('[data-testid="job-error"]').text()).toContain(t('ep.imports.job_cancelled'))
    const callsAfterCancel = getImportJob.mock.calls.length

    await wait(900)
    expect(getImportJob.mock.calls.length).toBe(callsAfterCancel)

    unmount(wrapper)
  })

  it('shows the failure reason and retries the import', async () => {
    startImportJob
      .mockResolvedValueOnce({ job_id: 'job-bad', status: 'RUNNING' })
      .mockResolvedValueOnce({ job_id: 'job-retry', status: 'RUNNING' })
    getImportJob.mockResolvedValueOnce({ status: 'FAILED', reason: 'parse exploded', imported_count: 0, total: 3 })
    const wrapper = await startTextJob()

    await wrapper.vm.pollJobOnce()
    await flush()

    expect(wrapper.find('[data-testid="job-error"]').text()).toContain('parse exploded')
    expect(startImportJob).toHaveBeenCalledTimes(1)

    await wrapper.find('[data-testid="job-retry"]').trigger('click')
    await flush()

    expect(startImportJob).toHaveBeenCalledTimes(2)
    expect(activeStepIndex(wrapper)).toBe(4)

    unmount(wrapper)
  })
})

describe('ImportView pasted text source', () => {
  it('previews and imports pasted text without a file', async () => {
    previewImport.mockResolvedValue({ question_count: 2, duplicates: [] })
    startImportJob.mockResolvedValue({ job_id: 'job-paste', status: 'RUNNING' })
    getImportJob.mockResolvedValue({ status: 'COMPLETED', imported_count: 2, total: 2 })
    const wrapper = await mountView()

    await wrapper.find('[data-testid="source-mode-paste"]').trigger('click')
    await flush()
    expect(wrapper.find('.file-drop').exists()).toBe(false)
    expect(nextButton(wrapper).attributes('disabled')).toBeDefined()

    await wrapper.find('#import-paste').setValue('# Q1\nA')
    await flush()
    expect(nextButton(wrapper).attributes('disabled')).toBeUndefined()

    await nextButton(wrapper).trigger('click')
    await flush()

    expect(previewImport).toHaveBeenCalledWith('t1', 'b1', { format: 'markdown', content: '# Q1\nA' })
    expect(activeStepIndex(wrapper)).toBe(3)

    await nextButton(wrapper).trigger('click')
    await flush()

    expect(startImportJob).toHaveBeenCalledWith('t1', 'b1', expect.objectContaining({
      format: 'markdown',
      content: '# Q1\nA',
    }))
    expect(activeStepIndex(wrapper)).toBe(4)

    unmount(wrapper)
  })
})

describe('ImportView duplicate step', () => {
  it('re-reads the spreadsheet with the chosen mapping before showing duplicates', async () => {
    // Duplicates depend on (file + mapping + current bank), so the strategy
    // step must be built from the mapping the user picked, not the auto one.
    previewFileImport
      .mockResolvedValueOnce(SPREADSHEET_PREVIEW)
      .mockResolvedValueOnce({
        ...SPREADSHEET_PREVIEW,
        duplicates: [{ index: 0, question_id: 'q1', stem: 'same stem' }],
      })

    const wrapper = await mountView()
    await chooseFile(wrapper, spreadsheetFile())
    await nextButton(wrapper).trigger('click')
    await flush()
    expect(activeStepIndex(wrapper)).toBe(2)

    await wrapper.find('[data-step="check"] .import-actions .btn-primary').trigger('click')
    await flush()
    await flush()

    expect(previewFileImport).toHaveBeenCalledTimes(2)
    const mapping = previewFileImport.mock.calls[1][3]
    expect(mapping).toMatchObject({ stem: 0, answer: 1 })
    expect(activeStepIndex(wrapper)).toBe(3)
    expect(wrapper.find('.dup-list').exists()).toBe(true)

    unmount(wrapper)
  })
})
