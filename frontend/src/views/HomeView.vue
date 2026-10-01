<template>
  <main class="home-page">
    <header class="page-header home-header">
      <div class="home-brand-area">
        <div class="home-brand-title">
          <span class="home-brand-icon">
            <LinearIcon name="layers" size="18" />
          </span>
          <h1>题库资产大厅</h1>
        </div>
        <p class="home-user-pill">
          <span class="user-role-dot" :class="user?.is_admin ? 'role-admin' : 'role-user'"></span>
          {{ user?.username }}
          <span v-if="user?.is_admin" class="user-role-badge">管理员</span>
        </p>
      </div>

      <nav class="home-main-nav">
        <button type="button" class="main-nav-tab featured" @click="$emit('learning')">
          <LinearIcon name="chart" size="14" /> {{ t('nav.learning') }}
        </button>
        <button type="button" class="main-nav-tab featured" @click="$emit('mistakes')">
          <LinearIcon name="target" size="14" /> {{ t('nav.mistakes') }}
        </button>
        <button type="button" class="main-nav-tab" @click="$emit('import')">
          <LinearIcon name="inbox" size="14" /> {{ t('nav.imports') }}
        </button>
      </nav>

      <div class="home-actions-area">
        <button type="button" class="primary btn-create-bank" @click="showCreateDialog = true">
          <LinearIcon name="plus" size="14" /> {{ t('home.create_bank') }}
        </button>
        <div class="home-utility-group">
          <button type="button" class="btn-util" @click="openBlueprintDialog" title="蓝图配置">
            <LinearIcon name="blueprint" size="14" /> <span class="btn-util-label">蓝图</span>
          </button>
          <button type="button" class="btn-util" @click="openDraftsDialog" title="变式草稿箱">
            <LinearIcon name="draft" size="14" /> <span class="btn-util-label">草稿箱</span>
          </button>
          <button type="button" class="btn-util" @click="openAiConfigDialog" title="AI与搜索配置">
            <LinearIcon name="cpu" size="14" /> <span class="btn-util-label">AI配置</span>
          </button>
          <button type="button" class="btn-util" @click="openAssetsDialog" title="个人资料">
            <LinearIcon name="user" size="14" /> <span class="btn-util-label">资料</span>
          </button>
          <button type="button" class="btn-util btn-logout" @click="$emit('logout')" :title="t('nav.logout')">
            {{ t('nav.logout') }}
          </button>
        </div>
      </div>
    </header>

    <!-- EE-019: 未完成会话恢复与管理终端 HUD -->
    <section v-if="activeSessions.length > 0" class="active-session-banner">
      <div class="banner-content">
        <span class="banner-badge">
          <LinearIcon name="terminal" size="13" /> ACTIVE SESSION
        </span>
        <span class="banner-text">
          <template v-if="activeSessions.length === 1">
            未完成会话：【{{ activeSessions[0].bank_name }}】{{ formatSessionMode(activeSessions[0].mode) }}
            <span class="font-mono-code">({{ activeSessions[0].answered_count }} / {{ activeSessions[0].total_questions }} 题)</span>
          </template>
          <template v-else>
            {{ activeSessions.length }} 个进行中会话。最近：【{{ activeSessions[0].bank_name }}】{{ formatSessionMode(activeSessions[0].mode) }}
            <span class="font-mono-code">({{ activeSessions[0].answered_count }} / {{ activeSessions[0].total_questions }} 题)</span>
          </template>
        </span>
      </div>
      <div class="banner-btn-group">
        <button type="button" class="primary btn-resume-session" @click="handleResume(activeSessions[0])">
          <LinearIcon name="play" size="13" /> {{ activeSessions.length > 1 ? '恢复最近会话' : '继续答题' }}
        </button>
        <button v-if="activeSessions.length > 1" type="button" class="secondary-btn btn-view-all-sessions" @click="showActiveSessionsModal = true">
          全部会话 ({{ activeSessions.length }})
        </button>
        <button v-else type="button" class="btn-abandon-single text-btn" :disabled="abandoningSession" @click="handleAbandonSession(activeSessions[0].id)">
          放弃会话
        </button>
      </div>
    </section>

    <!-- 未完成会话列表与管理对话框 (EE-019) -->
    <div v-if="showActiveSessionsModal" class="exam-setup-backdrop" @click.self="showActiveSessionsModal = false" @keydown.esc="showActiveSessionsModal = false">
      <div class="exam-setup-dialog active-sessions-dialog" role="dialog" aria-modal="true" style="width: min(100%, 46rem); max-height: 85vh; overflow-y: auto;">
        <div class="dialog-header-row" style="display: flex; justify-content: space-between; align-items: center;">
          <h2 style="font-size: 1.15rem; margin: 0;">未完成作答会话 (共 {{ activeSessions.length }} 个)</h2>
          <button type="button" class="btn-close-icon" style="border: none; background: none; font-size: 1.25rem; cursor: pointer; color: var(--linear-text-muted);" @click="showActiveSessionsModal = false">✕</button>
        </div>
        <p style="font-size: 0.825rem; color: var(--linear-text-dim); margin: 0.25rem 0 0.75rem;">
          检测到多个未完成历史会话，可在此恢复继续作答，或放弃不再需要的草稿会话。
        </p>

        <div class="active-sessions-list" style="display: grid; gap: 0.75rem; margin-bottom: 1rem;">
          <div
            v-for="sess in activeSessions"
            :key="sess.id"
            class="session-card-item"
            style="border: 1px solid var(--border); border-radius: 8px; padding: 0.85rem 1rem; background: var(--bg-card); display: flex; justify-content: space-between; align-items: center; gap: 1rem;"
          >
            <div style="flex: 1;">
              <div style="display: flex; gap: 0.5rem; align-items: center; margin-bottom: 0.35rem;">
                <span style="font-size: 0.75rem; font-weight: 600; padding: 0.15rem 0.5rem; border-radius: 4px; background: var(--primary-light); color: var(--linear-cyan); font-family: var(--linear-mono);">
                  {{ formatSessionMode(sess.mode) }}
                </span>
                <strong style="font-size: 0.95rem; color: var(--text-main);">{{ sess.bank_name }}</strong>
                <small style="color: var(--text-tertiary); font-family: var(--linear-mono);">{{ formatTimeAgo(sess.updated_at || sess.created_at) }}</small>
              </div>
              <div style="display: flex; align-items: center; gap: 0.75rem;">
                <div style="flex: 1; height: 6px; background: var(--border-strong); border-radius: 3px; overflow: hidden; max-width: 180px;">
                  <div
                    style="height: 100%; background: var(--primary); border-radius: 3px;"
                    :style="{ width: `${sess.total_questions ? Math.min(100, Math.round((sess.answered_count / sess.total_questions) * 100)) : 0}%` }"
                  ></div>
                </div>
                <span style="font-size: 0.8rem; color: var(--text-muted); font-family: var(--linear-mono);">
                  {{ sess.answered_count }} / {{ sess.total_questions }} 题
                  ({{ sess.total_questions ? Math.min(100, Math.round((sess.answered_count / sess.total_questions) * 100)) : 0 }}%)
                </span>
              </div>
            </div>
            <div style="display: flex; gap: 0.5rem; align-items: center;">
              <button type="button" class="primary" style="padding: 0.4rem 0.85rem; font-size: 0.85rem;" @click="handleResume(sess)">
                继续答题
              </button>
              <button
                type="button"
                style="padding: 0.4rem 0.75rem; font-size: 0.85rem; border: 1px solid var(--border); background: var(--bg-card); color: var(--danger); border-radius: 6px; cursor: pointer;"
                :disabled="abandoningSession"
                @click="handleAbandonSession(sess.id)"
              >
                放弃
              </button>
            </div>
          </div>
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border); padding-top: 0.75rem;">
          <button
            type="button"
            style="color: var(--danger); background: none; border: 1px solid var(--danger-border); border-radius: 6px; padding: 0.4rem 0.8rem; font-size: 0.85rem; cursor: pointer;"
            :disabled="abandoningSession"
            @click="handleAbandonAllSessions"
          >
            全部放弃 (清空草稿)
          </button>
          <button type="button" class="secondary-btn" style="padding: 0.4rem 1rem;" @click="showActiveSessionsModal = false">关闭</button>
        </div>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading" class="muted" style="padding: 2rem; text-align: center; font-family: var(--linear-mono);">正在载入题库资源...</p>
    <section v-else class="bank-grid">
      <article v-for="bank in banks" :key="bank.id" class="bank-card" :class="{ 'has-active-session': Boolean(getActiveSessionForBank(bank.id)) }">
        <div class="bank-card-title-row">
          <h2>{{ bank.name }}</h2>
          <span v-if="getActiveSessionForBank(bank.id)" class="badge-active-progress">
            <LinearIcon name="clock" size="12" /> 进行中 ({{ getActiveSessionForBank(bank.id).answered_count }}/{{ getActiveSessionForBank(bank.id).total_questions }} 题)
          </span>
        </div>
        <p>{{ bank.description || '暂无描述' }}</p>
        <div class="bank-meta-info">
          <small>{{ bank.question_count }} 题</small>
          <span v-if="bank.category" class="bank-category-pill">{{ bank.category }}</span>
        </div>
        <div class="bank-actions-container">
          <div class="bank-primary-actions">
            <button
              v-if="getActiveSessionForBank(bank.id)"
              class="primary btn-resume-direct"
              @click="handleResume(getActiveSessionForBank(bank.id))"
            >
              <LinearIcon name="play" size="13" /> 继续答题
            </button>
            <button class="primary" :disabled="!bank.question_count" @click="$emit('start', bank)">
              <LinearIcon name="play" size="13" /> 开始刷题
            </button>
            <button class="secondary-btn" :disabled="!bank.question_count" @click="openExamSetup(bank)">
              <LinearIcon name="award" size="13" /> 开始模考
            </button>
          </div>
          <div class="bank-utility-actions">
            <button type="button" class="btn-util-link" @click="openAddQuestion(bank)">+ 录入</button>
            <button type="button" class="btn-util-link" @click="openShareDialog(bank)">共享</button>
            <button type="button" class="btn-util-link" @click="openExportDialog(bank)">导出</button>
          </div>
        </div>
      </article>
      <p v-if="!banks.length" class="muted" style="grid-column: 1 / -1; padding: 3rem; text-align: center;">还没有题库，请点击上方“创建题库”或通过“导入题目”添加。</p>
    </section>

    <!-- 创建题库对话框 -->
    <div v-if="showCreateDialog" class="exam-setup-backdrop" @click.self="showCreateDialog = false" @keydown.esc="showCreateDialog = false">
      <form class="exam-setup-dialog" role="dialog" aria-modal="true" aria-labelledby="create-bank-title" @submit.prevent="handleCreateBank">
        <h2 id="create-bank-title">创建新题库</h2>
        <label>题库名称
          <input v-model.trim="newBank.name" type="text" placeholder="例如：软考高项历年真题" required />
        </label>
        <label>分类
          <input v-model.trim="newBank.category" type="text" placeholder="默认分类" />
        </label>
        <label>描述说明
          <textarea v-model.trim="newBank.description" placeholder="关于该题库的简要说明" rows="3"></textarea>
        </label>
        <p v-if="createError" class="error">{{ createError }}</p>
        <div class="bank-actions">
          <button type="button" @click="showCreateDialog = false">取消</button>
          <button type="submit" :disabled="creatingBank">{{ creatingBank ? '正在创建…' : '确认创建' }}</button>
        </div>
      </form>
    </div>

    <!-- 模考设置对话框 (EE-002, EE-010: 支持蓝图选择与错题入库开关) -->
    <div v-if="examBank" class="exam-setup-backdrop" @click.self="examBank = null" @keydown.esc="examBank = null">
      <form class="exam-setup-dialog" role="dialog" aria-modal="true" aria-labelledby="exam-setup-title" @submit.prevent="beginExam">
        <h2 id="exam-setup-title">模考设置</h2>
        <p>{{ examBank.name }} · 共 {{ examBank.question_count }} 题</p>
        <label>本次题量
          <input v-model.number="totalQuestions" type="number" min="1" :max="examBank.question_count" required />
        </label>
        <label>时长（分钟，0 表示不限时）
          <input v-model.number="timeLimitMinutes" type="number" min="0" max="600" required />
        </label>
        <label>考试蓝图 / 档案（可选）
          <div style="display: flex; gap: 0.5rem; align-items: center;">
            <select v-model="selectedProfileId" style="flex: 1;" @change="onExamProfileChange">
              <option value="">全题库随机抽取 (无蓝图)</option>
              <option v-for="p in examProfiles" :key="p.id" :value="p.id">
                {{ p.name }} {{ p.latest_blueprint ? '(已绑定章节/题型规则)' : '(默认)' }}
              </option>
            </select>
            <button type="button" class="action-link-btn" style="white-space: nowrap; font-size: 0.8rem; padding: 0.35rem 0.6rem;" @click="openBlueprintDialogFromExam">
              蓝图配置
            </button>
          </div>
        </label>
        <div v-if="selectedProfileBlueprintSummary" style="background: var(--success-light); border: 1px solid var(--success-border); border-radius: 6px; padding: 0.6rem 0.75rem; font-size: 0.85rem; color: var(--success);">
          <strong>蓝图规则已就绪：</strong>
          共 {{ selectedProfileBlueprintSummary.sectionsCount }} 个大题小节 · 预设题量 {{ selectedProfileBlueprintSummary.totalQuestions }} 题
          <span v-if="selectedProfileBlueprintSummary.negativeMark > 0">· 错题倒扣 {{ selectedProfileBlueprintSummary.negativeMark }} 分</span>
          <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 0.2rem;">
            题量已自动同步为蓝图标准题量 ({{ totalQuestions }} 题)
          </div>
        </div>
        <label class="ctrl-check exam-option-checkbox">
          <input v-model="recordMistakes" type="checkbox" />
          <span>错题入库（取消勾选则本场模考错题不计入错题本）</span>
        </label>
        <p v-if="examError" class="error">{{ examError }}</p>
        <div class="dialog-actions-row">
          <button type="button" class="secondary-btn" @click="examBank = null">取消</button>
          <button type="submit" class="primary" :disabled="startingExam">{{ startingExam ? '正在创建…' : '开始考试' }}</button>
        </div>
      </form>
    </div>

    <!-- EE-011: 手动录入题目对话框 -->
    <div v-if="showAddQuestionDialog" class="exam-setup-backdrop" @click.self="showAddQuestionDialog = false" @keydown.esc="showAddQuestionDialog = false">
      <form class="exam-setup-dialog" role="dialog" style="width: min(100%, 36rem); max-height: 85vh; overflow-y: auto;" @submit.prevent="handleCreateQuestion">
        <h2>手动录入题目（题库：{{ targetBankForQuestion?.name }}）</h2>
        <label>题干
          <textarea v-model.trim="addQuestionForm.stem" rows="2" placeholder="请输入题目内容" required></textarea>
        </label>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
          <label>题型
            <select v-model="addQuestionForm.type" @change="onQuestionTypeChange">
              <option value="SINGLE">单选题</option>
              <option value="MULTI">多选题</option>
              <option value="JUDGE">判断题</option>
              <option value="ESSAY">主观/简答题</option>
            </select>
          </label>
          <label>难度
            <select v-model.number="addQuestionForm.difficulty">
              <option :value="1">1 (入门)</option>
              <option :value="2">2 (较易)</option>
              <option :value="3">3 (中等)</option>
              <option :value="4">4 (较难)</option>
              <option :value="5">5 (极难)</option>
            </select>
          </label>
        </div>
        <div v-if="addQuestionForm.type === 'SINGLE' || addQuestionForm.type === 'MULTI' || addQuestionForm.type === 'JUDGE'">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
            <label style="margin: 0; font-weight: 600;">选项配置（点选直接设为标准答案）</label>
            <button v-if="addQuestionForm.type !== 'JUDGE'" type="button" class="btn-add-opt" @click="handleAddOpt">+ 加选项</button>
          </div>
          <div v-for="(opt, idx) in addQuestionForm.options" :key="idx" class="add-opt-row" style="display: flex; gap: 0.5rem; align-items: center; margin-bottom: 0.45rem;">
            <label style="display: flex; align-items: center; margin: 0; cursor: pointer;" :title="`设为标准答案 (${opt.key})`">
              <input
                v-if="addQuestionForm.type === 'SINGLE' || addQuestionForm.type === 'JUDGE'"
                type="radio"
                name="correct-opt-radio"
                :checked="addQuestionForm.answer === opt.key"
                @change="addQuestionForm.answer = opt.key"
              />
              <input
                v-else-if="addQuestionForm.type === 'MULTI'"
                type="checkbox"
                :checked="addQuestionForm.answer.includes(opt.key)"
                @change="handleToggleMultiAnswer(opt.key)"
              />
            </label>
            <input v-model.trim="opt.key" style="width: 3.5rem; text-align: center; font-weight: 600;" placeholder="标识" />
            <input v-model.trim="opt.text" style="flex: 1;" placeholder="选项文本" />
            <button
              v-if="addQuestionForm.type !== 'JUDGE'"
              type="button"
              class="btn-remove-opt"
              title="删除此选项"
              style="border: none; background: var(--danger-light); color: var(--danger); border-radius: 4px; padding: 0.35rem 0.6rem; cursor: pointer; font-size: 0.85rem;"
              @click="addQuestionForm.options.splice(idx, 1)"
            >✕</button>
          </div>
        </div>
        <label>标准答案
          <div style="display: flex; gap: 0.5rem; align-items: center;">
            <input v-model.trim="addQuestionForm.answer" placeholder="如 A / AB / T" required style="flex: 1;" />
            <span style="font-size: 0.8rem; color: var(--text-muted);">(可在上方直接点选)</span>
          </div>
        </label>
        <label>解析
          <textarea v-model.trim="addQuestionForm.explanation" rows="2" placeholder="题目解析说明"></textarea>
        </label>
        <label>标签（逗号分隔）
          <input v-model.trim="addQuestionForm.tags" placeholder="如：重点, 必背" />
        </label>
        <p v-if="addQuestionError" class="error">{{ addQuestionError }}</p>
        <div class="bank-actions">
          <button type="button" @click="showAddQuestionDialog = false">取消</button>
          <button type="submit" :disabled="savingQuestion">{{ savingQuestion ? '正在保存…' : '保存题目' }}</button>
        </div>
      </form>
    </div>

    <!-- EE-020: 共享成员管理与跨库复制对话框 -->
    <div v-if="showShareDialog" class="exam-setup-backdrop" @click.self="showShareDialog = false" @keydown.esc="showShareDialog = false">
      <div class="exam-setup-dialog" role="dialog" style="width: min(100%, 36rem);">
        <h2>题库共享与成员管理</h2>
        <p>题库：【{{ targetBankForShare?.name }}】</p>

        <!-- 现有成员列表 -->
        <div style="margin-bottom: 1rem;">
          <h3 style="font-size: 0.95rem; margin-bottom: 0.4rem;">现有成员列表</h3>
          <div v-if="loadingMembers" style="color: var(--text-tertiary); font-size: 0.85rem;">正在加载成员...</div>
          <div v-else style="display: flex; flex-direction: column; gap: 0.4rem; max-height: 8rem; overflow-y: auto;">
            <div v-for="m in bankMembersList" :key="m.user_id" style="display: flex; justify-content: space-between; align-items: center; padding: 0.4rem 0.6rem; background: var(--bg-page); border: 1px solid var(--border); border-radius: 4px;">
              <span style="font-size: 0.85rem; font-weight: 500;">{{ m.username }}</span>
              <div style="display: flex; align-items: center; gap: 0.6rem;">
                <span style="font-size: 0.75rem; padding: 0.1rem 0.4rem; background: var(--bg-subtle); border-radius: 4px;">
                  {{ m.role === 'ADMIN' ? '管理员' : m.role === 'EDITOR' ? '编辑者' : '只读成员' }}
                </span>
                <button v-if="m.role !== 'ADMIN' && m.user_id !== user?.id" type="button" style="color: var(--danger); border: none; background: none; cursor: pointer; font-size: 0.75rem;" @click="handleRemoveMember(m.user_id)">
                  移除
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- 添加成员表单 -->
        <form style="border-top: 1px dashed var(--border-strong); padding-top: 0.75rem; margin-bottom: 1rem;" @submit.prevent="handleAddMember">
          <h3 style="font-size: 0.95rem; margin-bottom: 0.4rem;">添加新成员</h3>
          <div style="display: flex; gap: 0.5rem; margin-bottom: 0.4rem;">
            <input v-model.trim="memberUsername" style="flex: 1;" placeholder="输入成员用户名" required />
            <select v-model="memberRole" style="width: 7rem;">
              <option value="MEMBER">只读成员</option>
              <option value="EDITOR">编辑者</option>
            </select>
            <button type="submit" :disabled="submittingMember">{{ submittingMember ? '添加中…' : '添加' }}</button>
          </div>
          <p v-if="shareMessage" :class="{ error: shareIsError, success: !shareIsError }" style="margin: 0.2rem 0; font-size: 0.85rem;">{{ shareMessage }}</p>
        </form>

        <!-- 跨库复制题目小工具 -->
        <div style="border-top: 1px dashed var(--border-strong); padding-top: 0.75rem;">
          <h3 style="font-size: 0.95rem; margin-bottom: 0.4rem;">题目跨库快速复制</h3>
          <div style="display: flex; gap: 0.5rem; align-items: center;">
            <input v-model.trim="copyQuestionId" style="flex: 1;" placeholder="输入当前题库的题目 ID" />
            <select v-model="copyTargetBankId" style="width: 9rem;">
              <option value="">选择目标题库</option>
              <option v-for="b in banks.filter(x => x.id !== targetBankForShare?.id)" :key="b.id" :value="b.id">
                {{ b.name }}
              </option>
            </select>
            <button type="button" :disabled="!copyQuestionId.trim() || !copyTargetBankId || copyingQuestion" @click="handleCopyQuestion">
              {{ copyingQuestion ? '复制中…' : '复制题目' }}
            </button>
          </div>
          <p v-if="copyNotice" style="font-size: 0.85rem; color: var(--primary); margin: 0.3rem 0 0 0;">{{ copyNotice }}</p>
        </div>

        <div class="bank-actions" style="margin-top: 1rem;">
          <button type="button" @click="showShareDialog = false">关闭</button>
        </div>
      </div>
    </div>

    <!-- EE-008: 题库多格式导出对话框 -->
    <div v-if="showExportDialog" class="exam-setup-backdrop" @click.self="showExportDialog = false" @keydown.esc="showExportDialog = false">
      <div class="exam-setup-dialog" role="dialog" style="width: min(100%, 28rem);">
        <h2>题库数据导出</h2>
        <p>题库：【{{ targetBankForExport?.name }}】（共 {{ targetBankForExport?.question_count || 0 }} 题）</p>
        <label>导出文件格式
          <select v-model="exportFormat">
            <option value="json">JSON 格式 (.json - 包含完整结构与元数据)</option>
            <option value="csv">CSV 表格 (.csv - 适用于 Excel / 统计)</option>
            <option value="txt">纯文本排版 (.txt - 适用于离线打印/阅读)</option>
            <option value="xlsx">Excel 电子表格 (.xlsx)</option>
          </select>
        </label>
        <div class="bank-actions">
          <button type="button" @click="showExportDialog = false">取消</button>
          <button type="button" class="primary" :disabled="exporting" @click="handleDownloadExport">
            {{ exporting ? '正在生成导出…' : '立即下载文件' }}
          </button>
        </div>
      </div>
    </div>

    <!-- EE-005: 变式题草稿箱对话框 -->
    <div v-if="showDraftsDialog" class="exam-setup-backdrop" @click.self="showDraftsDialog = false" @keydown.esc="showDraftsDialog = false">
      <div class="exam-setup-dialog" role="dialog" style="width: min(100%, 46rem); max-height: 85vh; overflow-y: auto;">
        <h2>AI 变式题草稿箱</h2>
        <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.75rem;">
          AI 根据错题或考点生成的变式题在此暂存。未经您审阅确认，变式题绝不会自动进入正式题库。
        </p>
        <div v-if="loadingDrafts" style="text-align: center; color: var(--text-tertiary); padding: 1.5rem;">正在加载草稿…</div>
        <div v-else-if="!draftsList.length" style="text-align: center; color: var(--text-tertiary); padding: 2rem;">
          暂无待审阅的变式题草稿。您可以在刷题过程中点击“生成变式题草稿”。
        </div>
        <div v-else style="display: flex; flex-direction: column; gap: 1rem;">
          <div v-for="d in draftsList" :key="d.id" style="border: 1px solid var(--border); border-radius: 8px; padding: 1rem; background: var(--bg-subtle);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
              <span style="font-size: 0.75rem; padding: 0.15rem 0.4rem; background: var(--primary-light); color: var(--linear-cyan); border-radius: 4px; font-weight: 600; font-family: var(--linear-mono);">
                {{ d.type }} · 难度 {{ d.difficulty }}
              </span>
              <span style="font-size: 0.75rem; color: var(--text-tertiary);">{{ d.created_at }}</span>
            </div>
            <label style="font-size: 0.8rem; font-weight: 600;">题干：
              <textarea v-model="d.stem" rows="2" style="font-size: 0.85rem; margin-top: 0.2rem;"></textarea>
            </label>
            <div v-if="d.options && d.options.length" style="margin: 0.5rem 0;">
              <span style="font-size: 0.8rem; font-weight: 600;">选项：</span>
              <div v-for="(opt, idx) in d.options" :key="idx" style="display: flex; gap: 0.4rem; margin-top: 0.2rem;">
                <input v-model="opt.key" style="width: 3rem; font-size: 0.8rem;" />
                <input v-model="opt.text" style="flex: 1; font-size: 0.8rem;" />
              </div>
            </div>
            <div style="display: flex; gap: 1rem; margin-top: 0.5rem;">
              <label style="flex: 1; font-size: 0.8rem; font-weight: 600;">标准答案：
                <input v-model="d.answer" style="font-size: 0.85rem;" />
              </label>
            </div>
            <label style="font-size: 0.8rem; font-weight: 600; margin-top: 0.5rem;">解析说明：
              <textarea v-model="d.explanation" rows="2" style="font-size: 0.85rem; margin-top: 0.2rem;"></textarea>
            </label>
            <div style="display: flex; justify-content: flex-end; gap: 0.6rem; margin-top: 0.75rem;">
              <button type="button" style="color: var(--danger);" :disabled="d.processing" @click="handleDiscardDraft(d.id)">
                丢弃草稿
              </button>
              <button type="button" class="primary" :disabled="d.processing" @click="handleAcceptDraft(d)">
                {{ d.processing ? '入库中…' : '确认转正入库' }}
              </button>
            </div>
          </div>
        </div>
        <div class="bank-actions" style="margin-top: 1rem;">
          <button type="button" @click="showDraftsDialog = false">关闭</button>
        </div>
      </div>
    </div>

    <!-- EE-010: 考试蓝图档案与规则配置对话框 -->
    <div v-if="showBlueprintDialog" class="exam-setup-backdrop" @click.self="showBlueprintDialog = false" @keydown.esc="showBlueprintDialog = false">
      <div class="exam-setup-dialog" role="dialog" style="width: min(100%, 42rem); max-height: 85vh; overflow-y: auto;">
        <h2>考试蓝图档案与组卷规则配置</h2>

        <!-- 蓝图引导卡片 -->
        <div style="background: var(--linear-bg-subtle); border: 1px solid var(--border); border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 1rem;">
          <div style="display: flex; gap: 0.5rem; align-items: flex-start;">
            <LinearIcon name="blueprint" size="20" style="color: var(--primary); margin-top: 2px;" />
            <div style="font-size: 0.85rem; color: var(--text-main); line-height: 1.5;">
              <strong>什么是考试蓝图 (Blueprint)？</strong>
              <p style="margin: 0.2rem 0 0.4rem; color: var(--text-muted);">
                考试蓝图用于定义标准化试卷规则（如：35道单选题 + 10道多选题 + 5道判断题）。模考时将严格按照各小节设定的题型、数量、难度与章节，从题库中动态抽题，真实还原官方考场结构。
              </p>
              <div style="display: flex; gap: 0.4rem; align-items: center; flex-wrap: wrap;">
                <span style="font-weight: 600; color: var(--primary);">快速套用模板：</span>
                <button type="button" style="font-size: 0.75rem; padding: 0.15rem 0.5rem; background: var(--primary-light); border: 1px solid var(--primary-border); border-radius: 4px; cursor: pointer;" @click="applyBlueprintTemplate('STANDARD_50')">
                  标准综合卷 (50题)
                </button>
                <button type="button" style="font-size: 0.75rem; padding: 0.15rem 0.5rem; background: var(--primary-light); border: 1px solid var(--primary-border); border-radius: 4px; cursor: pointer;" @click="applyBlueprintTemplate('OBJECTIVE_30')">
                  客观题速测 (30题)
                </button>
                <button type="button" style="font-size: 0.75rem; padding: 0.15rem 0.5rem; background: var(--primary-light); border: 1px solid var(--primary-border); border-radius: 4px; cursor: pointer;" @click="applyBlueprintTemplate('ADVANCED_SPRINT')">
                  考前冲刺卷 (75题含倒扣分)
                </button>
                <button type="button" style="font-size: 0.75rem; padding: 0.15rem 0.5rem; background: var(--primary-light); border: 1px solid var(--primary-border); border-radius: 4px; cursor: pointer;" @click="applyBlueprintTemplate('BASIC_25')">
                  基础概念卷 (25题)
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- 档案选择与新建 -->
        <div style="display: flex; gap: 0.5rem; align-items: center; margin-bottom: 1rem;">
          <select v-model="activeBlueprintProfileId" style="flex: 1;" @change="loadProfileBlueprint">
            <option value="">-- 选择要配置的考试档案 --</option>
            <option v-for="p in examProfiles" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
          <button type="button" @click="showCreateProfileBox = !showCreateProfileBox">+ 新建档案</button>
        </div>

        <form v-if="showCreateProfileBox" style="background: var(--bg-subtle); padding: 0.75rem; border-radius: 6px; margin-bottom: 1rem;" @submit.prevent="handleCreateExamProfile">
          <div style="display: flex; gap: 0.5rem; margin-bottom: 0.4rem;">
            <input v-model.trim="newProfileName" style="flex: 1;" placeholder="新档案名称（如：系统分析师模拟一卷）" required />
            <button type="submit" :disabled="creatingProfile">{{ creatingProfile ? '创建中…' : '创建' }}</button>
          </div>
          <input v-model.trim="newProfileDesc" placeholder="简要描述说明（可选）" />
        </form>

        <div v-if="activeBlueprintProfileId" style="border: 1px solid var(--border); border-radius: 8px; padding: 1rem; background: var(--bg-card);">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; padding-bottom: 0.5rem; border-bottom: 1px solid var(--border);">
            <h3 style="font-size: 0.95rem; margin: 0; color: var(--text-main);">编辑组卷规则</h3>
            <span style="font-size: 0.8rem; background: var(--bg-subtle); border: 1px solid var(--border); border-radius: 4px; padding: 0.2rem 0.5rem; color: var(--text-muted); font-family: var(--linear-mono);">
              已规划 {{ blueprintConfig.sections.length }} 个小节 · 共 <strong>{{ computedBlueprintTotal }}</strong> 题 · 建议限时 {{ Math.round(computedBlueprintTotal * 1.5) }} 分钟
            </span>
          </div>

          <label style="font-size: 0.85rem; margin-bottom: 0.75rem; color: var(--text-main);">错题负分扣减分值 (negative_mark)：
            <input v-model.number="blueprintConfig.negative_mark" type="number" step="0.1" min="0" max="10" style="width: 8rem;" />
            <span style="font-size: 0.75rem; color: var(--text-tertiary); font-weight: normal; margin-left: 0.5rem;">答错时倒扣分值，0 表示不倒扣</span>
          </label>

          <div style="margin-bottom: 0.75rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
              <span style="font-size: 0.85rem; font-weight: 600; color: var(--text-main);">试卷大题 / 小节规则定义 (Sections)：</span>
              <button type="button" style="font-size: 0.75rem; padding: 0.2rem 0.5rem;" @click="handleAddBlueprintSection">+ 添加大题小节</button>
            </div>
            <div v-if="!blueprintConfig.sections.length" style="font-size: 0.8rem; color: var(--text-muted); padding: 0.5rem; background: var(--bg-subtle); border-radius: 4px; text-align: center;">
              暂无小节规则，组卷时将使用默认全题库抽选。您可以点击上方按钮添加小节或套用预设模板。
            </div>
            <div v-for="(sec, sIdx) in blueprintConfig.sections" :key="sIdx" style="display: flex; flex-direction: column; gap: 0.4rem; margin-bottom: 0.5rem; padding: 0.6rem; background: var(--bg-subtle); border: 1px solid var(--border); border-radius: 6px;">
              <div style="display: flex; gap: 0.4rem; align-items: center;">
                <input v-model.trim="sec.name" placeholder="小节名（如：单选第1部分）" style="width: 10rem; font-size: 0.8rem;" />
                <select v-model="sec.type" style="width: 6.5rem; font-size: 0.8rem;">
                  <option value="SINGLE">单选题</option>
                  <option value="MULTI">多选题</option>
                  <option value="JUDGE">判断题</option>
                  <option value="ESSAY">简答题</option>
                </select>
                <input v-model.number="sec.count" type="number" min="1" placeholder="题量" style="width: 4.5rem; font-size: 0.8rem;" title="抽取题量" />
                <select v-model.number="sec.difficulty" style="width: 5.5rem; font-size: 0.8rem;" title="难度要求">
                  <option :value="null">任意难度</option>
                  <option :value="1">1 (入门)</option>
                  <option :value="2">2 (较易)</option>
                  <option :value="3">3 (中等)</option>
                  <option :value="4">4 (较难)</option>
                  <option :value="5">5 (极难)</option>
                </select>
                <button type="button" style="color: var(--danger); border: none; background: none; cursor: pointer; padding: 0 0.3rem;" title="删除小节" @click="blueprintConfig.sections.splice(sIdx, 1)">✕</button>
              </div>
              <div style="display: flex; gap: 0.4rem; align-items: center; font-size: 0.75rem;">
                <input v-model.trim="sec.chapter_id" placeholder="限定章节(可选，如：第1章)" style="flex: 1; font-size: 0.75rem;" />
                <input v-model.trim="sec.tags" placeholder="限定标签(可选，逗号分隔，如：必考,计算题)" style="flex: 1; font-size: 0.75rem;" />
              </div>
            </div>
          </div>

          <div style="display: flex; justify-content: flex-end; gap: 0.6rem;">
            <button type="button" class="primary" :disabled="savingBlueprint" @click="handleSaveBlueprint">
              {{ savingBlueprint ? '正在保存…' : '保存蓝图配置' }}
            </button>
          </div>
        </div>

        <div class="bank-actions" style="margin-top: 1rem;">
          <button type="button" @click="showBlueprintDialog = false">关闭</button>
        </div>
      </div>
    </div>

    <!-- EE-012: 个人资料管理对话框 -->
    <div v-if="showAssetsDialog" class="exam-setup-backdrop" @click.self="showAssetsDialog = false" @keydown.esc="showAssetsDialog = false">
      <div class="exam-setup-dialog assets-dialog" role="dialog" aria-modal="true" style="width: min(100%, 40rem);" aria-labelledby="assets-dialog-title">
        <h2 id="assets-dialog-title">个人学习资料管理</h2>
        <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1rem;">
          管理您的个人笔记、速记口诀与参考文档。AI 答疑时将自动基于此专属知识库提供点拨。
        </p>

        <!-- 新增快速笔记 -->
        <form style="display: flex; gap: 0.5rem; margin-bottom: 1rem;" @submit.prevent="handleCreateAsset">
          <select v-model="newAssetType" style="width: 7rem;">
            <option value="NOTE">个人笔记</option>
            <option value="SUMMARY">知识总结</option>
            <option value="MNEMONIC">速记口诀</option>
          </select>
          <input v-model.trim="newAssetContent" style="flex: 1;" placeholder="输入笔记或口诀内容..." required />
          <button type="submit" :disabled="savingAsset">{{ savingAsset ? '添加中…' : '+ 添加' }}</button>
        </form>

        <!-- 上传文档 -->
        <div style="margin-bottom: 1.25rem; padding: 0.75rem; border: 1px dashed var(--border-strong); border-radius: 6px;">
          <label style="font-size: 0.85rem; display: block; margin-bottom: 0.4rem;">
            上传参考文档（支持 PDF / Markdown / TXT，由服务器统一解析文本并隔离存储）：
          </label>
          <input type="file" accept=".pdf,.md,.txt,.markdown" @change="handleUploadAssetFile" :disabled="uploadingAsset" />
          <span v-if="uploadingAsset" style="margin-left: 0.5rem; color: var(--primary); font-size: 0.85rem;">正在解析上传…</span>
        </div>

        <!-- 资料列表 -->
        <div style="max-height: 18rem; overflow-y: auto; margin-bottom: 1rem;">
          <div v-if="loadingAssets" style="text-align: center; padding: 1rem; color: var(--text-tertiary);">正在加载资料…</div>
          <div v-else-if="!assetsList.length" style="text-align: center; padding: 1.5rem; color: var(--text-tertiary);">
            暂无个人资料，您可以通过上方输入笔记或上传文档。
          </div>
          <div v-else style="display: flex; flex-direction: column; gap: 0.6rem;">
            <div
              v-for="item in assetsList"
              :key="item.id"
              style="padding: 0.75rem; border: 1px solid var(--border); border-radius: 6px; background: var(--bg-page);"
            >
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                <span style="font-size: 0.75rem; font-weight: 600; padding: 0.15rem 0.4rem; background: var(--primary-light); color: var(--primary); border-radius: 4px;">
                  {{ item.asset_type === 'MNEMONIC' ? '速记口诀' : item.asset_type === 'SUMMARY' ? '知识总结' : '笔记' }}
                </span>
                <div style="display: flex; align-items: center; gap: 0.75rem;">
                  <time style="font-size: 0.75rem; color: var(--text-tertiary);">{{ item.created_at?.slice(0, 10) }}</time>
                  <button type="button" style="background: none; border: none; color: var(--danger); font-size: 0.75rem; cursor: pointer; padding: 0;" @click="handleDeleteAsset(item.id)">
                    删除
                  </button>
                </div>
              </div>
              <p style="margin: 0; font-size: 0.85rem; line-height: 1.4; color: var(--text-main); white-space: pre-wrap;">{{ item.content }}</p>
            </div>
          </div>
        </div>

        <div class="bank-actions">
          <button type="button" @click="showAssetsDialog = false">关闭</button>
        </div>
      </div>
    </div>

    <!-- EE-009: AI 与搜索配置对话框 -->
    <div v-if="showAiConfigDialog" class="exam-setup-backdrop" @click.self="showAiConfigDialog = false">
      <div class="exam-setup-dialog" role="dialog" style="width: min(100%, 36rem);" aria-modal="true">
        <h2>AI 模型与联网搜索配置</h2>
        <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1rem;">
          支持配置自定义大模型服务（如本地 Ollama、OpenAI 兼容接口）及联网搜索服务。敏感密钥在前端展示时自动脱敏，在后端受保护加载。
        </p>

        <div v-if="aiConfigNotice" :style="{ padding: '0.6rem 0.8rem', borderRadius: '6px', fontSize: '0.85rem', marginBottom: '0.75rem', background: aiConfigNotice.includes('成功') ? 'var(--success-light)' : 'var(--danger-light)', color: aiConfigNotice.includes('成功') ? 'var(--success)' : 'var(--danger)' }">
          {{ aiConfigNotice }}
        </div>

        <div style="display: flex; flex-direction: column; gap: 0.75rem; margin-bottom: 1rem;">
          <label style="font-size: 0.85rem; font-weight: 500;">
            AI 服务商类型
            <select v-model="aiConfigForm.ai_provider" style="width: 100%; margin-top: 0.25rem;">
              <option value="openai">OpenAI / 兼容接口 (如 vLLM / DeepSeek / 通义等)</option>
              <option value="ollama">本地 Ollama (如 http://localhost:11434/v1)</option>
            </select>
          </label>

          <label style="font-size: 0.85rem; font-weight: 500;">
            API Base URL
            <input v-model="aiConfigForm.ai_api_base" type="text" placeholder="https://api.openai.com/v1" style="width: 100%; margin-top: 0.25rem;" />
          </label>

          <label style="font-size: 0.85rem; font-weight: 500;">
            模型标识 (Model)
            <input v-model="aiConfigForm.ai_model" type="text" placeholder="如 gpt-4o-mini 或 qwen2.5:7b" style="width: 100%; margin-top: 0.25rem;" />
          </label>

          <label style="font-size: 0.85rem; font-weight: 500;">
            API Key (输入新密钥以更新，留空或带星号将保留原密文)
            <input v-model="aiConfigForm.ai_api_key" type="password" placeholder="sk-..." style="width: 100%; margin-top: 0.25rem;" />
          </label>

          <label style="font-size: 0.85rem; font-weight: 500;">
            联网核查服务
            <select v-model="aiConfigForm.search_provider" style="width: 100%; margin-top: 0.25rem;">
              <option value="open-webSearch">open-webSearch (本地或远程搜索适配器)</option>
              <option value="offline">完全离线 (不进行外部检索)</option>
            </select>
          </label>

          <label v-if="aiConfigForm.search_provider === 'open-webSearch'" style="font-size: 0.85rem; font-weight: 500;">
            联网搜索端点 URL
            <input v-model="aiConfigForm.search_api_base" type="text" placeholder="http://localhost:8000/v1/search" style="width: 100%; margin-top: 0.25rem;" />
          </label>
        </div>

        <div class="bank-actions">
          <button type="button" @click="showAiConfigDialog = false">关闭</button>
          <button type="button" class="primary" :disabled="aiConfigLoading" @click="saveAiConfigAction">
            {{ aiConfigLoading ? '保存中…' : '保存配置' }}
          </button>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import LinearIcon from '../components/LinearIcon.vue'
import { listBanks, createBank, createQuestion, addBankMember, listBankMembers, removeBankMember, copyQuestionToBank } from '../api/banks'
import { startExam, listProfiles, createProfile, saveBlueprint, getBlueprint } from '../api/exams'
import { listActiveSessions, getSession, abandonSession, abandonAllSessions } from '../api/practice'
import { listAssets, createAsset, uploadAssetFile, deleteAsset } from '../api/assets'
import { listDrafts, acceptDraft, discardDraft, getAiConfig, updateAiConfig } from '../api/ai'
import { triggerSyncEvent } from '../api/sync'
import { useLocale } from '../composables/useLocale.js'

const { t } = useLocale()

const props = defineProps({ token: { type: String, required: true }, user: { type: Object, default: null } })
const emit = defineEmits(['start', 'mock-exam', 'resume-session', 'learning', 'mistakes', 'import', 'logout'])

const banks = ref([])
const activeSessions = ref([])
const showActiveSessionsModal = ref(false)
const abandoningSession = ref(false)
const loading = ref(true)
const error = ref('')

function getActiveSessionForBank(bankId) {
  return activeSessions.value.find(s => s.bank_id === bankId) || null
}

const examBank = ref(null)
const examProfiles = ref([])
const selectedProfileId = ref('')
const selectedProfileBlueprintSummary = ref(null)
const recordMistakes = ref(true)
const totalQuestions = ref(0)
const timeLimitMinutes = ref(120)
const startingExam = ref(false)
const examError = ref('')

const showCreateDialog = ref(false)
const creatingBank = ref(false)
const createError = ref('')
const newBank = ref({ name: '', description: '', category: '默认分类' })

const showAddQuestionDialog = ref(false)
const targetBankForQuestion = ref(null)
const savingQuestion = ref(false)
const addQuestionError = ref('')
const addQuestionForm = ref({
  stem: '',
  type: 'SINGLE',
  options: [{ key: 'A', text: '' }, { key: 'B', text: '' }, { key: 'C', text: '' }, { key: 'D', text: '' }],
  answer: 'A',
  explanation: '',
  difficulty: 3,
  tags: '',
})

const showShareDialog = ref(false)
const targetBankForShare = ref(null)
const memberUsername = ref('')
const memberRole = ref('MEMBER')
const submittingMember = ref(false)
const shareMessage = ref('')
const shareIsError = ref(false)
const bankMembersList = ref([])
const loadingMembers = ref(false)
const copyQuestionId = ref('')
const copyTargetBankId = ref('')
const copyingQuestion = ref(false)
const copyNotice = ref('')

// EE-008: 导出状态
const showExportDialog = ref(false)
const targetBankForExport = ref(null)
const exportFormat = ref('json')
const exporting = ref(false)

// EE-005: 变式题草稿箱状态
const showDraftsDialog = ref(false)
const draftsList = ref([])
const loadingDrafts = ref(false)

// EE-010: 考试蓝图档案与规则状态
const showBlueprintDialog = ref(false)
const activeBlueprintProfileId = ref('')
const showCreateProfileBox = ref(false)
const newProfileName = ref('')
const newProfileDesc = ref('')
const creatingProfile = ref(false)
const savingBlueprint = ref(false)
const blueprintConfig = ref({
  negative_mark: 0,
  sections: [],
})

// EE-012: 个人资料管理状态与方法
const showAssetsDialog = ref(false)
const assetsList = ref([])
const loadingAssets = ref(false)
const savingAsset = ref(false)
const uploadingAsset = ref(false)
const newAssetType = ref('NOTE')
const newAssetContent = ref('')

async function openAssetsDialog() {
  showAssetsDialog.value = true
  await fetchAssets()
}

async function fetchAssets() {
  loadingAssets.value = true
  try {
    assetsList.value = await listAssets(props.token)
  } catch (err) {
    console.error('加载资料失败', err)
  } finally {
    loadingAssets.value = false
  }
}

async function handleCreateAsset() {
  if (!newAssetContent.value.trim()) return
  savingAsset.value = true
  try {
    await createAsset(props.token, {
      asset_type: newAssetType.value,
      content: newAssetContent.value.trim(),
    })
    newAssetContent.value = ''
    await fetchAssets()
  } catch (err) {
    alert(`添加资料失败：${err.detail || err.message}`)
  } finally {
    savingAsset.value = false
  }
}

async function handleUploadAssetFile(event) {
  const file = event.target.files?.[0]
  if (!file) return
  uploadingAsset.value = true
  try {
    await uploadAssetFile(props.token, file, 'NOTE')
    event.target.value = ''
    await fetchAssets()
  } catch (err) {
    alert(`上传资料失败：${err.detail || err.message}`)
  } finally {
    uploadingAsset.value = false
  }
}

async function handleDeleteAsset(assetId) {
  if (!confirm('确认删除该条个人资料吗？')) return
  try {
    await deleteAsset(props.token, assetId)
    await fetchAssets()
  } catch (err) {
    alert(`删除资料失败：${err.detail || err.message}`)
  }
}

async function handleResume(sessionSummary) {
  try {
    const fullSession = await getSession(props.token, sessionSummary.id)
    showActiveSessionsModal.value = false
    emit('resume-session', fullSession)
  } catch (err) {
    alert(`恢复会话失败：${err.detail || err.message}`)
  }
}

async function handleCreateBank() {
  if (!newBank.value.name) return
  creatingBank.value = true
  createError.value = ''
  try {
    const created = await createBank(props.token, {
      name: newBank.value.name,
      description: newBank.value.description,
      category: newBank.value.category || '默认分类',
    })
    triggerSyncEvent('BANK_CREATED', 'BANK', created.id, { name: created.name })
    showCreateDialog.value = false
    newBank.value = { name: '', description: '', category: '默认分类' }
    banks.value = await listBanks(props.token)
  } catch (err) {
    createError.value = err.detail || err.message
  } finally {
    creatingBank.value = false
  }
}

async function openExamSetup(bank) {
  examBank.value = bank
  totalQuestions.value = bank.question_count
  timeLimitMinutes.value = 120
  examError.value = ''
  selectedProfileId.value = ''
  recordMistakes.value = true
  try {
    examProfiles.value = await listProfiles(props.token)
  } catch (_) {
    examProfiles.value = []
  }
}

async function beginExam() {
  if (!examBank.value || totalQuestions.value < 1 || totalQuestions.value > examBank.value.question_count) return
  startingExam.value = true
  examError.value = ''
  try {
    const session = await startExam(props.token, {
      bank_id: examBank.value.id,
      total_questions: totalQuestions.value,
      time_limit: timeLimitMinutes.value,
      profile_id: selectedProfileId.value || undefined,
      record_mistakes: recordMistakes.value,
    })
    emit('mock-exam', session)
    examBank.value = null
  } catch (err) {
    examError.value = err.detail || err.message
  } finally {
    startingExam.value = false
  }
}

function openAddQuestion(bank) {
  targetBankForQuestion.value = bank
  addQuestionForm.value = {
    stem: '',
    type: 'SINGLE',
    options: [{ key: 'A', text: '' }, { key: 'B', text: '' }, { key: 'C', text: '' }, { key: 'D', text: '' }],
    answer: 'A',
    explanation: '',
    difficulty: 3,
    tags: '',
  }
  addQuestionError.value = ''
  showAddQuestionDialog.value = true
}

function handleAddOpt() {
  const letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
  const nextKey = letters[addQuestionForm.value.options.length] || `Opt${addQuestionForm.value.options.length + 1}`
  addQuestionForm.value.options.push({ key: nextKey, text: '' })
}

function handleToggleMultiAnswer(key) {
  let curr = addQuestionForm.value.answer ? addQuestionForm.value.answer.split('') : []
  if (curr.includes(key)) {
    curr = curr.filter(k => k !== key)
  } else {
    curr.push(key)
    curr.sort()
  }
  addQuestionForm.value.answer = curr.join('')
}

function onQuestionTypeChange() {
  if (addQuestionForm.value.type === 'JUDGE') {
    addQuestionForm.value.options = [
      { key: 'T', text: '正确' },
      { key: 'F', text: '错误' }
    ]
    addQuestionForm.value.answer = 'T'
  } else if ((addQuestionForm.value.type === 'SINGLE' || addQuestionForm.value.type === 'MULTI') && addQuestionForm.value.options.length === 2 && addQuestionForm.value.options[0].key === 'T') {
    addQuestionForm.value.options = [
      { key: 'A', text: '' },
      { key: 'B', text: '' },
      { key: 'C', text: '' },
      { key: 'D', text: '' }
    ]
    addQuestionForm.value.answer = 'A'
  }
}

async function handleCreateQuestion() {
  if (!targetBankForQuestion.value || !addQuestionForm.value.stem.trim()) return
  savingQuestion.value = true
  addQuestionError.value = ''
  try {
    const tagsList = addQuestionForm.value.tags
      ? addQuestionForm.value.tags.split(/[,，\s]+/).filter(Boolean)
      : []
    const created = await createQuestion(props.token, targetBankForQuestion.value.id, {
      stem: addQuestionForm.value.stem.trim(),
      type: addQuestionForm.value.type,
      options: addQuestionForm.value.options,
      answer: addQuestionForm.value.answer.trim(),
      explanation: addQuestionForm.value.explanation.trim(),
      difficulty: addQuestionForm.value.difficulty,
      tags: tagsList,
    })
    triggerSyncEvent('QUESTION_CREATED', 'QUESTION', created.id, { bank_id: targetBankForQuestion.value.id })
    targetBankForQuestion.value.question_count = (targetBankForQuestion.value.question_count || 0) + 1
    showAddQuestionDialog.value = false
  } catch (err) {
    addQuestionError.value = err.detail || err.message
  } finally {
    savingQuestion.value = false
  }
}

async function openShareDialog(bank) {
  targetBankForShare.value = bank
  memberUsername.value = ''
  memberRole.value = 'MEMBER'
  shareMessage.value = ''
  shareIsError.value = false
  copyQuestionId.value = ''
  copyTargetBankId.value = ''
  copyNotice.value = ''
  showShareDialog.value = true
  await fetchBankMembers(bank.id)
}

async function fetchBankMembers(bankId) {
  loadingMembers.value = true
  try {
    bankMembersList.value = await listBankMembers(props.token, bankId)
  } catch (err) {
    console.error('获取成员列表失败', err)
    bankMembersList.value = []
  } finally {
    loadingMembers.value = false
  }
}

async function handleAddMember() {
  if (!targetBankForShare.value || !memberUsername.value.trim()) return
  submittingMember.value = true
  shareMessage.value = ''
  try {
    await addBankMember(props.token, targetBankForShare.value.id, memberUsername.value.trim(), memberRole.value)
    shareIsError.value = false
    shareMessage.value = `成功添加成员 ${memberUsername.value}！`
    memberUsername.value = ''
    await fetchBankMembers(targetBankForShare.value.id)
  } catch (err) {
    shareIsError.value = true
    shareMessage.value = err.detail || err.message
  } finally {
    submittingMember.value = false
  }
}

async function handleRemoveMember(memberUserId) {
  if (!targetBankForShare.value || !confirm('确认移除该成员吗？')) return
  try {
    await removeBankMember(props.token, targetBankForShare.value.id, memberUserId)
    await fetchBankMembers(targetBankForShare.value.id)
  } catch (err) {
    alert(`移除成员失败：${err.detail || err.message}`)
  }
}

async function handleCopyQuestion() {
  if (!targetBankForShare.value || !copyQuestionId.value.trim() || !copyTargetBankId.value) return
  copyingQuestion.value = true
  copyNotice.value = ''
  try {
    await copyQuestionToBank(props.token, targetBankForShare.value.id, copyQuestionId.value.trim(), copyTargetBankId.value)
    triggerSyncEvent('QUESTION_COPIED', 'QUESTION', copyQuestionId.value.trim(), { target_bank_id: copyTargetBankId.value })
    copyNotice.value = '题目已成功复制到目标题库！'
    copyQuestionId.value = ''
    banks.value = await listBanks(props.token)
  } catch (err) {
    copyNotice.value = `复制失败：${err.detail || err.message}`
  } finally {
    copyingQuestion.value = false
  }
}

function openExportDialog(bank) {
  targetBankForExport.value = bank
  exportFormat.value = 'json'
  showExportDialog.value = true
}

async function handleDownloadExport() {
  if (!targetBankForExport.value) return
  exporting.value = true
  try {
    const res = await fetch(`/api/v1/banks/${targetBankForExport.value.id}/export?format=${exportFormat.value}`, {
      headers: {
        Authorization: `Bearer ${props.token}`,
      },
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || `导出失败 (${res.status})`)
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const ext = exportFormat.value === 'xlsx' ? 'xlsx' : exportFormat.value === 'csv' ? 'csv' : exportFormat.value === 'txt' ? 'txt' : 'json'
    a.download = `${targetBankForExport.value.name}_export.${ext}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    showExportDialog.value = false
  } catch (err) {
    alert(`导出失败：${err.message}`)
  } finally {
    exporting.value = false
  }
}

async function openDraftsDialog() {
  showDraftsDialog.value = true
  await fetchDrafts()
}

async function fetchDrafts() {
  loadingDrafts.value = true
  try {
    const drafts = await listDrafts(props.token, 'DRAFT')
    draftsList.value = (drafts || []).map(d => ({
      ...d,
      processing: false,
    }))
  } catch (err) {
    console.error('加载草稿失败', err)
  } finally {
    loadingDrafts.value = false
  }
}

async function handleAcceptDraft(draft) {
  draft.processing = true
  try {
    const modifications = {
      stem: draft.stem,
      options: draft.options,
      answer: draft.answer,
      explanation: draft.explanation,
    }
    await acceptDraft(props.token, draft.id, modifications)
    draftsList.value = draftsList.value.filter(d => d.id !== draft.id)
    banks.value = await listBanks(props.token)
  } catch (err) {
    alert(`转正入库失败：${err.detail || err.message}`)
  } finally {
    draft.processing = false
  }
}

async function handleDiscardDraft(draftId) {
  if (!confirm('确认丢弃该草稿吗？')) return
  try {
    await discardDraft(props.token, draftId)
    draftsList.value = draftsList.value.filter(d => d.id !== draftId)
  } catch (err) {
    alert(`丢弃草稿失败：${err.detail || err.message}`)
  }
}

async function openBlueprintDialog() {
  showBlueprintDialog.value = true
  try {
    examProfiles.value = await listProfiles(props.token)
  } catch (_) {
    examProfiles.value = []
  }
  if (examProfiles.value.length > 0 && !activeBlueprintProfileId.value) {
    activeBlueprintProfileId.value = examProfiles.value[0].id
    await loadProfileBlueprint()
  }
}

async function loadProfileBlueprint() {
  if (!activeBlueprintProfileId.value) return
  try {
    const bp = await getBlueprint(props.token, activeBlueprintProfileId.value)
    if (bp && (bp.sections || bp.negative_mark !== undefined)) {
      blueprintConfig.value = {
        negative_mark: bp.negative_mark || 0,
        sections: bp.sections || [],
      }
    } else {
      blueprintConfig.value = { negative_mark: 0, sections: [] }
    }
  } catch (err) {
    console.error('加载蓝图失败', err)
    blueprintConfig.value = { negative_mark: 0, sections: [] }
  }
}

async function handleCreateExamProfile() {
  if (!newProfileName.value.trim()) return
  creatingProfile.value = true
  try {
    const profile = await createProfile(props.token, {
      name: newProfileName.value.trim(),
      description: newProfileDesc.value.trim(),
    })
    examProfiles.value.push(profile)
    activeBlueprintProfileId.value = profile.id
    showCreateProfileBox.value = false
    newProfileName.value = ''
    newProfileDesc.value = ''
    blueprintConfig.value = { negative_mark: 0, sections: [] }
  } catch (err) {
    alert(`创建档案失败：${err.detail || err.message}`)
  } finally {
    creatingProfile.value = false
  }
}

function handleAddBlueprintSection() {
  blueprintConfig.value.sections.push({
    name: `小节 ${blueprintConfig.value.sections.length + 1}`,
    type: 'SINGLE',
    count: 10,
    difficulty: null,
  })
}

async function handleSaveBlueprint() {
  if (!activeBlueprintProfileId.value) return
  savingBlueprint.value = true
  try {
    await saveBlueprint(props.token, activeBlueprintProfileId.value, {
      negative_mark: blueprintConfig.value.negative_mark,
      sections: blueprintConfig.value.sections,
    })
    alert('考试蓝图保存成功！')
    examProfiles.value = await listProfiles(props.token)
  } catch (err) {
    alert(`保存蓝图失败：${err.detail || err.message}`)
  } finally {
    savingBlueprint.value = false
  }
}

const computedBlueprintTotal = computed(() => {
  if (!blueprintConfig.value?.sections?.length) return 0
  return blueprintConfig.value.sections.reduce((acc, s) => acc + (Number(s.count) || 0), 0)
})

function formatSessionMode(mode) {
  const map = {
    EXAM: '模拟考试',
    PRACTICE: '刷题练习',
    MISTAKE: '错题强化',
    FSRS: 'FSRS 复习',
    ELIMINATION: '斩杀查漏',
  }
  return map[mode] || mode || '刷题'
}

function formatTimeAgo(dateStr) {
  if (!dateStr) return ''
  try {
    const diffMs = Date.now() - new Date(dateStr).getTime()
    const diffMins = Math.floor(diffMs / 60000)
    if (diffMins < 1) return '刚刚'
    if (diffMins < 60) return `${diffMins} 分钟前`
    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours} 小时前`
    const diffDays = Math.floor(diffHours / 24)
    return `${diffDays} 天前`
  } catch (_) {
    return String(dateStr).slice(0, 16).replace('T', ' ')
  }
}

async function refreshActiveSessions() {
  try {
    activeSessions.value = await listActiveSessions(props.token)
  } catch (_) {
    activeSessions.value = []
  }
}

async function handleAbandonSession(sessionId) {
  if (!confirm('确认放弃此未完成会话吗？作答草稿将清除，不会再提示继续作答。')) return
  abandoningSession.value = true
  try {
    await abandonSession(props.token, sessionId)
    await refreshActiveSessions()
    if (activeSessions.value.length === 0) {
      showActiveSessionsModal.value = false
    }
  } catch (err) {
    alert(`放弃会话失败：${err.detail || err.message}`)
  } finally {
    abandoningSession.value = false
  }
}

async function handleAbandonAllSessions() {
  if (!confirm(`确认放弃全部 ${activeSessions.value.length} 个未完成会话吗？所有未完成草稿进度将被清空。`)) return
  abandoningSession.value = true
  try {
    await abandonAllSessions(props.token)
    await refreshActiveSessions()
    showActiveSessionsModal.value = false
  } catch (err) {
    alert(`放弃全部会话失败：${err.detail || err.message}`)
  } finally {
    abandoningSession.value = false
  }
}

function applyBlueprintTemplate(templateKey) {
  if (templateKey === 'STANDARD_50') {
    blueprintConfig.value = {
      negative_mark: 0,
      sections: [
        { name: '第一部分：单项选择题', type: 'SINGLE', count: 35, difficulty: null, chapter_id: '', tags: '' },
        { name: '第二部分：多项选择题', type: 'MULTI', count: 10, difficulty: null, chapter_id: '', tags: '' },
        { name: '第三部分：判断正误题', type: 'JUDGE', count: 5, difficulty: null, chapter_id: '', tags: '' },
      ],
    }
  } else if (templateKey === 'OBJECTIVE_30') {
    blueprintConfig.value = {
      negative_mark: 0,
      sections: [
        { name: '基础单选题', type: 'SINGLE', count: 20, difficulty: null, chapter_id: '', tags: '' },
        { name: '进阶多选题', type: 'MULTI', count: 10, difficulty: null, chapter_id: '', tags: '' },
      ],
    }
  } else if (templateKey === 'ADVANCED_SPRINT') {
    blueprintConfig.value = {
      negative_mark: 0.5,
      sections: [
        { name: '冲刺基础单选', type: 'SINGLE', count: 30, difficulty: 2, chapter_id: '', tags: '' },
        { name: '高难压轴单选', type: 'SINGLE', count: 20, difficulty: 4, chapter_id: '', tags: '' },
        { name: '考前多选提分', type: 'MULTI', count: 15, difficulty: 3, chapter_id: '', tags: '' },
        { name: '案例主观简答', type: 'ESSAY', count: 10, difficulty: null, chapter_id: '', tags: '' },
      ],
    }
  } else if (templateKey === 'BASIC_25') {
    blueprintConfig.value = {
      negative_mark: 0,
      sections: [
        { name: '入门概念单选', type: 'SINGLE', count: 20, difficulty: 1, chapter_id: '', tags: '' },
        { name: '判断明辨是非', type: 'JUDGE', count: 5, difficulty: 1, chapter_id: '', tags: '' },
      ],
    }
  }
}

async function onExamProfileChange() {
  if (!selectedProfileId.value) {
    selectedProfileBlueprintSummary.value = null
    return
  }
  try {
    const bp = await getBlueprint(props.token, selectedProfileId.value)
    if (bp && bp.sections?.length) {
      const total = bp.sections.reduce((acc, s) => acc + (Number(s.count) || 0), 0)
      selectedProfileBlueprintSummary.value = {
        sectionsCount: bp.sections.length,
        totalQuestions: total,
        negativeMark: bp.negative_mark || 0,
      }
      if (total > 0 && examBank.value) {
        totalQuestions.value = Math.min(total, examBank.value.question_count || total)
      }
    } else {
      selectedProfileBlueprintSummary.value = null
    }
  } catch (_) {
    selectedProfileBlueprintSummary.value = null
  }
}

function openBlueprintDialogFromExam() {
  examBank.value = null
  openBlueprintDialog()
}

const showAiConfigDialog = ref(false)
const aiConfigForm = ref({
  ai_provider: 'openai',
  ai_api_base: 'https://api.openai.com/v1',
  ai_model: 'gpt-4o-mini',
  ai_api_key: '',
  search_provider: 'open-webSearch',
  search_api_key: '',
  search_api_base: 'http://localhost:8000/v1/search',
})
const aiConfigNotice = ref('')
const aiConfigLoading = ref(false)

async function openAiConfigDialog() {
  showAiConfigDialog.value = true
  aiConfigNotice.value = ''
  try {
    const res = await getAiConfig(props.token)
    aiConfigForm.value = {
      ai_provider: res.ai_provider || 'openai',
      ai_api_base: res.ai_api_base || 'https://api.openai.com/v1',
      ai_model: res.ai_model || 'gpt-4o-mini',
      ai_api_key: res.ai_api_key || '',
      search_provider: res.search_provider || 'open-webSearch',
      search_api_key: res.search_api_key || '',
      search_api_base: res.search_api_base || 'http://localhost:8000/v1/search',
    }
  } catch (e) {
    aiConfigNotice.value = '加载配置失败：' + (e.message || e)
  }
}

async function saveAiConfigAction() {
  aiConfigLoading.value = true
  aiConfigNotice.value = ''
  try {
    const updated = await updateAiConfig(props.token, aiConfigForm.value)
    aiConfigForm.value.ai_api_key = updated.ai_api_key
    aiConfigForm.value.search_api_key = updated.search_api_key
    aiConfigNotice.value = '配置已保存成功！密钥已受保护加载并生效。'
  } catch (e) {
    aiConfigNotice.value = '保存配置失败：' + (e.message || e)
  } finally {
    aiConfigLoading.value = false
  }
}

async function handleSyncedEvents(e) {
  const detail = e.detail || {}
  const events = Array.isArray(detail) ? detail : (detail.events || [])
  if (detail.userId && props.user?.id && detail.userId !== props.user.id) {
    return
  }
  const hasBankOrQuestion = events.some(ev => ev.aggregate_type === 'BANK' || ev.aggregate_type === 'QUESTION')
  const hasSession = events.some(ev => ev.aggregate_type === 'SESSION')
  if (hasBankOrQuestion) {
    try { banks.value = await listBanks(props.token) } catch (_) {}
  }
  if (hasSession) {
    try { activeSessions.value = await listActiveSessions(props.token) } catch (_) {}
  }
}

onMounted(async () => {
  window.addEventListener('easyexam:events-synced', handleSyncedEvents)
  try {
    banks.value = await listBanks(props.token)
  } catch (err) {
    error.value = err.detail || err.message
  } finally {
    loading.value = false
  }
  try {
    activeSessions.value = await listActiveSessions(props.token)
  } catch (_) {
    activeSessions.value = []
  }
})

onUnmounted(() => {
  window.removeEventListener('easyexam:events-synced', handleSyncedEvents)
})

defineExpose({
  openBlueprintDialog,
  openDraftsDialog,
  openAiConfigDialog,
  openAssetsDialog,
  showCreateDialog
})
</script>

<style scoped>
.home-page {
  width: min(100% - 2rem, 76rem);
  margin: 1.5rem auto;
}

.home-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.25rem;
  padding: 0.85rem 1.25rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm);
}

