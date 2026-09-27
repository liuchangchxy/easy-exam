# fnOS FPK 安装包构建与部署指南

本文档记录 EasyExam 在飞牛私有云（fnOS）平台上的 `.fpk` 原生手动安装包设计、构建与实机部署规范。

> **当前版本基线**：`manifest` 版本 `1.0.2`（2026-09-27）。版本号只有一个来源——`fpk/easy-exam/manifest` 的 `version` 字段；`app/docker/docker-compose.yaml` 的镜像 tag 必须与之逐字一致，由 `tests/test_fpk_packaging.py` 强制校验。打包产物文件名同样由该字段派生。

---

## 1. 应用规范与元数据

| 项目 | 参数 / 设定 | 说明 |
| :--- | :--- | :--- |
| **应用标识 (appname)** | `easy-exam` | fnOS 内部唯一标识 |
| **版本号 (version)** | `1.0.2` | 以 `fpk/easy-exam/manifest` 为唯一来源；严禁使用 `latest`。Any 升级时必须同时推进 manifest、compose 镜像 tag 与随包镜像 tag |
| **服务端口 (port)** | `3000` | 容器映射 `3000:3000` |
| **数据持久化 (volume)** | `${TRIM_PKGVAR:-/var/apps/easy-exam/var}:/app/data` | 自动映射到 fnOS 存储卷（如 `/vol4/@appdata/easy-exam`） |
| **健康检查 (healthcheck)** | `http://127.0.0.1:3000/api/v1/health` | HTTP 200 返回 `{"status":"ok","app":"easy-exam","version":"v1"}` |
| **运行架构** | `x86_64` (AMD64) | 支持主流 x86 NAS 硬件 |
| **底层运行体** | Docker Compose (`docker-project`) | 由 fnOS App Center 统一管理容器生命周期 |

---

## 2. 目录结构与打包规范

仓库中 FPK 目录位于 `fpk/easy-exam/`：

```text
fpk/easy-exam/
├── manifest                      # fnOS 清单文件 (appname, version, ports, checksum)
├── ICON.PNG                      # 64x64 应用图标
├── ICON_256.PNG                  # 256x256 高清应用图标
├── config/
│   ├── privilege                 # 运行权限（root 权限与 docker 组，确保执行 docker load）
│   └── resource                  # 声明 docker-project 项目路径
├── app/
│   ├── docker/
│   │   └── docker-compose.yaml   # 容器部署配置
│   ├── images/                   # 打包时放置离线镜像 (easy-exam-1.0.0.tar.gz)
│   └── ui/
│       ├── config                # fnOS 桌面应用启动与 iframe 配置
│       └── images/               # 桌面快捷方式图标 (icon_64.png, icon_256.png)
└── cmd/
    ├── install_init              # 安装前：最早钩子，从暂存目录 docker load 随包镜像
    ├── install_callback          # 安装后：初始化持久化 .env 主密钥 + 兜底加载镜像
    ├── upgrade_init              # 升级前：与 install_init 同源加载新版本镜像
    ├── upgrade_callback          # 升级后：重新加载镜像
    ├── uninstall_init            # 卸载前停止并清理容器（保留数据卷）
    ├── uninstall_callback        # 卸载后资源清理（数据默认保留）
    └── main                      # 应用状态检查与启动引导脚本（start 时先加载镜像再 compose up）
```

> `cmd/install_init` 与 `cmd/upgrade_init` 的镜像加载不是冗余保险，而是**唯一能满足平台启停时序的位置**，原因见第 3 节。

---

## 3. 构建 FPK 安装包

打包脚本位于 `scripts/build_fpk.py`，支持两种打包后端：
1. **官方 fnpack CLI**：自动检测 `.tools/fnpack.exe` 或系统 `PATH` 中的 `fnpack`。
2. **纯 Python 打包引擎**：若无 `fnpack` 工具，全平台内置标准 Python 打包引擎，零外部依赖输出标准 `.fpk` 归档。

### 3.1 构建全离线安装包（推荐）
包含自包含离线 Docker 镜像，可在无公网或私有镜像仓库拉取权限受限的 NAS 上直接完成安装：

```bash
python scripts/build_fpk.py --bundle-image
```
- 输出文件：`dist/easy-exam-<manifest 版本>.fpk`（当前为 `dist/easy-exam-1.0.2.fpk`，约 30MB）
- 内置镜像：`ailm32442/easy-exam:<manifest 版本>`（当前 `ailm32442/easy-exam:1.0.2`）

