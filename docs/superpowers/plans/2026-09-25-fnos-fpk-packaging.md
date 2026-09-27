# fnOS 本地手动安装 FPK 应用包 Implementation Plan

> **For agentic workers:** 本计划由主 Agent 执行，严格遵守 `AGENTS.md` 工程底线，包含本地可执行构建与物理 fnOS 设备端到端验证。

**Goal:** 在当前 EasyExam 仓库中实现可在飞牛 NAS (fnOS) 应用中心手动安装的 `.fpk` 应用包，支持自包含 Docker 镜像离线安装，保持端口 3000、数据持久化 `/app/data`、健康检查 `/api/v1/health`，并在真实 fnOS NAS 设备上完成安装、运行、升级与数据保留全生命周期验证。

**Architecture:**
1. 保留根目录现有 `Dockerfile` 和 `docker-compose.yml`，不修改业务代码和产品规范。
2. 在 `fpk/easy-exam/` 建立标准 fnOS FPK 源码层：
   - `manifest`: 元数据（固定 appname `easy-exam`, version `1.0.0`, port `3000`, 描述, 作者）
   - `config/resource`: 声明 `docker-project` (`easy-exam`)
   - `config/privilege`: 声明专用包用户 `easy_exam`
   - `app/docker/docker-compose.yaml`: 生产编排，挂载 `${TRIM_PKGVAR}:/app/data`，映射 `${service_port:-${TRIM_SERVICE_PORT:-3000}}:3000`，固定镜像 `ailm32442/easy-exam:1.0.0`
   - `app/ui/config`: 桌面 WebUI 入口及图标映射
   - `cmd/main`: 容器运行状态检查 (`docker inspect`)
   - `cmd/install_callback` & `cmd/upgrade_callback`: 若随包携带离线镜像则自动 `docker load`
   - `ICON.PNG`, `ICON_256.PNG`, `app/ui/images/icon_64.png`, `app/ui/images/icon_256.png`: 高清应用图标
3. `scripts/build_fpk.py`: 自动化打包工具，支持自动检测官方 `fnpack` CLI 或内置纯 Python 打包引擎，支持 `--bundle-image` 离线自包含打包与 `--thin` 轻量打包。
4. 修正现有部署脚本 `deploy_fnos.sh` 和 `deploy_fnos.ps1` 中的健康检查路径为 `/api/v1/health`。

---

### Task 1: 修正部署脚本健康检查路径不一致
**Files:**
- Modify: `scripts/deploy_fnos.sh`
- Modify: `scripts/deploy_fnos.ps1`
- Modify: `tests/test_deployment_config.py`

- [x] 将 `scripts/deploy_fnos.sh` 中 `/api/health` 调整为 `/api/v1/health`。
- [x] 将 `scripts/deploy_fnos.ps1` 中 `/api/health` 调整为 `/api/v1/health`。
- [x] 更新 `tests/test_deployment_config.py` 断言，并运行回归测试确保通过。

### Task 2: 创建 FPK 标准规范源文件目录与图标
**Files:**
- Create: `fpk/easy-exam/manifest`
- Create: `fpk/easy-exam/config/privilege`
- Create: `fpk/easy-exam/config/resource`
- Create: `fpk/easy-exam/app/docker/docker-compose.yaml`
- Create: `fpk/easy-exam/app/ui/config`
- Create: `fpk/easy-exam/cmd/main`
- Create: `fpk/easy-exam/cmd/install_init`
- Create: `fpk/easy-exam/cmd/install_callback`
- Create: `fpk/easy-exam/cmd/upgrade_init`
- Create: `fpk/easy-exam/cmd/upgrade_callback`
- Create: `fpk/easy-exam/cmd/uninstall_init`
- Create: `fpk/easy-exam/cmd/uninstall_callback`
- Create: `fpk/easy-exam/wizard/`
- Create: `fpk/easy-exam/ICON.PNG` & `ICON_256.PNG`
- Create: `fpk/easy-exam/app/ui/images/icon_64.png` & `icon_256.png`