.home-brand-area {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  flex-shrink: 0;
}

.home-brand-title {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.home-brand-icon {
  font-size: 1.4rem;
  line-height: 1;
}

.home-brand-title h1 {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-main);
  letter-spacing: -0.01em;
  margin: 0;
}

.home-user-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.2rem 0.6rem;
  background: var(--bg-muted);
  border: 1px solid var(--border);
  border-radius: var(--radius-full);
  font-size: 0.775rem;
  color: var(--text-muted);
  margin: 0;
}

.user-role-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--primary);
}
.user-role-dot.role-admin {
  background: var(--success);
}

.user-role-badge {
  font-size: 0.7rem;
  color: var(--primary);
  font-weight: 600;
  margin-left: 0.15rem;
}

.home-main-nav {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.main-nav-tab {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.45rem 0.85rem;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-lg);
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-main);
  cursor: pointer;
  transition: all 0.15s ease;
}

.main-nav-tab:hover {
  background: var(--bg-muted);
  border-color: var(--border);
  color: var(--primary);
}

.main-nav-tab.featured {
  color: var(--primary);
  font-weight: 600;
}

.main-nav-tab.featured:hover {
  background: var(--primary-light);
  border-color: var(--primary-border);
}

.home-actions-area {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  flex-shrink: 0;
}

