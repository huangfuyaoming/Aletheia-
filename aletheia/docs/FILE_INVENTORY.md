# 观真 · 项目文件清单

[返回项目首页](../README.md) · [使用说明](USAGE.md)

清点日期：2026-09-13。范围为当前本地交付目录，包含隐藏配置模板、源码、文档、截图和 `web/dist/`，共 **69 个文件**（不计 macOS 自动生成的 `.DS_Store`）。本地目录没有 `.git/` 元数据，因此这是一份交付文件清单，不是 Git 跟踪状态报告。未把不存在的模型权重或将来生成的数据计入交付数量。

## 按任务查找文件

| 你要做什么 | 主要入口 |
| --- | --- |
| 了解产品或向他人介绍项目 | [README](../README.md) |
| 启动、使用或排错 | [使用说明](USAGE.md) |
| 修改首页和导航 | `web/src/App.jsx`、`StarNavigation.jsx`、`StarTransition.jsx` |
| 修改上传和结果展示 | `web/src/components/Detection.jsx`、`web/src/api.js` |
| 修改对话或历史 | `Chat.jsx`、`History.jsx`、`app.py`、`server/jobs.py` |
| 调整外观和动画 | `style.css`、`constellation.css`、`Cosmos.jsx` |
| 新增或调整 API | `app.py`、`docs/API.md`、`tests/test_api.py` |
| 接入原模型 | `server/legacy.py`、`preflight.py`、`docs/CLAUDE_DEPLOY.md` |
| 调整配置或数据结构 | `server/settings.py`、`.env.example`、`server/db.py`、`server/schema.sql` |
| 配置清理和守护 | `cleanup.py`、`server/maintenance.py`、`deploy/` |

上表中的短文件名可在下方完整路径中定位。

## 逐文件清单

### 根目录

| 文件 | 职责与使用方式 |
| --- | --- |
| [.env.example](../.env.example) | 环境变量模板；首次启动复制为 `.env` 后填写实际配置。 |
| [.gitignore](../.gitignore) | 声明本地数据、密钥、依赖和缓存等 Git 忽略规则。 |
| [README.md](../README.md) | 产品概览、功能边界、快速开始与文档导航。 |
| [app.py](../app.py) | Flask 应用工厂、会话保护、鉴别/对话/产物 API 和前端静态托管；本地运行入口。 |
| [cleanup.py](../cleanup.py) | 手动或定时清理到期且已结束的鉴别任务；在项目根目录执行。 |
| [preflight.py](../preflight.py) | 对外部模型入口、TruFor 接口和权重路径做只读静态检查，不加载权重。 |
| [requirements-web.txt](../requirements-web.txt) | Web 层 Python 依赖，不包含 torch、模型或权重。 |

### 后端服务

| 文件 | 职责与使用方式 |
| --- | --- |
| [server/__init__.py](../server/__init__.py) | Python 包标记。 |
| [server/settings.py](../server/settings.py) | 读取 `.env` 和环境变量，校验生产密钥，集中提供配置。 |
| [server/db.py](../server/db.py) | SQLite 连接、事务、初始化和迁移；转换任务对外字段。 |
| [server/schema.sql](../server/schema.sql) | 数据库初始表和索引；消息顺序字段与后续迁移由 `db.py` 补充。 |
| [server/jobs.py](../server/jobs.py) | 单线程鉴别、双线程对话、容量控制与任务状态持久化；对接文字供应商。 |
| [server/legacy.py](../server/legacy.py) | 惰性加载外部入口，设置 eval、限制 TruFor 输入、重定向产物及规范化分数。 |
| [server/maintenance.py](../server/maintenance.py) | 清理逻辑实现，供 `cleanup.py` 与测试调用。 |

### 前端配置与入口

