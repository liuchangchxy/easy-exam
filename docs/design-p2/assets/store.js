/* ==========================================================================
   EasyExam 产品原型 · 共享状态层（第三轮：跨页面交互收敛）
   --------------------------------------------------------------------------
   作用：把原本各自为政的规格页连成一个可连续操作的产品原型。
     · 单一数据源：题库 / 题目 / 笔记 / 导入任务 / 学习会话 / 成员 / 设置 / 角色
     · 持久化：localStorage（刷新、跨页面不丢；「重置演示数据」可一键清空）
     · 跨页同步：storage 事件（另一页写了数据，本页即时跟上）+ 同页订阅
     · 视图状态：各页的筛选/搜索/页签/分页/选择集按页保存，返回时恢复；
       URL 参数优先于记忆（深链可穿透）
   约定（所有页面必须遵守）：
     1. 页面脚本只通过 eeStore 读写业务数据，不再自己维护第二份；
     2. 改数据用 eeStore 的领域方法（addBank / finishSession …），
        它们会同步派生计数并通知订阅者；
     3. 视图状态用 eeStore.view.save(key, patch) / eeStore.view.load(key)；
     4. 导航用真实链接 + 查询参数带上下文（?bank=b_acc&tab=questions）。
   ========================================================================== */
(function () {
  var KEY = 'eeStore.v3';
  var VERSION = 5;

  /* ---------------- 种子数据（与第一/二轮屏幕内容一致，便于对照验收） ---------------- */
  function seed() {
    return {
      version: VERSION,
      session: { loggedIn: false, user: 'accept_admin_1794570360969' },
      settings: {
        theme: 'light',        // light | dark | system
        palette: 'editorial',  // editorial | gruvbox | everforest | catppuccin
        density: 'cozy',       // cozy | compact
        lang: 'zh',            // zh | en
        practiceTimer: false,  // 普通练习计时器默认隐藏（已定决策），模考常驻
        /* 判定模式（账户偏好，P3 随账号同步）：submit = 明确提交后判；instant = 点选即判。
           只影响单选与判断题，多选一律保持提交后判。 */
        judgeMode: 'submit',
        /* AI 解释开关与密钥：账户偏好，P3 随账号同步。密钥只存「已配置」，不回显原文。 */
        aiEnabled: true,
        aiKey: '',
        netKey: '',
        autoSave: true,
        online: true
      },
      role: 'OWNER',           // 题库角色：OWNER | EDITOR | MEMBER | VIEWER（当前题库内的身份）
      // 实例角色与题库角色是两个独立维度：实例管理员不因此获得任何题库的访问权，
      // 题库所有者也不因此获得实例管理权。instance.manage 只按 instanceRole 判定。
      instanceRole: 'admin',   // admin | user（实例角色，与题库角色互不推导）
      banks: [
        { id: 'b_acc', name: '验收题库 1794570360969', category: '默认分类', desc: '', count: 4, archived: false, shared: false, role: 'OWNER', updatedAt: '2026-11-24' },
        { id: 'b_rk', name: '软考真题库 1794570360969', category: '软考', desc: '系统集成项目管理工程师历年真题', count: 120, archived: false, shared: false, role: 'OWNER', updatedAt: '2026-11-20' },
        { id: 'b_sh', name: '共享题库 网络技术', category: '共享', desc: '他人共享，只读', count: 0, archived: false, shared: true, role: 'VIEWER', readonly: true, updatedAt: '2026-11-18' },
        { id: 'b_en', name: '英语词汇 · 每日 50 词', category: '英语', desc: '每日定量背诵', count: 50, archived: false, shared: false, role: 'OWNER', updatedAt: '2026-11-22' },
        { id: 'b_old', name: '旧题库 1794570360969', category: '默认分类', desc: '', count: 12, archived: true, shared: false, role: 'OWNER', updatedAt: '2026-10-30' }
      ],
      questions: [
        { id: '3F9A1C02', bankId: 'b_acc', stem: '每周一学校开展直播课程，在直播中实时回复学生问题属于（ ）', type: '单选题', difficulty: '基础', chapter: '沟通管理', version: 'v1', archived: false, tags: ['沟通'] },
        { id: '7B21E4D9', bankId: 'b_acc', stem: 'OSI 的（ ）不适合提供相应的安全服务。', type: '单选题', difficulty: '进阶', chapter: '信息安全', version: 'v1', archived: false, tags: ['OSI'] },
        { id: 'A05C8F31', bankId: 'b_acc', stem: '以下不属于“临时性”的是（ ）', type: '单选题', difficulty: '基础', chapter: '项目管理基础', version: 'v1', archived: false, tags: [] },
        { id: 'E4D72B60', bankId: 'b_acc', stem: '（ ）按照业务功能聚合性进行应用规划，建设与应用组件对应的应用系统。', type: '单选题', difficulty: '困难', chapter: '范围管理', version: 'v2', archived: false, tags: ['新题'] }
      ],
      notes: [
        { id: 'n1', title: 'OSI 安全服务归类：传输层、网络层、应用层可提供，会话层不适合', bankId: 'b_acc', tags: ['安全'], starred: true, updatedAt: '2026-11-24' },
        { id: 'n2', title: '子网划分的快速算法：借一位翻一倍，/25 起可用 1/2/4/8 递增', bankId: 'b_rk', tags: ['网络'], starred: false, updatedAt: '2026-11-23' },
        { id: 'n3', title: '挣值分析的记忆顺序：先 PV→EV→AC，再算 SV/CV/SPI/CPI', bankId: 'b_rk', tags: ['成本'], starred: true, updatedAt: '2026-11-22' },
        { id: 'n4', title: '范围基准是规划的输出，不是制定预算的输出', bankId: 'b_acc', tags: ['范围'], starred: false, updatedAt: '2026-11-21' },
        { id: 'n5', title: '十大管理域口诀：整合先行，范围跟进，进度管工期，成本看挣值', bankId: 'b_rk', tags: ['口诀'], starred: false, updatedAt: '2026-11-20' },
        { id: 'n6', title: '案例题答题模板：先找问题，再给措施，最后写依据', bankId: 'b_rk', tags: ['案例'], starred: false, updatedAt: '2026-11-19' }
      ],
      importJobs: [
        { id: 'j1', bankId: 'b_acc', file: '软考真题整理.csv', status: 'done', strategy: 'skip', total: 12, written: 10, skipped: 2, at: '2026-11-23 21:14' },
        { id: 'j2', bankId: 'b_rk', file: '历年真题汇总.md', status: 'done', strategy: 'merge', total: 30, written: 28, merged: 2, at: '2026-11-20 10:02' }
      ],
      drafts: [
        { id: 'd1', bankId: 'b_acc', file: '章节练习第二批.csv', step: 2, at: '2026-11-24 09:31' },
        { id: 'd2', bankId: 'b_rk', file: '案例分析整理.json', step: 1, at: '2026-11-22 16:40' }
      ],
      /* 学习会话：practice / exam / review 三态共用一份，跨页面可恢复。
         字段契约（D 域四页与 E 域入口共用，缺一不可）：
           kind / mode / bankId / origin      身份与来源
           answers / selections               已提交作答 / 已选未提交（刷新与暂存都不能丢）
           index / flags / ratings / elapsed  光标、旗标、评级、用时
           rowIds / params / blueprint       指定题目集合 / 本次参数 / 模考蓝图
           origin                            来源页 + 返回位置（返回来源用，不固定回首页） */
      sessions: [
        { id: 's1', kind: 'practice', bankId: 'b_acc', mode: '顺序练习', total: 3, done: 1,
          answers: { 0: 'A' }, selections: {}, ratings: {}, flags: {}, index: 1, elapsed: 0,
          rowIds: [], params: { count: 3, type: '不限', tag: '不限', scope: '全部题目', mode: '顺序练习' },
          blueprint: null, origin: { page: 'home', href: 'home.html', label: '今天页' },
          startedAt: '2026-11-24 22:10', updatedAt: '2026-11-24 22:12' }
      ],
      members: [
        { id: 'b_acc', list: [
          { user: 'accept_admin_1794570360969', role: 'OWNER' },
          { user: 'editor_lin', role: 'EDITOR' },
          { user: 'reviewer_02', role: 'MEMBER' }
        ] }
      ],
      /* 已交卷报告：回看入口的数据源。一份完整报告自带逐题明细（BR-109：判分版本快照
         随作答记录落库），所以归档回看与交卷当次看到的是同一份内容。 */
      reports: [
        { id: 'r1', kind: 'exam', bankId: 'b_rk', title: '模考 · 系统集成项目管理工程师', at: '2026-11-21 09:40',
          score: 9, full: 14, rate: 64, accObj: 80, answered: 5, objTotal: 6, total: 6, correct: 4, ungraded: 0,
          minutes: 96, wall: 101, via: 'manual',
          items: [
            { qid: '3F9A1C02', bankId: 'b_rk', type: '单选题', answered: true, ratio: 1, correctness: 'CORRECT',
              stem: '每周一学校开展直播课程，在直播中实时回复学生问题属于（ ）',
              mine: 'A', answer: 'A', explain: '直播中实时回复学生问题，信息按需推送、学生自行获取，属于拉式沟通。',
              rating: '良好', ratingDue: '12 月 4 日', ver: 'v1', verAt: '2026-11-10 08:30' },
            { qid: '7B21E4D9', bankId: 'b_rk', type: '单选题', answered: true, ratio: 1, correctness: 'CORRECT',
              stem: 'OSI 的（ ）不适合提供相应的安全服务。',
              mine: 'B', answer: 'B', explain: '传输层、网络层、应用层都可以提供相应安全服务，会话层不适合。',
              rating: '一般', ratingDue: '11 月 30 日', ver: 'v2', verAt: '2026-11-12 10:05' },
            { qid: 'A05C8F31', bankId: 'b_rk', type: '单选题', answered: true, ratio: 1, correctness: 'CORRECT',
              stem: '以下不属于“临时性”的是（ ）',
              mine: 'D', answer: 'D', explain: '“结束阶段”是项目阶段名称，不属于临时性这一特征。',
              rating: '良好', ratingDue: '12 月 6 日', ver: 'v1', verAt: '2026-11-10 08:30' },
            { qid: 'E4D72B60', bankId: 'b_rk', type: '单选题', answered: true, ratio: 0, correctness: 'INCORRECT',
              stem: '（ ）按照业务功能聚合性进行应用规划，建设与应用组件对应的应用系统，实现专业化发展。',
              mine: 'B', answer: 'A', explain: '按业务功能聚合性进行应用规划，体现的是功能专业化原则。',
              rating: '重来', ratingDue: '11 月 27 日', ver: 'v1', verAt: '2026-11-10 08:30' },
            { qid: 'q_rk_09', bankId: 'b_rk', type: '多选题', answered: true, ratio: 1, correctness: 'CORRECT', multi: true,
              stem: '以下属于项目临时性特征的有（ ）。',
              mine: 'A · B · D', answer: 'A · B · D',
              explain: '临时性的特征是：有明确的开始时间和结束时间、可交付成果在项目结束后依然存在、独特性；「结束阶段」是阶段名称，不属于特征。',
              rating: '一般', ratingDue: '12 月 1 日', ver: 'v2', verAt: '2026-11-15 19:02' },
            { qid: 'q_rk_10', bankId: 'b_rk', type: '多选题', answered: false, ratio: null, correctness: 'BLANK', multi: true,
              stem: '关于项目沟通管理，下列说法正确的有（ ）。',
              mine: '未作答', answer: 'A · B · D',
              explain: '沟通管理计划描述干系人的信息需求与分发方式；会议管理属于执行沟通；沟通需求分析是规划沟通的输入。C 项把交互式、推式、拉式多种沟通模型说成一种，错误。',
              rating: null, ver: 'v3', verAt: '2026-11-18 09:24' }
          ] }
      ],
      /* 复习合并队列：到期 / 错题 / 薄弱 / 斩杀恢复 合并为一行一题 */
      reviewQueue: [
        { id: 'rq1', bankId: 'b_acc', stem: 'OSI 的（ ）不适合提供相应的安全服务。', reasons: ['due', 'mistakes'], due_at: '2026-11-25 08:00', stability: 2.4, mistake_count: 2, killed_at: null },
        { id: 'rq2', bankId: 'b_rk', stem: '关于范围基准，以下说法不正确的是（）。', reasons: ['weak', 'mistakes'], due_at: '2026-11-28 08:00', stability: 1.2, mistake_count: 1, killed_at: null },
        { id: 'rq3', bankId: 'b_rk', stem: '（ ）属于融合基础设施。', reasons: ['killed'], due_at: '2026-11-27 08:00', stability: 3.1, mistake_count: 0, killed_at: '2026-11-24 21:00' },
        { id: 'rq4', bankId: 'b_rk', stem: '让（ ）干系人积极参与，确保成功。（ ）干系人知晓但抵制。', reasons: ['weak'], due_at: '2026-11-30 08:00', stability: 0.9, mistake_count: 0, killed_at: null },
        { id: 'rq5', bankId: 'b_rk', stem: '当出现异常时软件需要有持续提供服务，属于（）。', reasons: ['due'], due_at: '2026-11-25 08:00', stability: 2.0, mistake_count: 0, killed_at: null },
        { id: 'rq6', bankId: 'b_rk', stem: '沟通管理计划中应记录干系人的（）。', reasons: ['due', 'weak', 'mistakes'], due_at: '2026-11-25 20:00', stability: 1.2, mistake_count: 3, killed_at: null },
        { id: 'rq7', bankId: 'b_acc', stem: '以下属于「临时性」的是（ ）。', reasons: ['due', 'weak'], due_at: '2026-11-26 07:00', stability: 0.9, mistake_count: 0, killed_at: null },
        { id: 'rq8', bankId: 'b_en', stem: '按照业务功能聚合性进行应用规划，建设与应用组件对应的应用系统。', reasons: ['due'], due_at: '2026-11-26 09:00', stability: 2.6, mistake_count: 0, killed_at: null }
      ],
      views: {}   // 各页视图状态（见 eeStore.view）
    };
  }

  /* ---------------- 存取 ---------------- */
  var state = load();
  var listeners = [];

  function load() {
    try {
      var raw = localStorage.getItem(KEY);
      if (!raw) return seed();
      var s = JSON.parse(raw);
      if (!s || s.version !== VERSION) return seed();
      return s;
    } catch (e) { return seed(); }
  }
  function persist() {
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {}
  }
  function notify(evt) {
    persist();
    listeners.forEach(function (fn) { try { fn(state, evt || {}); } catch (e) {} });
  }
  function commit(evt) { notify(evt || {}); }

  /* ---------------- 通用 ---------------- */
  function uid(p) { return (p || 'id') + '_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }
  function findBank(id) {
    for (var i = 0; i < state.banks.length; i++) if (state.banks[i].id === id) return state.banks[i];
    return null;
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  /* ---------------- 设置 ---------------- */
  function applySettings() {
    var s = state.settings;
    var html = document.documentElement;
    var theme = s.theme === 'system'
      ? (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
      : s.theme;
    html.setAttribute('data-theme', theme);
    html.setAttribute('data-theme-palette', s.palette);
    if (s.density === 'compact') html.setAttribute('data-density', 'compact');
    else html.removeAttribute('data-density');
    html.setAttribute('lang', s.lang === 'en' ? 'en' : 'zh-CN');
  }

  /* ---------------- 复习集合判定（CR-05 · 全产品唯一） ----------------
     可执行复习集合 = 到期（FSRS 卡片 due_at 已到）∧ 未斩杀 ∧ 题库未归档 ∧ 我对该题库仍有访问权。
     它与「到期全集」「到期原因标签」都不是同一个集合：
       · 到期与否只看 due_at，不看 reasons 里有没有 'due'（答完一次评级后 due_at 会被推到未来）；
       · 斩杀同时认 killed_at 与 reasons 里的 'killed'（两条路径都写）；
       · 错题未清除 / 薄弱 / 巩固是叠加在集合之上的原因标签，一道题可同时带多个。
     侧栏角标、题库与题目页的侧栏计数、复习页待复习视图都走 executableReview。

     已知缺口（未修，P3 开工前需先裁定额，见 review/P3-HANDOFF.md §三 C-1 / C-2）：
       · 下面 bankReachable() 实际只判了「题库未归档」，访问权那一腿只有上面这句注释，
         没有判定——题库对象上有 role（OWNER / VIEWER）与 shared / readonly 但没用。
       · home.html 与 diagnosis.html 仍在本地重写到期 / 可执行口径，diagnosis 那份比这里还少一腿。 */
  function reviewDueAt(row) {
    var d = new Date(String((row && row.due_at) || '').replace(' ', 'T'));
    return isNaN(d.getTime()) ? null : d.getTime();
  }
  function reviewKilled(row) {
    return !!row && (!!row.killed_at || (row.reasons || []).indexOf('killed') > -1);
  }
  function bankReachable(bankId) {
    var b = findBank(bankId);
    return !!b && !b.archived;
  }

  /* ---------------- 领域方法 ---------------- */
  var api = {
    VERSION: VERSION,
    esc: esc,
    uid: uid,

    /* 读：返回 state 的浅副本视图（页面只读用） */
    get: function () { return state; },
    settings: function () { return state.settings; },
    role: function () { return state.role; },
    user: function () { return state.session.user; },
    isLoggedIn: function () { return !!state.session.loggedIn; },

    subscribe: function (fn) { listeners.push(fn); return function () { listeners = listeners.filter(function (x) { return x !== fn; }); }; },

    setSetting: function (k, v) {
      state.settings[k] = v;
      applySettings();
      commit({ type: 'settings', key: k });
    },
    applySettings: applySettings,
    setRole: function (r) { state.role = r; commit({ type: 'role' }); },
    /* 实例角色与题库角色互不推导（P1 §5.1）：切实例面才能验证「普通用户看不到实例管理入口」 */
    setInstanceRole: function (r) { state.instanceRole = (r === 'admin') ? 'admin' : 'user'; commit({ type: 'instanceRole' }); },
    login: function (user) { state.session.loggedIn = true; if (user) state.session.user = user; commit({ type: 'login' }); },
    logout: function () { state.session.loggedIn = false; commit({ type: 'logout' }); },
    /* 已知缺口（未修，见 review/P3-HANDOFF.md §三 C-3）：原型只有一份共享 state，login 只换
       session.user，个人学习数据（会话 / 复习队列 / 错题 / 报告）不按账户隔离——切换账户会看到
       上一个人的学习数据。隔离规则见该清单 C-3 与 §二 第 9 项。 */

    /* ---- 题库 ---- */
    banks: function (opts) {
      opts = opts || {};
      return state.banks.filter(function (b) {
        if (opts.archived === false && b.archived) return false;
        if (opts.archived === true && !b.archived) return false;
        if (opts.shared === false && b.shared) return false;
        return true;
      });
    },
    bank: findBank,
    bankName: function (id) { var b = findBank(id); return b ? b.name : '未知题库'; },
    addBank: function (data) {
      var b = {
        id: uid('b'), name: (data.name || '').trim(), category: (data.category || '默认分类').trim(),
        desc: (data.desc || '').trim(), count: 0, archived: false, shared: false,
        role: 'OWNER', updatedAt: today()
      };
      state.banks.unshift(b);
      commit({ type: 'bank:add', id: b.id });
      return b;
    },
    updateBank: function (id, patch) {
      var b = findBank(id); if (!b) return null;
      Object.keys(patch).forEach(function (k) { b[k] = patch[k]; });
      b.updatedAt = today();
      commit({ type: 'bank:update', id: id });
      return b;
    },
    archiveBank: function (id) { return api.updateBank(id, { archived: true }); },
    restoreBank: function (id) { return api.updateBank(id, { archived: false }); },
    removeBank: function (id) {
      state.banks = state.banks.filter(function (b) { return b.id !== id; });
      state.questions = state.questions.filter(function (q) { return q.bankId !== id; });
      state.notes = state.notes.filter(function (n) { return n.bankId !== id; });
      commit({ type: 'bank:remove', id: id });
    },

    /* ---- 题目 ---- */
    questions: function (bankId, opts) {
      opts = opts || {};
      return state.questions.filter(function (q) {
        if (bankId && q.bankId !== bankId) return false;
        if (opts.archived === false && q.archived) return false;
        if (opts.archived === true && !q.archived) return false;
        return true;
      });
    },
    question: function (id) {
      for (var i = 0; i < state.questions.length; i++) if (state.questions[i].id === id) return state.questions[i];
      return null;
    },
    /* 按题干找题（复习队列行 / 报告快照与题库题目之间的桥）。归一化同 normStem。 */
    questionByStem: function (stem) {
      var k = api.normStem(stem);
      for (var i = 0; i < state.questions.length; i++) {
        if (api.normStem(state.questions[i].stem) === k) return state.questions[i];
      }
      return null;
    },
    /* 题干归一化：报告与复习队列两端唯一的同一性判据。
       报告存的是交卷当时的题目快照，复习队列有自己的行 id，两套编号对不上时
       只能靠题干把两边架起来。归一化故意只做「去空白 + 忽略大小写」：
       - 去空白：同一道题在报告里可能带折行 / 全角空格，队列里是单行，逐字符比对会漏
       - 忽略大小写：英文题干大小写不影响是同一题
       - 不动标点与用词：那会让「哪项不属于」和「哪项属于」撞成同一题。
       调用方在跨页深链里带这个值（review.html?stem=<normStem>），本地比对同理。 */
    normStem: function (s) {
      return String(s == null ? '' : s).replace(/\s+/g, '').toLowerCase();
    },
    addQuestion: function (data) {
      var q = {
        id: data.id || uid('q'), bankId: data.bankId, stem: (data.stem || '').trim(),
        type: data.type || '单选题', difficulty: data.difficulty || '基础',
        chapter: data.chapter || '未分章', version: 'v1', archived: false, tags: data.tags || []
      };
      state.questions.push(q);
      var b = findBank(q.bankId); if (b) { b.count += 1; b.updatedAt = today(); }
      commit({ type: 'question:add', id: q.id });
      return q;
    },
    updateQuestion: function (id, patch) {
      var q = api.question(id); if (!q) return null;
      Object.keys(patch).forEach(function (k) { q[k] = patch[k]; });
      commit({ type: 'question:update', id: id });
      return q;
    },
    archiveQuestions: function (ids) {
      ids.forEach(function (id) { var q = api.question(id); if (q) q.archived = true; });
      commit({ type: 'question:archive', ids: ids });
    },
    restoreQuestions: function (ids) {
      ids.forEach(function (id) { var q = api.question(id); if (q) q.archived = false; });
      commit({ type: 'question:restore', ids: ids });
    },
    removeQuestions: function (ids) {
      state.questions = state.questions.filter(function (q) { return ids.indexOf(q.id) < 0; });
      commit({ type: 'question:remove', ids: ids });
    },
    bulkSetChapter: function (ids, chapter) {
      ids.forEach(function (id) { var q = api.question(id); if (q) q.chapter = chapter; });
      commit({ type: 'question:chapter', ids: ids });
    },

    /* ---- 笔记 ---- */
    notes: function (bankId) {
      return state.notes.filter(function (n) { return !bankId || n.bankId === bankId; });
    },
    note: function (id) {
      for (var i = 0; i < state.notes.length; i++) if (state.notes[i].id === id) return state.notes[i];
      return null;
    },
    addNote: function (data) {
      var n = { id: uid('n'), title: (data.title || '').trim(), bankId: data.bankId || 'b_acc', tags: data.tags || [], starred: false, updatedAt: today() };
      state.notes.unshift(n);
      commit({ type: 'note:add', id: n.id });
      return n;
    },
    updateNote: function (id, patch) {
      var n = api.note(id); if (!n) return null;
      Object.keys(patch).forEach(function (k) { n[k] = patch[k]; });
      n.updatedAt = today();
      commit({ type: 'note:update', id: id });
      return n;
    },
    removeNote: function (id) {
      state.notes = state.notes.filter(function (n) { return n.id !== id; });
      commit({ type: 'note:remove', id: id });
    },

    /* ---- 导入 ---- */
    importJobs: function (bankId) {
      return state.importJobs.filter(function (j) { return !bankId || j.bankId === bankId; });
    },
    addImportJob: function (job) {
      var j = Object.assign({ id: uid('j'), at: nowTime() }, job);
      state.importJobs.unshift(j);
      commit({ type: 'import:add', id: j.id });
      return j;
    },
    /* 导入落地：按策略真实写入题目与题库计数，并生成一条可回看的历史记录
       job = { bankId, file, strategy: 'skip'|'new'|'merge', items: [{stem,type,difficulty,chapter}] } */
    applyImport: function (job) {
      var written = 0, skipped = 0, merged = 0;
      (job.items || []).forEach(function (it) {
        var dup = state.questions.some(function (q) {
          return q.bankId === job.bankId && q.stem === it.stem;
        });
        if (dup) {
          if (job.strategy === 'skip') { skipped++; return; }
          if (job.strategy === 'merge') { merged++; return; }
        }
        api.addQuestion({
          bankId: job.bankId, stem: it.stem, type: it.type || '单选题',
          difficulty: it.difficulty || '基础', chapter: it.chapter || '未分章'
        });
        written++;
      });
      return api.addImportJob({
        bankId: job.bankId, file: job.file, status: 'done', strategy: job.strategy,
        total: (job.items || []).length, written: written, skipped: skipped, merged: merged
      });
    },
    drafts: function () { return state.drafts; },
    addDraft: function (d) {
      var draft = Object.assign({ id: uid('d'), at: nowTime() }, d);
      state.drafts.unshift(draft);
      commit({ type: 'draft:add', id: draft.id });
      return draft;
    },
    removeDraft: function (id) {
      state.drafts = state.drafts.filter(function (d) { return d.id !== id; });
      commit({ type: 'draft:remove', id: id });
    },

    /* ---- 学习会话（跨页面可恢复） ----
       冲突口径全产品唯一（CR-14）：同一 mode 同时只保留一个进行中会话；与 kind、题库无关。
       不同 mode 互不牵连——一个 PRACTICE 与一个 FSRS 可以并存，互不提示、互不代管。
       页面不再各写一份 conflictsFor，一律调 sessionConflicts(ctx)。 */
    sessions: function (kind) {
      return state.sessions.filter(function (s) { return !kind || s.kind === kind; });
    },
    activeSession: function (kind, bankId) {
      var list = state.sessions.filter(function (s) {
        return s.kind === kind && (!bankId || s.bankId === bankId);
      });
      return list.length ? list[list.length - 1] : null;
    },
    /* sessionConflicts(ctx) → 与该次开始请求同 mode 的进行中会话列表。
       ctx 可以是字段对象 { kind, mode, bankId, rowIds … }，也可以是 URLSearchParams。
       只按 mode 判定：mode 缺省视为「顺序练习」（与题库页 / 工作区入口的默认一致）。 */
    sessionConflicts: function (ctx) {
      var q = ctx || {};
      var mode = (q.mode || (q.get && q.get('mode')) || '顺序练习').trim();
      return state.sessions.filter(function (s) {
        return (s.mode || '顺序练习') === mode;
      });
    },
    /* startSession 不再静默覆盖同模式旧会话（CR-14 的「不悄悄收掉」）。
       返回形状对老调用方向后兼容：成功时返回会话对象本身（带 ok:true），
       `var s = S.startSession(...); s.id` 照旧可用；冲突时返回 {ok:false, conflicts}，
       由页面决定「继续 / 结束并新建」。页面选定后传 replace:true 重建，或先逐条
       finishSession 再调用——两条路径都不存在「页面以为结束了、store 却留着」的错位。 */
    startSession: function (data) {
      var payload = Object.assign({}, data || {});
      var conflicts = api.sessionConflicts(payload);
      if (conflicts.length && !payload.replace) {
        return { ok: false, conflicts: conflicts, reason: 'conflict' };
      }
      if (payload.replace) {
        conflicts.forEach(function (s) { api.finishSession(s.id); });
        delete payload.replace;
      }
      var s = Object.assign({
        id: uid('s'), kind: 'practice', done: 0,
        answers: {}, selections: {}, ratings: {}, flags: {}, index: 0, elapsed: 0,
        rowIds: [], total: 0, params: {}, blueprint: null,
        origin: { page: '', href: '', label: '' },
        startedAt: nowTime(), updatedAt: nowTime()
      }, payload);
      s.ok = true;
      state.sessions.push(s);
      commit({ type: 'session:start', id: s.id });
      return s;
    },
    updateSession: function (id, patch) {
      var s = null;
      for (var i = 0; i < state.sessions.length; i++) if (state.sessions[i].id === id) s = state.sessions[i];
      if (!s) return null;
      Object.keys(patch).forEach(function (k) { s[k] = patch[k]; });
      s.updatedAt = nowTime();
      commit({ type: 'session:update', id: id });
      return s;
    },
    finishSession: function (id, report) {
      var s = null;
      for (var i = 0; i < state.sessions.length; i++) if (state.sessions[i].id === id) s = state.sessions[i];
      if (!s) return null;
      state.sessions = state.sessions.filter(function (x) { return x.id !== id; });
      if (report) {
        state.reports.unshift(Object.assign({ id: uid('r'), at: nowStamp(), kind: s.kind, bankId: s.bankId }, report));
      }
      commit({ type: 'session:finish', id: id });
      return s;
    },
    reports: function (kind) {
      return state.reports.filter(function (r) { return !kind || r.kind === kind; });
    },

    /* ---- 复习合并队列 ---- */
    reviewQueue: function (bankId, reason) {
      return state.reviewQueue.filter(function (r) {
        if (bankId && r.bankId !== bankId) return false;
        if (reason && reason !== 'all' && r.reasons.indexOf(reason) < 0) return false;
        return true;
      });
    },
    /* ---- 复习集合：CR-05 唯一判定（页面不再自己写一遍到期/斩杀/归档/访问权） ---- */
    reviewDueAt: reviewDueAt,
    reviewDue: function (row) { return reviewDueAt(row) != null && reviewDueAt(row) <= Date.now(); },
    reviewKilled: reviewKilled,
    reviewReachable: bankReachable,
    /* 当前可执行复习集合。bankId 可选（不给就是全部题库）。
       侧栏角标（nav.js）、题库与题目页侧栏计数、复习页待复习视图都用它。 */
    executableReview: function (bankId) {
      return state.reviewQueue.filter(function (r) {
        if (reviewKilled(r)) return false;
        if (bankId && r.bankId !== bankId) return false;
        if (reviewDueAt(r) == null || reviewDueAt(r) > Date.now()) return false;
        return bankReachable(r.bankId);
      });
    },
    /* 已排期但还没到期（同口径反向，用来说清「为什么现在是空的」） */
    scheduledReview: function (bankId) {
      return state.reviewQueue.filter(function (r) {
        if (reviewKilled(r)) return false;
        if (bankId && r.bankId !== bankId) return false;
        if (reviewDueAt(r) == null) return false;
        return reviewDueAt(r) > Date.now() && bankReachable(r.bankId);
      });
    },
    /* 到期但被归档或失去访问权挡在外面（同口径反向） */
    blockedReview: function (bankId) {
      return state.reviewQueue.filter(function (r) {
        if (reviewKilled(r)) return false;
        if (bankId && r.bankId !== bankId) return false;
        return !bankReachable(r.bankId);
      });
    },
    reviewRow: function (id) {
      for (var i = 0; i < state.reviewQueue.length; i++) if (state.reviewQueue[i].id === id) return state.reviewQueue[i];
      return null;
    },
    /* 答错回流：加「错题」原因、错题次数 +1、按评级重排到期时间与稳定度 */
    reflowRow: function (id, rating) {
      var r = api.reviewRow(id); if (!r) return null;
      if (r.reasons.indexOf('mistakes') < 0) r.reasons.push('mistakes');
      r.mistake_count += 1;
      // 稳定度与到期间隔与界面实时推算同一套模型：stability 表 + base x stability
      r.stability = { 1: 1.2, 2: 1.8, 3: 2.4, 4: 3.1 }[rating] || 1.2;
      var base = { 1: 0.5, 2: 1.2, 3: 2.6, 4: 5.0 }[rating];
      var days = Math.max(0.5, (base == null ? 1 : base) * r.stability);
      r.due_at = datePlusDays(Math.round(days)) + ' 08:00';
      commit({ type: 'review:reflow', id: id });
      return r;
    },
    updateReviewRow: function (id, patch) {
      var r = api.reviewRow(id); if (!r) return null;
      Object.keys(patch).forEach(function (k) { r[k] = patch[k]; });
      commit({ type: 'review:update', id: id });
      return r;
    },
    /* 题干 → 复习行。练习 / 模考没有 rowId，回流错题与薄弱时按题干找到同一行。 */
    rowForStem: function (bankId, stem) {
      var k = api.normStem(stem);
      for (var i = 0; i < state.reviewQueue.length; i++) {
        var r = state.reviewQueue[i];
        if (bankId && r.bankId !== bankId) continue;
        if (api.normStem(r.stem) === k) return r;
      }
      return null;
    },
    /* 普通练习 / 模考的回流入口：答错 → 错题，标记薄弱 → 薄弱。
       同一道题复用它已有的复习行，不重复建卡；到期时间排到明天，
       不把刚答错的题立刻塞进「今天待复习」把计数抬上去。 */
    recordOutcome: function (bankId, stem, kind, questionId) {
      if (!stem) return null;
      var r = api.rowForStem(bankId, stem);
      var created = false;
      if (!r) {
        r = {
          id: uid('rq'), bankId: bankId, stem: stem, reasons: [],
          due_at: datePlusDays(1) + ' 08:00',
          stability: kind === 'mistake' ? 1.2 : 0.9,
          mistake_count: 0, killed_at: null, questionId: questionId || null
        };
        state.reviewQueue.push(r);
        created = true;
      }
      var reason = kind === 'mistake' ? 'mistakes' : 'weak';
      if (!Array.isArray(r.reasons)) r.reasons = [];
      if (r.reasons.indexOf(reason) < 0) r.reasons.push(reason);
      if (kind === 'mistake') {
        r.mistake_count = (r.mistake_count || 0) + 1;
        r.stability = 1.2;
      }
      if (!r.due_at || api.reviewDue(r)) r.due_at = datePlusDays(1) + ' 08:00';
      commit({ type: created ? 'review:create' : 'review:' + kind, id: r.id });
      return r;
    },

    /* ---- 成员 ---- */
    members: function (bankId) {
      for (var i = 0; i < state.members.length; i++) if (state.members[i].id === bankId) return state.members[i].list;
      return [];
    },
    addMember: function (bankId, user, role) {
      var entry = null;
      for (var i = 0; i < state.members.length; i++) if (state.members[i].id === bankId) entry = state.members[i];
      if (!entry) { entry = { id: bankId, list: [] }; state.members.push(entry); }
      if (entry.list.some(function (m) { return m.user === user; })) return { ok: false, reason: 'exists' };
      entry.list.push({ user: user, role: role || 'MEMBER' });
      commit({ type: 'member:add', bankId: bankId });
      return { ok: true };
    },
    removeMember: function (bankId, user) {
      for (var i = 0; i < state.members.length; i++) {
        if (state.members[i].id === bankId) {
          state.members[i].list = state.members[i].list.filter(function (m) { return m.user !== user; });
        }
      }
      commit({ type: 'member:remove', bankId: bankId });
    },

    /* ---- 权限（全产品同一套语义） ---- */
    can: function (action) {
      // 实例级能力：只按实例角色判定，与题库角色无关
      if (action === 'instance.manage') return state.instanceRole === 'admin';
      var r = state.role;
      var table = {
        'bank.create': ['OWNER', 'EDITOR', 'MEMBER'],
        'bank.edit': ['OWNER', 'EDITOR'],
        'bank.archive': ['OWNER', 'EDITOR'],
        'bank.import': ['OWNER', 'EDITOR'],
        'question.create': ['OWNER', 'EDITOR'],
        'question.edit': ['OWNER', 'EDITOR'],
        'question.archive': ['OWNER', 'EDITOR'],
        'member.manage': ['OWNER'],
        'note.create': ['OWNER', 'EDITOR', 'MEMBER', 'VIEWER'],
        'note.edit': ['OWNER', 'EDITOR', 'MEMBER', 'VIEWER']
      };
      var allow = table[action];
      return !allow || allow.indexOf(r) >= 0;
    },

    /* ---- CR-12：权限改变能力，不改变结构；表达方式按「相关性」分流 ----
       与当前用户相关、但此刻不可用的控件 → 禁用并解释（置灰 + 可读原因）。
       与当前用户完全无关的管理入口 → 不渲染。
       判据：这个入口说的事，对这个用户有意义吗。有意义但不能做 → 禁用；
       没意义 → 不出现。不得用英文 banner 或错误码当唯一反馈。

       只对「库与实例的管理权」判定相关性：普通成员没有归档/删除一个自己只读的库
       的理由，普通用户也没有进入实例管理的理由。内容操作（编辑题目、批量维护、
       导入）与成员名单对所有成员都有意义，一律禁用并解释而不是隐藏。 */
    relevant: function (action) {
      if (action === 'instance.manage') return state.instanceRole === 'admin';
      if (action === 'bank.archive' || action === 'bank.delete' || action === 'bank.settings') {
        return state.role === 'OWNER' || state.role === 'EDITOR';
      }
      return true;
    },
    isInstanceAdmin: function () { return state.instanceRole === 'admin'; },
    instanceRole: function () { return state.instanceRole; },
    denyReason: function (action) {
      if (api.can(action)) return '';
      var ro = state.role === 'VIEWER';
      if (action === 'instance.manage') return '只有实例管理员可以管理实例；实例管理员身份不会自动给你任何题库的访问权';
      if (action === 'member.manage') return '只有所有者可以管理成员';
      if (action === 'bank.create') return ro
        ? '你是只读成员，不能新建题库；可以在别人共享给你的题库里练习，或让所有者给你编辑权限'
        : '当前角色不能新建题库';
      if (action === 'bank.edit') return ro
        ? '你是只读成员，不能修改题库资料'
        : '你是成员，只能查看，不能修改';
      if (action === 'question.edit') return ro
        ? '你是只读成员，不能编辑题目'
        : '你是成员，只能查看，不能修改';
      if (action === 'question.create' || action === 'question.archive') return ro
        ? '你是只读成员，不能新增或归档题目'
        : '你是成员，只能查看，不能新增或归档题目';
      if (action === 'bank.archive') return '只有所有者可以归档或删除题库；编辑者与成员不能改动题库本身';
      if (action === 'bank.settings') return '只有所有者可以改题库设置；编辑者与成员不能改动题库本身';
      if (action === 'bank.import') return ro
        ? '你是只读成员，无法导入题目'
        : '你不是管理员或编辑者，无法导入题目';
      return '当前角色没有该操作权限';
    },

    /* ---- 视图状态：跨页面返回时恢复筛选/页签/滚动/选择 ----
     key 一律带作用域（规则 §4）：`页面:作用域[:<userId>]`。
       题库工作区 workspace:<bankId> / 题库列表 banks:<scope> / 资料 notes:<noteId 或 list>
       复习 review:<tab>:<bankId> / 答题器 runner:<sid>。
       userId 位现在就留在键里（`view.key('review', tab, bankId)` 第三段默认取当前用户），
       P3 接账户隔离时不用再改页面。不同题库、题目、账户的视图状态不得互相污染。 */
    view: {
      /* key(page, scope?, userId?)：scope 可以是字符串，也可以是数组（多段作用域，
         例如复习页 view.key('review', ['mistakes', 'b_acc']) → review:mistakes:b_acc:<userId>）。
         数组里的空段跳过（题库范围未选时 bankId 为空，键退成 review:<tab>:<userId>）。 */
      key: function (page, scope, userId) {
        var parts = [page || 'page'];
        var segs = Array.isArray(scope) ? scope : [scope];
        for (var i = 0; i < segs.length; i++) {
          if (segs[i] != null && segs[i] !== '') parts.push(String(segs[i]));
        }
        parts.push(userId || state.session.user || 'anon');
        return parts.join(':');
      },
      save: function (page, patch) {
        state.views[page] = Object.assign({}, state.views[page], patch);
        persist();
      },
      load: function (page) { return state.views[page] || {}; },
      clear: function (page) { delete state.views[page]; persist(); }
    },

    /* ---- 演示数据 ---- */
    reset: function () {
      state = seed();
      /* 同时清掉页面级的会话内草稿（导入向导等）：否则复位后
         其他页还挂着指向已删除数据的「继续上次导入」 */
      try {
        sessionStorage.removeItem('ee-import-wizard-v1');
      } catch (e) {}
      applySettings();
      commit({ type: 'reset' });
    }
  };

  function datePlusDays(n) {
    var d = new Date();
    d.setDate(d.getDate() + n);
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }
  function today() {
    var d = new Date();
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }
  function nowTime() {
    var d = new Date();
    return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
  }
  /* 报告是永久记录，可能要隔很多天再回看，`at` 用完整日期时间
     （与种子报告 r1 的 '2026-11-21 09:40' 同格式，避免归档报告顶栏只有时分） */
  function nowStamp() {
    return today() + ' ' + nowTime();
  }

  /* 另一页改了数据 → 本页跟上（file:// 下同源 storage 事件可用） */
  window.addEventListener('storage', function (e) {
    if (e.key !== KEY || !e.newValue) return;
    try {
      state = JSON.parse(e.newValue);
      applySettings();
      listeners.forEach(function (fn) { try { fn(state, { type: 'external' }); } catch (err) {} });
    } catch (err) {}
  });

  /* 主题跟随系统时，系统切换要即时生效 */
  if (window.matchMedia) {
    var mq = window.matchMedia('(prefers-color-scheme: dark)');
    /* 系统明暗变化：既要换配色，也要通知订阅者——顶栏的太阳/月亮图标与
       aria-label 由 spec-boot 的 syncThemeButtons 负责，不 notify 就会「配色变了、图标没变」。 */
    var onSys = function () {
      if (state.settings.theme !== 'system') return;
      applySettings();
      listeners.forEach(function (fn) { try { fn(state, { type: 'theme' }); } catch (err) {} });
    };
    if (mq.addEventListener) mq.addEventListener('change', onSys);
    else if (mq.addListener) mq.addListener(onSys);
  }

  window.eeStore = api;
  applySettings();
})();
