<template>
  <div class="import-page">
    <button
      v-if="backBankId"
      type="button"
      class="page-back"
      data-testid="page-back"
      :aria-label="backLabel"
      :title="backLabel"
      @click="backToBank"
    >
      <LinearIcon name="arrow-left" :size="15" />
      <span>{{ backLabel }}</span>
    </button>

    <div class="page-head">
      <div class="page-head-main">
        <div class="page-eyebrow">
          <button type="button" class="link-btn" @click="$router.push('/banks')">{{ t('ep.banks.title') }}</button>
          <span aria-hidden="true">/</span>
        </div>
        <h1 class="page-title">{{ t('ep.imports.title') }}</h1>
        <p class="page-sub">{{ t('ep.imports.sub') }}</p>
      </div>
    </div>

    <ol class="import-steps" :aria-label="t('ep.imports.title')">
      <li
        v-for="(step, idx) in steps"
        :key="step.key"
        class="import-step"
        :class="{ 'is-active': stepNo === idx + 1, 'is-done': stepNo > idx + 1 }"
        :data-step-state="stepState(idx + 1)"
        :aria-current="stepNo === idx + 1 ? 'step' : undefined"
      >
        <span class="step-idx mono">{{ String(idx + 1).padStart(2, '0') }}</span>
        <span class="step-label">{{ step.label }}</span>
        <span class="step-state">{{ stepStateLabel(idx + 1) }}</span>
      </li>
    </ol>
    <div
      class="import-progress"
      role="progressbar"
      :aria-label="t('ep.imports.title')"
      :aria-valuemin="1"
      :aria-valuemax="4"
      :aria-valuenow="stepNo"
    >
      <i :style="{ width: `${stepPercent}%` }"></i>
    </div>

    <p v-if="draftSaveError" class="notice bad import-draft-error" role="status" data-testid="draft-save-error">
      <LinearIcon name="alert" :size="15" />
      <span>{{ t('ep.imports.draft_save_failed', { message: draftSaveError }) }}</span>
    </p>

    <section v-if="openDrafts.length" class="import-resume" data-testid="import-resume">
      <div class="import-resume-head">
        <span class="rule-label">{{ t('ep.imports.resume_title') }}</span>
        <span class="mono small dim">{{ t('ep.imports.resume_count', { count: openDrafts.length }) }}</span>
      </div>
      <p class="hint">{{ t('ep.imports.resume_hint') }}</p>
      <div class="list import-resume-list">
        <div v-for="draft in openDrafts" :key="draft.id" class="list-row import-resume-row" data-testid="draft-row">
          <span class="list-main">
            <span class="qrow-stem">{{ draft.filename || t('ep.imports.untitled') }}</span>
            <span class="hint">
              {{ sourceKindLabel(draft.source_kind) }}<template v-if="draft.updated_at"> · {{ formatDateTime(draft.updated_at, locale) }}</template>
            </span>
          </span>
          <button type="button" class="btn btn-sm" data-testid="draft-resume" @click="resumeDraftFromBanner(draft)">
            {{ t('ep.imports.resume_continue') }}
          </button>
          <button type="button" class="btn btn-sm btn-quiet" data-testid="draft-delete" @click="removeDraft(draft)">
            {{ t('ep.imports.resume_delete') }}
          </button>
        </div>
      </div>
      <p v-if="draftListError" class="hint bad-text" role="status">{{ t('ep.imports.draft_load_failed', { message: draftListError }) }}</p>
    </section>

    <section v-if="previewing || precheckPanel" class="import-precheck-panel" aria-live="polite">
      <div class="import-precheck-panel-head">
        <span class="rule-label">{{ t('ep.imports.submit_preview') }}</span>
        <span class="tag" :class="precheckPanel && precheckPanel.accepted ? 'ok' : 'warn'">
          {{ previewing && !precheckPanel ? t('ep.imports.uploading') : precheckPanel?.status }}
        </span>
      </div>
      <div v-if="precheckPanel" class="import-precheck-grid">
        <div class="import-precheck-cell">
          <b>{{ precheckPanel.count }}</b>
          <span>{{ t('ep.imports.rows', { count: precheckPanel.count }) }}</span>
        </div>
        <div class="import-precheck-cell">
          <b :class="{ 'is-warn': precheckPanel.duplicates > 0 }">{{ precheckPanel.duplicates }}</b>
          <span>{{ t('ep.imports.step_duplicates') }}</span>
        </div>
        <div class="import-precheck-cell">
          <b :class="{ 'is-warn': precheckPanel.attention > 0 }">{{ precheckPanel.attention }}</b>
          <span>{{ t('ep.imports.pdf_low') }}</span>
        </div>
      </div>
      <p v-else class="import-precheck-loading">{{ t('ep.imports.uploading') }}</p>
    </section>

    <div class="import-layout">
      <div class="import-main">
        <form class="import-form" @submit.prevent="onFormSubmit">
          <!-- The target bank stays reachable on every step: it is the context
               of the whole wizard, not a field of the file picker. -->
          <div class="import-target" data-step="target">
            <div class="field" style="margin-bottom: 18px">
              <label class="label" for="import-bank">{{ t('ep.imports.bank') }}</label>
              <select
                id="import-bank"
                v-model="bankId"
                class="select"
                required
                :disabled="bankBusy"
                :title="bankBusy ? t('ep.imports.bank_locked_busy') : undefined"
              >
                <option value="" disabled>{{ t('ep.imports.bank_placeholder') }}</option>
                <option v-for="bank in banks" :key="bank.id" :value="bank.id">{{ bank.name }} · {{ t('ep.banks.questions', { count: bank.question_count || 0 }) }}</option>
              </select>
            </div>

            <div v-if="bankLoadFailed" class="notice bad bank-load-error" role="alert" style="margin-bottom: 16px">
              <LinearIcon name="alert" :size="15" />
              <span>{{ t('ep.imports.bank_load_failed') }}</span>
              <button type="button" class="btn btn-sm" :disabled="banksLoading" @click="loadBanks">{{ t('ep.common.retry') }}</button>
            </div>

            <div v-if="bankId && !canImport" class="notice warn" style="margin-bottom: 16px">
              <LinearIcon name="lock" :size="15" />
              <span>{{ t('ep.imports.readonly_bank') }}</span>
            </div>
          </div>

          <!-- Completed source step, kept as a compact receipt while later steps run. -->
          <section v-if="stepNo > 1" class="step-block step-summary" data-step="source-summary">
            <div class="step-head">
              <span class="step-no mono">01</span>
              <div>
                <div class="step-title">{{ t('ep.imports.step_source') }}</div>
                <div class="step-sub">{{ sourceSummary }}</div>
              </div>
              <button type="button" class="btn btn-sm btn-quiet" @click="goStep(1)">
                {{ t('ep.imports.change_source') }}
              </button>
            </div>
          </section>

          <!-- Step 1: source -->
          <section v-if="stepNo === 1" class="step-block" data-step="source">
            <div class="step-head">
              <span class="step-no mono">01</span>
              <div>
                <div class="step-title">{{ t('ep.imports.step_source') }}</div>
                <div class="step-sub">{{ t('ep.imports.preview_hint') }}</div>
              </div>
            </div>

            <div class="source-modes">
              <button
                type="button"
                class="btn btn-sm"
                :class="{ 'is-active': sourceMode === 'file' }"
                data-testid="source-mode-file"
                @click="setSourceMode('file')"
              >
                {{ t('ep.imports.source_file') }}
              </button>
              <button
                type="button"
                class="btn btn-sm"
                :class="{ 'is-active': sourceMode === 'paste' }"
                data-testid="source-mode-paste"
                @click="setSourceMode('paste')"
              >
                {{ t('ep.imports.source_paste') }}
              </button>
            </div>

            <template v-if="sourceMode === 'file'">
              <div
                class="file-drop"
              :class="{ 'is-dragging': isDragging, 'has-file': Boolean(file) }"
              @click="onDropZoneClick"
              @dragenter.prevent="isDragging = true"
              @dragover.prevent="isDragging = true"
              @dragleave="onDragLeave"
              @drop.prevent="onDropFile"
            >
              <template v-if="isDragging">
                <LinearIcon name="upload" :size="22" />
                <strong>{{ t('ep.imports.release') }}</strong>
              </template>
              <template v-else-if="file">
                <span class="file-icon"><LinearIcon name="file" :size="20" /></span>
                <span class="file-main">
                  <span class="file-name">{{ file.name }}</span>
                  <span class="file-meta">{{ t('ep.imports.size', { size: (file.size / 1024).toFixed(1) }) }}</span>
                </span>
                <button type="button" class="btn btn-sm" @click.stop="triggerFileInput">{{ t('ep.imports.change') }}</button>
              </template>
              <template v-else>
                <span class="file-icon"><LinearIcon name="inbox" :size="20" /></span>
                <span class="file-main">
                  <span class="file-name">{{ t('ep.imports.drop') }}</span>
                  <span class="file-meta">{{ t('ep.imports.drop_hint') }}</span>
                </span>
                <button type="button" class="btn btn-sm" @click.stop="triggerFileInput">{{ t('ep.imports.choose') }}</button>
              </template>
              <input
                ref="fileInputRef"
                type="file"
                accept=".xlsx,.csv,.json,.txt,.md,.markdown,.pdf"
                :required="!file"
                class="file-input-hidden"
                @change="selectFile"
              />
            </div>

            <div class="file-formats">
              <span class="tag mono">.xlsx</span>
              <span class="tag mono">.csv</span>
              <span class="tag mono">.json</span>
              <span class="tag mono">.md / .txt</span>
              <span class="tag mono">.pdf</span>
            </div>
            </template>

            <template v-else>
              <p class="hint" style="margin-bottom: 10px">{{ t('ep.imports.paste_hint') }}</p>
              <label class="field" for="import-paste">
                <span class="label">{{ t('ep.imports.source_paste') }}</span>
                <textarea
                  id="import-paste"
                  v-model="pastedText"
                  class="textarea"
                  rows="10"
                  :placeholder="t('ep.imports.paste_placeholder')"
                ></textarea>
              </label>
            </template>

            <div class="import-actions">
              <button
                type="button"
                class="btn btn-primary"
                :disabled="Boolean(nextDisabledReason)"
                :title="nextDisabledReason ? t(nextDisabledReason) : undefined"
                @click="nextFromSource"
              >
                {{ loading || previewing ? t('ep.imports.uploading') : t('ep.imports.next') }}
              </button>
            </div>
          </section>

          <!-- Step 2: check (field mapping / PDF correction / text precheck) -->
          <section v-if="stepNo === 2" class="step-block" data-step="check">
            <!-- Spreadsheet field mapping -->
            <template v-if="mode === 'spreadsheet' && spreadsheetPreview">
              <div class="step-head">
                <span class="step-no mono">02</span>
                <div>
                  <div class="step-title">{{ t('ep.imports.fields_title') }}</div>
                  <div class="step-sub">{{ t('ep.imports.fields_hint') }}</div>
                </div>
              </div>

              <div class="mapping-grid">
                <label class="field">
                  <span class="label">{{ t('ep.imports.col_stem') }}</span>
                  <select v-model.number="currentMapping.stem" class="select">
                    <option :value="null">{{ t('ep.imports.none') }}</option>
                    <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
                  </select>
                </label>
                <label class="field">
                  <span class="label">{{ t('ep.imports.col_answer') }}</span>
                  <select v-model.number="currentMapping.answer" class="select">
                    <option :value="null">{{ t('ep.imports.none') }}</option>
                    <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
                  </select>
                </label>
                <label class="field">
                  <span class="label">{{ t('ep.imports.col_type') }}</span>
                  <select v-model.number="currentMapping.type" class="select">
                    <option :value="null">{{ t('ep.imports.auto') }}</option>
                    <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
                  </select>
                </label>
                <label class="field">
                  <span class="label">{{ t('ep.imports.col_explanation') }}</span>
                  <select v-model.number="currentMapping.explanation" class="select">
                    <option :value="null">{{ t('ep.imports.none') }}</option>
                    <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
                  </select>
                </label>
                <label class="field">
                  <span class="label">{{ t('ep.imports.col_difficulty') }}</span>
                  <select v-model.number="currentMapping.difficulty" class="select">
                    <option :value="null">{{ t('ep.imports.none') }}</option>
                    <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
                  </select>
                </label>
                <label class="field">
                  <span class="label">{{ t('ep.imports.col_tags') }}</span>
                  <select v-model.number="currentMapping.tags" class="select">
                    <option :value="null">{{ t('ep.imports.none') }}</option>
                    <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
                  </select>
                </label>
                <label class="field">
                  <span class="label">{{ t('ep.imports.col_options') }}</span>
                  <select v-model.number="currentMapping.combined_options" class="select">
                    <option :value="null">{{ t('ep.imports.none') }}</option>
                    <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
                  </select>
                </label>
                <label v-if="currentMapping.combined_options !== null" class="field">
                  <span class="label">{{ t('ep.imports.delimiter') }}</span>
                  <select v-model="currentMapping.options_delimiter" class="select">
                    <option value="">{{ t('ep.imports.auto') }}</option>
                    <option value="prefix">{{ t('ep.imports.delimiter_prefix') }}</option>
                    <option value=";">{{ t('ep.imports.delimiter_semicolon') }}</option>
                    <option value="；">{{ t('ep.imports.delimiter_cn_semicolon') }}</option>
                    <option value="\n">{{ t('ep.imports.delimiter_newline') }}</option>
                    <option value="|">{{ t('ep.imports.delimiter_pipe') }}</option>
                    <option value="、">{{ t('ep.imports.delimiter_dunhao') }}</option>
                  </select>
                </label>
                <label v-for="(letter, slotIdx) in optionLetters" :key="letter" class="field">
                  <span class="label">{{ t('ep.imports.col_option', { letter }) }}</span>
                  <select :value="getOptionCol(slotIdx)" class="select" @change="setOptionCol(slotIdx, $event.target.value)">
                    <option value="">{{ t('ep.imports.none') }}</option>
                    <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
                  </select>
                </label>
              </div>

              <div v-if="spreadsheetPreview.missing?.length" class="notice warn" style="margin-top: 14px">
                <LinearIcon name="alert" :size="15" />
                <span>{{ t('ep.imports.missing_fields') }}{{ spreadsheetPreview.missing.join(', ') }}</span>
              </div>

              <div v-if="spreadsheetPreview.preview_rows?.length" class="sample-block">
                <div class="rule-label">{{ t('ep.imports.sample') }} · {{ t('ep.imports.rows', { count: spreadsheetPreview.preview_rows.length }) }}</div>
                <div class="sample-scroll">
                  <table class="sample-table">
                    <thead>
                      <tr><th v-for="(h, idx) in spreadsheetPreview.headers" :key="idx">{{ h }}</th></tr>
                    </thead>
                    <tbody>
                      <tr v-for="(row, rIdx) in spreadsheetPreview.preview_rows" :key="rIdx">
                        <td v-for="(cell, cIdx) in row" :key="cIdx">{{ cell }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </template>

            <!-- PDF correction draft -->
            <template v-else-if="mode === 'pdf' && pdfPreview">
              <div class="step-head">
                <span class="step-no mono">02</span>
                <div>
                  <div class="step-title">{{ t('ep.imports.pdf_title') }}</div>
                  <div class="step-sub">{{ t('ep.imports.pdf_hint') }}</div>
                </div>
                <span class="tag" :class="pdfPreview.confidence === 'HIGH' ? 'ok' : 'warn'">
                  {{ pdfPreview.confidence === 'HIGH' ? t('ep.imports.pdf_high') : t('ep.imports.pdf_low') }}
                </span>
              </div>

              <div v-if="pdfCandidates.length" class="pdf-list">
                <article v-for="(cand, cIdx) in pdfCandidates" :key="cIdx" class="pdf-card">
                  <div class="pdf-card-head">
                    <span class="mono small">{{ t('ep.imports.candidate_no', { index: cIdx + 1 }) }}</span>
                    <span class="pdf-card-actions">
                      <button v-if="cIdx > 0" type="button" class="btn btn-sm btn-quiet" @click="mergeWithPrev(cIdx)">{{ t('ep.imports.merge_prev') }}</button>
                      <button type="button" class="btn btn-sm btn-quiet" @click="splitCandidate(cIdx)">{{ t('ep.imports.split') }}</button>
                      <button type="button" class="btn btn-sm btn-quiet" @click="removeCandidate(cIdx)">{{ t('ep.imports.remove') }}</button>
                    </span>
                  </div>

                  <div v-if="cand.is_uncertain" class="notice warn" style="margin-bottom: 12px">
                    <LinearIcon name="alert" :size="14" />
                    <span>{{ t('ep.imports.uncertain', { reason: cand.uncertain_reason }) }}</span>
                  </div>

                  <div class="pdf-grid">
                    <label class="field">
                      <span class="label">{{ t('ep.imports.type') }}</span>
                      <select v-model="cand.type" class="select">
                        <option value="SINGLE">{{ t('ep.question_types.single') }}</option>
                        <option value="MULTI">{{ t('ep.question_types.multi') }}</option>
                        <option value="JUDGE">{{ t('ep.question_types.judge') }}</option>
                        <option value="QA">{{ t('ep.question_types.essay') }}</option>
                      </select>
                    </label>
                    <label class="field">
                      <span class="label">{{ t('ep.imports.answer') }}</span>
                      <input v-model="cand.answer" class="input" :placeholder="t('ep.imports.answer_placeholder')" />
                    </label>
                  </div>

                  <label class="field" style="margin-top: 12px">
                    <span class="label">{{ t('ep.imports.stem') }}</span>
                    <textarea v-model="cand.stem" class="textarea" rows="3"></textarea>
                  </label>

                  <div v-if="cand.type === 'SINGLE' || cand.type === 'MULTI'" class="pdf-options">
                    <div class="pdf-options-head">
                      <span class="label">{{ t('ep.imports.options') }}</span>
                      <button type="button" class="btn btn-sm btn-quiet" @click="addCandidateOption(cand)">{{ t('ep.imports.add_option') }}</button>
                    </div>
                    <div v-for="(opt, optIdx) in cand.options" :key="optIdx" class="pdf-option-row">
                      <input v-model="opt.key" class="input opt-key" placeholder="A" />
                      <input v-model="opt.content" class="input" :placeholder="t('ep.imports.option_text')" />
                      <button type="button" class="icon-btn" :aria-label="t('ep.imports.remove')" @click="cand.options.splice(optIdx, 1)">
                        <LinearIcon name="x" :size="14" />
                      </button>
                    </div>
                  </div>

                  <label class="field" style="margin-top: 12px">
                    <span class="label">{{ t('ep.imports.explanation') }}</span>
                    <input v-model="cand.explanation" class="input" :placeholder="t('ep.imports.explanation_placeholder')" />
                  </label>
                </article>
              </div>
              <div v-else class="empty" style="padding: 24px 0">
                <div class="empty-desc">{{ t('ep.imports.no_candidates') }}</div>
              </div>
            </template>

            <!-- Text precheck -->
            <template v-else-if="mode === 'text' && textPreview">
              <div class="step-head">
                <span class="step-no mono">02</span>
                <div>
                  <div class="step-title">{{ t('ep.imports.text_precheck_title') }}</div>
                  <div class="step-sub">{{ t('ep.imports.text_precheck_hint') }}</div>
                </div>
                <span class="tag" :class="textPreview.accepted === false ? 'warn' : 'ok'">
                  {{ textPreview.accepted === false ? t('ep.imports.pdf_low') : t('ep.imports.pdf_high') }}
                </span>
              </div>
              <div class="import-precheck-grid">
                <div class="import-precheck-cell">
                  <b>{{ Number(textPreview.question_count || 0) }}</b>
                  <span>{{ t('ep.imports.rows', { count: Number(textPreview.question_count || 0) }) }}</span>
                </div>
                <div class="import-precheck-cell">
                  <b :class="{ 'is-warn': duplicateList.length > 0 }">{{ duplicateList.length }}</b>
                  <span>{{ t('ep.imports.step_duplicates') }}</span>
                </div>
              </div>

              <div v-if="duplicateList.length" class="pdf-duplicates">
                <div class="notice warn">
                  <LinearIcon name="alert" :size="15" />
                  <span>{{ t('ep.imports.dup_hint', { count: duplicateList.length }) }}</span>
                </div>
                <div class="list dup-list">
                  <div v-for="(dup, idx) in duplicateList.slice(0, 8)" :key="idx" class="list-row">
                    <span class="mono small dim">{{ String(idx + 1).padStart(2, '0') }}</span>
                    <span class="list-main">
                      <span class="qrow-stem">{{ dup.stem || dup.question_stem || dup.id }}</span>
                    </span>
                  </div>
                  <details v-if="duplicateList.length > 8" class="dup-more">
                    <summary class="dup-more-summary">{{ t('ep.common.more_count', { count: duplicateList.length - 8 }) }}</summary>
                    <div v-for="(dup, idx) in duplicateList.slice(8)" :key="`more-${idx}`" class="list-row">
                      <span class="mono small dim">{{ String(idx + 9).padStart(2, '0') }}</span>
                      <span class="list-main">
                        <span class="qrow-stem">{{ dup.stem || dup.question_stem || dup.id }}</span>
                      </span>
                    </div>
                  </details>
                </div>
              </div>
              <p v-else class="hint" style="margin-top: 14px">{{ t('ep.imports.no_duplicates') }}</p>
            </template>

            <div v-else class="empty" style="padding: 24px 0">
              <div class="empty-desc">{{ t('ep.imports.resume_need_file') }}</div>
              <div class="empty-actions">
                <button type="button" class="btn btn-sm" @click="triggerResumeFileInput">{{ t('ep.imports.resume_pick_file') }}</button>
              </div>
              <input ref="resumeFileInputRef" type="file" class="file-input-hidden" @change="selectResumeFile" />
            </div>

            <div v-if="needsFile" class="notice warn" style="margin-top: 14px" data-testid="resume-needs-file">
              <LinearIcon name="alert" :size="15" />
              <span>{{ t('ep.imports.resume_need_file') }}</span>
              <button type="button" class="btn btn-sm" @click="triggerResumeFileInput">{{ t('ep.imports.resume_pick_file') }}</button>
              <input ref="resumeFileInputRef" type="file" class="file-input-hidden" @change="selectResumeFile" />
            </div>

            <div class="import-actions">
              <button type="button" class="btn btn-quiet" @click="goStep(1)">{{ t('ep.imports.prev') }}</button>
              <button
                type="button"
                class="btn btn-primary"
                :disabled="Boolean(checkDisabledReason)"
                :title="checkDisabledReason ? t(checkDisabledReason) : undefined"
                @click="nextFromCheck"
              >
                {{ t('ep.imports.next') }}
              </button>
              <button type="button" class="btn btn-quiet" @click="requestDiscard(mode)">{{ t('ep.imports.cancel_preview') }}</button>
            </div>
          </section>

          <!-- Step 3: duplicates -->
          <section v-if="stepNo === 3" class="step-block" data-step="duplicates">
            <div class="step-head">
              <span class="step-no mono">03</span>
              <div>
                <div class="step-title">{{ t('ep.imports.dup_title') }}</div>
                <div class="step-sub">{{ duplicateList.length ? t('ep.imports.dup_hint', { count: duplicateList.length }) : t('ep.imports.no_duplicates') }}</div>
              </div>
            </div>

            <div v-if="duplicateList.length" class="list dup-list">
              <div v-for="(dup, idx) in duplicateList.slice(0, 8)" :key="idx" class="list-row">
                <span class="mono small dim">{{ String(idx + 1).padStart(2, '0') }}</span>
                <span class="list-main">
                  <span class="qrow-stem">{{ dup.stem || dup.question_stem || dup.id }}</span>
                </span>
              </div>
              <details v-if="duplicateList.length > 8" class="dup-more">
                <summary class="dup-more-summary">{{ t('ep.common.more_count', { count: duplicateList.length - 8 }) }}</summary>
                <div v-for="(dup, idx) in duplicateList.slice(8)" :key="`more-${idx}`" class="list-row">
                  <span class="mono small dim">{{ String(idx + 9).padStart(2, '0') }}</span>
                  <span class="list-main">
                    <span class="qrow-stem">{{ dup.stem || dup.question_stem || dup.id }}</span>
                  </span>
                </div>
              </details>
            </div>

            <div class="field" style="margin-top: 16px; max-width: 320px">
              <label class="label" for="import-strategy">{{ t('ep.imports.strategy') }}</label>
              <select id="import-strategy" v-model="currentStrategy" class="select">
                <option value="" disabled>{{ t('ep.imports.strategy_choose') }}</option>
                <option value="skip">{{ t('ep.imports.strategy_skip') }}</option>
                <option value="new">{{ t('ep.imports.strategy_new') }}</option>
                <option value="merge">{{ t('ep.imports.strategy_merge') }}</option>
              </select>
            </div>

            <div class="import-actions">
              <button type="button" class="btn btn-quiet" @click="goStep(2)">{{ t('ep.imports.prev') }}</button>
              <button
                type="button"
                class="btn btn-primary"
                :disabled="Boolean(confirmDisabledReason)"
                :title="confirmDisabledReason ? t(confirmDisabledReason) : undefined"
                @click="confirmImport"
              >
                {{ loading ? t('ep.imports.uploading') : t('ep.imports.submit_confirm') }}
              </button>
            </div>
          </section>

          <!-- Step 4: result / running job -->
          <section
            v-if="stepNo === 4"
            class="step-block result-block"
            aria-live="polite"
            data-testid="import-result"
          >
            <div class="step-head">
              <span class="step-no mono">04</span>
              <div>
                <div class="step-title">
                  <template v-if="result">{{ t('ep.imports.result_title') }}</template>
                  <template v-else-if="jobFailed">{{ t('ep.imports.job_failed') }}</template>
                  <template v-else-if="jobCancelled">{{ t('ep.imports.job_cancelled') }}</template>
                  <template v-else>{{ t('ep.imports.job_title') }}</template>
                </div>
                <div class="step-sub">
                  <template v-if="result">{{ t('ep.imports.result_desc', { count: resultImportedCount }) }}</template>
                  <template v-else-if="jobFailed">{{ t('ep.imports.job_failed_reason', { reason: jobReason }) }}</template>
                  <template v-else-if="jobCancelled">{{ t('ep.imports.job_cancelled') }}</template>
                  <template v-else>{{ t('ep.imports.job_progress', { done: jobDone, total: jobTotal }) }}</template>
                </div>
              </div>
              <span v-if="jobStatusLabel" class="tag" :class="jobStatusClass">{{ jobStatusLabel }}</span>
            </div>

            <template v-if="result">
              <div class="kv">
                <div class="kv-row"><span class="kv-key">{{ t('ep.imports.job') }}</span><span class="kv-val mono">{{ result.job_id }}</span></div>
                <div class="kv-row"><span class="kv-key">{{ t('ep.imports.result_bank') }}</span><span class="kv-val" data-testid="result-bank">{{ resultBank || t('ep.common.none') }}</span></div>
              </div>
              <div
                v-if="resultBankChanged"
                class="notice warn result-bank-changed"
                data-testid="result-bank-changed"
                role="status"
              >
                <LinearIcon name="alert" :size="15" />
                <span>{{ t('ep.imports.result_bank_changed', { bank: resultBank }) }}</span>
                <span class="dim">{{ t('ep.imports.bank') }} {{ bankNameFor(bankId) }}</span>
              </div>
              <div class="import-actions">
                <button type="button" class="btn btn-primary" @click="goBank">{{ t('ep.imports.view_bank') }}</button>
                <button type="button" class="btn" @click="resetImport">{{ t('ep.imports.again') }}</button>
              </div>
            </template>

            <template v-else>
              <div v-if="jobRunning" class="job-progress" data-testid="job-progress">
                <div class="job-bar"><i :style="{ width: `${jobPercent}%` }"></i></div>
                <div class="job-meta mono">{{ t('ep.imports.job_progress', { done: jobDone, total: jobTotal }) }}</div>
                <p class="hint">{{ t('ep.imports.job_left_hint') }}</p>
              </div>
              <div v-else class="notice bad job-failure" data-testid="job-error" role="alert">
                <LinearIcon name="alert" :size="15" />
                <span>{{ jobFailed ? t('ep.imports.job_failed_reason', { reason: jobReason }) : t('ep.imports.job_cancelled') }}</span>
              </div>
              <div class="import-actions">
                <button
                  v-if="jobRunning"
                  type="button"
                  class="btn btn-danger"
                  data-testid="job-cancel"
                  :disabled="jobCancelling"
                  @click="cancelJob"
                >
                  {{ jobCancelling ? t('ep.imports.job_cancelling') : t('ep.imports.job_cancel') }}
                </button>
                <button
                  v-else
                  type="button"
                  class="btn btn-primary"
                  data-testid="job-retry"
                  @click="retryImport"
                >
                  {{ t('ep.imports.job_retry') }}
                </button>
                <button type="button" class="btn btn-quiet" @click="goStep(3)">{{ t('ep.imports.prev') }}</button>
              </div>
            </template>
          </section>

          <div v-if="error" ref="errorNoticeRef" class="notice bad import-error" role="alert" tabindex="-1">
            <LinearIcon name="alert" :size="15" /><span>{{ errorText }}</span>
          </div>
        </form>
      </div>

      <aside class="import-rail">
        <div class="rail-title">{{ t('ep.imports.rules_title') }}</div>
        <ul class="rules-list">
          <li>{{ t('ep.imports.rules_formats') }}</li>
          <li>{{ t('ep.imports.rules_dup') }}</li>
          <li>{{ t('ep.imports.rules_pdf') }}</li>
          <li>{{ t('ep.imports.rules_version') }}</li>
        </ul>
      </aside>
    </div>

    <AppDialog
      :open="bankConfirmOpen"
      :title="t('ep.imports.bank')"
      initial-focus=".bank-change-cancel"
      data-testid="change-bank-dialog"
      @close="cancelBankChange"
    >
      <p class="hint">{{ t('ep.imports.change_bank_confirm') }}</p>
      <template #foot>
        <button type="button" class="btn btn-quiet bank-change-cancel" @click="cancelBankChange">{{ t('ep.common.cancel') }}</button>
        <button type="button" class="btn btn-primary bank-change-accept" @click="acceptBankChange">{{ t('ep.common.confirm') }}</button>
      </template>
    </AppDialog>

    <AppDialog
      :open="discardConfirmOpen"
      :title="t('ep.imports.cancel_preview')"
      initial-focus=".discard-preview-cancel"
      data-testid="discard-preview-dialog"
      @close="cancelDiscard"
    >
      <p class="hint">{{ t('ep.imports.discard_preview_confirm') }}</p>
      <template #foot>
        <button type="button" class="btn btn-quiet discard-preview-cancel" @click="cancelDiscard">{{ t('ep.common.cancel') }}</button>
        <button type="button" class="btn btn-danger discard-preview-accept" @click="acceptDiscard">{{ t('ep.imports.cancel_preview') }}</button>
      </template>
    </AppDialog>

    <AppDialog
      :open="leaveDialogOpen"
      :title="t('ep.imports.leave_title')"
      initial-focus=".leave-stay"
      data-testid="leave-dialog"
      @close="stayOnPage"
    >
      <p class="hint">{{ t('ep.imports.leave_hint') }}</p>
      <template #foot>
        <button type="button" class="btn btn-quiet leave-stay" @click="stayOnPage">{{ t('ep.imports.leave_stay') }}</button>
        <button type="button" class="btn btn-danger leave-discard" @click="discardAndLeave">{{ t('ep.imports.leave_discard') }}</button>
        <button type="button" class="btn btn-primary leave-later" @click="leaveForLater">{{ t('ep.imports.leave_later') }}</button>
      </template>
    </AppDialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import LinearIcon from '../components/LinearIcon.vue'
import AppDialog from '../components/AppDialog.vue'
import { listBanks } from '../api/banks'
import {
  previewImport,
  previewFileImport,
  uploadImport,
  previewPdfImport,
  confirmPdfImport,
  createImportDraft,
  listImportDrafts,
  getImportDraft,
  updateImportDraft,
  deleteImportDraft,
  startImportJob,
  getImportJob,
  cancelImportJob,
} from '../api/imports'
import { useLocale } from '../composables/useLocale.js'
import { formatDateTime } from '../utils/datetime.js'
import { readQueryNumber, readQueryString, queriesEqual } from '../utils/routeQuery.js'

const { t, locale } = useLocale()

const props = defineProps({ token: { type: String, required: true } })
defineEmits(['back'])
const router = useRouter()
const route = useRoute()
const banks = ref([])
const bankId = ref('')

// Contextual import entry: ?bankId= turns the top-level page into a child of
// the bank. The control points at a deterministic route, never history.
const isFromManage = computed(() => String(route.query?.from || '') === 'manage')
const backBankId = computed(() => {
  const preset = String(route.query?.bankId || '')
  if (preset) return preset
  return isFromManage.value ? String(bankId.value || '') : ''
})
const backBank = computed(() => banks.value.find(b => String(b.id) === backBankId.value) || null)
const backLabel = computed(() => {
  if (isFromManage.value) return t('ep.imports.back_to_imports')
  return backBank.value?.name || t('ep.common.back_to_bank')
})

function backToBank() {
  if (!backBankId.value) return
  if (isFromManage.value) {
    router.push({ name: 'bank-manage', params: { bankId: backBankId.value }, query: { tab: 'imports' } })
    return
  }
  router.push({ name: 'bank-detail', params: { bankId: backBankId.value } })
}

const file = ref(null)
// Text can be pasted directly instead of living in a file; both paths run the
// same preview/import pipeline, only the source of `content` differs.
const sourceMode = ref('file')
const pastedText = ref('')
const isDragging = ref(false)
const fileInputRef = ref(null)
const resumeFileInputRef = ref(null)
const loading = ref(false)
const previewing = ref(false)
// Any preview or import request owns the bank selector while it runs: swapping
// the target mid-request would let a stale response describe another bank.
const requestInFlight = computed(() => previewing.value || loading.value)
// The selector is locked whenever a request owns it: a preview, an upload, or
// a background job writing into the bank that was chosen when it started.
const bankBusy = computed(() => previewing.value || loading.value || jobRunning.value)
const error = ref(null)
const errorNoticeRef = ref(null)
const errorText = computed(() => {
  if (error.value instanceof Error) return error.value.message
  return typeof error.value === 'string' ? error.value : ''
})

// The error notice sits under the current step block, but later blocks can
// still push it off-screen. Bring it into view and focus it so the failure is
// announced instead of silently appearing below the fold.
watch(errorText, async (text) => {
  if (!text) return
  await nextTick()
  const el = errorNoticeRef.value
  if (!el) return
  if (typeof el.scrollIntoView === 'function') {
    el.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }
  if (typeof el.focus === 'function') el.focus({ preventScroll: true })
})

const result = ref(null)
// Snapshot of the bank that actually accepted the job. The select can move on
// (or be reset) while the upload is in flight; the receipt must not follow it.
const resultBank = ref('')
const resultBankId = ref('')
// The result card must state plainly when the selector has moved away from the
// bank that accepted the job, instead of implying the new bank received it.
const resultBankChanged = computed(() => Boolean(
  result.value &&
  resultBankId.value &&
  String(bankId.value) !== String(resultBankId.value),
))
const duplicatePreview = ref(null)
const duplicateStrategy = ref('skip')
const spreadsheetPreview = ref(null)
const textPreview = ref(null)
const pdfPreview = ref(null)
const pdfCandidates = ref([])
const pdfDuplicateStrategy = ref('')
const textContent = ref('')
const textFormat = ref('')
const resumedFilename = ref('')
const resumedSourceKind = ref('')
// Job state is declared early: the draft snapshot watcher serializes it during
// setup, before the job section below is reached.
const job = ref(null)
const jobId = ref('')
const jobCancelling = ref(false)
let jobTimer = null

function defaultMapping() {
  return {
    stem: null,
    answer: null,
    type: null,
    explanation: null,
    difficulty: null,
    tags: null,
    combined_options: null,
    options_delimiter: '',
    options: [],
  }
}
const currentMapping = ref(defaultMapping())

const bankLoadFailed = ref(false)
const banksLoading = ref(false)
const bankConfirmOpen = ref(false)
const pendingBankId = ref('')
const previousBankId = ref('')
let suppressBankWatch = false
// Monotonic token for preview requests. A response is only applied when it is
// still the newest request and the target bank is the one it was sent for.
let previewSeq = 0
const discardConfirmOpen = ref(false)
const discardKind = ref('')

// --- Wizard step ------------------------------------------------------------
// The step is addressable (?step=) so reload and back/forward land on the same
// place. Local state is kept in sync when the query changes from the outside.
const initialStep = readQueryNumber(route.query?.step, 1, { min: 1, max: 4 })
const stepNo = ref(initialStep)

const steps = computed(() => [
  { key: 'source', label: t('ep.imports.step_source') },
  { key: 'check', label: t('ep.imports.step_fields') },
  { key: 'duplicates', label: t('ep.imports.step_duplicates') },
  { key: 'result', label: t('ep.imports.step_result') },
])

const stepPercent = computed(() => ((stepNo.value - 1) / 3) * 100)

function stepState(index) {
  if (stepNo.value > index) return 'done'
  if (stepNo.value === index) return 'active'
  return 'pending'
}

function activeStepKey(index) {
  if (index === 4) return jobRunning.value ? 'ep.imports.job_running' : 'ep.imports.result_title'
  if (requestInFlight.value) return 'ep.imports.uploading'
  if (index === 1) {
    if (!bankId.value) return 'ep.imports.bank_placeholder'
    if (!file.value) return 'ep.imports.choose'
    return 'ep.imports.submit_preview'
  }
  if (index === 2) return 'ep.imports.submit_import'
  if (mode.value === 'pdf') return 'ep.imports.confirm_pdf'
  return 'ep.imports.submit_confirm'
}

function stepStateLabel(index) {
  const state = stepState(index)
  if (state === 'done') return t('ep.common.done')
  if (state === 'active') return t(activeStepKey(index))
  return ''
}

const mode = computed(() => {
  if (pdfPreview.value) return 'pdf'
  if (spreadsheetPreview.value) return 'spreadsheet'
  if (textPreview.value) return 'text'
  return ''
})

const isSpreadsheet = computed(() => {
  const name = file.value?.name?.toLowerCase() || ''
  return name.endsWith('.xlsx') || name.endsWith('.csv')
})

const isPdf = computed(() => {
  const name = file.value?.name?.toLowerCase() || ''
  return name.endsWith('.pdf')
})

const isTextFile = computed(() => {
  const name = file.value?.name?.toLowerCase() || ''
  return name.endsWith('.json') || name.endsWith('.md') || name.endsWith('.markdown') || name.endsWith('.txt')
})

const selectedBank = computed(() => banks.value.find(b => String(b.id) === String(bankId.value)) || null)

// Import writes questions, so member-level access must be rejected before the
// user spends time mapping columns or correcting a PDF draft.
const canImport = computed(() => {
  const role = String(selectedBank.value?.role || '').toUpperCase()
  return role === 'ADMIN' || role === 'EDITOR'
})

const optionLetters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
const optionSlots = ref(Array(8).fill(''))

function syncOptionsFromSlots() {
  const slots = optionSlots.value.map(v => (v !== '' && v !== null && v !== undefined ? Number(v) : null))
  let lastIdx = -1
  for (let i = slots.length - 1; i >= 0; i--) {
    if (slots[i] !== null) {
      lastIdx = i
      break
    }
  }
  currentMapping.value.options = lastIdx >= 0 ? slots.slice(0, lastIdx + 1) : []
}

function getOptionCol(index) {
  return optionSlots.value[index] || ''
}

function setOptionCol(index, rawVal) {
  optionSlots.value[index] = rawVal !== undefined && rawVal !== null ? String(rawVal) : ''
  syncOptionsFromSlots()
}

const precheckPanel = computed(() => {
  const source = spreadsheetPreview.value || pdfPreview.value || textPreview.value || duplicatePreview.value
  if (!source) return null
  const duplicates = Array.isArray(source.duplicates) ? source.duplicates.length : 0
  const isPdf = source === pdfPreview.value
  const count = isPdf
    ? Number(source.question_count || pdfCandidates.value.length || 0)
    : Number(source.question_count || 0)
  const attention = isPdf
    ? pdfCandidates.value.filter(candidate => candidate.is_uncertain).length
    : Array.isArray(source.missing) ? source.missing.length : 0
  const accepted = duplicates === 0 && attention === 0 && (isPdf || source.accepted !== false)
  // Labels come from the shared catalog and are derived from local state, so a
  // server-supplied reason string can never leak into the UI (e.g. Chinese text
  // under an English locale).
  const status = duplicates
    ? t('ep.imports.dup_title')
    : attention || !accepted
      ? t('ep.imports.pdf_low')
      : t('ep.imports.pdf_high')

  return { count, duplicates, attention, accepted, status }
})

const duplicateSource = computed(() => (
  duplicatePreview.value || pdfPreview.value || spreadsheetPreview.value || textPreview.value || null
))
const duplicateList = computed(() => (
  Array.isArray(duplicateSource.value?.duplicates) ? duplicateSource.value.duplicates : []
))

const currentStrategy = computed({
  get: () => (mode.value === 'pdf' ? pdfDuplicateStrategy.value : duplicateStrategy.value),
  set: (value) => {
    if (mode.value === 'pdf') pdfDuplicateStrategy.value = value
    else duplicateStrategy.value = value
  },
})

const strategyMissing = computed(() => duplicateList.value.length > 0 && !currentStrategy.value)

const textNeedsCheck = computed(() => {
  const preview = textPreview.value
  if (!preview) return false
  return Boolean(preview.duplicates?.length) || preview.accepted === false
})

const needsFile = computed(() => Boolean(
  (spreadsheetPreview.value || pdfPreview.value) && !file.value,
))

const sourceKind = computed(() => {
  if (mode.value) return mode.value
  if (isPdf.value) return 'pdf'
  if (isSpreadsheet.value) return 'spreadsheet'
  if (isTextFile.value) return 'text'
  return resumedSourceKind.value
})

const currentFilename = computed(() => {
  if (sourceMode.value === 'paste') {
    return pastedText.value.trim() ? t('ep.imports.pasted_source') : ''
  }
  return file.value?.name || resumedFilename.value || ''
})

function sourceKindLabel(kind) {
  const raw = String(kind || '').toLowerCase()
  if (raw === 'spreadsheet' || raw === 'sheet' || raw === 'xlsx' || raw === 'csv') return t('ep.imports.source_sheet')
  if (raw === 'pdf') return t('ep.imports.source_pdf')
  if (raw === 'text' || raw === 'markdown' || raw === 'json') return t('ep.imports.source_text')
  return t('ep.imports.untitled')
}

const sourceSummary = computed(() => t('ep.imports.summary_source', {
  bank: (bankId.value && bankNameFor(bankId.value)) || t('ep.imports.summary_source_unknown_bank'),
  file: currentFilename.value || t('ep.imports.untitled'),
}))

const nextDisabledReason = computed(() => {
  if (requestInFlight.value) return 'ep.imports.next_reason_busy'
  if (!bankId.value) return 'ep.imports.bank_placeholder'
  if (!canImport.value) return 'ep.imports.readonly_bank'
  if (sourceMode.value === 'paste') {
    return pastedText.value.trim() ? '' : 'ep.imports.paste_empty'
  }
  if (!file.value) return 'ep.imports.next_reason_file'
  return ''
})

const checkDisabledReason = computed(() => {
  if (requestInFlight.value) return 'ep.imports.next_reason_busy'
  if (mode.value === 'pdf' && !pdfCandidates.value.length) return 'ep.imports.next_reason_candidates'
  return ''
})

const confirmDisabledReason = computed(() => {
  if (requestInFlight.value || jobRunning.value) return 'ep.imports.next_reason_busy'
  if (!bankId.value) return 'ep.imports.bank_placeholder'
  if (!canImport.value) return 'ep.imports.readonly_bank'
  if (mode.value === 'pdf' && !pdfCandidates.value.length) return 'ep.imports.next_reason_candidates'
  if (needsFile.value) return 'ep.imports.resume_need_file'
  if (mode.value === 'text' && !textContent.value) return 'ep.imports.resume_need_file'
  if (strategyMissing.value) return 'ep.imports.next_reason_strategy'
  return ''
})

// --- Draft persistence ------------------------------------------------------
const draftId = ref(String(route.query?.draft || ''))
const draftSaving = ref(false)
const draftSaveError = ref('')
const draftListError = ref('')
const openDrafts = ref([])
const restoring = ref(false)
let draftTimer = null
let draftSeq = 0
const DRAFT_DEBOUNCE_MS = 600

const hasImportState = computed(() => Boolean(
  spreadsheetPreview.value ||
  textPreview.value ||
  pdfPreview.value ||
  duplicatePreview.value ||
  result.value,
))

const hasWizardState = computed(() => Boolean(
  hasImportState.value ||
  file.value ||
  pastedText.value ||
  currentFilename.value ||
  job.value ||
  stepNo.value > 1,
))

const wizardDirty = computed(() => !result.value && Boolean(
  spreadsheetPreview.value ||
  textPreview.value ||
  pdfPreview.value ||
  file.value ||
  pastedText.value ||
  currentFilename.value ||
  job.value,
))

function buildState() {
  return {
    step: stepNo.value,
    source_mode: sourceMode.value,
    source_kind: sourceKind.value,
    filename: currentFilename.value,
    spreadsheet_preview: spreadsheetPreview.value,
    text_preview: textPreview.value,
    pdf_preview: pdfPreview.value,
    pdf_candidates: pdfCandidates.value,
    mapping: currentMapping.value,
    option_slots: optionSlots.value,
    duplicate_strategy: duplicateStrategy.value,
    pdf_duplicate_strategy: pdfDuplicateStrategy.value,
    duplicate_preview: duplicatePreview.value,
    text_content: textContent.value,
    text_format: textFormat.value,
    pasted_text: pastedText.value,
    job_id: jobId.value,
    job: job.value,
    result: result.value,
    result_bank: resultBank.value,
    result_bank_id: resultBankId.value,
  }
}

const wizardSnapshot = computed(() => JSON.stringify(buildState()))

watch(wizardSnapshot, () => {
  if (restoring.value || !hasWizardState.value) return
  scheduleDraftSave()
})

function scheduleDraftSave() {
  if (draftTimer !== null) clearTimeout(draftTimer)
  draftTimer = setTimeout(() => {
    draftTimer = null
    void persistDraft()
  }, DRAFT_DEBOUNCE_MS)
}

function saveDraftNow(status) {
  if (draftTimer !== null) {
    clearTimeout(draftTimer)
    draftTimer = null
  }
  return persistDraft(status)
}

async function persistDraft(status) {
  if (restoring.value) return
  const bankAtStart = String(bankId.value || '')
  if (!bankAtStart || !hasWizardState.value) return
  const seq = ++draftSeq
  draftSaving.value = true
  const payload = {
    source_kind: sourceKind.value || 'text',
    filename: currentFilename.value,
    step: stepNo.value,
    state: buildState(),
    ...(status ? { status } : {}),
  }
  try {
    const saved = draftId.value
      ? await updateImportDraft(props.token, draftId.value, payload)
      : await createImportDraft(props.token, bankAtStart, payload)
    if (seq !== draftSeq) return
    if (saved?.id) {
      draftId.value = String(saved.id)
      syncDraftQuery()
    }
    draftSaveError.value = ''
  } catch (err) {
    if (seq !== draftSeq) return
    // Saving is a convenience; a failed save must never block local editing.
    draftSaveError.value = err?.message || t('ep.imports.error_fallback')
  } finally {
    if (seq === draftSeq) draftSaving.value = false
  }
}

function syncDraftQuery() {
  const current = route.query || {}
  if (String(current.draft || '') === draftId.value) return
  const next = { ...current }
  if (bankId.value) next.bankId = String(bankId.value)
  if (draftId.value) next.draft = draftId.value
  else delete next.draft
  router.replace({ query: next })
}

async function loadOpenDrafts() {
  const targetBankId = String(bankId.value || '')
  if (!targetBankId) {
    openDrafts.value = []
    return
  }
  try {
    const rows = await listImportDrafts(props.token, targetBankId, 'OPEN')
    if (String(bankId.value) !== targetBankId) return
    openDrafts.value = (Array.isArray(rows) ? rows : [])
      .filter(row => row && row.id && String(row.id) !== draftId.value)
    draftListError.value = ''
  } catch (err) {
    if (String(bankId.value) !== targetBankId) return
    openDrafts.value = []
    draftListError.value = err?.message || t('ep.imports.error_fallback')
  }
}

function applyDraft(draft) {
  if (!draft) return false
  const state = draft.state && typeof draft.state === 'object' ? draft.state : {}
  draftId.value = String(draft.id || '')
  spreadsheetPreview.value = state.spreadsheet_preview || null
  textPreview.value = state.text_preview || null
  pdfPreview.value = state.pdf_preview || null
  pdfCandidates.value = Array.isArray(state.pdf_candidates)
    ? JSON.parse(JSON.stringify(state.pdf_candidates))
    : []
  duplicatePreview.value = state.duplicate_preview || null
  currentMapping.value = { ...defaultMapping(), ...(state.mapping || {}) }
  optionSlots.value = Array(8).fill('')
  if (Array.isArray(state.option_slots)) {
    state.option_slots.slice(0, 8).forEach((value, idx) => {
      optionSlots.value[idx] = value !== null && value !== undefined ? String(value) : ''
    })
  }
  if (Array.isArray(state.mapping?.options)) {
    state.mapping.options.slice(0, 8).forEach((colIdx, slotIdx) => {
      optionSlots.value[slotIdx] = colIdx !== null && colIdx !== undefined ? String(colIdx) : ''
    })
  }
  duplicateStrategy.value = state.duplicate_strategy || 'skip'
  pdfDuplicateStrategy.value = state.pdf_duplicate_strategy || ''
  textContent.value = state.text_content || ''
  textFormat.value = state.text_format || ''
  pastedText.value = state.pasted_text || ''
  sourceMode.value = state.source_mode === 'paste' || (!state.source_mode && pastedText.value) ? 'paste' : 'file'
  resumedFilename.value = draft.filename || state.filename || ''
  resumedSourceKind.value = draft.source_kind || state.source_kind || ''
  jobId.value = String(state.job_id || '')
  job.value = state.job || null
  result.value = state.result || null
  resultBank.value = state.result_bank || ''
  resultBankId.value = state.result_bank_id || ''
  const savedStepRaw = Number(draft.step ?? state.step ?? 1)
  const savedStep = Number.isFinite(savedStepRaw) ? Math.min(4, Math.max(1, Math.trunc(savedStepRaw))) : 1
  stepNo.value = clampStep(savedStep)
  error.value = ''
  if (jobRunning.value) startPolling()
  return true
}

function clampStep(step) {
  if (step <= 1) return 1
  if (step === 2) return (spreadsheetPreview.value || pdfPreview.value || textPreview.value) ? 2 : 1
  if (step === 3) return (spreadsheetPreview.value || pdfPreview.value || textPreview.value || duplicatePreview.value) ? 3 : 1
  if (!result.value && !job.value && !jobId.value) return 3
  return 4
}

async function resumeDraft(id) {
  if (!id) return false
  restoring.value = true
  try {
    const draft = await getImportDraft(props.token, id)
    const applied = applyDraft(draft)
    await nextTick()
    return applied
  } catch (err) {
    error.value = err
    return false
  } finally {
    restoring.value = false
  }
}

async function resumeDraftFromBanner(draft) {
  if (!draft?.id) return
  const ok = await resumeDraft(draft.id)
  if (!ok) return
  openDrafts.value = openDrafts.value.filter(row => String(row.id) !== String(draft.id))
  syncStepQuery()
}

async function removeDraft(draft) {
  if (!draft?.id) return
  try {
    await deleteImportDraft(props.token, draft.id)
    openDrafts.value = openDrafts.value.filter(row => String(row.id) !== String(draft.id))
    if (draftId.value === String(draft.id)) {
      draftId.value = ''
      syncDraftQuery()
    }
  } catch (err) {
    draftSaveError.value = err?.message || t('ep.imports.error_fallback')
  }
}

async function discardDraft() {
  const current = draftId.value
  draftId.value = ''
  if (!current) return
  try {
    await deleteImportDraft(props.token, current)
  } catch {
    // Discarding is best effort; the stale draft is harmless and can be removed
    // from the import records later.
  }
}

// --- Step navigation --------------------------------------------------------
function validateStep(next) {
  const step = Math.max(1, Math.min(4, Number(next) || 1))
  if (step >= 2 && !(spreadsheetPreview.value || pdfPreview.value || textPreview.value || duplicatePreview.value)) return 1
  if (step === 4 && !(result.value || job.value || jobId.value)) return 3
  return step
}

function syncStepQuery() {
  const current = route.query || {}
  const next = { ...current }
  if (bankId.value) next.bankId = String(bankId.value)
  if (stepNo.value > 1) next.step = String(stepNo.value)
  else delete next.step
  if (draftId.value) next.draft = draftId.value
  else delete next.draft
  if (queriesEqual(next, current)) return
  // A step change is a real navigation: browser Back walks the wizard too.
  router.push({ query: next })
}

function goStep(next) {
  const target = validateStep(next)
  if (target === stepNo.value) return
  stepNo.value = target
  syncStepQuery()
  void saveDraftNow()
}

watch(() => route.query?.step, (value) => {
  if (value === undefined || value === null || value === '') return
  const next = validateStep(readQueryNumber(value, 1, { min: 1, max: 4 }))
  if (next !== stepNo.value) stepNo.value = next
})

// --- Source step ------------------------------------------------------------
const SUPPORTED_EXTENSIONS = ['.xlsx', '.csv', '.json', '.txt', '.md', '.markdown', '.pdf']

function isSupportedFile(candidate) {
  const lower = String(candidate?.name || '').toLowerCase()
  return SUPPORTED_EXTENSIONS.some(ext => lower.endsWith(ext))
}

// Switching between a file and pasted text changes where the import content
// comes from, so any preview produced by the previous source is dropped. The
// typed text itself is kept while toggling, so a detour to the picker does not
// throw away what the user pasted.
function setSourceMode(next) {
  const target = next === 'paste' ? 'paste' : 'file'
  if (sourceMode.value === target) return
  sourceMode.value = target
  if (target === 'paste') file.value = null
  else pastedText.value = ''
  previewSeq += 1
  if (previewing.value) {
    previewing.value = false
    loading.value = false
  }
  clearPreviews()
  resetJobState()
  error.value = ''
  if (stepNo.value !== 1) goStep(1)
  void saveDraftNow()
}

function clearPreviews() {
  duplicatePreview.value = null
  duplicateStrategy.value = 'skip'
  spreadsheetPreview.value = null
  textPreview.value = null
  pdfPreview.value = null
  pdfCandidates.value = []
  pdfDuplicateStrategy.value = ''
  currentMapping.value = defaultMapping()
  optionSlots.value = Array(8).fill('')
  textContent.value = ''
  textFormat.value = ''
}

function resetJobState() {
  stopPolling()
  jobId.value = ''
  job.value = null
  result.value = null
  resultBank.value = ''
  resultBankId.value = ''
}

function handleSelectedFile(selected) {
  // A new file invalidates any preview still in flight for the old one.
  previewSeq += 1
  if (previewing.value) {
    previewing.value = false
    loading.value = false
  }
  file.value = selected || null
  resumedFilename.value = selected?.name || ''
  resumedSourceKind.value = ''
  result.value = null
  resultBank.value = ''
  resultBankId.value = ''
  resetJobState()
  clearPreviews()
  error.value = ''
}

// The picker must enforce the same rule as drag-and-drop: an unsupported file
// never becomes the selected file, so the primary action stays disabled and
// the reason is announced.
function acceptSelectedFile(selected) {
  if (!selected) return
  if (!isSupportedFile(selected)) {
    handleSelectedFile(null)
    error.value = t('ep.imports.supported')
    return
  }
  handleSelectedFile(selected)
}

function selectFile(event) {
  const selected = event.target?.files?.[0] || null
  if (event.target) {
    // Allow choosing the same file again after a failed validation.
    try { event.target.value = '' } catch { /* read-only in some environments */ }
  }
  acceptSelectedFile(selected)
}

function triggerFileInput() {
  fileInputRef.value?.click()
}

function triggerResumeFileInput() {
  resumeFileInputRef.value?.click()
}

// Re-selecting the original file after a reload restores the ability to import
// without discarding the preview, mapping or PDF corrections restored from the
// draft. A different file means the draft no longer describes it.
function selectResumeFile(event) {
  const selected = event.target?.files?.[0] || null
  if (event.target) {
    try { event.target.value = '' } catch { /* read-only in some environments */ }
  }
  if (!selected) return
  if (!isSupportedFile(selected)) {
    error.value = t('ep.imports.supported')
    return
  }
  if (resumedFilename.value && selected.name !== resumedFilename.value) {
    handleSelectedFile(selected)
    goStep(1)
    return
  }
  file.value = selected
  error.value = ''
}

function onDropZoneClick(event) {
  const target = event.target
  if (target?.closest?.('button')) return
  // The hidden input's synthetic click bubbles here too; ignore it or the
  // programmatic open would recurse forever.
  if (target === fileInputRef.value) return
  triggerFileInput()
}

function onDropFile(event) {
  isDragging.value = false
  acceptSelectedFile(event.dataTransfer?.files?.[0] || null)
}

function onDragLeave(event) {
  if (event.currentTarget && event.relatedTarget && event.currentTarget.contains(event.relatedTarget)) return
  isDragging.value = false
}

function bankNameFor(id) {
  return banks.value.find(b => String(b.id) === String(id))?.name || t('ep.common.none')
}

async function loadBanks() {
  bankLoadFailed.value = false
  banksLoading.value = true
  try {
    banks.value = await listBanks(props.token)
    const preset = String(route.query?.bankId || '')
    if (preset && banks.value.some(b => String(b.id) === preset)) {
      suppressBankWatch = true
      bankId.value = preset
      await nextTick()
      suppressBankWatch = false
    }
  } catch {
    bankLoadFailed.value = true
    banks.value = []
  } finally {
    banksLoading.value = false
  }
}

async function initializeWizard() {
  const presetDraft = readQueryString(route.query?.draft)
  if (presetDraft && bankId.value) {
    const ok = await resumeDraft(presetDraft)
    if (ok) return
  }
  stepNo.value = validateStep(stepNo.value)
  if (bankId.value) void loadOpenDrafts()
}

onMounted(async () => {
  await loadBanks()
  await initializeWizard()
})

function syncBankQuery(nextId) {
  const currentQuery = route.query || {}
  if (!nextId || String(currentQuery.bankId || '') === String(nextId)) return
  const next = { ...currentQuery, bankId: String(nextId) }
  // A new target bank starts a fresh wizard; step/draft belong to the old one.
  delete next.step
  delete next.draft
  router.replace({ query: next })
}

// Changing the target bank while a preview/mapping/result exists is destructive:
// ask first, and never let the old preview silently write to the new bank.
watch(bankId, (next, prev) => {
  if (suppressBankWatch) return
  const nextId = String(next || '')
  if (!nextId) return
  if (!hasImportState.value) {
    syncBankQuery(nextId)
    void loadOpenDrafts()
    return
  }
  previousBankId.value = String(prev || '')
  pendingBankId.value = nextId
  bankConfirmOpen.value = true
})

function cancelBankChange() {
  const restore = previousBankId.value
  bankConfirmOpen.value = false
  pendingBankId.value = ''
  if (restore) {
    suppressBankWatch = true
    bankId.value = restore
    nextTick(() => { suppressBankWatch = false })
  }
}

function acceptBankChange() {
  const nextId = pendingBankId.value
  bankConfirmOpen.value = false
  pendingBankId.value = ''
  void discardDraft()
  resetImportState()
  syncBankQuery(nextId)
  void loadOpenDrafts()
}

function isCurrentPreview(requestId, bankAtStart) {
  return requestId === previewSeq && String(bankId.value) === bankAtStart
}

// --- Preview requests -------------------------------------------------------
async function inspectSpreadsheet(customMapping = null) {
  if (!file.value || !bankId.value) return false
  const bankAtStart = String(bankId.value)
  const requestId = ++previewSeq
  previewing.value = true
  loading.value = true
  error.value = ''
  try {
    // Keep the three-argument call when the user has not mapped anything yet;
    // the mapping is only added when it is a real choice to verify.
    const prev = customMapping
      ? await previewFileImport(props.token, bankAtStart, file.value, customMapping)
      : await previewFileImport(props.token, bankAtStart, file.value)
    if (!isCurrentPreview(requestId, bankAtStart)) return false
    spreadsheetPreview.value = prev
    if (Array.isArray(prev.duplicates) && prev.duplicates.length) duplicateStrategy.value = ''
    // A caller-supplied mapping is the user's decision; only adopt the server's
    // auto-detection when the user has not mapped the columns themselves.
    if (prev.mapping && !customMapping) {
      currentMapping.value = { ...currentMapping.value, ...prev.mapping }
      optionSlots.value = Array(8).fill('')
      if (Array.isArray(prev.mapping.options)) {
        prev.mapping.options.slice(0, 8).forEach((colIdx, slotIdx) => {
          optionSlots.value[slotIdx] = colIdx !== null && colIdx !== undefined ? String(colIdx) : ''
        })
      }
      syncOptionsFromSlots()
    }
    return true
  } catch (err) {
    if (!isCurrentPreview(requestId, bankAtStart)) return false
    error.value = err
    return false
  } finally {
    if (requestId === previewSeq) {
      previewing.value = false
      loading.value = false
    }
  }
}

async function inspectPdf() {
  if (!file.value || !bankId.value) return false
  const bankAtStart = String(bankId.value)
  const requestId = ++previewSeq
  previewing.value = true
  loading.value = true
  error.value = ''
  try {
    const prev = await previewPdfImport(props.token, bankAtStart, file.value)
    if (!isCurrentPreview(requestId, bankAtStart)) return false
    pdfPreview.value = prev
    pdfCandidates.value = JSON.parse(JSON.stringify(prev.candidates || []))
    pdfDuplicateStrategy.value = prev.duplicates?.length ? '' : 'skip'
    return true
  } catch (err) {
    if (!isCurrentPreview(requestId, bankAtStart)) return false
    error.value = err
    return false
  } finally {
    if (requestId === previewSeq) {
      previewing.value = false
      loading.value = false
    }
  }
}

async function inspectText() {
  if (!file.value || !bankId.value || !isTextFile.value) return false
  const bankAtStart = String(bankId.value)
  const requestId = ++previewSeq
  previewing.value = true
  loading.value = true
  error.value = ''
  try {
    const text = await file.value.text()
    const format = file.value.name.toLowerCase().endsWith('.json') ? 'json' : 'markdown'
    textContent.value = text
    textFormat.value = format
    const preview = await previewImport(props.token, bankAtStart, { format, content: text })
    if (!isCurrentPreview(requestId, bankAtStart)) return false
    textPreview.value = preview
    duplicateStrategy.value = preview?.duplicates?.length ? '' : 'skip'
    return true
  } catch (err) {
    if (!isCurrentPreview(requestId, bankAtStart)) return false
    error.value = err
    return false
  } finally {
    if (requestId === previewSeq) {
      previewing.value = false
      loading.value = false
    }
  }
}

async function inspectPastedText() {
  const text = pastedText.value
  if (!text.trim() || !bankId.value) return false
  const bankAtStart = String(bankId.value)
  const requestId = ++previewSeq
  previewing.value = true
  loading.value = true
  error.value = ''
  try {
    const trimmed = text.trim()
    const format = trimmed.startsWith('{') || trimmed.startsWith('[') ? 'json' : 'markdown'
    textContent.value = text
    textFormat.value = format
    const preview = await previewImport(props.token, bankAtStart, { format, content: text })
    if (!isCurrentPreview(requestId, bankAtStart)) return false
    textPreview.value = preview
    duplicateStrategy.value = preview?.duplicates?.length ? '' : 'skip'
    return true
  } catch (err) {
    if (!isCurrentPreview(requestId, bankAtStart)) return false
    error.value = err
    return false
  } finally {
    if (requestId === previewSeq) {
      previewing.value = false
      loading.value = false
    }
  }
}

async function nextFromSource() {
  if (nextDisabledReason.value) return
  let ok = false
  if (sourceMode.value === 'paste') ok = await inspectPastedText()
  else if (isSpreadsheet.value) ok = await inspectSpreadsheet()
  else if (isPdf.value) ok = await inspectPdf()
  else ok = await inspectText()
  if (!ok) return
  // Text has no mapping UI: its precheck is only worth a step when it found
  // something to decide (duplicates or rejected rows); otherwise go straight
  // to the duplicate strategy.
  if (mode.value === 'text') goStep(textNeedsCheck.value ? 2 : 3)
  else goStep(2)
}

// Leaving the mapping step re-reads the file with the columns the user chose.
// Duplicates are a property of (file + mapping + current bank), so step 3 must
// never show the duplicate list computed from the auto-detected mapping.
async function nextFromCheck() {
  if (checkDisabledReason.value) return
  if (mode.value === 'spreadsheet' && file.value) {
    syncOptionsFromSlots()
    const ok = await inspectSpreadsheet({ ...currentMapping.value })
    if (!ok) return
  }
  goStep(3)
}

function onFormSubmit() {
  if (stepNo.value === 1) {
    void nextFromSource()
    return
  }
  if (stepNo.value === 2) {
    void nextFromCheck()
    return
  }
  if (stepNo.value === 3) void confirmImport()
}

// --- Import job -------------------------------------------------------------
const JOB_POLL_MS = 800
const JOB_DONE_STATUSES = ['COMPLETED', 'IMPORTED', 'SUCCESS', 'SUCCEEDED', 'DONE', 'FINISHED']
const JOB_FAILED_STATUSES = ['FAILED', 'FAILURE', 'ERROR', 'PRECHECK_FAILED']
const JOB_CANCELLED_STATUSES = ['CANCELLED', 'CANCELED']

function normalizedJobStatus(status) {
  return String(status || '').toUpperCase()
}

const jobRunning = computed(() => {
  if (!job.value) return false
  const status = normalizedJobStatus(job.value.status)
  return ![...JOB_DONE_STATUSES, ...JOB_FAILED_STATUSES, ...JOB_CANCELLED_STATUSES].includes(status)
})

const jobFailed = computed(() => Boolean(job.value) && JOB_FAILED_STATUSES.includes(normalizedJobStatus(job.value.status)))
const jobCancelled = computed(() => Boolean(job.value) && JOB_CANCELLED_STATUSES.includes(normalizedJobStatus(job.value.status)))

const jobDone = computed(() => Number(job.value?.imported_count || 0))
const jobTotal = computed(() => {
  const total = Number(job.value?.total)
  if (Number.isFinite(total) && total > 0) return total
  return Number(precheckPanel.value?.count || 0)
})
const jobPercent = computed(() => {
  if (jobTotal.value > 0) return Math.min(100, Math.max(0, Math.round((jobDone.value / jobTotal.value) * 100)))
  const progress = Number(job.value?.progress)
  return Number.isFinite(progress) ? Math.min(100, Math.max(0, Math.round(progress))) : 0
})

const jobReason = computed(() => job.value?.reason || t('ep.imports.job_unknown_reason'))

const JOB_STATUS_KEYS = {
  QUEUED: 'ep.imports.job_pending',
  PENDING: 'ep.imports.job_pending',
  PROCESSING: 'ep.imports.job_running',
  RUNNING: 'ep.imports.job_running',
  COMPLETED: 'ep.common.done',
  IMPORTED: 'ep.common.done',
  SUCCESS: 'ep.common.done',
  DONE: 'ep.common.done',
  FAILED: 'ep.imports.job_failed',
  PRECHECK_FAILED: 'ep.imports.job_failed',
  CANCELLED: 'ep.imports.job_cancelled',
}

const jobStatusLabel = computed(() => {
  if (!job.value) return ''
  const key = JOB_STATUS_KEYS[normalizedJobStatus(job.value.status)]
  return key ? t(key) : ''
})
const jobStatusClass = computed(() => (
  jobFailed.value ? 'bad' : jobCancelled.value ? 'warn' : jobRunning.value ? '' : 'ok'
))

const resultImportedCount = computed(() => Number(result.value?.imported_count || 0))

function stopPolling() {
  if (jobTimer !== null) {
    clearInterval(jobTimer)
    jobTimer = null
  }
}

function startPolling() {
  stopPolling()
  if (!jobId.value) return
  jobTimer = setInterval(() => { void pollJobOnce() }, JOB_POLL_MS)
}

async function pollJobOnce() {
  if (!jobId.value) return
  try {
    const snapshot = await getImportJob(props.token, jobId.value)
    if (!snapshot) return
    applyJobSnapshot(snapshot)
  } catch {
    // A transient poll failure is not the job's verdict. Keep the last known
    // status and let the next tick retry.
  }
}

function applyJobSnapshot(snapshot) {
  const status = normalizedJobStatus(snapshot?.status) || normalizedJobStatus(job.value?.status)
  job.value = { ...(job.value || {}), ...snapshot, status }
  if (jobRunning.value) return
  stopPolling()
  if (jobFailed.value || jobCancelled.value) {
    void saveDraftNow()
    return
  }
  result.value = {
    job_id: jobId.value,
    imported_count: Number(job.value.imported_count || 0),
    total: job.value.total,
  }
  void saveDraftNow('DONE')
}

function beginJob(started, targetBankId, targetBankName) {
  const id = started?.job_id || started?.id
  if (!id) {
    finishWithResult(started, targetBankId, targetBankName)
    return
  }
  jobId.value = String(id)
  job.value = {
    id: jobId.value,
    status: started.status || 'QUEUED',
    imported_count: Number(started.imported_count || 0),
    total: Number(started.total ?? precheckPanel.value?.count ?? 0),
    progress: Number(started.progress || 0),
    reason: started.reason || '',
  }
  resultBank.value = targetBankName
  resultBankId.value = targetBankId
  stepNo.value = 4
  syncStepQuery()
  void saveDraftNow()
  if (jobRunning.value) startPolling()
  else applyJobSnapshot(started)
}

function finishWithResult(receipt, targetBankId, targetBankName) {
  result.value = {
    ...(receipt || {}),
    imported_count: Number(receipt?.imported_count || 0),
  }
  if (receipt?.job_id) jobId.value = String(receipt.job_id)
  job.value = null
  resultBank.value = targetBankName
  resultBankId.value = targetBankId
  stepNo.value = 4
  syncStepQuery()
  void saveDraftNow('DONE')
}

async function confirmImport() {
  if (confirmDisabledReason.value) return
  const targetBankId = String(bankId.value)
  const targetBankName = bankNameFor(targetBankId)
  const strategy = duplicateList.value.length ? currentStrategy.value : (mode.value === 'pdf' ? (pdfDuplicateStrategy.value || 'skip') : (duplicateStrategy.value || 'skip'))
  loading.value = true
  error.value = ''
  try {
    if (mode.value === 'pdf' && pdfPreview.value) {
      // PDF corrections are submitted as the corrected candidate list; the
      // backend's pdf-confirm endpoint stays synchronous by contract.
      const receipt = await confirmPdfImport(props.token, targetBankId, {
        draft_id: pdfPreview.value.draft_id,
        questions: pdfCandidates.value,
        duplicate_strategy: strategy,
      })
      finishWithResult(receipt, targetBankId, targetBankName)
      return
    }
    if (mode.value === 'spreadsheet' && spreadsheetPreview.value) {
      syncOptionsFromSlots()
      const started = await startImportJob(props.token, targetBankId, {
        file: file.value,
        column_mapping: currentMapping.value,
        duplicate_strategy: strategy,
      })
      if (started) {
        beginJob(started, targetBankId, targetBankName)
        return
      }
      // Older backends have no job endpoint. The synchronous file import stays
      // available, so the wizard still completes instead of dead-ending.
      const receipt = await uploadImport(props.token, targetBankId, file.value, strategy, currentMapping.value)
      finishWithResult(receipt, targetBankId, targetBankName)
      return
    }

    if (!textContent.value && file.value) {
      textContent.value = await file.value.text()
      textFormat.value = file.value.name.toLowerCase().endsWith('.json') ? 'json' : 'markdown'
    }
    const started = await startImportJob(props.token, targetBankId, {
      format: textFormat.value || 'markdown',
      content: textContent.value,
      duplicate_strategy: strategy,
    })
    if (started) {
      beginJob(started, targetBankId, targetBankName)
      return
    }
    const fallbackFile = file.value || new File([textContent.value], currentFilename.value || 'import.md', { type: 'text/markdown' })
    const receipt = await uploadImport(props.token, targetBankId, fallbackFile, strategy, null)
    finishWithResult(receipt, targetBankId, targetBankName)
  } catch (err) {
    if (err.status === 409 && err.detail && typeof err.detail === 'object') {
      // Duplicates appeared after the preview (another editor changed the bank).
      // Keep the corrections and let the user choose a strategy here.
      duplicatePreview.value = err.detail
      duplicateStrategy.value = ''
      goStep(3)
    } else {
      error.value = err
    }
  } finally {
    loading.value = false
  }
}

async function retryImport() {
  if (jobRunning.value) return
  job.value = null
  jobId.value = ''
  result.value = null
  stepNo.value = 3
  syncStepQuery()
  await confirmImport()
}

async function cancelJob() {
  if (!jobId.value || jobCancelling.value) return
  jobCancelling.value = true
  try {
    await cancelImportJob(props.token, jobId.value)
  } catch (err) {
    // The job may already have reached a terminal state; the next poll or the
    // explicit status below is the source of truth.
    error.value = err
  } finally {
    stopPolling()
    job.value = { ...(job.value || {}), status: 'CANCELLED' }
    jobCancelling.value = false
    void saveDraftNow()
  }
}

// --- Discard / reset --------------------------------------------------------
function resetPreviewState() {
  duplicatePreview.value = null
  duplicateStrategy.value = 'skip'
  spreadsheetPreview.value = null
  textPreview.value = null
  pdfPreview.value = null
  pdfCandidates.value = []
  pdfDuplicateStrategy.value = ''
  currentMapping.value = defaultMapping()
  optionSlots.value = Array(8).fill('')
  textContent.value = ''
  textFormat.value = ''
  pastedText.value = ''
  sourceMode.value = 'file'
  resumedFilename.value = ''
  resumedSourceKind.value = ''
}

function resetImportState() {
  resetJobState()
  resetPreviewState()
  stepNo.value = 1
  error.value = ''
}

function resetImport() {
  void discardDraft()
  resetImportState()
  file.value = null
  draftId.value = ''
  syncStepQuery()
}

function performDiscard(kind) {
  if (kind === 'spreadsheet') {
    spreadsheetPreview.value = null
    currentMapping.value = defaultMapping()
    optionSlots.value = Array(8).fill('')
  } else if (kind === 'pdf') {
    pdfPreview.value = null
    pdfCandidates.value = []
    pdfDuplicateStrategy.value = ''
  } else if (kind === 'text') {
    textPreview.value = null
    textContent.value = ''
    textFormat.value = ''
    duplicateStrategy.value = 'skip'
  }
  stepNo.value = 1
  syncStepQuery()
  void saveDraftNow()
}

// The destructive "leave the preview" action must name what it does and ask
// before throwing away field edits, corrected PDF candidates or a preview.
function requestDiscard(kind) {
  discardKind.value = kind
  if (hasImportState.value || stepNo.value > 1) {
    discardConfirmOpen.value = true
    return
  }
  performDiscard(kind)
}

function cancelDiscard() {
  discardConfirmOpen.value = false
  discardKind.value = ''
}

function acceptDiscard() {
  const kind = discardKind.value
  discardConfirmOpen.value = false
  discardKind.value = ''
  performDiscard(kind)
}

// --- Leave guard ------------------------------------------------------------
const leaveDialogOpen = ref(false)
let leaveNext = null

onBeforeRouteLeave((to, from, next) => {
  // A running job belongs to the server; leaving is safe and the workspace
  // shows its status. Nothing else needs a prompt when the wizard is clean.
  if (jobRunning.value || !wizardDirty.value) {
    void saveDraftNow()
    next()
    return
  }
  leaveNext = next
  void saveDraftNow()
  leaveDialogOpen.value = true
})

function stayOnPage() {
  const next = leaveNext
  leaveNext = null
  leaveDialogOpen.value = false
  if (next) next(false)
}

async function leaveForLater() {
  const next = leaveNext
  leaveNext = null
  leaveDialogOpen.value = false
  await saveDraftNow()
  if (next) next()
}

async function discardAndLeave() {
  const next = leaveNext
  leaveNext = null
  leaveDialogOpen.value = false
  stopPolling()
  await discardDraft()
  resetPreviewState()
  resetJobState()
  if (next) next()
}

onBeforeUnmount(() => {
  if (draftTimer !== null) clearTimeout(draftTimer)
  draftTimer = null
  stopPolling()
})

function goBank() {
  // Follow the bank that accepted the job, not whatever the selector shows now.
  const targetBankId = String(resultBankId.value || '')
  if (!targetBankId) return
  if (isFromManage.value) {
    router.push({ name: 'bank-manage', params: { bankId: targetBankId }, query: { tab: 'imports' } })
    return
  }
  router.push(`/banks/${targetBankId}`)
}

// --- PDF candidates ---------------------------------------------------------
function mergeWithPrev(idx) {
  if (idx <= 0) return
  const current = pdfCandidates.value[idx]
  const prev = pdfCandidates.value[idx - 1]
  prev.stem += '\n' + current.stem
  if (current.options && current.options.length) {
    prev.options = [...(prev.options || []), ...current.options]
  }
  if (!prev.answer && current.answer) {
    prev.answer = current.answer
  }
  if (current.explanation) {
    prev.explanation = (prev.explanation ? prev.explanation + '\n' : '') + current.explanation
  }
  pdfCandidates.value.splice(idx, 1)
}

function splitCandidate(idx) {
  const item = pdfCandidates.value[idx]
  const stem = item.stem || ''

  let splitIndex = -1
  const newlineMatch = stem.search(/\n(?=[0-9]+[.\s、\)])/)
  if (newlineMatch > 0) {
    splitIndex = newlineMatch + 1
  } else {
    const anyNewline = stem.indexOf('\n')
    if (anyNewline > 0) {
      splitIndex = anyNewline + 1
    } else {
      const mid = Math.floor(stem.length / 2)
      const terminators = ['。', '？', '！', '?', '!', '；', ';', '. ']
      let bestDist = Infinity
      for (const t of terminators) {
        let pos = stem.indexOf(t)
        while (pos !== -1) {
          const cutPos = pos + t.length
          const dist = Math.abs(cutPos - mid)
          if (dist < bestDist && cutPos < stem.length) {
            bestDist = dist
            splitIndex = cutPos
          }
          pos = stem.indexOf(t, pos + 1)
        }
      }
    }
  }

  if (splitIndex <= 0 || splitIndex >= stem.length) {
    splitIndex = Math.floor(stem.length / 2)
  }

  const firstStem = stem.slice(0, splitIndex).trim()
  const secondStem = stem.slice(splitIndex).trim() || t('ep.imports.split_continuation')

  item.stem = firstStem
  pdfCandidates.value.splice(idx + 1, 0, {
    candidate_id: pdfCandidates.value.length + 1,
    type: item.type,
    stem: secondStem,
    options: [],
    answer: '',
    explanation: '',
    difficulty: item.difficulty || 3,
    tags: item.tags ? [...item.tags] : [],
    is_uncertain: true,
    uncertain_reason: t('ep.imports.split_uncertain'),
  })
}

