<template>
  <main class="practice-page" @touchstart="handleTouchStart" @touchend="handleTouchEnd">
    <header class="page-header compact-header">
      <div class="header-left-bar">
        <button type="button" class="btn-back" @click="$emit('back')">← 返回</button>
        <div class="header-titles">
          <h1 class="practice-title">{{ session?.mode === 'ELIMINATION' ? '斩杀查漏补缺' : session?.mode === 'FSRS' ? 'FSRS 复习' : '练习刷题' }}</h1>
          <span v-if="question" class="badge-type-pill">{{ formatType(question.type) }}</span>
          <button v-if="question" type="button" class="badge-index-pill btn-sheet-trigger-pill" @click="showSheetModal = true" title="点击打开答题卡">
            <small>{{ index + 1 }} / {{ questions.length }}</small> 📑 答题卡
          </button>
        </div>
      </div>
      <div class="header-actions">
        <!-- 桌面端平铺操作 -->
        <button type="button" class="secondary-btn btn-help-guide desktop-only-btn" @click="showHelpTip = !showHelpTip" title="操作与快捷键指南">
          💡 操作指南
        </button>
        <button type="button" class="btn-flag desktop-only-btn" :class="{ active: isWeak }" @click="toggleWeak">
          {{ isWeak ? '已标薄弱' : '标记薄弱' }}
        </button>
        <button type="button" class="btn-kill desktop-only-btn" @click="handleKill">
          斩杀此题
        </button>
        <button type="button" class="btn-edit-question desktop-only-btn" @click="toggleEditQuestion">
          {{ isEditingQuestion ? '取消编辑' : '编辑题目' }}
        </button>
        <button type="button" class="primary btn-header-complete" @click="complete">交卷</button>

        <!-- 移动端右上角“更多 ⋯”菜单 -->
        <div class="mobile-more-wrapper mobile-only-inline">
          <button type="button" class="btn-help-mobile" @click="showHelpTip = !showHelpTip" title="操作指南">
            💡
          </button>
          <button type="button" class="btn-more-menu" @click="showMoreMenu = !showMoreMenu" aria-label="更多操作">
            ⋯
          </button>
          <div v-if="showMoreMenu" class="mobile-dropdown-menu" @click="showMoreMenu = false">
            <button type="button" class="dropdown-item" :class="{ active: isWeak }" @click="toggleWeak">
              {{ isWeak ? '★ 取消薄弱' : '☆ 标记薄弱' }}
            </button>
            <button type="button" class="dropdown-item text-danger" @click="handleKill">
              ⚡ 斩杀此题
            </button>
            <button type="button" class="dropdown-item" @click="toggleEditQuestion">
              ✎ {{ isEditingQuestion ? '取消编辑' : '编辑题目' }}
            </button>
          </div>
        </div>
      </div>
    </header>

    <!-- 快捷键与操作指南弹窗 (轻量弹出，零侵占刷题黄金视野) -->
    <div v-if="showHelpTip" class="help-tip-backdrop" @click.self="showHelpTip = false">
      <div class="help-tip-dialog" role="dialog" aria-modal="true">
        <div class="help-tip-header">
          <h3>💡 刷题操作与快捷键指南</h3>
          <button type="button" class="btn-close-tip" @click="showHelpTip = false">✕</button>
        </div>
        <div class="help-tip-body">
          <div class="tip-section">
            <strong>⌨️ 键盘盲操快捷键</strong>
            <ul>
              <li><kbd>A</kbd> / <kbd>B</kbd> / <kbd>C</kbd> / <kbd>D</kbd>：直接选中对应选项</li>
              <li><kbd>Enter ↵</kbd>：提交作答（或交卷）</li>
              <li><kbd>Space ␣</kbd> 或 <kbd>→</kbd>：下一题</li>
              <li><kbd>←</kbd> 或 <kbd>K</kbd>：上一题</li>
              <li><kbd>F</kbd>：标记 / 取消薄弱</li>
              <li><kbd>1</kbd> ~ <kbd>4</kbd>：FSRS 记忆评级 (1-重来 2-困难 3-良好 4-简单)</li>
            </ul>
          </div>
          <div class="tip-section">
            <strong>📱 移动端手势</strong>
            <p>题目卡片区域支持左滑下一题、右滑上一题（已自动排除文本输入区防误触）。</p>
          </div>
          <div class="tip-section">
            <strong>📑 快速答题卡</strong>
            <p>随时点击顶栏的 <strong>“{{ index + 1 }}/{{ questions.length }} 📑 答题卡”</strong> 即可呼出全卷面板并直达未做题。</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 答题卡抽屉 / 快速跳转面板 (移动端底部抽屉，桌面端居中弹窗) -->
    <div v-if="showSheetModal" class="sheet-modal-backdrop" @click.self="showSheetModal = false" data-testid="practice-sheet-drawer">
      <div class="sheet-modal-drawer">
        <div class="sheet-drawer-header">
          <div class="sheet-drawer-title">
            <h3>答题卡</h3>
            <span class="sheet-stats-pill">已答 {{ answeredCount }} / {{ questions.length }} 题</span>
          </div>
          <button type="button" class="btn-close-sheet" @click="showSheetModal = false">✕</button>
        </div>

        <div class="sheet-quick-actions">
          <button type="button" class="btn-jump-next-unanswered" @click="jumpNextUnanswered">
            ⏭ 跳至下一道未做题
          </button>
        </div>

        <div class="sheet-legend-bar">
          <span class="legend-item"><span class="legend-dot unanswered"></span> 未答</span>
          <span class="legend-item"><span class="legend-dot correct"></span> 正确</span>
          <span class="legend-item"><span class="legend-dot incorrect"></span> 错误</span>
          <span class="legend-item"><span class="legend-dot partial"></span> 漏选</span>
        </div>

        <div class="sheet-numbers-grid">
          <button
            v-for="(qItem, qIdx) in questions"
            :key="qItem.id"
            type="button"
            class="sheet-num-btn"
            :class="getSheetButtonClass(qItem.id, qIdx)"
            @click="goTo(qIdx)"
          >
            {{ qIdx + 1 }}
          </button>
        </div>
      </div>
    </div>


    <p v-if="loading">正在加载题目…</p>
    <section v-else-if="question" class="question-card">
      <!-- 离线暂存提示 -->
      <div v-if="offlineNotice" class="offline-banner" data-testid="offline-banner">
        <span>{{ offlineNotice }}</span>
        <button type="button" class="btn-sync-offline" @click="syncOfflineEdits">重试重放同步</button>
      </div>

      <!-- 题目编辑面板 (EE-011: 支持完整题干、选项、题型、答案、难度、解析与标签编辑) -->
      <div v-if="isEditingQuestion" class="question-edit-panel" data-testid="question-edit-panel">
        <h3>编辑题目 (基于版本 v{{ question.version_number }})</h3>
        <div class="edit-form-grid">
          <label class="form-row">
            <span>题干：</span>
            <textarea v-model="editStem" class="input-edit-stem" rows="3"></textarea>
          </label>
          <div class="form-row-group">
            <label>
              <span>题型：</span>
              <select v-model="editType" class="select-edit-type">
                <option value="SINGLE">单选题</option>
                <option value="MULTI">多选题</option>
                <option value="JUDGE">判断题</option>
                <option value="ESSAY">主观/简答题</option>
              </select>
            </label>
            <label>
              <span>难度：</span>
              <select v-model.number="editDifficulty" class="select-edit-diff">
                <option :value="1">1 (入门)</option>
                <option :value="2">2 (较易)</option>
                <option :value="3">3 (中等)</option>
                <option :value="4">4 (较难)</option>
                <option :value="5">5 (极难)</option>
              </select>
            </label>
            <label>
              <span>标准答案：</span>
              <input v-model="editAnswer" class="input-edit-answer" placeholder="如 A / AB / T / F" />
            </label>
          </div>
          <div v-if="editType === 'SINGLE' || editType === 'MULTI' || editType === 'JUDGE'" class="options-edit-block">
            <div class="options-header">
              <span>选项列表：</span>
              <button type="button" class="btn-add-option" @click="addOption">+ 添加选项</button>
            </div>
            <div v-for="(opt, oIdx) in editOptions" :key="oIdx" class="option-edit-row">
              <input v-model="opt.key" class="opt-key-input" placeholder="标识" style="width: 3.5rem;" />
              <input v-model="opt.text" class="opt-text-input" placeholder="选项内容" style="flex: 1;" />
              <button type="button" class="btn-del-option" @click="removeOption(oIdx)">删除</button>
            </div>
          </div>
          <label class="form-row">
            <span>解析说明：</span>
            <textarea v-model="editExplanation" class="input-edit-exp" rows="2"></textarea>
          </label>
          <label class="form-row">
            <span>标签（逗号分隔）：</span>
            <input v-model="editTags" class="input-edit-tags" placeholder="如：重点, 逻辑推理" />
          </label>
          <div class="edit-regrade-option" style="margin: 0.5rem 0; padding: 0.5rem; background: var(--bg-secondary, #f8fafc); border-radius: 6px;">
            <label style="display: flex; align-items: center; gap: 0.5rem; font-size: 0.85rem; cursor: pointer;">
              <input type="checkbox" v-model="editRegradeHistory" class="checkbox-regrade-history" />
              <span>可控历史重判：修改标准答案后，同步重判历史作答并重算 FSRS 状态与学习记录</span>
            </label>
          </div>
        </div>
        <div class="edit-actions">
          <button type="button" @click="isEditingQuestion = false">取消</button>
          <button type="button" class="primary btn-save-question-edit" @click="saveQuestionEdit">保存新版本</button>
        </div>
      </div>

      <!-- 多端并发修改冲突保留与选择横幅 (基于服务端真实冲突检测) -->
      <div v-if="activeConflict || conflictResolvedMessage" class="conflict-banner" data-testid="conflict-banner">
        <div v-if="activeConflict" class="conflict-header">
          <span class="conflict-badge">⚠️ 检测到多端并发编辑冲突：您基于版本 v{{ activeConflict.base_version_number }} 的修改与服务端最新版本 v{{ activeConflict.server_version_number }} 发生冲突（双方版本均已完整保留在历史中）</span>
          <button type="button" class="btn-conflict-toggle" @click="showConflictModal = !showConflictModal">
            {{ showConflictModal ? '收起冲突比对' : '比对并选择最终采用版本' }}
          </button>
        </div>
        <p v-if="conflictResolvedMessage" class="conflict-resolved-msg">{{ conflictResolvedMessage }}</p>

        <div v-if="showConflictModal" class="conflict-list" data-testid="conflict-list">
          <div
            v-for="v in questionVersions"
            :key="v.id"
            class="conflict-version-item"
            :class="{ active: v.version_number === question.version_number }"
            :data-testid="`conflict-version-${v.version_number}`"
          >
            <div class="conflict-version-meta">
              <strong>版本 v{{ v.version_number }}</strong>
              <small>{{ v.created_at ? v.created_at.slice(0, 19).replace('T', ' ') : '' }}</small>
              <span v-if="v.version_number === question.version_number" class="badge-current">当前生效</span>
            </div>
            <div class="conflict-version-body">
              <p><strong>题干：</strong>{{ v.stem }}</p>
              <p><strong>答案：</strong>{{ v.answer }}</p>
              <p v-if="v.explanation"><strong>解析：</strong>{{ v.explanation }}</p>
            </div>
            <div class="conflict-version-actions">
              <button
                type="button"
                class="btn-adopt-version primary"
                :disabled="!activeConflict && v.version_number === question.version_number"
                @click="handleAdoptQuestionVersion(v)"
              >
                {{ !activeConflict && v.version_number === question.version_number ? '当前已是此版本' : `采用此版本 (v${v.version_number})` }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div :key="question.id" class="question-slide-wrapper" :class="slideTransition">
          <div class="practice-split-grid">
            <div class="practice-split-left">
              <div class="stem-box">
                <h2>{{ question.stem }}</h2>
              </div>

              <!-- 客观选择题 -->
              <div v-if="question.options?.length" class="options-group">
                <label
                  v-for="option in question.options"
                  :key="option.key"
                  class="option"
                  :class="{
                    selected: isOptionSelected(option.key),
                    'option-correct': result && isCorrectOption(option.key),
                    'option-wrong': result && isWrongOption(option.key)
                  }"
                  @click.prevent="selectOption(option.key)"
                >
                  <kbd class="key-cap" :title="`按键盘 ${option.key} 键直接选择`">{{ option.key }}</kbd>
                  <input
                    :type="question.type === 'MULTI' ? 'checkbox' : 'radio'"
                    :name="`practice-${question.id}`"
                    :value="option.key"
                    :checked="isOptionSelected(option.key)"
                    :disabled="Boolean(result)"
                  />
                  <span class="option-text-content">{{ option.content }}</span>
                  <span v-if="result && isCorrectOption(option.key)" class="inline-verdict-badge correct">✔ 正确答案</span>
                  <span v-if="result && isWrongOption(option.key)" class="inline-verdict-badge wrong">✘ 你的作答</span>
                </label>
              </div>

              <!-- 主观题 / 填空题文本输入 -->
              <div v-else class="text-answer-box">
                <label>
                  <span>作答内容</span>
                  <textarea
                    v-model="textAnswer"
                    :disabled="Boolean(result)"
                    rows="4"
                    placeholder="输入你的答案或解题思路…"
                  />
                </label>
              </div>

              <!-- 紧凑即时判分结果摘要条 (无需向下滚动即可直观看到对错与标准答案) -->
              <div v-if="result" class="quick-verdict-bar" :class="result.correctness.toLowerCase()">
                <div class="verdict-status-title">
                  <span class="verdict-icon">{{ result.correctness === 'CORRECT' ? '🎉' : result.correctness === 'PARTIAL' ? '⚠️' : '❌' }}</span>
                  <strong>{{ formatVerdictTitle(question.type, result.correctness, result.is_objective) }}</strong>
                </div>
                <div class="verdict-text-inline">
                  <span v-if="question.answer">标准答案：<strong class="text-correct">{{ question.answer }}</strong></span>
                  <span v-if="hasAnswer">你的作答：<strong :class="result.correctness === 'CORRECT' ? 'text-correct' : 'text-danger'">{{ formatUserAnswer(question.options?.length ? answer : textAnswer) }}</strong></span>
                  <span v-if="result.is_objective && result.score_ratio !== undefined">得分率：{{ Math.round((result.score_ratio || 0) * 100) }}%</span>
                </div>
              </div>
            </div>

            <div class="practice-split-right">
              <!-- 判分结果卡片 -->
              <section v-if="result" class="result-card">
                <div class="result-header">
                  <strong :class="result.correctness.toLowerCase()">
                    {{ formatVerdictTitle(question.type, result.correctness, result.is_objective) }}
                    <span v-if="result.correctness === 'CORRECT'" class="sub-correct-badge">（完全正确）</span>
                  </strong>
                  <span v-if="result.is_objective">得分比例：{{ result.score_ratio }}</span>
                </div>

                <!-- FSRS 记忆评级交互区 (驱动下次复习时间) -->
                <div v-if="session?.mode === 'FSRS' || session?.mode === 'MISTAKE'" class="fsrs-rating-box">
                  <h4>FSRS 记忆评级 (驱动下次复习时间，快捷键 1-4)：</h4>
                  <div class="fsrs-buttons">
                    <button
                      type="button"
                      class="rating-btn again"
                      :class="{ selected: selectedFsrsRating === 1 }"
                      @click="submitRating(1)"
                    >
                      1 - 重来 (Again)
                    </button>
                    <button
                      type="button"
                      class="rating-btn hard"
                      :disabled="result.correctness === 'INCORRECT'"
                      :class="{ selected: selectedFsrsRating === 2 }"
                      @click="submitRating(2)"
                    >
                      2 - 困难 (Hard)
                    </button>
                    <button
                      type="button"
                      class="rating-btn good"
                      :disabled="result.correctness !== 'CORRECT'"
                      :class="{ selected: selectedFsrsRating === 3 }"
                      @click="submitRating(3)"
                    >
                      3 - 良好 (Good)
                    </button>
                    <button
                      type="button"
                      class="rating-btn easy"
                      :disabled="result.correctness !== 'CORRECT'"
                      :class="{ selected: selectedFsrsRating === 4 }"
                      @click="submitRating(4)"
                    >
                      4 - 简单 (Easy)
                    </button>
                  </div>
                  <p v-if="fsrsRatingStatus" class="fsrs-status">{{ fsrsRatingStatus }}</p>
                </div>

                <div v-if="question.explanation" class="official-explanation">
                  <h4>官方解析</h4>
                  <p>{{ question.explanation }}</p>
                </div>

                <!-- AI 助教入口卡片 (位于官方解析下方，阅读解析后可直接展开提问) -->
                <div class="ai-assistant-entry-block">
                  <div class="ai-entry-meta">
                    <span class="ai-badge">🤖 AI 深度助教</span>
                    <span class="ai-desc">考点深度剖析 · 联网证据核查 · 变式题拓展</span>
                  </div>
                  <button
                    type="button"
                    class="secondary-btn btn-toggle-ai-card"
                    :class="{ active: showAiPanel }"
                    @click="toggleAiPanel"
                  >
                    {{ showAiPanel ? '收起助教 ▲' : '🤖 向 AI 助教提问 / 展开解析 ▼' }}
                  </button>
                </div>
              </section>

              <!-- 桌面端未判分时的专注作答状态卡 -->
              <div v-else class="practice-answering-placeholder desktop-only-block">
                <div class="placeholder-icon">✍️</div>
                <div class="placeholder-content">
                  <h4>专注作答中</h4>
                  <p>请在左侧选择或输入你的答案。</p>
                  <p>作答后点击底栏“<strong>提交答案</strong>”或直接敲击 <strong>Enter</strong> 键即可立即查看评级与解析。</p>
                </div>
              </div>

      <!-- AI 助教与多版本解释面板 -->
      <section v-if="showAiPanel" class="ai-panel">
        <div class="ai-toolbar">
          <h3>AI 助教与多版本解释</h3>
          <div class="ai-btn-group">
            <button type="button" :disabled="aiLoading || generatingVariant" @click="generateExplanation">
              {{ aiLoading ? '正在分析…' : '重新生成 AI 解释' }}
            </button>
            <button type="button" :disabled="aiLoading || generatingVariant" @click="handleVerifyWeb">
              {{ aiLoading ? '正在核查…' : '联网核查证据' }}
            </button>
            <button type="button" :disabled="aiLoading || generatingVariant" @click="handleGenerateVariant">
              {{ generatingVariant ? '正在生成草稿…' : '生成变式题草稿' }}
            </button>
          </div>
        </div>

        <!-- 自定义追问输入框 -->
        <div class="ai-ask-box">
          <input
            v-model="customQuery"
            type="text"
            placeholder="对这道题有疑问？输入追问内容，如：为什么选 B 不选 C…"
            @keyup.enter="askCustomQuery"
          />
          <button type="button" :disabled="!customQuery.trim() || aiLoading" @click="askCustomQuery">
            追问
          </button>
        </div>

        <p v-if="aiStatusMessage" class="ai-status">{{ aiStatusMessage }}</p>

        <!-- 连续追问对话历史 (MiaowTest 对话模型) -->
        <div v-if="chatMessages.length" class="ai-chat-thread">
          <h4>连续追问历史 ({{ chatMessages.length }})</h4>
          <div v-for="msg in chatMessages" :key="msg.id" class="chat-bubble" :class="msg.role">
            <div class="chat-sender">
              <strong>{{ msg.role === 'user' ? '我的追问' : 'AI 助教解答' }}</strong>
              <small class="muted">#{{ msg.sequence }}</small>
            </div>
            <p class="chat-text">{{ msg.content }}</p>
          </div>
        </div>

        <!-- 历史解释版本列表 -->
        <div v-if="answerVersions.length" class="ai-history">
          <h4>解释版本历史 ({{ answerVersions.length }})</h4>
          <article
            v-for="version in answerVersions"
            :key="version.id"
            class="version-card"
            :class="{ adopted: version.is_adopted }"
          >
            <div class="version-meta">
              <span class="source-tag">{{ formatSource(version.source) }}</span>
              <span v-if="version.is_adopted" class="badge-adopted">当前主解释</span>
              <small class="muted">{{ version.created_at ? version.created_at.slice(0, 19).replace('T', ' ') : '' }}</small>
            </div>

            <!-- 查看模式 -->
            <div v-if="editingVersionId !== version.id" class="version-content">
              <p class="content-text">{{ version.content }}</p>

              <!-- 联网证据展示 -->
              <div v-if="version.evidence?.length" class="evidence-box">
                <h5>联网检索证据依据 ({{ version.evidence.length }})</h5>
                <ul>
                  <li v-for="(ev, idx) in version.evidence" :key="idx">
                    <strong>{{ ev.title }}</strong>
                    <span v-if="ev.snippet"> - {{ ev.snippet }}</span>
                    <a v-if="ev.url" :href="ev.url" target="_blank" rel="noopener">来源链接</a>
                  </li>
                </ul>
              </div>

              <div class="version-actions">
                <button
                  v-if="!version.is_adopted"
                  type="button"
                  class="btn-adopt"
                  @click="adopt(version.id)"
                >采纳为主解释</button>
                <button
                  type="button"
                  @click="startEdit(version)"
                >编辑并存为个人解释</button>
              </div>
            </div>

            <!-- 编辑模式 -->
            <div v-else class="version-edit-box">
              <textarea v-model="editDraft" rows="4" />
              <div class="version-edit-actions">
                <button type="button" @click="editingVersionId = null">取消</button>
                <button type="button" class="primary" :disabled="!editDraft.trim()" @click="savePersonalExplanation">
                  保存为个人解释版本
                </button>
              </div>
            </div>
          </article>
        </div>
        <p v-else class="muted">暂无历史解释，点击上方按钮让 AI 展开剖析。</p>
      </section>
        </div>
      </div>
    </div>
