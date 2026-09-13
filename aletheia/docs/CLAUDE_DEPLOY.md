# 给服务器 Claude 的部署与接入任务书

## 0. 目标与真实完成状态

请将「观真 ALETHEIA」部署到现有多模型鉴别服务器，保留原有模型架构、权重格式和推理管线。这里交付的前端、Flask API、SQLite 数据库、任务队列、文本大模型适配器均已实现；不是要求从零开发。

**本地开发只有 PROJECT_CONTEXT.md 和 README_使用说明.md，并没有服务器 sys.py / trufor_infer.py / 模型权重，也没有服务器 SSH 权限。** 因此 `server/legacy.py` 是基于交接契约实现的适配器；必须在服务器读取真实源码并完成一次完整联调，不能把本地夹具测试误报为真实模型实测。

先读以下文件：

1. 原始 `handoff/PROJECT_CONTEXT.md`，保留不可变更项。
2. 本文件。
3. `docs/API.md` 与 `docs/DATABASE.md`。
4. `server/legacy.py`、原服务器 `sys.py` 的模型加载段、`process_image()`、`_save_heatmap()`、`trufor_infer.py`。

## 1. 不可变更项

- 对外继续是 `0.0.0.0:6006`，只有该端口被平台映射。
- 原模型根目录 `/root/autodl-tmp/sys_all` 不动。
- 权重：`yolo11n.pt`、`SAE_best.pth`、`SAE_v2.pth`、`mesorch-98.pth`、`mesorch_p-118.pth` 及 TruFor 权重原路径。
- `trufor_infer.py` 与 `TruFor/` 相对位置不动。
- 不重新训练，不用本地 `SAE.py` 替换服务器 `ForgeryNetV2`，不把本地简化代码当作现有分割模型。
- Mesorch key remap `convnext.* → convnext._model.*` 与既有 strict=False 及已知缺失 key 处理不动。
- 各模型输入预处理、ImageNet mean/std、Mesorch 的 Resize(512)+CenterCrop(512) 不动。
- timm 创建模型必须 pretrained=False，不联网下载。
- 不覆盖已安装 torch 2.7.0+cu128、torchvision 0.22.0+cu128、numpy 2.2.6；不引入 mmcv/detectron2/transformers。
- 只启动 1 个 Gunicorn worker。推理有独立单线程队列；绝不能通过增加 worker 数提高并发。

## 2. 建议目录

```text
/root/autodl-tmp/sys_all/
├── sys.py                  # 旧系统，保留作回滚入口
├── trufor_infer.py
├── TruFor/
├── *.pth / *.pt            # 不动
├── aletheia/               # 解压本次交付目录
│   ├── app.py
│   ├── server/
│   ├── web/dist/           # 已构建；服务器不用安装 Node
│   ├── docs/
│   └── .env
└── aletheia-data/          # 新产品数据库和私有图片
```

**部署前先备份 sys.py 和 trufor_infer.py。** 本适配器优先不改旧文件；若下面的静态核对发现命名差异，只调整适配器对接位置，不改网络定义。

## 3. 必须核对的模型适配细节

### A. 安全导入旧入口

适配器通过 importlib 以 `aletheia_legacy_sys` 模块名加载 `LEGACY_ROOT/sys.py`，不使用 `import sys`，避免与 Python 内置 sys 模块冲突。

确认旧脚本的 `app.run()` 在 `if __name__ == '__main__':` 保护内，不能在模块导入时启动旧服务器。若不满足，添加该保护后再继续。只导入一次，模型对象常驻。

执行 `python3 preflight.py` 做只读静态检查：入口函数、已知输出目录变量、TruFor 接口、8 个权重文件与配置是否存在。该命令不加载模型，也不证明检测结果正确。修复所有 BLOCKED 后再启动。

### B. process_image 的实际签名与产物路径

交接契约为 `process_image(filepath, filename) -> dict`。`server/legacy.py` 使用 UUID 输入目录和独立 results 目录，重绑定已知 `UPLOAD_FOLDER`、`RESULT_FOLDER` / `RESULTS_FOLDER` / `OUTPUT_FOLDER` 以及旧 app.config。

必须阅读原 `_save_heatmap`、YOLO 保存段、TruFor 保存段，确认它们实际在运行时读取这些全局变量。若使用其它全局名称、默认函数参数捕获了旧目录、闭包路径或硬编码路径，请把相应路径改为适配器传入的私有任务输出目录。优先新增 `output_dir` 参数或统一配置目录，不要把旧 static/results 公开映射到新系统。

运行一个任务后检查**全部生成图片都在 `aletheia-data/tasks/<uuid>/results/` 内**。适配器遇到不存在的产物会让任务失败，不能假装成功，也不要把缺失热力图替换成生成图片。

### C. 推理行为

