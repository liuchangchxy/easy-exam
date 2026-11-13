import { beforeEach, describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ImportView from '../../src/views/ImportView.vue'
import { t } from '../../src/composables/useLocale.js'
import { listBanks } from '../../src/api/banks'
import { previewImport, previewFileImport, uploadImport } from '../../src/api/imports'

const push = vi.fn()
const replace = vi.fn()
const route = { query: { bankId: 'b1' } }

vi.mock('vue-router', () => ({
  useRouter: () => ({ push, replace }),
  useRoute: () => route,
  onBeforeRouteLeave: vi.fn(),
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

const BANKS = [
  { id: 'b1', name: 'Bank One', question_count: 3, role: 'ADMIN' },
  { id: 'b2', name: 'Bank Two', question_count: 5, role: 'ADMIN' },
]

function duplicates(count) {
  return Array.from({ length: count }, (_, i) => ({ id: `dup-${i + 1}`, stem: `Duplicate ${i + 1}` }))
}

function markdownFile() {
  const file = new File(['# questions'], 'questions.md', { type: 'text/markdown' })
  if (typeof file.text !== 'function') {
    file.text = () => Promise.resolve('# questions')
  }
  return file
}

function spreadsheetFile() {
  return new File(['a,b'], 'questions.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
}

async function mountView() {
  const wrapper = mount(ImportView, { props: { token: 't1' }, attachTo: document.body })
  await flush()
  return wrapper
}

async function chooseFile(wrapper, file) {
  await wrapper.find('.file-drop').trigger('drop', { dataTransfer: { files: [file] } })
  await flush()
}

async function mountWithTextPreview(duplicateCount) {
  previewImport.mockResolvedValue({ question_count: duplicateCount, duplicates: duplicates(duplicateCount) })
  const wrapper = await mountView()

  await chooseFile(wrapper, markdownFile())

  await wrapper.find('.import-actions .btn-primary').trigger('click')
  await flush()

  return wrapper
}

function unmount(wrapper) {
  wrapper.unmount()
  document.body.innerHTML = ''
}

describe('ImportView duplicate list truncation', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    route.query = { bankId: 'b1' }
    listBanks.mockResolvedValue(BANKS)
  })

  it('caps the visible duplicate list and reveals the rest behind a more-count summary', async () => {
    const wrapper = await mountWithTextPreview(10)

    const list = wrapper.find('.dup-list')
    expect(list.exists()).toBe(true)
    const directRows = Array.from(list.element.children).filter(el => el.classList.contains('list-row'))
    expect(directRows).toHaveLength(8)
    expect(directRows.some(el => el.textContent.includes('Duplicate 10'))).toBe(false)

    const details = list.find('details.dup-more')
    expect(details.exists()).toBe(true)
    expect(details.find('summary').text()).toBe(t('ep.common.more_count', { count: 2 }))
    expect(details.findAll('.list-row')).toHaveLength(2)
    expect(details.text()).toContain('Duplicate 10')

    unmount(wrapper)
  })

  it('renders no more-count control when every duplicate already fits', async () => {
    const wrapper = await mountWithTextPreview(3)

    const list = wrapper.find('.dup-list')
    expect(list.element.querySelectorAll('.list-row')).toHaveLength(3)
    expect(list.find('details.dup-more').exists()).toBe(false)

    unmount(wrapper)
  })

  it('places the error notice under the primary action row', async () => {
    previewImport.mockRejectedValue(new Error('preview exploded'))
    const wrapper = await mountView()

    await chooseFile(wrapper, markdownFile())
    await wrapper.find('.import-actions .btn-primary').trigger('click')
    await flush()

    const notice = wrapper.find('.import-error')
    expect(notice.exists()).toBe(true)
    expect(notice.text()).toContain('preview exploded')
    expect(notice.attributes('role')).toBe('alert')

    // It sits inside the form, immediately after the first step block.
    const noticeEl = notice.element
    expect(noticeEl.parentElement.classList.contains('import-form')).toBe(true)
    expect(noticeEl.previousElementSibling.classList.contains('step-block')).toBe(true)

    unmount(wrapper)
  })
})

describe('ImportView target bank and result', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    route.query = { bankId: 'b1' }
    listBanks.mockResolvedValue(BANKS)
  })

  it('confirms a bank switch after a preview, resets the preview and replaces the URL', async () => {
    const wrapper = await mountWithTextPreview(3)
    expect(wrapper.find('.dup-list').exists()).toBe(true)

    await wrapper.find('#import-bank').setValue('b2')
    await flush()

    const accept = document.body.querySelector('.bank-change-accept')
    expect(accept).toBeTruthy()
    accept.click()
    await flush()

    expect(replace).toHaveBeenCalledWith({ query: { bankId: 'b2' } })
    expect(wrapper.find('#import-bank').element.value).toBe('b2')
    expect(wrapper.find('.dup-list').exists()).toBe(false)
    expect(wrapper.find('[data-testid="import-result"]').exists()).toBe(false)

    unmount(wrapper)
  })

  it('restores the previous bank when the switch is cancelled', async () => {
    const wrapper = await mountWithTextPreview(3)

    await wrapper.find('#import-bank').setValue('b2')
    await flush()

    const cancel = document.body.querySelector('.bank-change-cancel')
    expect(cancel).toBeTruthy()
    cancel.click()
    await flush()

    expect(replace).not.toHaveBeenCalled()
    expect(wrapper.find('#import-bank').element.value).toBe('b1')
    expect(wrapper.find('.dup-list').exists()).toBe(true)

    unmount(wrapper)
  })

  it('shows the bank that received the job, not the bank selected afterwards', async () => {
    let resolveUpload
    uploadImport.mockImplementation(() => new Promise(resolve => { resolveUpload = resolve }))

    const wrapper = await mountWithTextPreview(0)
    await wrapper.find('.import-actions .btn-primary').trigger('click')
    await flush()
    expect(uploadImport).toHaveBeenCalledWith('t1', 'b1', expect.any(File), 'skip', null)

    // The upload is still in flight, so the selector is locked. A target change
    // can still arrive from outside the select (route/state); accept the reset.
    expect(wrapper.find('#import-bank').element.disabled).toBe(true)
    wrapper.vm.bankId = 'b2'
    await flush()
    document.body.querySelector('.bank-change-accept').click()
    await flush()

    resolveUpload({ job_id: 'job-1', imported_count: 1 })
    await flush()

    const result = wrapper.find('[data-testid="import-result"]')
    expect(result.exists()).toBe(true)
    expect(result.find('[data-testid="result-bank"]').text()).toBe('Bank One')
    expect(result.find('.kv-key').text()).toBeTruthy()
    expect(result.text()).toContain(t('ep.imports.result_bank'))
    expect(result.find('[data-testid="result-bank"]').text()).not.toContain('Bank Two')
    expect(wrapper.find('#import-bank').element.value).toBe('b2')

    // The mismatch is stated on the receipt, and "open bank" follows the bank
    // that accepted the job rather than the selector's current value.
    const changed = result.find('[data-testid="result-bank-changed"]')
    expect(changed.exists()).toBe(true)
    expect(changed.text()).toContain('Bank One')
    expect(changed.text()).toContain('Bank Two')

    await result.find('.import-actions .btn-primary').trigger('click')
    expect(push).toHaveBeenCalledWith('/banks/b1')

    unmount(wrapper)
  })

  it('discards a preview response for a bank that is no longer selected and locks the selector meanwhile', async () => {
    let resolvePreview
    previewFileImport.mockImplementation(() => new Promise(resolve => { resolvePreview = resolve }))

    const wrapper = await mountView()
    expect(wrapper.find('#import-bank').element.disabled).toBe(false)

    await chooseFile(wrapper, spreadsheetFile())
    await wrapper.find('.import-actions .btn-primary').trigger('click')
    await flush()

    expect(previewFileImport).toHaveBeenCalledWith('t1', 'b1', expect.any(File))
    const locked = wrapper.find('#import-bank')
    expect(locked.element.disabled).toBe(true)
    expect(locked.attributes('title')).toBe(t('ep.imports.bank_locked_busy'))

    // The request was sent for b1; the target changes before it resolves.
    wrapper.vm.bankId = 'b2'
    await flush()

    resolvePreview({
      accepted: true,
      headers: ['Stem', 'Answer'],
      preview_rows: [],
      missing: [],
      question_count: 1,
      mapping: { stem: 0, answer: 1 },
    })
    await flush()

    // The stale mapping step never appears, so it can never be confirmed into
    // the newly selected bank.
    expect(wrapper.findAll('.step-no').map(el => el.text())).toEqual(['01'])
    expect(wrapper.find('[data-step="fields"]').exists()).toBe(false)
    expect(wrapper.find('#import-bank').element.disabled).toBe(false)
    expect(wrapper.find('#import-bank').element.value).toBe('b2')

    unmount(wrapper)
  })
})