</section>
<p v-else>本题库暂无可练习题目。</p>

<!-- 屏幕底部固定操作底栏 (屏幕Y坐标永久固定，零位移，绝不被答案挤压) -->
<footer v-if="question" class="ergonomic-action-bar" data-testid="practice-action-bar">
  <div class="action-bar-inner">
    <div class="action-left">
      <button
        type="button"
        class="secondary-btn btn-prev-question"
        :disabled="index === 0"
        @click="prev"
        title="快捷键：← 或 K"
      >
        ← 上一题
        <kbd class="hotkey-badge">←</kbd>
      </button>
    </div>

    <!-- 键盘盲操指南条 (直观呈现，无需猜测，移动端自动隐藏) -->
    <div class="hotkey-helper-bar">
      <span class="hotkey-item"><kbd>A-D</kbd> 选选项</span>
      <span class="hotkey-item"><kbd>Enter</kbd> 提交/继续</span>
      <span class="hotkey-item"><kbd>Space</kbd> 下一题</span>
      <span class="hotkey-item"><kbd>←</kbd> 上一题</span>
      <span class="hotkey-item"><kbd>F</kbd> 标薄弱</span>
    </div>

    <div class="action-right">
      <!-- 次要操作：未作答时提供跳过按钮 -->
      <button
        v-if="!result && index < questions.length - 1"
        type="button"
        class="secondary-btn btn-skip-unanswered"
        @click="next"
        title="快捷键：Space 或 →"
      >
        <span>跳过 →</span>
      </button>

      <!-- 核心主按钮：提交与下一题锁定在相同物理基准位置，消除跳动与误触 -->
      <button
        v-if="!result"
        type="button"
        class="primary btn-submit-answer btn-action-fixed-primary"
        :disabled="!hasAnswer && question.options?.length"
        @click="submit"
        title="快捷键：Enter"
      >
        <span>提交答案</span>
        <kbd class="hotkey-badge">Enter ↵</kbd>
      </button>

      <!-- 已作答状态：原位推进到下一题或交卷 -->
      <template v-else>
        <button
          v-if="index < questions.length - 1"
          type="button"
          class="primary btn-next-question btn-action-fixed-primary"
          @click="next"
          title="快捷键：Space 或 →"
        >
          <span>下一题 →</span>
          <kbd class="hotkey-badge">Space ␣</kbd>
        </button>
        <button
          v-else
          type="button"
          class="primary btn-finish-session btn-action-fixed-primary"
          @click="complete"
          title="快捷键：Enter"
        >
          <span>查看报告并交卷 🎉</span>
        </button>
      </template>
    </div>
  </div>