function removeCandidate(idx) {
  pdfCandidates.value.splice(idx, 1)
}

function addCandidateOption(cand) {
  if (!cand.options) cand.options = []
  const nextKey = String.fromCharCode(65 + cand.options.length)
  cand.options.push({ key: nextKey, content: '' })
}
</script>

<style scoped>
.import-page { padding-top: 26px; }
.link-btn { border: 0; background: none; padding: 0; color: var(--ink-3); font: inherit; cursor: pointer; }
.link-btn:hover { color: var(--brand); }

/* Contextual back control, matching the shell's second-level back button. */
.page-back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 26px;
  margin-bottom: 14px;
  padding: 0 8px;
  border: 1px solid var(--line);
  border-radius: 2px;
  background: transparent;
  color: var(--ink-3);
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: .04em;
  white-space: nowrap;
  cursor: pointer;
  transition: border-color .15s ease, color .15s ease;
}
.page-back:hover { border-color: var(--line-strong); color: var(--ink); }
.page-back:focus-visible { outline: 1px solid var(--brand); outline-offset: 2px; }
.page-back svg { flex: none; }

.import-steps { display: flex; gap: 18px; margin: 22px 0 0; padding: 12px 0; list-style: none; border-top: 1px solid var(--line); flex-wrap: wrap; }
.import-step { display: flex; align-items: baseline; gap: 7px; flex: 1 1 150px; min-width: 0; color: var(--ink-4); }
.import-step.is-active { color: var(--ink); }
.import-step.is-done { color: var(--ink-3); }
.step-idx { font-size: 12px; letter-spacing: .04em; }
.step-label { font-size: 12px; }
.step-state { margin-left: auto; font-size: 12px; color: var(--ink-4); white-space: nowrap; }
.import-step[data-step-state="active"] .step-state { color: var(--brand); }
.import-step[data-step-state="done"] .step-state { color: var(--ok); }
.import-step.is-active .step-label { font-weight: 600; }
.import-progress { height: 2px; margin: 0 0 18px; background: var(--line); overflow: hidden; }
.import-progress i { display: block; height: 100%; background: var(--brand); transition: width .2s var(--ease); }