describe('ImportView file selection', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    route.query = { bankId: 'b1' }
    listBanks.mockResolvedValue(BANKS)
  })

  it('rejects an unsupported extension chosen from the picker and disables the primary action', async () => {
    const wrapper = await mountView()

    const input = wrapper.find('input[type="file"]')
    const badFile = new File(['nope'], 'notes.exe', { type: 'application/octet-stream' })
    Object.defineProperty(input.element, 'files', { value: [badFile], configurable: true })
    await input.trigger('change')
    await flush()

    expect(wrapper.text()).toContain(t('ep.imports.supported'))
    const primary = wrapper.find('.import-actions .btn-primary')
    expect(primary.exists()).toBe(true)
    expect(primary.attributes('disabled')).toBeDefined()
    expect(wrapper.find('.file-name').text()).toBe(t('ep.imports.drop'))

    unmount(wrapper)
  })

  it('opens the picker when the drop zone itself is clicked', async () => {
    const wrapper = await mountView()
    const input = wrapper.find('input[type="file"]')
    const clickSpy = vi.spyOn(input.element, 'click').mockImplementation(() => {})

    await wrapper.find('.file-drop').trigger('click')
    expect(clickSpy).toHaveBeenCalledTimes(1)

    await wrapper.find('.file-drop .btn').trigger('click')
    expect(clickSpy).toHaveBeenCalledTimes(2)

    unmount(wrapper)
  })
})