</footer>

  </main>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useAuthStore } from '../stores/authStore'
import { getSession, getSessionQuestions, submitAttempt, completeSession } from '../api/practice'
import { getQuestion, listQuestionVersions, updateQuestion, getQuestionConflict, resolveQuestionConflict, regradeQuestion } from '../api/questions'
import { generateAnswer, listAnswerVersions, adoptAnswer, saveCandidate, verifyWeb, listQuestionConversations, listConversationMessages, sendChatMessage, generateVariant } from '../api/ai'
import { markWeak, unmarkWeak } from '../api/learning'
import { killQuestion } from '../api/kills'
import { triggerSyncEvent } from '../api/sync'
import { formatVerdictTitle, findNextUnansweredIndex, isSwipeGestureValid } from '../domain/exam.js'

const props = defineProps({ token: { type: String, required: true }, sessionId: { type: String, required: true } })
const emit = defineEmits(['back', 'completed'])

const auth = useAuthStore()

function getOfflineQueueKey() {
  const uid = auth.user?.value?.id || auth.user?.value?.username || 'user'
  return `easyexam_offline_question_edits_${uid}`
}

const session = ref(null)
const questions = ref([])
const index = ref(0)
const answer = ref([])
const textAnswer = ref('')
const result = ref(null)
const sessionAnswers = ref({}) // questionId -> { answer, textAnswer, result, showAiPanel, selectedFsrsRating }
const showSheetModal = ref(false)
const showMoreMenu = ref(false)
const showHelpTip = ref(false)
const slideTransition = ref('slide-next')
const selectedFsrsRating = ref(null)
const fsrsRatingStatus = ref('')
const loading = ref(true)
const answerVersions = ref([])
const chatMessages = ref([])
const activeConversationId = ref(null)
const showAiPanel = ref(false)
const aiLoading = ref(false)
const generatingVariant = ref(false)
const aiStatusMessage = ref('')
const customQuery = ref('')
const editingVersionId = ref(null)
const editDraft = ref('')
const isWeak = ref(false)
const questionVersions = ref([])
const activeConflict = ref(null)
const showConflictModal = ref(false)
const conflictResolvedMessage = ref('')
const isEditingQuestion = ref(false)
const editStem = ref('')
const editType = ref('SINGLE')
const editOptions = ref([])
const editAnswer = ref('')
const editExplanation = ref('')
const editDifficulty = ref(3)
const editTags = ref('')
const editRegradeHistory = ref(false)
const offlineNotice = ref('')


const question = computed(() => questions.value[index.value])

const hasAnswer = computed(() => {
  if (!question.value) return false
  if (question.value.options?.length) {
    return Array.isArray(answer.value) ? answer.value.length > 0 : Boolean(answer.value)
  }
  return textAnswer.value.trim().length > 0
})

function selectOption(key) {
  if (result.value) return
  if (question.value?.type === 'MULTI') {
    const list = Array.isArray(answer.value) ? [...answer.value] : []
    const idx = list.indexOf(key)
    if (idx >= 0) list.splice(idx, 1)
    else list.push(key)
    answer.value = list
  } else {
    answer.value = key
  }
  saveCurrentQuestionState()
}

function isOptionSelected(key) {
  if (question.value?.type === 'MULTI') {
    return Array.isArray(answer.value) && answer.value.includes(key)
  }
  return answer.value === key
}