| 文件 | 职责与使用方式 |
| --- | --- |
| [web/.npmrc](../web/.npmrc) | 包管理器配置，关闭自动管理包管理器版本并指定 pnpm 缓存位置。 |
| [web/package.json](../web/package.json) | React/Vite 依赖及 dev、build、preview 脚本。 |
| [web/pnpm-lock.yaml](../web/pnpm-lock.yaml) | pnpm 依赖锁文件；项目文档以 pnpm 安装与构建。 |
| [web/package-lock.json](../web/package-lock.json) | 同时交付的 npm 锁文件；使用 npm 时才消费此文件。 |
| [web/pnpm-workspace.yaml](../web/pnpm-workspace.yaml) | pnpm 构建许可、缓存目录与运行前依赖检查设置。 |
| [web/vite.config.js](../web/vite.config.js) | 开发 API 代理、构建目标与 source map 设置。 |
| [web/index.html](../web/index.html) | Vite HTML 模板，引用源码入口。 |
| [web/src/main.jsx](../web/src/main.jsx) | 挂载 React 根组件并加载样式。 |
| [web/src/App.jsx](../web/src/App.jsx) | 首页引导、健康与会话初始化、面板切换及减少动态偏好。 |
| [web/src/api.js](../web/src/api.js) | API 请求、CSRF、图片上传进度、状态和模型名称映射。 |
| [web/src/style.css](../web/src/style.css) | 全局布局、业务面板、响应式与基础视觉样式。 |
| [web/src/constellation.css](../web/src/constellation.css) | 星辰导航、返回控件与过渡相关样式。 |

### 前端组件

| 文件 | 职责与使用方式 |
| --- | --- |
| [web/src/components/Detection.jsx](../web/src/components/Detection.jsx) | 图片选择、预览、任务轮询及模型结果视图。 |
| [web/src/components/Chat.jsx](../web/src/components/Chat.jsx) | 对话消息展示、输入发送与回复状态查询。 |
| [web/src/components/History.jsx](../web/src/components/History.jsx) | 鉴别/对话历史分页、恢复入口和删除操作。 |
| [web/src/components/Surface.jsx](../web/src/components/Surface.jsx) | 通用面板容器、Escape 关闭、焦点圈定与焦点恢复。 |
| [web/src/components/Cosmos.jsx](../web/src/components/Cosmos.jsx) | Canvas 星空和光球动画。 |
| [web/src/components/StarNavigation.jsx](../web/src/components/StarNavigation.jsx) | 对话之星与记忆之星的入口组件。 |
| [web/src/components/StarTransition.jsx](../web/src/components/StarTransition.jsx) | 星辰过渡上下文、交互按钮与返回之星。 |
| [web/src/components/Icon.jsx](../web/src/components/Icon.jsx) | 共享 SVG 图标组件。 |

### 前端构建产物

| 文件 | 职责与使用方式 |
| --- | --- |
| [web/dist/index.html](../web/dist/index.html) | Flask 首页实际提供的构建后 HTML；由前端构建生成。 |
| [web/dist/assets/index-BFof3N2L.js](../web/dist/assets/index-BFof3N2L.js) | 当前交付的打包 JavaScript；不要手工编辑。 |
| [web/dist/assets/index-BkwQLOy_.css](../web/dist/assets/index-BkwQLOy_.css) | 当前交付的打包 CSS；不要手工编辑。 |

### 部署与测试

| 文件 | 职责与使用方式 |
| --- | --- |
| [deploy/start.sh](../deploy/start.sh) | 启动 Gunicorn，固定单 worker、4 个 HTTP 线程和 6006 端口。 |
| [deploy/aletheia.service](../deploy/aletheia.service) | systemd 网站服务模板；安装前核对运行路径与可执行文件位置。 |
| [deploy/aletheia-cleanup.service](../deploy/aletheia-cleanup.service) | systemd 一次性清理服务模板，调用 `cleanup.py`。 |
| [deploy/aletheia-cleanup.timer](../deploy/aletheia-cleanup.timer) | 每日清理定时器模板；启用后才会按计划调用清理服务。 |
| [tests/test_api.py](../tests/test_api.py) | 8 个现有测试方法，使用推理和文字供应商夹具验证 API、队列、隔离、清理及分数解析。 |