describe('ImportView contextual return path', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    route.query = { bankId: 'b1', from: 'manage' }
    listBanks.mockResolvedValue(BANKS)
  })

  it('returns to the bank-manage imports tab', async () => {
    const wrapper = await mountView()

    const back = wrapper.find('[data-testid="page-back"]')
    expect(back.exists()).toBe(true)
    expect(back.text()).toContain(t('ep.imports.back_to_imports'))

    await back.trigger('click')
    expect(push).toHaveBeenCalledWith({
      name: 'bank-manage',
      params: { bankId: 'b1' },
      query: { tab: 'imports' },
    })

    unmount(wrapper)
  })

  it('sends the post-import navigation to the bank-manage imports tab', async () => {
    previewImport.mockResolvedValue({ question_count: 0, duplicates: [] })
    uploadImport.mockResolvedValue({ job_id: 'job-2', imported_count: 1 })
    const wrapper = await mountView()

    await chooseFile(wrapper, markdownFile())
    await wrapper.find('.import-actions .btn-primary').trigger('click')
    await flush()
    await wrapper.find('.import-actions .btn-primary').trigger('click')
    await flush()

    const openBank = wrapper.find('[data-testid="import-result"] .btn-primary')
    expect(openBank.exists()).toBe(true)
    await openBank.trigger('click')

    expect(push).toHaveBeenCalledWith({
      name: 'bank-manage',
      params: { bankId: 'b1' },
      query: { tab: 'imports' },
    })

    unmount(wrapper)
  })
})