function formatType(type) {
  const map = {
    SINGLE: '单选题',
    MULTI: '多选题',
    JUDGE: '判断题',
    FILL: '填空题',
    ESSAY: '主观题',
    SHORT_ANSWER: '简答题',
    SUBJECTIVE: '论述题',
  }
  return map[String(type || '').toUpperCase()] || String(type || '')
}

function formatSource(source) {
  const map = { AI: 'AI 助教生成', WEB: '联网核查', PERSONAL: '个人定制解释', OFFICIAL: '官方解析' }
  return map[source] || source
}

function normalizedAnswer() {
  if (question.value?.options?.length) {
    if (question.value?.type === 'MULTI') {
      const selected = Array.isArray(answer.value) ? answer.value : [answer.value]
      return [...selected].sort().join('')
    }
    return answer.value
  }
  return textAnswer.value.trim()
}

function isCorrectOption(key) {
  if (!question.value?.answer) return false
  const cleaned = String(question.value.answer).replace(/[,\s]/g, '').toUpperCase()
  return cleaned.includes(String(key).toUpperCase())
}

function isWrongOption(key) {
  return isOptionSelected(key) && !isCorrectOption(key)
}

function formatUserAnswer(val) {
  if (Array.isArray(val)) {
    return val.length ? val.join(', ') : '未作答'
  }
  return val ? String(val) : '未作答'
}

let touchStartX = 0
let touchStartY = 0

function handleTouchStart(e) {
  if (!e.touches || e.touches.length !== 1) return
  const tag = e.target?.tagName?.toLowerCase()
  if (tag === 'textarea' || tag === 'input' || tag === 'pre' || tag === 'code' || tag === 'button') return
  touchStartX = e.touches[0].clientX
  touchStartY = e.touches[0].clientY
}

function handleTouchEnd(e) {
  if (!e.changedTouches || e.changedTouches.length !== 1) return
  const tag = e.target?.tagName?.toLowerCase()
  if (tag === 'textarea' || tag === 'input' || tag === 'pre' || tag === 'code' || tag === 'button') return
  const touchEndX = e.changedTouches[0].clientX
  const touchEndY = e.changedTouches[0].clientY
  const gesture = isSwipeGestureValid(touchStartX, touchStartY, touchEndX, touchEndY)
  if (gesture === 'prev') {
    prev()
  } else if (gesture === 'next') {
    next()
  }
}

function saveCurrentQuestionState() {
  if (!question.value) return
  const qid = question.value.id
  sessionAnswers.value[qid] = {
    answer: Array.isArray(answer.value) ? [...answer.value] : answer.value,
    textAnswer: textAnswer.value,
    result: result.value,
    showAiPanel: showAiPanel.value,
    selectedFsrsRating: selectedFsrsRating.value,
  }
}

function restoreQuestionState(targetIndex) {
  saveCurrentQuestionState()
  index.value = targetIndex
}

async function handleSyncedEvents(e) {
  const detail = e.detail || {}
  const events = Array.isArray(detail) ? detail : (detail.events || [])
  if (detail.userId && props.user?.id && detail.userId !== props.user.id) {
    return
  }
  if (!question.value) return
  const qEvent = events.find(ev => ev.aggregate_type === 'QUESTION' && ev.aggregate_id === question.value?.id)
  if (qEvent) {
    try {
      const fresh = await getQuestion(props.token, question.value.id)
      if (fresh && fresh.version_number !== question.value.version_number) {
        questions.value[index.value] = fresh
        questionVersions.value = await listQuestionVersions(props.token, fresh.id)
        const conf = await getQuestionConflict(props.token, fresh.id)
        activeConflict.value = conf?.has_conflict ? conf.conflict : null
      }
    } catch (_) {}
  }
}

onMounted(async () => {
  window.addEventListener('online', syncOfflineEdits)
  window.addEventListener('keydown', handleKeyDown)
  window.addEventListener('easyexam:events-synced', handleSyncedEvents)
  try {
    session.value = await getSession(props.token, props.sessionId)
    questions.value = await getSessionQuestions(props.token, props.sessionId)
    await syncOfflineEdits()
  } finally {
    loading.value = false
  }
})

onUnmounted(() => {
  window.removeEventListener('online', syncOfflineEdits)
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('easyexam:events-synced', handleSyncedEvents)
})

watch(question, async (current, oldQuestion) => {
  if (current) {
    const isDifferentQuestion = !oldQuestion || current.id !== oldQuestion.id
    if (isDifferentQuestion) {
      const saved = sessionAnswers.value[current.id]
      if (saved) {
        answer.value = Array.isArray(saved.answer) ? [...saved.answer] : (saved.answer ?? '')
        textAnswer.value = saved.textAnswer ?? ''
        result.value = saved.result ?? null
        showAiPanel.value = saved.showAiPanel ?? false
        selectedFsrsRating.value = saved.selectedFsrsRating ?? null
      } else {
        answer.value = current.type === 'MULTI' ? [] : ''
        textAnswer.value = ''
        result.value = null
        showAiPanel.value = false
        selectedFsrsRating.value = null
      }
      showConflictModal.value = false
      conflictResolvedMessage.value = ''
      isWeak.value = false
      customQuery.value = ''
      editingVersionId.value = null
      fsrsRatingStatus.value = ''
    }
    answerVersions.value = await listAnswerVersions(props.token, current.id)
    try {
      questionVersions.value = await listQuestionVersions(props.token, current.id)
    } catch {
      questionVersions.value = []
    }
    try {
      const conf = await getQuestionConflict(props.token, current.id)
      activeConflict.value = conf?.has_conflict ? conf.conflict : null
    } catch {
      activeConflict.value = null
    }
    if (isDifferentQuestion) {
      try {
        const convs = await listQuestionConversations(props.token, current.id)
        if (convs?.length) {
          activeConversationId.value = convs[0].id
          chatMessages.value = await listConversationMessages(props.token, convs[0].id)
        } else {
          activeConversationId.value = null
          chatMessages.value = []
        }
      } catch {
        chatMessages.value = []
      }
    }
  }
}, { immediate: true })

async function submitRating(rating) {

  if (!question.value) return
  selectedFsrsRating.value = rating
  fsrsRatingStatus.value = '正在更新 FSRS 状态…'
  try {
    const res = await submitAttempt(props.token, props.sessionId, {
      question_id: question.value.id,
      user_answer: normalizedAnswer(),
      fsrs_rating: rating,
    })
    result.value = res
    saveCurrentQuestionState()
    triggerSyncEvent('PRACTICE_RATING', 'SESSION', props.sessionId, { question_id: question.value.id, rating })
    fsrsRatingStatus.value = `已更新 FSRS 评级：${['', '重来(Again)', '困难(Hard)', '良好(Good)', '简单(Easy)'][rating]}，已计算下次复习时间`
  } catch (err) {
    fsrsRatingStatus.value = `评级失败：${err.detail || err.message}`
  }
}

async function submit() {
  if (!hasAnswer.value) return
  result.value = await submitAttempt(props.token, props.sessionId, {
    question_id: question.value.id,
    user_answer: normalizedAnswer(),
  })
  saveCurrentQuestionState()
  triggerSyncEvent('PRACTICE_ATTEMPT', 'SESSION', props.sessionId, { question_id: question.value.id })
  if (result.value?.correctness === 'INCORRECT' && (session.value?.mode === 'FSRS' || session.value?.mode === 'MISTAKE')) {
    selectedFsrsRating.value = 1
    fsrsRatingStatus.value = '答错已自动记录为 Again (重来)'
    if (sessionAnswers.value[question.value.id]) {
      sessionAnswers.value[question.value.id].selectedFsrsRating = 1
    }
  }
}

function toggleAiPanel() {
  showAiPanel.value = !showAiPanel.value
  saveCurrentQuestionState()
}

async function generateExplanation() {
  if (!question.value) return
  aiLoading.value = true
  aiStatusMessage.value = ''
  try {
    const saved = await generateAnswer(props.token, question.value.id, { query: '请结合这道题详细解释解题思路与要点。' })
    answerVersions.value = [saved, ...answerVersions.value]
  } catch (err) {
    aiStatusMessage.value = `生成失败：${err.detail || err.message}`
  } finally {
    aiLoading.value = false
  }
}

async function askCustomQuery() {
  if (!question.value || !customQuery.value.trim()) return
  aiLoading.value = true
  aiStatusMessage.value = ''
  try {
    const parentMsgId = chatMessages.value.length ? chatMessages.value[chatMessages.value.length - 1].id : null
    const res = await sendChatMessage(props.token, question.value.id, {
      content: customQuery.value.trim(),
      conversation_id: activeConversationId.value,
      parent_message_id: parentMsgId,
    })
    activeConversationId.value = res.conversation.id
    chatMessages.value.push(res.user_message)
    chatMessages.value.push(res.assistant_message)
    customQuery.value = ''
  } catch (err) {
    aiStatusMessage.value = `追问失败：${err.detail || err.message}`
  } finally {
    aiLoading.value = false
  }
}

async function handleVerifyWeb() {
  if (!question.value) return
  aiLoading.value = true
  aiStatusMessage.value = ''
  try {
    const saved = await verifyWeb(props.token, question.value.id, { query: question.value.stem })
    answerVersions.value = [saved, ...answerVersions.value]
    if (saved.verification_status === 'UNAVAILABLE') {
      aiStatusMessage.value = '联网检索服务当前未配置或不可用，已保留离线空证据记录。'
    }
  } catch (err) {
    aiStatusMessage.value = `联网核查失败：${err.detail || err.message}`
  } finally {
    aiLoading.value = false
  }
}

