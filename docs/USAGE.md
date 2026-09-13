# 观真 · 使用说明

[返回项目首页](../README.md) · [文件清单](FILE_INVENTORY.md) · [部署指南](CLAUDE_DEPLOY.md)

本文依据当前交付代码整理，涵盖本地启动、用户操作、服务配置和日常维护。命令默认在项目根目录执行；生产服务器的模型接入以部署指南为准。

## 目录

- [选择运行方式](#选择运行方式)
- [本地启动](#本地启动)
- [用户操作](#用户操作)
- [配置参考](#配置参考)
- [前端开发](#前端开发)
- [服务器部署](#服务器部署)
- [日常维护](#日常维护)
- [常见问题](#常见问题)

## 选择运行方式

| 目的 | 需要准备 | 可以验证什么 |
| --- | --- | --- |
| 浏览界面与历史功能 | Python 3.10+、Web 依赖、已有 `web/dist/` | 页面、图片本地预览、访客会话与消息保存 |
| 修改前端 | 以上环境，加 Node.js 22.12+、Corepack/pnpm | 页面交互、样式、API 联调与构建 |
| 执行真实鉴别 | 既有推理程序、完整权重、兼容模型环境 | 实际分数、热力图、掩码和真实耗时 |
| 获得文字回复 | 可访问的 Chat Completions 兼容端点、模型名及所需密钥 | 真实文字对话及历史恢复 |

只安装 `requirements-web.txt` 不会获得推理模型或权重。代码在首次鉴别时加载模型，首页成功打开不代表模型已通过验证。

## 本地启动

### 1. 安装 Web 依赖

macOS / Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-web.txt
```

Windows PowerShell：

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-web.txt
```

生产模型服务器应沿用既有 Python/torch 环境，只补齐 Web 依赖，详见[部署指南](CLAUDE_DEPLOY.md#4-python-环境)。

### 2. 准备配置

首次配置时复制模板；如果已有 `.env`，直接编辑现有文件。

```bash
cp .env.example .env
```

Windows PowerShell 可使用 `Copy-Item .env.example .env`。

生成随机密钥，将输出填入 `.env` 的 `SECRET_KEY`：

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

本地 HTTP 访问保持 `APP_ENV=development`、`COOKIE_SECURE=0`。固定密钥可让已有访客 Cookie 在服务重启后继续有效；未固定时开发环境会在启动时生成随机密钥。

### 3. 启动并检查

```bash
python app.py
```

打开 [首页](http://127.0.0.1:6006) 和 [健康接口](http://127.0.0.1:6006/api/v1/health)。

| 健康字段 | 如何理解 |
| --- | --- |
| `status: ok` | Web 服务能够响应 |
| `inference.available: false` | 配置位置没有找到推理入口文件 |
| `inference.available: true` | 找到了入口文件，仍需实际加载和推理验证 |
| `inference.state: not_loaded` | 尚未触发首次加载 |
| `inference.state: error` | 加载阶段出错，应检查服务器日志 |
| `chat.available: true` | 已填写对话地址和模型名，不代表供应商连接或密钥已验证 |

在终端按 `Ctrl+C` 停止本地服务。

## 用户操作

### 图像鉴别

可先查看 [SAEv1、SAEv2 真实结果示例](../README.md#界面预览)，了解模型切换、伪造分数和热力图的呈现方式。

1. 点击首页中央光球，进入第二段引导，选择“图像鉴别”。
2. 点击选择框或拖入静态 JPG、PNG、WebP 文件。
3. 检查预览后点击“开始鉴别”。默认限制为 10 MiB、1600 万像素，动态或多帧图片不支持。
4. 页面显示实际上传百分比，上传后显示“等待鉴别”或“正在鉴别”。排队与推理没有进度百分比。
5. 完成后查看判决，切换模型、原图、热力图或二值掩码；热力图可调整叠加透明度。

上传获得服务器任务后，关闭面板不会取消任务，可从历史重新打开。上传过程中连接中断时，先查看历史，确认是否已经创建任务，再决定是否重新上传。

结果中的百分数为模型伪造倾向分数；“未返回”代表缺少该字段。不同模型的分数不可直接视为同一校准尺度。Mesorch 中心裁切、TruFor 降级等限制应结合结果提示理解。

### 文字对话

1. 点击“对话之星”，输入消息并发送。
2. 等待回复结束再发送下一条；单条消息最多 4000 字符。
3. 通过历史记录恢复已有对话，或重新进入新的对话。

同一对话最多 400 条消息，包含用户和助手消息；达到上限后需新建对话。调用供应商时仅发送最近最多 40 条已完成消息及系统提示，不会发送整个无限增长的历史。

未配置供应商时，用户消息仍会保存，助手位置显示标记为失败的系统说明。配置完成后可以继续发送新消息；历史失败回复不会自动补发。当前对话不读取图片，也不自动带入鉴别结果。

### 历史与删除

点击“记忆之星”，切换鉴别和对话列表，打开记录继续查看；有更多记录时加载下一页。

- 已完成或失败的鉴别任务可以删除，删除会移除对应图片产物与数据库记录。
- 对话删除会同时删除其消息；有待处理或运行中回复时不能删除。
- 排队或运行中的鉴别不能删除，也没有取消任务接口。
- 删除后没有产品内撤销或回收站。
- 历史属于当前浏览器 Cookie；清除 Cookie、切换浏览器或更换签名密钥后不能自动找回。当前没有账号登录、跨设备同步或用户端恢复功能。

## 配置参考

配置由 [`server/settings.py`](../server/settings.py) 读取：已导出的环境变量优先于项目根目录 `.env`，其次使用代码默认值。更改后重启应用生效。

| 配置项 | 默认值 | 用途 |
| --- | --- | --- |
| `APP_ENV` | `development` | `production` 时强制校验密钥长度 |
| `HOST` / `PORT` | `127.0.0.1` / `6006` | 仅用于 `python app.py`；部署脚本固定绑定 `0.0.0.0:6006` |
| `SECRET_KEY` | 开发模式随机生成 | 访客 Cookie 签名密钥；生产必须固定且至少 32 字符 |
| `COOKIE_SECURE` | `0` | HTTPS 访问设为 `1`，本地 HTTP 使用 `0` |
| `PUBLIC_ORIGIN` | 空 | 用户实际访问来源，如 `https://example.com`；留空使用请求 Host |
| `DATA_DIR` | 代码默认项目下 `data/`，模板为 `./data` | 数据库和任务产物位置；生产建议使用独立绝对路径 |
| `LEGACY_ROOT` | `/root/autodl-tmp/sys_all` | 仓库外推理程序与权重所在目录 |
| `LEGACY_MODULE` | `sys.py` | 相对模型目录的入口文件 |
| `MAX_UPLOAD_MB` | `10` | 按 MiB 计算的上传文件大小限制 |
| `MAX_IMAGE_PIXELS` | `16000000` | 解码后图片总像素限制 |
| `TRUFOR_MAX_SIDE` | `1536` | 仅 TruFor 分支限制最长边，输出图再恢复到输入尺寸 |
| `QUEUE_CAPACITY` | `8` | 等待与运行中的鉴别任务总容量；推理并发仍为 1 |
| `RETENTION_DAYS` | `30` | 新鉴别任务自创建起的保留天数，需清理命令实际执行 |
| `LLM_URL` | 空 | Chat Completions 兼容服务的完整 POST 地址 |
| `LLM_API_KEY` | 空 | 供应商所需服务端密钥；服务无需认证时可以为空 |
| `LLM_MODEL` | 空 | 供应商支持的真实模型名 |
| `LLM_TIMEOUT` | `90` | 对话 HTTP 请求超时秒数 |

`LLM_URL` 需要填写完整接口路径，不能只填域名，也不能直接使用不同协议的端点。配置检测仅要求 URL 和模型名非空；凭据、可达性和响应格式须通过真实消息验证。

调整保留天数仅影响此后创建的鉴别任务；已有任务保存了自己的 `expires_at`。对话与消息不受此项自动清理。

## 前端开发

在一个终端保持 Flask 运行，在第二个终端执行：

```bash
cd web
corepack pnpm install --frozen-lockfile
corepack pnpm run dev
```

访问 Vite 终端打印的地址。开发代理将 `/api` 请求交给 `127.0.0.1:6006`；若配置了 `PUBLIC_ORIGIN`，应匹配浏览器实际访问来源。

更新生产构建：

```bash
corepack pnpm run build
```

返回 Flask 首页验证更新后的 `web/dist/`。不要手工修改打包后的 JS/CSS。项目同时附有 npm 和 pnpm 锁文件，本说明沿用原项目的 pnpm 命令；变更依赖时应明确所用包管理器和对应锁文件。

## 服务器部署

完整接入流程见[部署指南](CLAUDE_DEPLOY.md)。执行顺序：

1. 在目标服务器确认原程序、模型权重与兼容依赖完整，保留其目录结构。
2. 配置 `.env`，设置 `APP_ENV=production`、固定密钥、数据目录、访问来源，以及需要的 LLM 参数。
3. 运行 `python3 preflight.py`；缺少外部模型时返回阻断属于预期结果，不能据此判断 Web 页面不可运行。
4. 确认旧服务已释放端口后，运行 `APP_ENV=production bash deploy/start.sh`。
5. 使用真实图片、真实对话供应商完成验收，再配置守护与定时清理。

部署脚本固定 1 个 Gunicorn worker、4 个 HTTP 线程；图像后台推理并发仍为 1。不要增加 worker，不要使用 `--preload` 或 `--reload`。

`deploy/*.service` 中的项目路径和 Python/Gunicorn 路径是原服务器模板值，安装前按真实环境修改。支持 systemd 时可用附带服务和清理定时器；不支持时按现有平台的进程守护与调度方式运行脚本。

## 日常维护

### 自动化验证

```bash
python -m unittest discover -s tests -v
```

现有测试覆盖上传、任务状态与队列、归属隔离、CSRF/Origin、对话适配、清理和分数解析。测试使用夹具，不需要真实 GPU 权重，也不能替代实机模型验收。

### 清理鉴别记录

```bash
python cleanup.py
```

命令只处理已到期且状态为 `completed` 或 `failed` 的鉴别任务，输出删除数量，不加载模型，也不重置运行任务。每日自动执行需要安装并启用清理定时器或配置平台调度；单纯启动网站不会自动清理。

### 备份与恢复

按[数据库说明](DATABASE.md)备份。简单方案是停止服务后完整备份 `DATA_DIR`，同时安全保存固定签名密钥和运行配置；恢复时保持数据路径和密钥一致。运行中不要只复制 SQLite 主文件而遗漏 WAL 数据。在线备份需要协调数据库备份与图片文件快照。

服务重启会把未结束的鉴别和回复标记为 `SERVER_RESTARTED`，用户需要重新提交，不会自动续跑。

## 常见问题

| 现象 | 原因或检查方向 | 处理方式 |
| --- | --- | --- |
| 模型未连接，不能开始鉴别 | 未找到配置的入口文件 | 检查 `LEGACY_ROOT`、`LEGACY_MODULE`；本地无模型时可继续预览 |
| 健康正常，但鉴别失败 | 健康检查没有验证权重与推理 | 先运行静态检查，再查模型加载日志、依赖与输出路径 |
| 首次鉴别较慢 | 首次加载模型，或使用 CPU | 查看日志及资源情况，实测耗时；不要通过增加 worker 加速 |
| `QUEUE_FULL` / `CHAT_BUSY` | 服务任务容量已满 | 等待已有任务结束后重试 |
| `CSRF_REJECTED` / `UNAUTHENTICATED` | 会话失效或没有带 Cookie/token | 刷新页面建立会话；确认浏览器允许 Cookie |
| `ORIGIN_REJECTED` | 实际页面来源与服务配置不一致 | 检查 `PUBLIC_ORIGIN` 的协议、域名、端口和代理设置 |
| HTTP 下反复丢失会话 | 可能设置了 Secure Cookie | 本地 HTTP 使用 `COOKIE_SECURE=0` |
| `FILE_TOO_LARGE` / `IMAGE_TOO_LARGE` | 超过字节数或像素限制 | 压缩文件或缩小图片；部分界面错误文案固定写 10 MB，以实际配置为准 |
| `INVALID_IMAGE` / `UNSUPPORTED_IMAGE` | 文件损坏、格式不支持或为多帧图 | 转为有效的静态 JPEG、PNG、WebP |
| `LLM_NOT_CONFIGURED` / `LLM_FAILED` | 未配置，或供应商请求失败 | 检查完整端点、模型名、密钥、网络与服务端日志 |
| 重启后历史不见了 | 签名密钥变化或访客 Cookie 丢失 | 检查配置；当前没有把旧历史合并给新访客的入口 |
| 修改源码后页面没变化 | Flask 仍在托管旧构建 | 重新构建 `web/dist/` 后刷新 |
| 过了 30 天文件还在 | 未运行清理，或任务仍在等待/运行 | 核查任务到期时间与定时任务日志 |