.import-draft-error { margin: 0 0 16px; }
.import-resume { margin-bottom: 18px; padding: 14px 16px; border: 1px solid var(--line-strong); border-radius: 4px; background: var(--surface-2); }
.import-resume-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.import-resume-list { margin-top: 10px; }
.import-resume-row .list-main { display: flex; flex-direction: column; gap: 3px; }
.import-resume-row .qrow-stem { -webkit-line-clamp: 1; }

.import-precheck-panel { margin-bottom: 18px; padding: 14px 16px; border: 1px solid var(--line-strong); border-radius: 4px; background: var(--surface-2); }
.import-precheck-panel-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.import-precheck-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; margin-top: 12px; }
.import-precheck-cell { min-width: 0; }
.import-precheck-cell b { display: block; font-family: var(--font-mono); font-size: 24px; font-weight: 500; line-height: 1.15; color: var(--ink); }
.import-precheck-cell b.is-warn { color: var(--warn); }
.import-precheck-cell span { display: block; margin-top: 3px; font-size: 12px; color: var(--ink-3); }
.import-precheck-loading { margin: 8px 0 0; font-size: 12px; color: var(--ink-3); }

.import-layout { display: grid; grid-template-columns: minmax(0, 1fr) 250px; gap: 44px; margin-top: 26px; align-items: start; }
.import-main { min-width: 0; }
.import-rail { border-top: 1px solid var(--line); padding-top: 13px; }
.rail-title { font-size: 12px; font-weight: 600; letter-spacing: .06em; color: var(--ink-2); }
.rules-list { margin: 10px 0 0; padding: 0 0 0 15px; }
.rules-list li { font-size: 12px; line-height: 1.8; color: var(--ink-3); margin-bottom: 6px; }