.btn-create-bank {
  padding: 0.45rem 1rem;
  font-size: 0.875rem;
  font-weight: 600;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-xs);
}

.home-utility-group {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.btn-util {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.4rem 0.6rem;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  font-size: 0.8rem;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-util:hover {
  background: var(--bg-muted);
  border-color: var(--border);
  color: var(--text-main);
}

.btn-util.btn-logout {
  color: var(--danger);
}

.btn-util.btn-logout:hover {
  background: var(--danger-light);
  border-color: var(--danger-border);
  color: var(--danger);
}

.bank-card-title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.5rem;
  margin-bottom: 0.35rem;
}

.bank-card-title-row h2 {
  margin: 0;
  font-size: 1.15rem;
}

.badge-active-progress {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.2rem 0.5rem;
  background: var(--primary-light);
  color: var(--primary);
  border: 1px solid var(--primary-border);
  border-radius: 9999px;
  white-space: nowrap;
}

.bank-card.has-active-session {
  border-color: var(--primary-border);
  box-shadow: var(--shadow-sm);
}

.btn-resume-direct {
  background: var(--primary) !important;
  color: var(--on-primary) !important;
}

.bank-meta-info {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin: 0.5rem 0 0.85rem 0;
}

.bank-category-pill {
  font-size: 0.75rem;
  background: var(--bg-subtle);
  color: var(--text-muted);
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
}

.bank-actions-container {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  margin-top: 0.5rem;
}

.bank-primary-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
}