- [x] 生成 EasyExam 专用 256x256 和 64x64 图标。
- [x] 编写符合 fnOS 官方规范的各项配置文件，固定版本号 `1.0.0` 和镜像 `ailm32442/easy-exam:1.0.0`。
- [x] 设置 `cmd/` 脚本具备标准权限与错误处理，并在 `install_callback` 中添加镜像自动加载逻辑。

### Task 3: 自动化 FPK 构建脚本与打包单元测试
**Files:**
- Create: `scripts/build_fpk.py`
- Create: `tests/test_fpk_packaging.py`

- [x] 编写 `scripts/build_fpk.py`，支持调用官方 `fnpack` 或纯 Python 引擎（自动生成 `app.tgz`、计算 MD5 校验和、打包 `.fpk`）。
- [x] 编写自动化测试 `tests/test_fpk_packaging.py`，验证 FPK 归档结构、文件权限、manifest 校验和一致性与 Compose 配置规范。
- [x] 运行测试确认 GREEN。

### Task 4: 生成自包含 `.fpk` 应用包
**Files:**
- Output: `dist/easy-exam-1.0.0.fpk`

- [x] 构建并导出 `ailm32442/easy-exam:1.0.0` 镜像。
- [x] 执行打包生成自包含离线安装包。
- [x] 验证安装包内部结构与镜像完整性。

### Task 5: 真实 fnOS NAS 物理端到端全生命周期验证
**Files:**
- Remote: `192.168.x.x` (fnOS 6.18)

- [x] 在 fnOS 上通过 `appcenter-cli install-fpk` 物理安装 `easy-exam-1.0.0.fpk`。
- [x] 验证应用启动、进程状态、端口 3000 监听。
- [x] 验证浏览器访问首页返回 200，PWA 标题正确。
- [x] 验证 `/api/v1/health` 返回 `{"status":"ok","app":"easy-exam","version":"v1"}`。
- [x] 写入测试数据（创建题库、导入题目），执行应用重启 (`stop` + `start`)，验证数据完全持久化保留。
- [x] 执行升级测试，验证应用升级后数据库不丢失。
- [x] 验证应用卸载后数据目录保留状态。

### Task 6: 交付文档与总结报告
**Files:**
- Modify: `docs/REQUIREMENTS_TRACEABILITY.md` (如有必要)
- Create: `docs/FNOS_FPK_GUIDE.md` (操作与安装手册)

- [x] 记录构建命令、安装步骤、测试结果（明确区分 pass/fail/skipped）。
- [x] 给出对原 Docker 部署方式的兼容性说明。

---

## 完成状态（2026-09-27 复核）

六个任务全部交付。计划文本中"固定版本号 `1.0.0`"是当时的取值，实际版本已推进至 `1.0.2`；版本号唯一来源为 `fpk/easy-exam/manifest`，由 `tests/test_fpk_packaging.py` 校验其与 compose 镜像 tag 一致。

交付证据：

- FPK 源码层、图标、`scripts/build_fpk.py`（fnpack CLI + 纯 Python 双后端）与 `tests/test_fpk_packaging.py` 均已落地。
- `dist/` 产出 `easy-exam-1.0.0.fpk` / `1.0.1.fpk` / `1.0.2.fpk`。
- 实机生命周期验证在 fnOS 6.18（`192.168.x.x`）完成：安装、启动、端口 3000、`/api/v1/health` 200、重启后数据与主密钥保留。
- 后续发现在安装流程中暴露的**离线镜像加载时序缺陷**（应用中心早于 callback 拉起 compose，导致回退拉取不存在的 Docker Hub tag 并整体回滚），已在 commit `48bfa85` 修复并由 `1.0.2` 实机安装确认。完整根因与维护约束见 [FNOS_FPK_GUIDE.md 第 3.3 节](../../FNOS_FPK_GUIDE.md)。
- `docs/FNOS_FPK_GUIDE.md` 已建立并在本轮更新至 `1.0.2` 基线。

**偏差说明**：Task 5 的"验证应用卸载后数据目录保留状态"未单独形成可复查的本轮证据；卸载保留策略在 `cmd/uninstall_callback` 中实现为显式保留 `TRIM_PKGVAR`，但未在实机上重跑卸载流程。作为未核验项保留，不记为已通过。