async function handleGenerateVariant() {
  if (!question.value) return
  generatingVariant.value = true
  aiStatusMessage.value = ''
  try {
    await generateVariant(props.token, {
      question_id: question.value.id,
      prompt: '请基于此题考点和解题逻辑生成一道高质量的变式题草稿。',
    })
    aiStatusMessage.value = '变式题草稿已生成并暂存！请前往首页【变式草稿箱】审阅并确认入库。'
  } catch (err) {
    aiStatusMessage.value = `生成变式题草稿失败：${err.detail || err.message}`
  } finally {
    generatingVariant.value = false
  }
}

async function adopt(answerId) {
  const saved = await adoptAnswer(props.token, answerId)
  answerVersions.value = answerVersions.value.map(item =>
    item.question_id === saved.question_id ? { ...item, is_adopted: item.id === saved.id } : item
  )
}

function startEdit(version) {
  editingVersionId.value = version.id
  editDraft.value = version.content
}

async function savePersonalExplanation() {
  if (!question.value || !editDraft.value.trim()) return
  try {
    const saved = await saveCandidate(props.token, question.value.id, {
      content: editDraft.value.trim(),
      source: 'PERSONAL',
    })
    answerVersions.value = [saved, ...answerVersions.value]
    editingVersionId.value = null
  } catch (err) {
    alert(`保存失败：${err.detail || err.message}`)
  }
}

async function toggleWeak() {
  if (!question.value) return
  try {
    if (isWeak.value) {
      await unmarkWeak(props.token, question.value.id)
      isWeak.value = false
    } else {
      await markWeak(props.token, question.value.id)
      isWeak.value = true
    }
  } catch (err) {
    alert(`操作失败：${err.detail || err.message}`)
  }
}

async function handleKill() {
  if (!question.value) return
  if (!window.confirm('确定要斩杀此题吗？斩杀后将从普通刷题与错题队列移出，进入斩杀题库（可在“错题与斩杀”中恢复）。')) return
  try {
    await killQuestion(props.token, question.value.id)
    alert('已成功斩杀此题！此题将从普通刷题与错题队列移出，进入斩杀题库。')
    next()
  } catch (err) {
    alert(`斩杀失败：${err.detail || err.message}`)
  }
}

function prev() {
  if (index.value > 0) {
    slideTransition.value = 'slide-prev'
    restoreQuestionState(index.value - 1)
  }
}

function next() {
  if (index.value < questions.value.length - 1) {
    slideTransition.value = 'slide-next'
    restoreQuestionState(index.value + 1)
  }
}

function goTo(targetIdx) {
  if (targetIdx >= 0 && targetIdx < questions.value.length) {
    slideTransition.value = targetIdx > index.value ? 'slide-next' : 'slide-prev'
    restoreQuestionState(targetIdx)
    showSheetModal.value = false
  }
}

function jumpNextUnanswered() {
  const nextIdx = findNextUnansweredIndex(questions.value, sessionAnswers.value, index.value)
  if (nextIdx >= 0) {
    goTo(nextIdx)
  } else {
    alert('所有题目均已作答！')
  }
}

const answeredCount = computed(() => {
  return Object.values(sessionAnswers.value).filter(s => {
    if (s?.result) return true
    if (Array.isArray(s?.answer) && s.answer.length > 0) return true
    if (typeof s?.answer === 'string' && s.answer.trim().length > 0) return true
    if (s?.textAnswer && s.textAnswer.trim().length > 0) return true
    return false
  }).length
})

function getSheetButtonClass(qid, qIdx) {
  const isCurrent = qIdx === index.value
  const saved = sessionAnswers.value[qid]
  const res = saved?.result
  const isAnswered = Boolean(res || (Array.isArray(saved?.answer) ? saved.answer.length : saved?.answer || saved?.textAnswer))

  return {
    current: isCurrent,
    answered: isAnswered && !res,
    correct: res?.correctness === 'CORRECT',
    incorrect: res?.correctness === 'INCORRECT',
    partial: res?.correctness === 'PARTIAL',
  }
}

function handleKeyDown(e) {
  const targetTag = e.target?.tagName?.toLowerCase()
  if (targetTag === 'input' || targetTag === 'textarea' || targetTag === 'select') {
    return
  }

  const key = e.key.toUpperCase()

  // 1. Select options via A, B, C, D... or 1, 2, 3, 4...
  if (question.value?.options?.length && !result.value) {
    const letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    let optKey = null
    if (letters.includes(key)) {
      optKey = key
    } else if (['1', '2', '3', '4', '5', '6', '7', '8'].includes(e.key)) {
      const idx = parseInt(e.key, 10) - 1
      if (idx >= 0 && idx < question.value.options.length) {
        optKey = question.value.options[idx].key
      }
    }
    if (optKey) {
      const exists = question.value.options.some(o => o.key === optKey)
      if (exists) {
        e.preventDefault()
        selectOption(optKey)
        return
      }
    }
  }

  // 2. FSRS rating 1-4 when result exists and in FSRS/MISTAKE mode
  if (result.value && (session.value?.mode === 'FSRS' || session.value?.mode === 'MISTAKE')) {
    if (['1', '2', '3', '4'].includes(e.key)) {
      const rating = parseInt(e.key, 10)
      const isAllowed = (rating === 1) ||
        (rating === 2 && result.value.correctness !== 'INCORRECT') ||
        (rating >= 3 && result.value.correctness === 'CORRECT')
      if (isAllowed) {
        e.preventDefault()
        submitRating(rating)
        return
      }
    }
  }

  // 3. Submit or Next on Enter
  if (e.key === 'Enter') {
    if (!result.value && hasAnswer.value) {
      e.preventDefault()
      submit()
      return
    } else if (result.value) {
      e.preventDefault()
      if (index.value < questions.value.length - 1) {
        next()
      } else {
        complete()
      }
      return
    }
  }

  // 4. Next on Space, ArrowRight, J (allow even if !result)
  if (e.key === ' ' || e.key === 'ArrowRight' || key === 'J') {
    if (index.value < questions.value.length - 1) {
      e.preventDefault()
      next()
      return
    }
  }

  // 5. Prev on ArrowLeft, K
  if (e.key === 'ArrowLeft' || key === 'K') {
    if (index.value > 0) {
      e.preventDefault()
      prev()
      return
    }
  }

  // 6. Toggle weak on F
  if (key === 'F') {
    e.preventDefault()
    toggleWeak()
    return
  }
}


function toggleEditQuestion() {
  if (!question.value) return
  isEditingQuestion.value = !isEditingQuestion.value
  if (isEditingQuestion.value) {
    editStem.value = question.value.stem || ''
    editType.value = question.value.type || 'SINGLE'
    editOptions.value = (question.value.options || []).map(o => ({ ...o }))
    editAnswer.value = question.value.answer || ''
    editExplanation.value = question.value.explanation || ''
    editDifficulty.value = question.value.difficulty ?? 3
    editTags.value = Array.isArray(question.value.tags) ? question.value.tags.join(', ') : (question.value.tags || '')
  }
}

function addOption() {
  const letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
  const nextKey = letters[editOptions.value.length] || `Option${editOptions.value.length + 1}`
  editOptions.value.push({ key: nextKey, text: '' })
}

function removeOption(idx) {
  editOptions.value.splice(idx, 1)
}

async function saveQuestionEdit() {
  if (!question.value || !editStem.value.trim()) return
  const tagsList = editTags.value
    ? editTags.value.split(/[,，\s]+/).map(t => t.trim()).filter(Boolean)
    : []
  const payload = {
    stem: editStem.value.trim(),
    type: editType.value,
    options: editOptions.value,
    answer: editAnswer.value.trim(),
    explanation: editExplanation.value.trim(),
    difficulty: Number(editDifficulty.value) || 3,
    tags: tagsList,
    base_version_number: question.value.version_number,
    regrade_history: editRegradeHistory.value,
    apply_fsrs: true,
  }
  const storageKey = 'easyexam_offline_question_edits'
  const userScopedKey = getOfflineQueueKey()
  const uid = auth.user?.value?.id || auth.user?.value?.username || 'user'
  const queueItem = { userId: uid, questionId: question.value.id, payload, queuedAt: Date.now() }
  if (!window.navigator.onLine) {
    const queue = JSON.parse(localStorage.getItem(storageKey) || '[]')
    queue.push(queueItem)
    localStorage.setItem(storageKey, JSON.stringify(queue))
    localStorage.setItem(userScopedKey, JSON.stringify(queue))
    offlineNotice.value = '当前网络处于离线状态，修改已暂存本地隔离队列，网络恢复后将自动重放同步至服务端。'
    isEditingQuestion.value = false
    return
  }
  try {
    const updated = await updateQuestion(props.token, question.value.id, payload)
    triggerSyncEvent('QUESTION_UPDATED', 'QUESTION', updated.id, { version_number: updated.version_number })
    isEditingQuestion.value = false
    questions.value[index.value] = updated
    questionVersions.value = await listQuestionVersions(props.token, updated.id)
    const conf = await getQuestionConflict(props.token, updated.id)
    activeConflict.value = conf?.has_conflict ? conf.conflict : null
  } catch {
    const queue = JSON.parse(localStorage.getItem(storageKey) || '[]')
    queue.push(queueItem)
    localStorage.setItem(storageKey, JSON.stringify(queue))
    localStorage.setItem(userScopedKey, JSON.stringify(queue))
    offlineNotice.value = '连接服务端失败，修改已自动暂存本地隔离队列，网络恢复后将自动重放同步至服务端。'
    isEditingQuestion.value = false
  }
}