.bank-utility-actions {
  display: flex;
  gap: 0.4rem;
  align-items: center;
  flex-wrap: wrap;
  border-top: 1px dashed var(--border);
  padding-top: 0.5rem;
}

.btn-util-link {
  font-size: 0.775rem;
  padding: 0.25rem 0.55rem;
  color: var(--text-muted);
  background: var(--bg-muted);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  transition: all 0.15s ease;
}

.btn-util-link:hover {
  color: var(--primary);
  border-color: var(--primary-border);
  background: var(--primary-light);
}

.dialog-actions-row {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  margin-top: 0.75rem;
}

.exam-option-checkbox {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: var(--bg-page);
  padding: 0.6rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 0.85rem;
  cursor: pointer;
}

.exam-setup-backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  place-items: center;
  padding: 1rem;
  background: color-mix(in srgb, var(--text-main) 44%, transparent);
  backdrop-filter: blur(2px);
}

.exam-setup-dialog {
  width: min(100%, 28rem);
  display: grid;
  gap: 1.15rem;
  padding: 1.75rem;
  border-radius: var(--radius-xl);
  background: var(--bg-card);
  box-shadow: var(--shadow-xl);
  border: 1px solid var(--border);
}

.exam-setup-dialog h2 {
  font-size: 1.25rem;
  color: var(--text-main);
}

