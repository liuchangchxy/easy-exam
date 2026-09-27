# 视觉冒烟（EasyExam 版）

移植自 vibe-coding-starter 的 `tests/visual_smoke/`，判据层完整保留，导航层按本项目实际结构改写。

## 为什么要正身信号

只判"不白"会**放过"有内容的非 App 页"**。starter 记录过一次真实翻车：错误占位页有内容、不是纯白，纯颜色判据直接放行。本项目同样适用——网关占位页、反代错误页、旧版残留 `dist/` 都不是纯白。

所以颜色判据之前必须先过四道正身信号，缺一即红：

1. **产物自检**：入口 HTML 有 `#app` 挂载点，且引用了主脚本；主脚本 HTTP 可取（200-3xx）。防止"服务起了但发的是空的/过期的 dist"。
2. **主文档状态**：主框架（过滤 iframe 子文档）响应状态为 2xx/3xx。
3. **主脚本加载成功**：主脚本确实向 `#app` 挂载了内容。
4. **宿主元素存在**：`#app` 存在。

逃生门用 `--allow-missing-host` **flag**，而不是拆闸门：挂载点改名时放行，判据本身不降级。

## 用法

本项目 SPA **没有 URL 路由**（`App.vue` 用响应式 state 切视图，无 vue-router），所以 starter 原版的 `#/route` 遍历方式在此无效。当前只采集登录后的首页；要覆盖更多视图，需由真实 UI 交互驱动（参考 `frontend/tests/capture_ui_screenshots.mjs` 的做法）。

```bash
# 1. 构建产物
npm --prefix frontend run build

# 2. 一条命令跑完（自动起静态服务 + 无头 Chrome，动态空闲端口）
node tests/visual_smoke/run.mjs --settle 1800
```

`run.mjs` 负责起服务、找空闲端口、拉起 Chrome，并在结束时清理（Chrome profile 建在系统临时目录，不落进仓库）。退出码 0 = 全部页面通过；1 = 至少一页信号失败；2 = 没找到构建产物。

Chrome 路径优先读 `CHROME_PATH` 环境变量，默认 `C:/Program Files/Google/Chrome/Application/chrome.exe`。

如需自己控制服务与浏览器，可直接调用 `shot.mjs`：

```bash
CDP_URL=http://localhost:<cdp_port> node tests/visual_smoke/shot.mjs   http://127.0.0.1:<app_port> ./screenshots/visual_smoke --settle 1800
```

## 约定

- 截图产物只做评审归档，不入库（`.gitignore` 已含 `screenshots/`）。
- `document.readyState` 只是"载入完"，首帧稳定靠 `--settle`（默认 2500ms）。
- 这层是**机器判白屏**。**"好不好看"机器测不了**，需要人眼或 AI 并排评审（参考实现 / 竞品 / 上一版），见 `TESTING.md` 测试层级第 6 条。
- 本工具是**否定判据**（不出错就算过），不能替代 `browser_e2e.test.js` 的肯定判据（真实链路必须跑通）。