let isSyncing = false
async function syncOfflineEdits() {
  if (isSyncing) return
  isSyncing = true
  const storageKey = 'easyexam_offline_question_edits'
  const userScopedKey = getOfflineQueueKey()
  const uid = auth.user?.value?.id || auth.user?.value?.username || 'user'
  try {
    const raw = localStorage.getItem(storageKey) || localStorage.getItem(userScopedKey)
    if (!raw) return
    let queue = JSON.parse(raw)
    if (!queue.length) return
    const userItems = queue.filter(item => !item.userId || item.userId === uid)
    if (!userItems.length) return
    offlineNotice.value = '正在将离线修改逐项重放至服务端…'

    // Process atomically item-by-item: NEVER wipe queue before confirmed completion!
    while (queue.length > 0) {
      const item = queue[0]
      if (item.userId && item.userId !== uid) {
        break
      }
      try {
        const updated = await updateQuestion(props.token, item.questionId, item.payload)
        triggerSyncEvent('QUESTION_UPDATED', 'QUESTION', updated.id, { version_number: updated.version_number })
        if (question.value && question.value.id === item.questionId) {
          questions.value[index.value] = updated
          questionVersions.value = await listQuestionVersions(props.token, updated.id)
          const conf = await getQuestionConflict(props.token, updated.id)
          activeConflict.value = conf?.has_conflict ? conf.conflict : null
        }
        // Remove item only upon confirmed success
        queue.shift()
        localStorage.setItem(storageKey, JSON.stringify(queue))
        localStorage.setItem(userScopedKey, JSON.stringify(queue))
      } catch (err) {
        // Keep remaining items in queue on network or server error
        break
      }
    }
    if (queue.length) {
      offlineNotice.value = `仍有 ${queue.length} 条离线修改待同步`
    } else {
      offlineNotice.value = ''
      localStorage.removeItem(storageKey)
      localStorage.removeItem(userScopedKey)
    }
  } finally {
    isSyncing = false
  }
}

async function handleAdoptQuestionVersion(targetVer) {
  try {
    let updated
    if (activeConflict.value) {
      updated = await resolveQuestionConflict(props.token, question.value.id, targetVer.version_number)
      activeConflict.value = null
    } else {
      updated = await updateQuestion(props.token, question.value.id, {
        stem: targetVer.stem,
        type: targetVer.type || question.value.type || 'SINGLE',
        options: targetVer.options || question.value.options || [],
        answer: targetVer.answer || question.value.answer || '',
        explanation: targetVer.explanation || question.value.explanation || '',
        difficulty: targetVer.difficulty ?? question.value.difficulty ?? 3,
        tags: targetVer.tags || question.value.tags || [],
      })
    }
    conflictResolvedMessage.value = `已成功确认采用版本 v${targetVer.version_number} 内容，服务端已原子生成最新生效版本！`
    triggerSyncEvent('QUESTION_UPDATED', 'QUESTION', updated.id, { version_number: updated.version_number })
    questions.value[index.value] = updated
    questionVersions.value = await listQuestionVersions(props.token, updated.id)
  } catch (err) {
    alert(`采用版本失败：${err.detail || err.message}`)
  }
}

async function complete() {
  const total = questions.value.length
  const answered = answeredCount.value
  const unanswered = Math.max(0, total - answered)
  let confirmMsg = '确定要结束本次练习并交卷吗？'
  if (unanswered > 0) {
    confirmMsg = `您还有 ${unanswered} 道题目尚未作答，确定现在提前交卷吗？`
  }
  if (!window.confirm(confirmMsg)) return
  const report = await completeSession(props.token, props.sessionId)
  window.alert(`本次练习结束！得分：${report.score}，正确率：${report.accuracy}%`)
  emit('completed', report)
  emit('back')
}

</script>

<style scoped>
.practice-page {
  width: min(100% - 2rem, 74rem);
  margin: 1.5rem auto;
  padding-bottom: 5.5rem;
}