.step-block { padding: 22px 0 26px; border-top: 1px solid var(--line); }
.step-block:first-of-type { border-top: 0; padding-top: 0; }
.step-head { display: flex; align-items: flex-start; gap: 14px; margin-bottom: 20px; }
.step-head .tag { margin-left: auto; }
.step-head .btn-quiet { margin-left: auto; }
.step-no { font-size: 12px; letter-spacing: .04em; color: var(--ink-4); padding-top: 3px; }
.step-title { font-family: var(--font-serif); font-size: 19px; font-weight: 600; line-height: 1.3; }
.step-sub { margin-top: 4px; font-size: 12px; line-height: 1.7; color: var(--ink-3); max-width: 62ch; }
.step-summary { padding: 16px 0 18px; }
.step-summary .step-head { margin-bottom: 0; }
.step-summary .step-title { font-size: 15px; }

.source-modes { display: flex; gap: 6px; margin: 18px 0 12px; }
.source-modes .btn.is-active { border-color: var(--brand-line); color: var(--brand); background: var(--surface-2); }

.file-drop { display: flex; align-items: center; gap: 12px; min-height: 76px; padding: 16px 18px; border: 1px dashed var(--line-strong); background: var(--surface); cursor: pointer; transition: border-color .15s ease, background .15s ease; }
.file-drop:hover, .file-drop.is-dragging { border-color: var(--brand-line); background: var(--surface-2); }
.file-drop.is-dragging { flex-direction: column; justify-content: center; color: var(--brand); }
.file-icon { display: grid; place-items: center; width: 34px; height: 34px; border: 1px solid var(--line); color: var(--ink-3); flex: none; }
.file-main { display: flex; flex-direction: column; gap: 3px; min-width: 0; flex: 1; }
.file-name { font-size: 13px; color: var(--ink); overflow-wrap: anywhere; }
.file-meta { font-size: 12px; color: var(--ink-3); }
.file-input-hidden { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
.file-formats { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
.file-formats .tag { font-size: 12px; }

.import-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 22px; padding-top: 16px; border-top: 1px solid var(--line); }
.import-target { margin-bottom: 6px; }

.mapping-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px 18px; }
.sample-block { margin-top: 22px; }
.sample-scroll { overflow-x: auto; border-top: 1px solid var(--line); }
.sample-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.sample-table th { padding: 7px 10px; text-align: left; font-size: 12px; letter-spacing: .05em; font-weight: 600; color: var(--ink-3); border-bottom: 1px solid var(--line); white-space: nowrap; }
.sample-table td { padding: 7px 10px; border-bottom: 1px solid var(--line); color: var(--ink-2); vertical-align: top; max-width: 220px; }