.exam-setup-dialog label {
  display: grid;
  gap: 0.4rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-main);
}

.exam-setup-dialog input:not([type="checkbox"]):not([type="radio"]),
.exam-setup-dialog textarea {
  width: 100%;
}

.exam-setup-dialog label.exam-option-checkbox,
.exam-setup-dialog label.ctrl-check {
  display: flex !important;
  flex-direction: row !important;
  align-items: center !important;
  gap: 0.6rem !important;
}

.exam-setup-dialog label.exam-option-checkbox input[type="checkbox"],
.exam-setup-dialog label.ctrl-check input[type="checkbox"],
.exam-setup-dialog input[type="checkbox"],
.exam-setup-dialog input[type="radio"] {
  width: auto !important;
  margin: 0 !important;
  flex: 0 0 auto !important;
}

.exam-setup-dialog .bank-actions {
  justify-content: flex-end;
  margin-top: 0.5rem;
}

.active-session-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  padding: 0.85rem 1.25rem;
  margin-bottom: 1.5rem;
  background: linear-gradient(135deg, var(--primary-light) 0%, var(--success-light) 100%);
  border: 1px solid var(--primary-border);
  border-radius: var(--radius-lg, 8px);
  box-shadow: var(--shadow-sm);
  flex-wrap: wrap;
}