/* 题目横向切换平滑过渡动效 */
.question-slide-wrapper.slide-next {
  animation: slideFromRight 0.18s cubic-bezier(0.16, 1, 0.3, 1);
}
.question-slide-wrapper.slide-prev {
  animation: slideFromLeft 0.18s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes slideFromRight {
  from {
    opacity: 0.6;
    transform: translateX(18px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes slideFromLeft {
  from {
    opacity: 0.6;
    transform: translateX(-18px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.question-slide-wrapper {
  width: 100%;
}

/* 核心主操作锁定最右侧固定尺寸与坐标 */
.btn-action-fixed-primary {
  min-width: 8.5rem;
  height: 2.65rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  flex-shrink: 0;
}

/* 帮助提示弹窗 */
.help-tip-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.5);
  backdrop-filter: blur(2px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 1rem;
}

.help-tip-dialog {
  background: #ffffff;
  border-radius: 12px;
  padding: 1.5rem;
  width: min(100%, 30rem);
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.15), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
  animation: tipPopIn 0.18s ease-out;
}

@keyframes tipPopIn {
  from { opacity: 0; transform: scale(0.96); }
  to { opacity: 1; transform: scale(1); }
}

.help-tip-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #e2e8f0;
  padding-bottom: 0.65rem;
  margin-bottom: 1rem;
}

.help-tip-header h3 {
  margin: 0;
  font-size: 1.05rem;
  color: #0f172a;
}

.btn-close-tip {
  border: none;
  background: none;
  font-size: 1.25rem;
  color: #64748b;
  cursor: pointer;
  padding: 0.2rem 0.4rem;
  border-radius: 4px;
}

.tip-section {
  margin-bottom: 0.85rem;
}

.tip-section strong {
  display: block;
  font-size: 0.875rem;
  color: #1e293b;
  margin-bottom: 0.35rem;
}

.tip-section ul {
  margin: 0;
  padding-left: 1.25rem;
  font-size: 0.825rem;
  color: #475569;
  line-height: 1.6;
}

.tip-section p {
  margin: 0;
  font-size: 0.825rem;
  color: #475569;
  line-height: 1.5;
}

.btn-help-guide {
  font-size: 0.85rem;
  padding: 0.35rem 0.65rem;
}

.btn-help-mobile {
  border: 1px solid #cbd5e1;
  background: #ffffff;
  border-radius: 6px;
  padding: 0.3rem 0.5rem;
  font-size: 0.95rem;
  cursor: pointer;
  margin-right: 0.4rem;
}

/* 官方解析下方的 AI 助教入口 */
.ai-assistant-entry-block {
  margin-top: 1rem;
  padding: 0.75rem 1rem;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.ai-entry-meta {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.ai-badge {
  font-weight: 600;
  font-size: 0.875rem;
  color: #166534;
}

.ai-desc {
  font-size: 0.785rem;
  color: #15803d;
}

.btn-toggle-ai-card {
  padding: 0.4rem 0.85rem;
  font-size: 0.825rem;
  font-weight: 500;
  background: #ffffff;
  border: 1px solid #86efac;
  color: #166534;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-toggle-ai-card:hover {
  background: #dcfce7;
}

.btn-toggle-ai-card.active {
  background: #166534;
  color: #ffffff;
}

/* 专注作答状态占位卡 */
.practice-answering-placeholder {
  padding: 2.25rem 1.25rem;
  background: #f8fafc;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  display: flex;
  align-items: flex-start;
  gap: 0.85rem;
  color: #64748b;
}

.placeholder-icon {
  font-size: 1.8rem;
  line-height: 1;
}

.placeholder-content h4 {
  margin: 0 0 0.35rem 0;
  font-size: 0.95rem;
  color: #1e293b;
}

.placeholder-content p {
  margin: 0.2rem 0;
  font-size: 0.825rem;
  line-height: 1.45;
}

.compact-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-bottom: 0.85rem;
  padding: 0.4rem 0.75rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}

.header-meta-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.badge-type-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.2rem 0.6rem;
  border-radius: 9999px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
  font-size: 0.775rem;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.badge-index-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.2rem 0.6rem;
  border-radius: 9999px;
  background: #f1f5f9;
  border: 1px solid #cbd5e1;
  color: #475569;
  font-size: 0.775rem;
  font-weight: 600;
}

.badge-conflict-warning {
  padding: 0.2rem 0.5rem;
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #dc2626;
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
  cursor: pointer;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
}

.btn-flag.active {
  background: var(--warning-light);
  border-color: var(--warning);
  color: var(--warning-hover);
  font-weight: 600;
}

.btn-kill {
  color: var(--danger);
  border-color: var(--danger-border);
}
.btn-kill:hover:not(:disabled) {
  background: var(--danger-light);
  border-color: var(--danger);
}

.question-card {
  padding: 1.75rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  background: var(--bg-card);
  box-shadow: var(--shadow-sm);
}

.stem-box h2 {
  font-size: 1.25rem;
  line-height: 1.6;
  margin-bottom: 1.5rem;
  white-space: pre-wrap;
  color: var(--text-main);
}

.options-group {
  display: grid;
  gap: 0.85rem;
  margin-bottom: 1.5rem;
}

.option {
  display: flex;
  gap: 0.85rem;
  align-items: flex-start;
  padding: 0.95rem 1.15rem;
  border: 1.5px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  cursor: pointer;
  transition: all 0.15s ease;
  font-size: 0.95rem;
  line-height: 1.5;
}

.option:hover {
  border-color: var(--primary-border);
  background: var(--primary-light);
}

.option.selected {
  border-color: var(--primary);
  background: #eff6ff;
  color: #1e3a8a;
  box-shadow: 0 0 0 1px var(--primary);
}

.option input {
  margin-top: 0.25rem;
  accent-color: var(--primary);
  cursor: pointer;
}

.text-answer-box textarea {
  width: 100%;
  padding: 0.85rem;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-lg);
  resize: vertical;
  margin-top: 0.5rem;
  font-size: 0.95rem;
  line-height: 1.5;
}

.practice-split-grid {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

@media (min-width: 1024px) {
  .practice-split-grid {
    display: grid;
    grid-template-columns: 1.15fr 0.85fr;
    gap: 1.5rem;
    align-items: start;
  }

  .practice-split-right {
    position: sticky;
    top: 1rem;
    max-height: calc(100vh - 7.5rem);
    overflow-y: auto;
    padding-right: 0.25rem;
  }
}

.practice-split-left {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.practice-split-right {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-width: 0;
}

.practice-side-guide {
  padding: 1.25rem;
  background: #f8fafc;
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-lg);
  color: var(--text-muted);
}

.practice-side-guide h4 {
  margin: 0 0 0.5rem 0;
  font-size: 0.95rem;
  color: var(--text-main);
}

.practice-side-guide p {
  margin: 0.35rem 0;
  font-size: 0.875rem;
  line-height: 1.5;
}

.quick-verdict-bar {
  margin-top: 1rem;
  padding: 0.75rem 1rem;
  border-radius: var(--radius-lg);
  border: 1.5px solid;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  animation: fadeIn 0.2s ease-in-out;
}

.quick-verdict-bar.correct {
  background: #f0fdf4;
  border-color: #86efac;
  color: #166534;
}

.quick-verdict-bar.incorrect {
  background: #fef2f2;
  border-color: #fca5a5;
  color: #991b1b;
}

.quick-verdict-bar.partial {
  background: #fffbeb;
  border-color: #fde68a;
  color: #92400e;
}

.verdict-status-title {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.95rem;
}

.verdict-text-inline {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  font-size: 0.875rem;
}

.text-correct {
  color: #16a34a;
}

.text-danger {
  color: #dc2626;
}

.option.option-correct {
  border-color: #22c55e;
  background: #f0fdf4;
}

.option.option-wrong {
  border-color: #ef4444;
  background: #fef2f2;
}

.inline-verdict-badge {
  margin-left: auto;
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
}

.inline-verdict-badge.correct {
  background: #dcfce7;
  color: #15803d;
}

.inline-verdict-badge.wrong {
  background: #fee2e2;
  color: #b91c1c;
}


.submit-bar {
  margin: 1.5rem 0 0.5rem;
}

.result-card {
  margin-top: 1.5rem;
  padding: 1.35rem;
  border-radius: var(--radius-lg);
  background: var(--bg-page);
  border: 1px solid var(--border);
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 1.1rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.result-header strong.correct {
  color: var(--success);
}
.result-header strong.partial {
  color: var(--warning);
}
.result-header strong.incorrect {
  color: var(--danger);
}

.official-explanation {
  margin: 1rem 0;
  padding: 1rem;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  border-left: 4px solid var(--primary);
  line-height: 1.6;
}

.official-explanation h4 {
  font-size: 0.95rem;
  margin-bottom: 0.35rem;
  color: var(--text-main);
}

.btn-ai-toggle.active {
  background: var(--primary-light);
  color: var(--primary);
  border-color: var(--primary-border);
}

.option:active {
  transform: scale(0.99);
}

.fsrs-rating-box {
  margin: 1rem 0;
  padding: 1rem;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
}

.fsrs-rating-box h4 {
  margin: 0 0 0.65rem;
  font-size: 0.9rem;
  color: var(--text-muted);
}

.fsrs-buttons {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.rating-btn {
  padding: 0.45rem 0.85rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-strong);
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 500;
  background: var(--bg-card);
  transition: all 0.15s ease;
}

.rating-btn.again {
  color: var(--danger);
  border-color: var(--danger-border);
}
.rating-btn.again:hover:not(:disabled) {
  background: var(--danger-light);
}

.rating-btn.hard {
  color: var(--warning);
  border-color: var(--warning-border);
}
.rating-btn.hard:hover:not(:disabled) {
  background: var(--warning-light);
}

.rating-btn.good {
  color: var(--primary);
  border-color: var(--primary-border);
}
.rating-btn.good:hover:not(:disabled) {
  background: var(--primary-light);
}

.rating-btn.easy {
  color: var(--success);
  border-color: var(--success-border);
}
.rating-btn.easy:hover:not(:disabled) {
  background: var(--success-light);
}

.rating-btn.selected {
  font-weight: 700;
  box-shadow: 0 0 0 2px currentColor;
}

.rating-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.fsrs-status {
  margin-top: 0.5rem;
  font-size: 0.85rem;
  color: var(--primary);
}

.ai-panel {
  margin-top: 1.5rem;
  padding: 1.35rem;
  border: 1px solid #bfdbfe;
  border-radius: var(--radius-lg);
  background: #f8faff;
}

.ai-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.ai-btn-group {
  display: flex;
  gap: 0.5rem;
}

.ai-ask-box {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.ai-ask-box input {
  flex: 1;
}

.ai-status {
  color: var(--warning);
  font-size: 0.875rem;
  margin-bottom: 0.75rem;
}

.ai-history {
  display: grid;
  gap: 0.85rem;
  margin-top: 1rem;
}

.version-card {
  padding: 1rem 1.15rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-card);
}

.version-card.adopted {
  border-color: var(--success);
  box-shadow: 0 0 0 1px var(--success);
}

.version-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  flex-wrap: wrap;
}

.source-tag {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.15rem 0.45rem;
  background: var(--bg-muted);
  border-radius: var(--radius-sm);
  color: var(--text-main);
}

.badge-adopted {
  font-size: 0.75rem;
  color: var(--success);
  font-weight: 700;
  background: var(--success-light);
  border: 1px solid var(--success-border);
  padding: 0.1rem 0.4rem;
  border-radius: var(--radius-sm);
}

.content-text {
  white-space: pre-wrap;
  line-height: 1.6;
  margin-bottom: 0.5rem;
  font-size: 0.925rem;
}

.evidence-box {
  margin: 0.5rem 0;
  padding: 0.65rem 0.85rem;
  background: var(--bg-page);
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
  border: 1px solid var(--border);
}

.evidence-box ul {
  margin-left: 1.25rem;
  margin-top: 0.35rem;
}

.version-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.75rem;
}

.btn-adopt {
  color: var(--success);
  border-color: var(--success-border);
}
.btn-adopt:hover:not(:disabled) {
  background: var(--success-light);
  border-color: var(--success);
}

.version-edit-box textarea {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.version-edit-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
  margin-top: 0.5rem;
}

.ai-chat-thread {
  margin: 1rem 0;
  display: grid;
  gap: 0.75rem;
}

.ai-chat-thread h4 {
  margin: 0;
  font-size: 0.95rem;
}

.chat-bubble {
  padding: 0.75rem 1rem;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  background: var(--bg-card);
}

.chat-bubble.user {
  background: #eff6ff;
  border-color: #bfdbfe;
  margin-left: 1.5rem;
}

.chat-bubble.assistant {
  background: var(--bg-card);
  border-color: #cbd5e1;
  margin-right: 1.5rem;
}

.chat-sender {
  display: flex;
  justify-content: space-between;
  font-size: 0.8125rem;
  margin-bottom: 0.35rem;
  font-weight: 600;
  color: var(--text-muted);
}

.chat-text {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.55;
  font-size: 0.925rem;
}

.conflict-banner {
  margin-bottom: 1.25rem;
  padding: 1.15rem;
  border: 1px solid var(--warning);
  background: var(--warning-light);
  border-radius: var(--radius-lg);
}

.conflict-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.conflict-badge {
  font-weight: 600;
  color: var(--warning-hover);
  font-size: 0.925rem;
}

.btn-conflict-toggle {
  padding: 0.35rem 0.75rem;
  border: 1px solid var(--warning);
  background: #fef3c7;
  color: #92400e;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 0.85rem;
}

.conflict-resolved-msg {
  margin-top: 0.5rem;
  color: var(--success);
  font-weight: 600;
  font-size: 0.9rem;
}

.conflict-list {
  display: grid;
  gap: 0.75rem;
  margin-top: 1rem;
}

.conflict-version-item {
  padding: 0.85rem 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-card);
}

.conflict-version-item.active {
  border-color: var(--primary);
  box-shadow: 0 0 0 1px var(--primary);
}

.conflict-version-meta {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin-bottom: 0.5rem;
}

.badge-current {
  font-size: 0.75rem;
  background: #dbeafe;
  color: #1e40af;
  padding: 0.1rem 0.4rem;
  border-radius: var(--radius-sm);
  font-weight: 600;
}

.conflict-version-body p {
  margin: 0.25rem 0;
  font-size: 0.875rem;
}

.conflict-version-actions {
  margin-top: 0.5rem;
  display: flex;
  justify-content: flex-end;
}

.btn-adopt-version {
  padding: 0.35rem 0.75rem;
  font-size: 0.85rem;
}

.offline-banner {
  margin-bottom: 1rem;
  padding: 0.75rem 1rem;
  background: var(--danger-light);
  border: 1px solid var(--danger-border);
  border-radius: var(--radius-md);
  color: var(--danger);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.875rem;
}

.btn-sync-offline {
  padding: 0.3rem 0.65rem;
  border: 1px solid var(--danger);
  background: #fff;
  color: var(--danger);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 0.85rem;
}

.question-edit-panel {
  margin-bottom: 1.25rem;
  padding: 1.25rem;
  background: var(--bg-page);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-lg);
  display: grid;
  gap: 0.75rem;
}

.question-edit-panel h3 {
  margin: 0;
  font-size: 1.05rem;
}

.question-edit-panel label {
  display: grid;
  gap: 0.35rem;
  font-weight: 600;
  font-size: 0.9rem;
}

.input-edit-stem, .input-edit-exp {
  padding: 0.5rem;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
  font-size: 0.95rem;
}

.edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.btn-edit-question {
  border: 1px solid var(--border-strong);
  background: var(--bg-card);
  cursor: pointer;
}

/* Visibility utilities */
.mobile-only-inline, .mobile-only-btn {
  display: none !important;
}
.desktop-only-btn {
  display: inline-flex !important;
}

.btn-sheet-trigger-pill {
  border: 1px solid var(--primary-border);
  background: var(--primary-light);
  color: var(--primary);
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s ease;
}
.btn-sheet-trigger-pill:hover {
  background: #dbeafe;
}

.mobile-more-wrapper {
  position: relative;
}

.btn-more-menu {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-main);
  font-size: 1.15rem;
  font-weight: 800;
  cursor: pointer;
}