.pdf-list { display: flex; flex-direction: column; gap: 0; }
.pdf-card { border-top: 1px solid var(--line); padding: 18px 0; }
.pdf-card:first-child { border-top: 0; padding-top: 4px; }
.pdf-card-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 14px; }
.pdf-card-actions { display: flex; gap: 2px; flex-wrap: wrap; }
.pdf-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 14px; }
.pdf-options { margin-top: 14px; }
.pdf-options-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.pdf-option-row { display: flex; gap: 7px; align-items: center; margin-top: 6px; }
.opt-key { width: 46px; flex: none; text-align: center; }

.dup-list { margin-top: 14px; }
.dup-more { margin-top: 10px; border-top: 1px solid var(--line); padding-top: 8px; }
.dup-more-summary {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--ink-3);
  cursor: pointer;
  list-style: none;
}
.dup-more-summary::-webkit-details-marker { display: none; }
.dup-more-summary:hover { color: var(--ink); }
.dup-more-summary::before { content: '+ '; }
.dup-more[open] > .dup-more-summary::before { content: '− '; }
.import-error { margin-top: 16px; scroll-margin-top: 16px; }
.import-error:focus { outline: 2px solid var(--bad); outline-offset: 2px; }
.pdf-duplicates { margin-top: 18px; }
.qrow-stem { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; font-family: var(--font-serif); font-size: 13.5px; line-height: 1.65; }
.result-block .kv { margin-top: 2px; }