describe('ImportView stepper numbering', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    route.query = { bankId: 'b1' }
    listBanks.mockResolvedValue(BANKS)
  })

  it('marks a spreadsheet preview as step 02', async () => {
    previewFileImport.mockResolvedValue({
      accepted: true,
      headers: ['Stem', 'Answer'],
      preview_rows: [],
      missing: [],
      question_count: 1,
      mapping: { stem: 0, answer: 1 },
    })
    const wrapper = await mountView()

    await chooseFile(wrapper, spreadsheetFile())
    await wrapper.find('.import-actions .btn-primary').trigger('click')
    await flush()

    const stepNumbers = wrapper.findAll('.step-no').map(el => el.text())
    expect(stepNumbers).toEqual(['01', '02'])
    expect(wrapper.findAll('li.import-step')[1].attributes('aria-current')).toBe('step')
    expect(wrapper.find('.import-progress').attributes('aria-valuenow')).toBe('2')

    unmount(wrapper)
  })

  it('keeps text correction at 03 and the result at 04', async () => {
    previewImport.mockResolvedValue({ question_count: 1, duplicates: [] })
    uploadImport.mockResolvedValue({ job_id: 'job-3', imported_count: 1 })
    const wrapper = await mountView()

    await chooseFile(wrapper, markdownFile())
    await wrapper.find('.import-actions .btn-primary').trigger('click')
    await flush()

    expect(wrapper.findAll('.step-no').map(el => el.text())).toEqual(['01', '03'])
    expect(wrapper.findAll('li.import-step')[2].attributes('aria-current')).toBe('step')
    expect(wrapper.find('.import-progress').attributes('aria-valuenow')).toBe('3')

    await wrapper.find('.import-actions .btn-primary').trigger('click')
    await flush()

    expect(wrapper.findAll('.step-no').map(el => el.text())).toEqual(['01', '04'])
    expect(wrapper.findAll('li.import-step')[3].attributes('aria-current')).toBe('step')
    expect(wrapper.find('.import-progress').attributes('aria-valuenow')).toBe('4')

    unmount(wrapper)
  })

  it('labels step 01 with what it is waiting for instead of claiming to work', async () => {
    previewImport.mockResolvedValue({ question_count: 0, duplicates: [] })
    uploadImport.mockResolvedValue({ job_id: 'job-4', imported_count: 1 })
    const wrapper = await mountView()

    const sourceState = () => wrapper.findAll('li.import-step')[0].find('.step-state').text()

    // No file chosen yet: waiting for a file, not working.
    expect(sourceState()).toBe(t('ep.imports.choose'))
    expect(sourceState()).not.toBe(t('ep.imports.uploading'))

    await chooseFile(wrapper, markdownFile())
    // File and bank chosen: the next action is the preview.
    expect(sourceState()).toBe(t('ep.imports.submit_preview'))

    await wrapper.find('.import-actions .btn-primary').trigger('click')
    await flush()

    // Steps 01 is done, step 03 awaits confirmation, and nothing claims to be
    // working while the user is only reviewing the preview.
    expect(sourceState()).toBe(t('ep.common.done'))
    const states = wrapper.findAll('li.import-step').map(el => el.find('.step-state').text())
    expect(states[2]).toBe(t('ep.imports.submit_confirm'))
    expect(states).not.toContain(t('ep.imports.uploading'))

    await wrapper.find('.import-actions .btn-primary').trigger('click')
    await flush()

    // The result step is complete, not perpetually working.
    const resultState = wrapper.findAll('li.import-step')[3].find('.step-state').text()
    expect(resultState).toBe(t('ep.imports.result_title'))
    expect(resultState).not.toBe(t('ep.imports.uploading'))

    unmount(wrapper)
  })

  it('labels the mapping step as awaiting import while the user edits fields', async () => {
    let resolvePreview
    previewFileImport.mockImplementation(() => new Promise(resolve => { resolvePreview = resolve }))
    const wrapper = await mountView()

    await chooseFile(wrapper, spreadsheetFile())
    await wrapper.find('.import-actions .btn-primary').trigger('click')
    await flush()

    // While the preview request runs, the source step is the one working.
    expect(wrapper.findAll('li.import-step')[0].find('.step-state').text()).toBe(t('ep.imports.uploading'))

    resolvePreview({
      accepted: true,
      headers: ['Stem', 'Answer'],
      preview_rows: [],
      missing: [],
      question_count: 1,
      mapping: { stem: 0, answer: 1 },
    })
    await flush()

    // The mapping step now waits for the import action, it is not working.
    const mappingState = wrapper.findAll('li.import-step')[1].find('.step-state').text()
    expect(mappingState).toBe(t('ep.imports.submit_import'))
    expect(mappingState).not.toBe(t('ep.imports.uploading'))

    unmount(wrapper)
  })
})