.mobile-dropdown-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 0.35rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  min-width: 8.5rem;
  z-index: 100;
  overflow: hidden;
}

.dropdown-item {
  padding: 0.6rem 0.85rem;
  text-align: left;
  background: none;
  border: none;
  border-bottom: 1px solid var(--border-subtle);
  font-size: 0.85rem;
  color: var(--text-main);
  cursor: pointer;
}
.dropdown-item:last-child {
  border-bottom: none;
}
.dropdown-item:active {
  background: var(--bg-muted);
}

/* Question Sheet Drawer (答题卡) */
.sheet-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  backdrop-filter: blur(2px);
  z-index: 100;
  display: flex;
  justify-content: center;
  align-items: flex-end;
}

.sheet-modal-drawer {
  background: var(--bg-card);
  width: 100%;
  max-width: 42rem;
  max-height: 80vh;
  border-radius: 1rem 1rem 0 0;
  box-shadow: var(--shadow-xl);
  display: flex;
  flex-direction: column;
  padding: 1.15rem 1.25rem;
  overflow-y: auto;
  animation: slideUp 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes slideUp {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}

.sheet-drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.85rem;
}

.sheet-drawer-title {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}
.sheet-drawer-title h3 {
  margin: 0;
  font-size: 1.15rem;
}
.sheet-stats-pill {
  font-size: 0.8rem;
  color: var(--text-muted);
  background: var(--bg-muted);
  padding: 0.15rem 0.5rem;
  border-radius: 9999px;
}

.btn-close-sheet {
  border: none;
  background: var(--bg-muted);
  width: 1.85rem;
  height: 1.85rem;
  border-radius: 50%;
  cursor: pointer;
  font-weight: 700;
  color: var(--text-muted);
}

.sheet-quick-actions {
  margin-bottom: 0.75rem;
}
.btn-jump-next-unanswered {
  width: 100%;
  padding: 0.55rem;
  background: var(--primary-light);
  border: 1px dashed var(--primary);
  color: var(--primary);
  border-radius: var(--radius-md);
  font-weight: 600;
  font-size: 0.875rem;
  cursor: pointer;
}

.sheet-legend-bar {
  display: flex;
  gap: 0.85rem;
  margin-bottom: 0.85rem;
  font-size: 0.8rem;
  color: var(--text-muted);
  flex-wrap: wrap;
}
.sheet-legend-bar .legend-item {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}
.legend-dot {
  width: 0.65rem;
  height: 0.65rem;
  border-radius: 50%;
  display: inline-block;
}
.legend-dot.unanswered { background: var(--border-strong); }
.legend-dot.correct { background: var(--success); }
.legend-dot.incorrect { background: var(--danger); }
.legend-dot.partial { background: var(--warning); }

.sheet-numbers-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(2.6rem, 1fr));
  gap: 0.5rem;
  margin-top: 0.35rem;
}

.sheet-num-btn {
  height: 2.6rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-strong);
  background: var(--bg-subtle);
  font-weight: 700;
  font-size: 0.9rem;
  color: var(--text-main);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}
.sheet-num-btn.current {
  border: 2px solid var(--primary) !important;
  box-shadow: 0 0 0 2px var(--primary-border);
}
.sheet-num-btn.answered {
  background: var(--bg-muted);
  border-color: var(--text-tertiary);
}
.sheet-num-btn.correct {
  background: var(--success);
  border-color: var(--success-hover);
  color: #fff;
}
.sheet-num-btn.incorrect {
  background: var(--danger);
  border-color: var(--danger-hover);
  color: #fff;
}
.sheet-num-btn.partial {
  background: var(--warning);
  border-color: var(--warning-hover);
  color: #fff;
}

/* ==========================================================================
   Mobile Responsive Overhaul (< 768px)
   ========================================================================== */
@media (max-width: 767px) {
  .practice-page {
    width: 100%;
    margin: 0;
    padding: 0.25rem 0.5rem 4.5rem;
  }

  .compact-header {
    display: flex !important;
    flex-direction: row !important;
    justify-content: space-between !important;
    align-items: center !important;
    padding: 0.35rem 0.5rem !important;
    margin-bottom: 0.75rem !important;
    gap: 0.35rem !important;
    height: auto !important;
    min-height: 44px !important;
    border-radius: var(--radius-md) !important;
    box-sizing: border-box !important;
    flex-wrap: wrap !important;
  }

  .header-left-bar {
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    gap: 0.35rem !important;
    flex: 1 1 auto !important;
    min-width: 0 !important;
  }

  .header-titles {
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    gap: 0.3rem !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
  }

  .btn-back {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    height: 2rem !important;
    padding: 0 0.5rem !important;
    font-size: 0.85rem !important;
    white-space: nowrap !important;
    border-radius: var(--radius-sm) !important;
    flex-shrink: 0 !important;
  }

  .practice-title {
    font-size: 0.9rem !important;
    margin: 0 !important;
  }

  .badge-type-pill {
    font-size: 0.72rem !important;
    padding: 0.1rem 0.35rem !important;
  }

  .btn-sheet-trigger-pill {
    font-size: 0.72rem !important;
    padding: 0.1rem 0.4rem !important;
  }

  .header-actions {
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    gap: 0.35rem !important;
    flex: 0 0 auto !important;
    width: auto !important;
    flex-wrap: nowrap !important;
  }

  .btn-header-complete {
    padding: 0.25rem 0.6rem !important;
    font-size: 0.8rem !important;
    height: 2rem !important;
    min-height: 2rem !important;
    border-radius: var(--radius-sm) !important;
  }

  .desktop-only-btn {
    display: none !important;
  }

  .mobile-only-inline {
    display: inline-flex !important;
  }
  .mobile-only-btn {
    display: inline-flex !important;
  }

  /* 消除桌面端键盘提示框在手机端的 120px 空间占用 */
  .practice-side-guide,
  .practice-tips {
    display: none !important;
  }

  .question-card {
    padding: 0.75rem 0.75rem 0.85rem;
    border-radius: var(--radius-md);
  }

  .stem-box h2 {
    font-size: 1rem;
    line-height: 1.45;
    margin-bottom: 0.75rem;
  }


  .options-group {
    gap: 0.5rem;
  }

  .option {
    padding: 0.6rem 0.75rem;
    border-radius: var(--radius-md);
    margin-bottom: 0;
  }

  .key-cap {
    min-width: 1.5rem;
    height: 1.5rem;
    font-size: 0.8rem;
  }

  .quick-verdict-bar {
    padding: 0.5rem 0.75rem;
    margin-top: 0.65rem;
    border-radius: var(--radius-md);
  }

  .result-actions {
    flex-direction: column;
  }
  .ai-toolbar {
    flex-direction: column;
    align-items: stretch;
  }
  .ai-btn-group {
    flex-direction: column;
  }

  /* 底部固定底栏极简化与安全区适配 */
  .ergonomic-action-bar {
    padding: 0.4rem 0.6rem max(0.45rem, env(safe-area-inset-bottom)) !important;
    min-height: 48px;
  }

  .action-bar-inner {
    gap: 0.35rem;
  }

  .btn-prev-question,
  .btn-next-question,
  .btn-submit-answer,
  .btn-skip-unanswered,
  .btn-finish-session,
  .btn-ai-toggle {
    min-height: 2.35rem !important;
    padding: 0.35rem 0.75rem !important;
    font-size: 0.825rem !important;
  }

  .hotkey-badge,
  .hotkey-helper-bar {
    display: none !important;
  }
}
</style>