.job-progress { margin-top: 4px; }
.job-bar { height: 4px; background: var(--line); overflow: hidden; }
.job-bar i { display: block; height: 100%; background: var(--brand); transition: width .3s var(--ease); }
.job-meta { margin-top: 8px; font-size: 12px; color: var(--ink-3); }
.job-failure { margin-top: 4px; }

@media (max-width: 960px) {
  .import-layout { grid-template-columns: minmax(0, 1fr); gap: 24px; }
  .import-rail { display: none; }
  .mapping-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 640px) {
  .import-page { overflow-x: hidden; }
  .import-steps { gap: 14px; }
  .import-step { flex: 1 1 40%; min-width: 0; }
  .step-state { display: none; }
  .import-precheck-grid { gap: 8px; }
  .import-precheck-cell b { font-size: 20px; }
  .mapping-grid, .pdf-grid { grid-template-columns: minmax(0, 1fr); }
  .file-drop { flex-wrap: wrap; }
  .file-drop .btn { margin-left: 0; flex: 1 1 auto; justify-content: center; }
  .file-main { flex-basis: calc(100% - 46px); }
  .step-block { padding: 18px 0 22px; }
  .step-title { font-size: 17px; }
  .step-head { flex-wrap: wrap; }
  .pdf-card-head { flex-wrap: wrap; align-items: flex-start; }
  .pdf-card-actions { width: 100%; justify-content: flex-end; }
  .pdf-option-row { flex-wrap: wrap; }
  .import-actions .btn { flex: 1 1 auto; justify-content: center; }
  .step-summary .step-head .btn-quiet { margin-left: 0; }
}

/* Touch targets: the contextual back control is the primary exit on a phone. */
@media (pointer: coarse) {
  .page-back {
    min-height: 38px;
    height: auto;
    padding: 0 12px;
  }
}
</style>