- 适配器对模型实例调用 eval()，补上旧版本漏掉的 MesorchP eval。
- 现有 SAEv2 与 TruFor 冲突修正、`s > 0.5` 投票和严格多数判定保留。
- TruFor 推理异常仍由旧管线捕获并降级至 4 模型，结果包含 degraded=true。
- 输入图片经过 EXIF 方向校正后转无损 RGB PNG，避免重编码 JPEG 损失；其后仍进入原模型预处理。
- 仅对 TruFor 输入执行长边上限 1536 的缩放，输出 loc/conf map 再恢复到输入图像大小。检查 `trufor_infer.infer` 实际是否为模块级函数，且输入 PIL、输出三项 `(score, loc, conf)`。若真实导入方式为对象方法，按相同规则在真正调用点加入边长保护。不能在校验失败时静默跳过此保护。
- SAE/Mesorch 不做整图限长重采样，保持原有尺寸与裁切。
- 保持原 `_save_heatmap()` 百分位裁剪和 JET 映射、TruFor 独立分支，前端不重新伪造图。

### D. 补充原始分数（建议）

旧返回值没有 conf_v1，默认适配器诚实地把 SAEv1 分数显示为 null/未返回。建议只在原 `process_image()` 最后返回 dict 前加入 `scores` 字段，使用**已计算、且 SAEv2 冲突修正之后**的变量：

```python
# 请先核对真实变量名，不要盲目粘贴。
"scores": {
    "sae_v1": float(prob_v1),
    "sae_v2": float(prob_v2),
    "mesorch": float(prob_meso),
    "mesorch_p": float(prob_meso_p),
    "trufor": None if prob_trufor is None else float(prob_trufor),
}
```

适配器优先读 scores；未补时兼容现有百分号字符串。不要把所有模型分数取平均当作置信度；不要把 1-prob 无条件称为整体真实性概率。UI 显示所选模型的伪造分数，判断结果仍来自原多数投票。

Mesorch 的 mask 均值和中心裁切行为是既有设计。UI 明确提示热力图对边缘区域没有完整覆盖，不要把拉伸后的图解释成精确的全图定位。

## 4. Python 环境

继续用 `/root/miniconda3/bin/python3`。先确认现有环境：

```bash
cd /root/autodl-tmp/sys_all/aletheia
python3 -c "import torch,numpy; print(torch.__version__,numpy.__version__,torch.cuda.is_available())"
python3 -c "import flask,PIL; print(flask.__version__,PIL.__version__)"
```

服务器已有 Flask/Pillow；仅安装缺失的轻量 Web 依赖。`gunicorn` 原环境未安装，可安装：

```bash
python3 -m pip install gunicorn==23.0.0
```

本项目 `requirements-web.txt` 没有 torch/numpy/timm，也不会要求新的模型框架。不要用本地 freeze 清单覆盖服务器环境。

## 5. 环境变量与数据库配置

复制 `.env.example` 为 `.env`，在服务器生成真实随机密钥；不要把密钥提交到 GitHub。环境中已导出的值优先于 `.env`。

```dotenv
APP_ENV=production
HOST=0.0.0.0
PORT=6006
SECRET_KEY=替换为至少32字符的随机值
COOKIE_SECURE=1
PUBLIC_ORIGIN=https://替换为平台的实际HTTPS域名
LEGACY_ROOT=/root/autodl-tmp/sys_all
LEGACY_MODULE=sys.py
DATA_DIR=/root/autodl-tmp/sys_all/aletheia-data
MAX_UPLOAD_MB=10
MAX_IMAGE_PIXELS=16000000
TRUFOR_MAX_SIDE=1536
QUEUE_CAPACITY=8
RETENTION_DAYS=30
LLM_URL=
LLM_API_KEY=
LLM_MODEL=
LLM_TIMEOUT=90
```

生成随机密钥：`python3 -c "import secrets; print(secrets.token_hex(32))"`。生产启动会拒绝缺失或过短的 SECRET_KEY。SECRET_KEY 用于签名访客 Cookie，更换会让所有访客失去既有历史入口，因此部署后应固定保存、不要轮换。

COOKIE_SECURE=1 只适合用户通过 HTTPS 访问。直接 HTTP 本地测试应设为 0；生产优先使用平台 HTTPS 隧道。PUBLIC_ORIGIN 写用户实际访问的域名，避免代理改写内部 Host 后触发 CSRF Origin 拒绝。无外部代理时留空会使用当前请求 Host。

数据库自动创建为 `DATA_DIR/aletheia.sqlite3`，不需 PostgreSQL/MySQL 密码或安装数据库进程。检查 `schema_version` 含 1、2，表包括 visitors/conversations/messages/detection_tasks/artifacts。数据目录用 `chmod 700`，进程 umask=0077。保留固定 SECRET_KEY 以让已有访客会话在重启后仍能读取历史。