### 文档

| 文件 | 职责与使用方式 |
| --- | --- |
| [docs/USAGE.md](../docs/USAGE.md) | 本地启动、终端用户操作、全部配置项、开发、部署、维护与排错。 |
| [docs/FILE_INVENTORY.md](../docs/FILE_INVENTORY.md) | 本文件，当前交付文件清单与查找指南。 |
| [docs/README.en.md](../docs/README.en.md) | 从原 README 拆出的英文概览，保留英文阅读入口。 |
| [docs/API.md](../docs/API.md) | API 契约、请求响应、状态与错误码。 |
| [docs/DATABASE.md](../docs/DATABASE.md) | 数据表、归属关系、保留策略与备份方式。 |
| [docs/DESIGN.md](../docs/DESIGN.md) | 视觉语言、界面行为与可访问性约定。 |
| [docs/CLAUDE_DEPLOY.md](../docs/CLAUDE_DEPLOY.md) | 当前 Web 层接入原模型服务器的部署任务书与验收清单。 |
| [docs/source/README_使用说明.md](../docs/source/README_使用说明.md) | 解释历史快照的范围、当前文档入口和交接方式。 |
| [docs/source/PROJECT_CONTEXT.md](../docs/source/PROJECT_CONTEXT.md) | 2026-09-11 旧推理服务器快照；含历史环境、模型路径和改造建议，非当前源码说明。 |

### 图片资源

| 文件 | 职责与使用方式 |
| --- | --- |
| [docs/screenshot-home.png](../docs/screenshot-home.png) | 本次提供的真实首页截图。 |
| [docs/screenshot-stage2.png](../docs/screenshot-stage2.png) | 本次提供的真实第二段引导截图。 |
| [docs/screenshot-upload-preview.png](../docs/screenshot-upload-preview.png) | 本次提供的真实图片上传预览截图。 |
| [docs/screenshot-chat.png](../docs/screenshot-chat.png) | 已有文字对话截图。 |
| [docs/screenshot-history.png](../docs/screenshot-history.png) | 本次提供的真实历史记录截图。 |
| [docs/screenshot-nav-star.png](../docs/screenshot-nav-star.png) | 本次提供的真实星辰导航截图。 |
| [docs/screenshot-mobile.png](../docs/screenshot-mobile.png) | 本次提供的真实移动端截图。 |
| `docs/concept-home.png` | 历史概念图文件，未用于产品文档展示。 |
| `docs/concept-result.png` | 历史概念图文件，未用于产品文档展示。 |

| [docs/screenshot-mobile-history.png](../docs/screenshot-mobile-history.png) | 真实检测记录的移动端历史截图。 |
| [docs/screenshot-result-realworld-trufor-heatmap.png](../docs/screenshot-result-realworld-trufor-heatmap.png) | IMD2020 样本的 TruFor 真实热力图界面。 |
| [docs/screenshot-result-realworld-trufor-mask.png](../docs/screenshot-result-realworld-trufor-mask.png) | IMD2020 样本的 TruFor 真实二值掩码界面。 |
| [docs/screenshot-result-realworld-original.png](../docs/screenshot-result-realworld-original.png) | IMD2020 待检测图片的原图视图，当前选中 SAEv2 分数。 |
| [docs/screenshot-result-splice-trufor-heatmap.png](../docs/screenshot-result-splice-trufor-heatmap.png) | CASIA v1 拼接样本的 TruFor 真实热力图界面。 |
| [docs/screenshot-result-splice-saev1-heatmap.png](../docs/screenshot-result-splice-saev1-heatmap.png) | 自研 SAEv1 对 CASIA v1 拼接样本的真实检测界面。 |
| [docs/screenshot-result-authentic-saev2-heatmap.png](../docs/screenshot-result-authentic-saev2-heatmap.png) | 自研 SAEv2 对 CASIA v1 未篡改样本的真实检测界面。 |
| [docs/real-results/MANIFEST.md](../docs/real-results/MANIFEST.md) | 随素材提供的样本来源清单；所列原始图片与标注保留在外部素材文件夹。 |
| [docs/real-results/inference_results.json](../docs/real-results/inference_results.json) | 随素材提供的推理结果快照；产物 API 地址属于原服务会话，并非仓库静态图片链接。 |

