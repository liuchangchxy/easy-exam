import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import BlueprintModal from '../../src/components/BlueprintModal.vue'

const api = vi.hoisted(() => ({
  getBlueprint: vi.fn(),
  saveBlueprint: vi.fn(),
  listProfiles: vi.fn(),
  createProfile: vi.fn(),
}))

vi.mock('../../src/api/exams', () => ({
  listProfiles: api.listProfiles,
  getBlueprint: api.getBlueprint,
  saveBlueprint: api.saveBlueprint,
  createProfile: api.createProfile,
}))

const storedBlueprint = {
  id: 'bp-1',
  profile_id: 'p-1',
  version_number: 3,
  blueprint: {
    negative_mark: 0.5,
    allow_fallback: false,
    custom_note: '保留我',
    sections: [
      { name: '自定义单选', type: 'SINGLE', count: 10, difficulty: 2, chapter_id: 'chapter-1', tags: 'tag-1', weight: 0.4 },
      { name: '自定义多选', type: 'MULTI', count: 5, difficulty: 4, chapter_id: '', tags: '' },
    ],
  },
}

function mountModal() {
  return mount(BlueprintModal, { props: { token: 'test-token' } })
}

async function switchMode(wrapper, index) {
  await wrapper.findAll('.seg')[index].trigger('click')
  await flushPromises()
}

describe('BlueprintModal simple/advanced conversion', () => {
  beforeEach(() => {
    api.listProfiles.mockResolvedValue([{ id: 'p-1', name: '收口试卷', latest_blueprint: storedBlueprint }])
    api.getBlueprint.mockResolvedValue(storedBlueprint)
    api.saveBlueprint.mockResolvedValue({ id: 'bp-2' })
    api.createProfile.mockResolvedValue({ id: 'p-2', name: '新试卷' })
    vi.stubGlobal('alert', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  it('reads the nested API shape and preserves custom names, filters, difficulty and meta', async () => {
    const wrapper = mountModal()
    await flushPromises()

    // Advanced view must show the stored custom sections, not an empty fallback.
    await switchMode(wrapper, 1)
    expect(wrapper.findAll('.section-name').map(input => input.element.value)).toEqual(['自定义单选', '自定义多选'])
    expect(wrapper.findAll('.section-filter input')[0].element.value).toBe('chapter-1')
    expect(wrapper.findAll('.section-filter input')[1].element.value).toBe('tag-1')

    // A simple-mode count edit must not rebuild the untouched sections.
    await switchMode(wrapper, 0)
    const simpleInputs = wrapper.findAll('.simple-grid input')
    expect(simpleInputs[0].element.value).toBe('10')
    expect(simpleInputs[1].element.value).toBe('5')
    await simpleInputs[0].setValue(12)
    await flushPromises()

    await switchMode(wrapper, 1)
    expect(wrapper.findAll('.section-name').map(input => input.element.value)).toEqual(['自定义单选', '自定义多选'])
    expect(wrapper.findAll('.section-count').map(input => input.element.value)).toEqual(['12', '5'])
    expect(wrapper.findAll('.section-diff').map(select => select.element.value)).toEqual(['2', '4'])
    expect(wrapper.findAll('.section-filter input')[0].element.value).toBe('chapter-1')

    await wrapper.find('.editor-actions .btn-primary').trigger('click')
    await flushPromises()
    expect(api.saveBlueprint).toHaveBeenCalledTimes(1)
    const payload = api.saveBlueprint.mock.calls[0][2]
    expect(payload.negative_mark).toBe(0.5)
    expect(payload.allow_fallback).toBe(false)
    expect(payload.custom_note).toBe('保留我')
    expect(payload.sections).toHaveLength(2)
    expect(payload.sections[0]).toMatchObject({
      name: '自定义单选',
      type: 'SINGLE',
      count: 12,
      difficulty: 2,
      chapter_id: 'chapter-1',
      tags: 'tag-1',
      weight: 0.4,
    })
    expect(payload.sections[1]).toMatchObject({ name: '自定义多选', count: 5, difficulty: 4 })
  })

  it('shows a load failure instead of silently editing an empty blueprint', async () => {
    api.getBlueprint.mockRejectedValue({ status: 500, detail: 'boom', message: 'boom' })
    const wrapper = mountModal()
    await flushPromises()

    expect(wrapper.find('.blueprint-error').exists()).toBe(true)
    expect(wrapper.find('.blueprint-error').text()).toContain('boom')
    expect(wrapper.find('.editor-actions .btn-primary').attributes('disabled')).toBeDefined()
  })

  it('treats a missing blueprint as a new empty configuration', async () => {
    api.getBlueprint.mockRejectedValue({ status: 404, detail: 'exam blueprint not found', message: 'exam blueprint not found' })
    const wrapper = mountModal()
    await flushPromises()

    expect(wrapper.find('.blueprint-error').exists()).toBe(false)
    expect(wrapper.find('.editor-actions .btn-primary').attributes('disabled')).toBeUndefined()
    expect(wrapper.findAll('.simple-grid input')[0].element.value).toBe('0')
  })
})
