import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import NotesView from '../../src/views/NotesView.vue'

vi.mock('../../src/api/assets', () => ({
  listAssets: vi.fn(),
  createAsset: vi.fn(),
  uploadAssetFile: vi.fn(),
  updateAsset: vi.fn(),
  deleteAsset: vi.fn(),
  fetchAssetBlob: vi.fn(),
}))

import { listAssets, updateAsset, fetchAssetBlob } from '../../src/api/assets'

const noteAsset = {
  id: 'a1',
  asset_type: 'NOTE',
  content: '原始笔记内容',
  file_name: null,
  created_at: '2026-11-11T08:00:00Z',
}

const fileAsset = {
  id: 'a2',
  asset_type: 'SUMMARY',
  content: 'PDF 提取出的文本',
  file_name: '复习资料.pdf',
  mime_type: 'application/pdf',
  created_at: '2026-11-11T09:00:00Z',
}

async function flush() {
  await new Promise(resolve => setTimeout(resolve, 0))
}

describe('NotesView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listAssets.mockResolvedValue([noteAsset, fileAsset])
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:mock-url')
    globalThis.URL.revokeObjectURL = vi.fn()
  })

  it('edits and saves the selected note', async () => {
    updateAsset.mockResolvedValue({ ...noteAsset, content: '更新后的笔记内容' })

    const wrapper = mount(NotesView, { props: { token: 't1' } })
    await flush()

    expect(listAssets).toHaveBeenCalledWith('t1')
    await wrapper.find('.note-edit').trigger('click')

    const textarea = wrapper.find('.reader-edit-input')
    expect(textarea.exists()).toBe(true)
    await textarea.setValue('更新后的笔记内容')
    await wrapper.find('.reader-edit-actions .btn-primary').trigger('click')
    await flush()

    expect(updateAsset).toHaveBeenCalledWith('t1', 'a1', { content: '更新后的笔记内容' })
    expect(wrapper.find('.reader-edit-input').exists()).toBe(false)
    expect(wrapper.find('.reader-body').text()).toContain('更新后的笔记内容')
  })

  it('previews and downloads a stored reference file with auth-backed blobs', async () => {
    const fakeWindow = { location: { href: '' }, close: vi.fn() }
    const openSpy = vi.spyOn(window, 'open').mockReturnValue(fakeWindow)
    const blob = new Blob(['%PDF-1.4'], { type: 'application/pdf' })
    fetchAssetBlob.mockResolvedValue({ blob, mimeType: 'application/pdf' })

    const wrapper = mount(NotesView, { props: { token: 't1' } })
    await flush()
    await wrapper.findAll('.library-row')[1].trigger('click')

    await wrapper.find('.file-preview').trigger('click')
    await flush()
    expect(fetchAssetBlob).toHaveBeenCalledWith('t1', 'a2')
    expect(openSpy).toHaveBeenCalled()
    expect(fakeWindow.location.href).toBe('blob:mock-url')

    await wrapper.find('.file-download').trigger('click')
    await flush()
    expect(fetchAssetBlob).toHaveBeenCalledWith('t1', 'a2', { download: true })
    openSpy.mockRestore()
  })

  it('shows an error and closes the preview window when the file is unavailable', async () => {
    const fakeWindow = { location: { href: '' }, close: vi.fn() }
    vi.spyOn(window, 'open').mockReturnValue(fakeWindow)
    fetchAssetBlob.mockRejectedValue(new Error('资料文件不存在'))

    const wrapper = mount(NotesView, { props: { token: 't1' } })
    await flush()
    await wrapper.findAll('.library-row')[1].trigger('click')
    await wrapper.find('.file-preview').trigger('click')
    await flush()

    expect(fakeWindow.close).toHaveBeenCalled()
    expect(wrapper.find('.notice.bad').exists()).toBe(true)
    expect(wrapper.find('.notes-reader .notice.bad').exists()).toBe(true)
    expect(wrapper.text()).toContain('资料文件不存在')
  })

  it('asks before discarding an unsaved note when the reader closes', async () => {
    const wrapper = mount(NotesView, { props: { token: 't1' } })
    await flush()

    await wrapper.find('.library-row').trigger('click')
    await wrapper.find('.note-edit').trigger('click')
    await wrapper.find('.reader-edit-input').setValue('未保存的修改')

    await wrapper.find('.notes-reader-close').trigger('click')
    expect(wrapper.find('[data-testid="unsaved-edit-dialog"]').exists()).toBe(true)
    expect(wrapper.find('.notes-reader.is-open').exists()).toBe(true)
    expect(updateAsset).not.toHaveBeenCalled()

    const actions = wrapper.findAll('[data-testid="unsaved-edit-dialog"] .bank-actions button')
    await actions[1].trigger('click')
    expect(wrapper.find('[data-testid="unsaved-edit-dialog"]').exists()).toBe(false)
    expect(wrapper.find('.notes-reader.is-open').exists()).toBe(false)
    expect(updateAsset).not.toHaveBeenCalled()
  })

  it('keeps editing when the unsaved-change prompt is cancelled', async () => {
    const wrapper = mount(NotesView, { props: { token: 't1' } })
    await flush()

    await wrapper.find('.library-row').trigger('click')
    await wrapper.find('.note-edit').trigger('click')
    await wrapper.find('.reader-edit-input').setValue('未保存的修改')
    await wrapper.find('.notes-reader-close').trigger('click')

    const actions = wrapper.findAll('[data-testid="unsaved-edit-dialog"] .bank-actions button')
    await actions[0].trigger('click')
    expect(wrapper.find('[data-testid="unsaved-edit-dialog"]').exists()).toBe(false)
    expect(wrapper.find('.notes-reader.is-open').exists()).toBe(true)
    expect(wrapper.find('.reader-edit-input').element.value).toBe('未保存的修改')
  })

  it('saves before switching to another note', async () => {
    updateAsset.mockResolvedValue({ ...noteAsset, content: '切换前保存的内容' })

    const wrapper = mount(NotesView, { props: { token: 't1' } })
    await flush()

    await wrapper.findAll('.library-row')[0].trigger('click')
    await wrapper.find('.note-edit').trigger('click')
    await wrapper.find('.reader-edit-input').setValue('切换前保存的内容')
    await wrapper.findAll('.library-row')[1].trigger('click')

    expect(wrapper.find('[data-testid="unsaved-edit-dialog"]').exists()).toBe(true)
    const actions = wrapper.findAll('[data-testid="unsaved-edit-dialog"] .bank-actions button')
    await actions[2].trigger('click')
    await flush()

    expect(updateAsset).toHaveBeenCalledWith('t1', 'a1', { content: '切换前保存的内容' })
    expect(wrapper.find('[data-testid="unsaved-edit-dialog"]').exists()).toBe(false)
    expect(wrapper.find('.notes-reader-title').text()).toContain('PDF 提取出的文本')
    expect(wrapper.find('.reader-edit-input').exists()).toBe(false)
  })
})