### 3.2 构建轻量在线包
仅打包配置和编排描述文件，NAS 在安装时从镜像源拉取：

```bash
python scripts/build_fpk.py --thin
```
- 输出文件：`dist/easy-exam-<manifest 版本>.fpk`（当前为 `dist/easy-exam-1.0.2.fpk`，约 8KB）

### 3.3 离线镜像加载时序约束（安装/升级必读）

这一节记录 2026-09-27 定位并修复的实机故障（commit `48bfa85`）。它不是可选的优化，而是决定 `.fpk` 能否安装成功的硬约束。

#### 故障现象

在 fnOS 应用中心手动安装 `easy-exam-1.0.1` / `1.0.2` 时，每次安装都在最后一步**回滚**，报错：

```text
easy-exam Error pull access denied for ailm32442/easy-exam
```

#### 根因

fnOS 应用中心在 `install_init` / `install_callback` 之前，就已经用包内的 `target/` 把 docker project 拉起来了。此时如果本地 Docker daemon 里还没有随包镜像，`docker compose up` 就会按 `pull_policy: if_not_present` 回退去 Docker Hub 拉取 `ailm32442/easy-exam:<version>`——而该 tag 从未发布到 Docker Hub，拉取被拒后整个安装流程回滚。

这解释了此前的诡异现象：`1.0.1` 曾成功装过一次（因为 `1.0.0` 时期 `docker load` 过的同名镜像还残留在本地），此后再装必失败。

#### 修复

把镜像加载挪到**能抢在 compose 之前的最早钩子**，并覆盖包在安装过程中可能出现过的所有暂存位置：

| 钩子 | 作用 |
| :--- | :--- |
| `cmd/install_init` | 从 `TRIM_APPDEST/images`、`TRIM_PKGINST_TEMP_DIR[/app]/images`、`TRIM_TEMP_TPKFILE[/app]/images` 逐个 `docker load`；失败只告警不退出，避免 setup 环境缺 docker 时阻断安装 |
| `cmd/upgrade_init` | 与 `install_init` 同源处理，保证升级时新版本镜像先就位 |
| `cmd/main start` | `docker compose up` 之前再加载一次 `target/images`，兜住手工 `start` 的场景 |
| `cmd/install_callback` / `cmd/upgrade_callback` | 保留加载逻辑作为兜底 |

#### 验证结论（实机）

- 设备：fnOS 6.18，`192.168.x.x`
- `appcenter-cli install-fpk` 安装成功，不再回滚
- 容器 `easy-exam-fpk` 正常起在 3000 端口，`/api/v1/health` 返回 200
- `stop` + `start` 重启后，已注册账号仍可登录，`var/.env` 主密钥 md5 不变

#### 维护约束

- 升级版本时，**随包镜像 tag、`app/docker/docker-compose.yaml` 的 `image`、`manifest` 的 `version` 三者必须同时推进**，否则本地镜像与 compose 期望的 tag 对不上，会重新触发上面的拉取回滚。
- 不要把镜像加载逻辑从 `install_init` / `upgrade_init` 中移除或"优化"为只在 callback 中执行。

---

## 4. 安装与验证

### 4.1 方法一：fnOS 桌面手动安装（用户常用）
1. 登录 fnOS 桌面，打开 **应用中心 (App Center)**。
2. 点击右上角设置菜单中的 **手动安装**。
3. 选择构建生成的 `dist/easy-exam-1.0.2.fpk` 文件并点击下一步。
4. 安装完成后，桌面上将出现 **EasyExam 易考宝** 应用图标。
5. 点击图标即可通过内置窗口或新标签页访问 `http://<NAS_IP>:3000`。

### 4.2 方法二：终端命令行安装（运维与调试）
通过 SSH 登录 NAS 执行：

```bash
# 复制安装包到 NAS
scp dist/easy-exam-1.0.2.fpk <user>@<nas_ip>:/tmp/easy-exam-1.0.2.fpk

# 执行安装
sudo appcenter-cli install-fpk /tmp/easy-exam-1.0.2.fpk

# 启动应用
sudo appcenter-cli start easy-exam

# 检查应用状态
sudo appcenter-cli status easy-exam
# 输出: running
```

---

## 5. 运维与生命周期命令