构建产物文件名含内容哈希，重新构建后名称可能变化，届时应同步更新清单。本次从 `aletheia-real-results/shots/` 原样复制 13 张实际截图，其中 6 张更新既有配图、7 张补充检测结果与移动端历史。概念图仅作为未引用的历史文件保留；本次没有重新生成或编辑截图像素。随附样本清单和推理记录保存在 `docs/real-results/`，不复制整套测试图片或标注。

## 运行后生成的文件

以下不属于本次静态交付清单。实际位置取决于配置和使用过的开发工具。

| 路径 | 如何产生 | 使用说明 |
| --- | --- | --- |
| `.env` | 从配置模板复制并填写 | 本机/服务器配置，可包含密钥；已列入 Git 忽略规则 |
| `.venv/` | 本地创建 Python 虚拟环境 | 依赖环境，不是应用源码 |
| `web/node_modules/` | 安装前端依赖 | 可按锁文件重建 |
| `.pnpm-store/` | 当前 pnpm 配置的依赖缓存 | 安装时生成，不需作为部署源码交付 |
| `__pycache__/`、`*.pyc` | Python 执行或编译 | 运行缓存 |
| `data/aletheia.sqlite3` | 默认配置下首次初始化应用或数据库 | 任务、访客和消息等持久化记录 |
| `data/aletheia.sqlite3-wal`、`data/aletheia.sqlite3-shm` | SQLite WAL 模式运行时 | 临时或运行相关文件，在线备份不能只复制主数据库 |
| `data/tasks/<task_id>/input.png` | 成功接收鉴别上传 | 规范化的原图，按任务隔离 |
| `data/tasks/<task_id>/results/` | 真实推理生成 | 各模型热力图、掩码与 YOLO 等产物 |

设置 `DATA_DIR` 后，以上 `data/` 路径整体迁移到指定目录。日常清理通过 `cleanup.py` 完成；不要把删除整个数据目录当作常规清理方式。

## 不在当前交付中的外部依赖

| 外部内容 | 接入方式 |
| --- | --- |
| 原 `sys.py` 与 `process_image()` | 通过 `LEGACY_ROOT` 和 `LEGACY_MODULE` 定位 |
| `trufor_infer.py` 与 `TruFor/` 模型代码 | 保留原服务器目录关系，由适配器对接 |
| SAE、Mesorch、YOLO、TruFor 等权重 | 使用原服务器资产，完整路径由 `preflight.py` 检查 |
| GPU、torch 及模型推理依赖 | 由目标服务器提供；Web requirements 不安装这些内容 |
| 文字大模型服务 | 通过服务端 `LLM_URL`、`LLM_MODEL` 与所需密钥接入 |

旧服务器的详细模型文件结构见[历史快照](source/PROJECT_CONTEXT.md)，当前接入要求以[部署指南](CLAUDE_DEPLOY.md)和实际源码为准。

## 交付与维护说明

- 运行网站需要后端代码、Web 依赖和完整 `web/dist/`；修改前端需要 `web/src/`、入口 HTML、构建配置与对应锁文件。
- `deploy/` 是部署模板，不能假定其中的绝对路径适用于所有机器。
- `tests/` 和 `docs/` 用于验证与交接，建议随源码保留。
- 本次未新增 Docker、CI、账号系统或许可证文件；不要把文档中的规划建议当成已有能力。