大模型配置详见 API.md：目前实现 Chat Completions 兼容格式；LLM_URL 为完整 POST 路径，LLM_MODEL 为提供商真实模型名。原生 Claude Messages 端点不能直接替换为同一格式，需要新增供应商适配器。密钥只保存在服务端。未配置时允许保存对话，显示未接入提示。

## 6. 启动与唯一端口

先检查 6006 是否由旧 sys.py 占用；确认现有进程和启动方式，平稳停止旧 Web 进程后再启动新系统。不要同时运行两个服务争抢端口。

```bash
cd /root/autodl-tmp/sys_all/aletheia
python3 preflight.py
bash deploy/start.sh
```

脚本使用：1 worker、gthread 4 个 HTTP 线程、300 秒超时、0.0.0.0:6006；模型推理仍由唯一后台推理线程串行处理。不要启用 Gunicorn --preload 或 --reload，以免错误复制线程状态或重新加载模型。

生产推荐安装 `deploy/aletheia.service`。很多 AutoDL 容器不运行 systemd；先检查 `ps -p 1 -o comm=`。如果不支持，使用平台进程守护或已有 supervisor 启动 `bash deploy/start.sh`，不要凭空假设 systemctl 可用。

前端构建产物已经位于 web/dist；不需在服务器开启 Vite/5173。修改前端后再重新构建并上传 dist。不要把 Python Flask 的开发服务器当成正式守护部署。

## 7. 清理与备份

手动执行 `python3 cleanup.py` 只清理过期已完成/失败的任务文件和记录，不载入模型、不重置运行中的任务。安装交付的 cleanup.service + cleanup.timer 才会每日自动清理。没有 systemd 时，在服务器已有调度工具中每日运行该命令，并记录日志。

绝不能递归删除 sys_all、TruFor、权重或旧 static 目录。备份请读 DATABASE.md：停服务后完整复制 DATA_DIR，或使用 SQLite Online Backup 并协调文件快照。不可运行时只复制主 sqlite 文件而遗漏 WAL。

## 8. 服务器验收清单（必须实际执行）

1. GET `/api/v1/health` 返回 status=ok；推理 state 初始 not_loaded。由文件存在得到 available=true 并不意味着已加载成功。
2. 经 HTTPS 打开首页：黑色星空向前运动；点击主球看到第二句指定文案；小球可以打开上传。
3. 打开页面即建立访客会话（无访问密钥门禁）；用实际图像上传，POST /detect 返回 202；等待真实 completed。
4. 日志确认权重正常加载，MesorchP.eval 生效，网络启动无下载。
5. 检查各模型分数（SAEv1 补字段后非 null）、实际热力图和掩码能访问，YOLO 产物正常保存。
6. 对同一张既有测试图，与旧系统比较原投票逻辑及结果；记录因 MesorchP.eval、EXIF 方向/无损保存、TruFor 限长导致的差异，不能自动声称结果完全一致。
7. 至少测试一张非正方形图、一张大图、一张正常图、一张伪造图；验证裁切提示、TruFor 限长、CPU 回退。可用 GPU 情况下实测耗时与峰值显存。当前本地没有资格给出这些指标。
8. 两个浏览器会话验证任务/图片/对话不能交叉读取；错误访问均应返回 404。
9. 连续提交任务，确认推理并发固定 1、队列满后 429，而健康接口与页面仍响应。
10. 配置真实大模型，发送问题，确认异步回复落库、会话恢复正确；不要将固定失败说明当作模型回复测试通过。
11. 重启服务，未完成任务标 failed/SERVER_RESTARTED，已完成历史保留；用户可重新发起任务。
12. 删除任务后对应 UUID 目录消失，其它任务不受影响；人工设置一条到期测试记录验证 cleanup.py。

## 9. 已知边界与后续扩展

- 用户身份只是浏览器 Cookie，不是多账户登录系统，站点也没有入口门禁：拿到地址即可使用。想要跨设备历史、用户配额或访问控制，需要独立账号模块。
- 当前队列在内存中，结果持久化；重启会标失败，不自动恢复执行。未来扩容需单独 GPU worker 与外部队列。
- HTTP 上传不支持幂等键，响应丢失后先看历史，避免重复任务。
- API 默认 10 MiB/1600 万像素；公开长期服务需在入口增加请求速率限制、存储配额和运维告警。不要把受共享密钥保护的研究部署当成完备的互联网多租户平台。
- 当前数据模式是 SQLite。只有实际扩大规模后再迁移 PostgreSQL，不能在代码未实现时只填 DATABASE_URL。
- 原模型许可证、数据集和权重使用范围沿用现有项目，交付 Web 层没有重新授权其模型资产。

最后交付给用户：实际访问地址、模型和 LLM 联调结果、部署配置位置（不回显密钥）、清理/备份安排、未通过项目。不要声称本地 UI 截图等于服务器真实模型验证。