| 操作 | 命令 | 说明 |
| :--- | :--- | :--- |
| **查询状态** | `sudo appcenter-cli status easy-exam` | 返回 `running` 或 `stopped` |
| **启动服务** | `sudo appcenter-cli start easy-exam` | 启动容器并打开健康检查 |
| **停止服务** | `sudo appcenter-cli stop easy-exam` | 优雅停止容器并释放端口 |
| **重启服务** | `sudo appcenter-cli restart easy-exam` | 重启容器服务 |
| **卸载应用** | `sudo appcenter-cli uninstall easy-exam` | 移除应用，数据保留在 `@appdata/easy-exam` |
| **查看日志** | `sudo docker logs -f easy-exam-fpk` | 查看容器后台运行与访问日志 |
| **健康探针** | `curl -i http://127.0.0.1:3000/api/v1/health` | 检查核心接口存活状态 |

---

## 6. 数据安全与持久化机制

1. **持久化目录**：
   - 物理路径：`/vol*/@appdata/easy-exam`（Btrfs 子卷）
   - 容器挂载：`/app/data`
   - 数据库文件：`/app/data/easyexam-v1.db`
2. **防丢失保证**：
   - 容器启停、系统重启：数据文件保持原样，服务无缝恢复。
   - 卸载重装：fnOS App Center 保留 `@appdata/` 目录，重新安装后数据完整继承。
   - 与原 Docker 部署隔离：独立容器名 `easy-exam-fpk`，不污染宿主机原有的 `/home/.../projects/fn-exam` 目录。

---

## 7. 凭证加密主密钥配置规范 (EASYEXAM_SECRET_KEY)

### 7.1 重要安全前提与一致性约束
- 系统在 `user_ai_configs` 表中对所有用户配置的 AI API Key 及联网搜索 Key 执行 **Fernet 对称加密落库**（物理列仅存储 `enc:...` 密文，不落明文）。
- **主密钥一致性约束**：`EASYEXAM_SECRET_KEY` 用于生成加解密派生密钥。**容器升级、重启或重建后，必须继续使用完全相同的主密钥！** 若误改或更换密钥，数据库中已保存的历史敏感凭据将无法解密（解密时将抛出明确的诊断异常 `ValueError: key mismatch or corrupted ciphertext`）。

### 7.2 如何生成高强度主密钥
请勿使用弱密码或固定字符串。建议生成 32 字节（256 位）十六进制随机串：
- **Linux / macOS / fnOS 终端 (OpenSSL)**：
  ```bash
  openssl rand -hex 32
  ```
- **Python (跨平台推荐)**：
  ```bash
  python3 -c "import secrets; print(secrets.token_hex(32))"
  ```
- **PowerShell (Windows)**：
  ```powershell
  python -c "import secrets; print(secrets.token_hex(32))"
  ```

### 7.3 飞牛 NAS (fnOS) 部署环境注入途径核查与操作步骤
> **核查结论**：fnOS 应用中心（App Center）图形化安装界面目前**未提供自定义环境变量输入框**，且由系统管理拉起 FPK 生命周期脚本时为独立受限上下文，**无法自动读取宿主机普通用户的 Shell 环境变量**。因此不能假设环境变量已自动继承，必须按以下步骤持久化提供：

#### 途径 A：原生 FPK 应用中心安装包部署
1. **自动生成与持久化**：
   FPK 安装脚本（`cmd/install_callback`）在初次安装时，会自动检测持久化卷 `/vol*/@appdata/easy-exam/.env` 是否存在；若不存在，会自动生成高强度的唯一随机密钥并写入该文件（权限设为 600）。
   启动脚本 `cmd/main` 在执行 `docker compose up` 前会自动加载该 `.env` 文件。
2. **自定义或多机迁移现有密钥**：
   若已有旧密钥或需要与其它实例保持一致，可在安装后（或停止应用后），通过 SSH 登录 NAS 或在飞牛“文件管理”中定位到：
   `/vol*/@appdata/easy-exam/.env`
   编辑并写入：
   ```env
   EASYEXAM_SECRET_KEY=你的高强度32字节密钥
   ```
   然后执行重启服务：
   ```bash
   sudo appcenter-cli restart easy-exam
   ```

#### 途径 B：标准 Docker Compose / 脚本一键部署
1. 进入项目根目录，复制或创建 `.env` 文件：
   ```bash
   cp .env.example .env  # 或直接 nano .env
   ```
2. 在 `.env` 中填入主密钥：
   ```env
   EASYEXAM_SECRET_KEY=你的高强度32字节密钥
   ```
3. 执行一键部署脚本：
   ```bash
   bash scripts/deploy_fnos.sh
   ```
   脚本会自动检测已有 `.env` 并安全加载；若首次运行未提供，脚本会自动生成新密钥保存至 `.env` 并提示保存。