.banner-content {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1;
  min-width: 280px;
}

.banner-badge {
  font-size: 0.8rem;
  font-weight: 700;
  padding: 0.2rem 0.55rem;
  background: var(--primary);
  color: var(--on-primary);
  border-radius: 4px;
  white-space: nowrap;
}

.banner-text {
  font-size: 0.9rem;
  color: var(--text-main);
  line-height: 1.4;
}

.banner-btn-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.btn-view-all-sessions {
  font-size: 0.85rem;
  padding: 0.45rem 0.85rem;
  background: var(--bg-card);
  border: 1px solid var(--border-strong);
  color: var(--text-main);
  border-radius: 6px;
  cursor: pointer;
  white-space: nowrap;
}

.btn-view-all-sessions:hover {
  background: var(--bg-subtle);
  border-color: var(--border-strong);
}

.btn-abandon-single {
  font-size: 0.85rem;
  color: var(--danger);
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.4rem 0.6rem;
  text-decoration: underline;
}

.btn-abandon-single:hover {
  color: var(--danger-hover);
}

@media (max-width: 900px) {
  .btn-util-label {
    display: none;
  }
}

@media (max-width: 768px) {
  .home-page {
    width: 100%;
    padding: 0 0.5rem;
    margin: 0.5rem auto;
  }
  .home-header {
    flex-direction: column;
    align-items: stretch;
    gap: 0.45rem;
    padding: 0.55rem 0.75rem;
    margin-bottom: 0.65rem;
  }
  .home-brand-area {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
  }
  .home-brand-title h1 {
    font-size: 1.1rem;
  }
  .home-user-pill {
    font-size: 0.75rem;
    padding: 0.15rem 0.45rem;
  }
  .home-main-nav {
    display: flex;
    overflow-x: auto;
    width: 100%;
    padding-bottom: 0.1rem;
    gap: 0.35rem;
  }
  .main-nav-tab {
    flex: 1;
    justify-content: center;
    padding: 0.35rem 0.4rem;
    font-size: 0.78rem;
    white-space: nowrap;
    background: var(--bg-muted);
    border-color: var(--border);
  }
  .home-actions-area {
    width: 100%;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.5rem;
  }
  .btn-create-bank {
    flex: 1;
    text-align: center;
    padding: 0.4rem 0.6rem;
    font-size: 0.82rem;
    min-height: 32px;
  }
  .home-utility-group {
    display: flex;
    gap: 0.25rem;
    justify-content: flex-end;
  }
  .home-utility-group .btn-util {
    padding: 0.35rem 0.45rem;
    font-size: 0.82rem;
    min-height: 32px;
  }
  .active-session-banner {
    padding: 0.6rem 0.85rem;
    gap: 0.5rem;
    margin-bottom: 0.85rem;
  }
  .banner-text {
    font-size: 0.82rem;
  }
  .bank-primary-actions {
    width: 100%;
  }
  .bank-primary-actions button {
    flex: 1;
    min-height: 2.4rem;
  }
}
</style>
