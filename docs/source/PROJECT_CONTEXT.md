# 图像伪造检测系统 — 现有配置与开发交接文档

> **历史资料：**本文记录 2026-09-11 的旧版服务器快照，未在本次整理中重新实测。目录、接口、GPU 状态和重构建议不代表当前 Web 项目；当前实现请从 [项目首页](../../README.md)、[使用说明](../USAGE.md) 和 [部署指南](../CLAUDE_DEPLOY.md) 开始阅读。

> 本文档描述一套**已在服务器上跑通**的多模型图像篡改检测系统的现状。
> 目标读者：负责在本地设计开发网页前端 / 后端 API 的开发者（含 AI 助手）。
> 交付要求：开发完成的代码上传到服务器后，**必须能直接运行，不允许要求重新训练模型或更换权重格式**。
>
> 核实时间：2026-09-11。以下所有版本号、路径、文件大小均由服务器实际检查得出，非估计值。

---

## 0. 一句话现状

服务器上有一个 **1400 行的单文件 Flask 应用** `sys.py`，它把 6 个模型的架构定义、HTML 前端模板、推理逻辑、路由全部写在一个文件里，只有一个路由 `/`，用 `render_template_string` 直接吐整页 HTML。**没有任何 JSON API**。

新的网页产品需要做的事情，本质是：**保留 `sys.py` 里的模型定义与推理管线，把前端剥离出去，补一层 JSON API。**

---

## 1. 服务器环境（实测）

| 项目 | 实际值 |
|------|--------|
| 操作系统 | Ubuntu 22.04.5 LTS (Jammy) |
| 内核 | Linux 5.15.0-94-generic |
| Python | 3.12.3 |
| Python 路径 | `/root/miniconda3/bin/python3`（conda base 环境，非 venv） |
| CPU | **1 核**（`nproc` = 1） |
| 内存 | 1007 GB total（宿主共享，实际可用约 920 GB） |
| 系统盘 | overlay 30 GB，已用 15 GB，**剩余仅 16 GB** |
| 项目所在盘 | `/root/autodl-tmp/`（数据盘） |
| GPU | **当前不可用** — 见下方 1.1 |

### 1.1 GPU 状态（重要）

```
nvidia-smi              →  无输出（无 GPU 设备）
torch.cuda.is_available() →  False
torch.version.cuda        →  12.8（torch 是 CUDA 版，但当前无卡）
```

**含义：**
- torch 安装的是 `2.7.0+cu128`（CUDA 12.8 构建），说明这台机器**原本有 GPU**，训练和之前的推理都在 GPU 上跑。
- 当前实例没挂载 GPU（可能是已释放显卡 / 无卡开机模式）。
- `sys.py` 第 1217 行是 `torch.device('cuda' if torch.cuda.is_available() else 'cpu')`，所以**代码不会崩，会自动退回 CPU**，但 1 核 CPU 跑 6 个模型（含 SegFormer-B4 + ConvNeXt）单张图推理会非常慢（预计 30 秒到数分钟）。
- **开发时请假设最终部署在 GPU 环境**（约需 6 GB 以上显存，见 §4.3），同时代码要保留 CPU 回退路径。

---

## 2. 依赖清单（实测版本，pip list）

```
torch                 2.7.0+cu128
torchvision           0.22.0+cu128
timm                  1.0.26
ultralytics           8.4.37
Flask                 3.1.3
Werkzeug              3.1.3
opencv-python         4.13.0.92
numpy                 2.2.6
pillow                11.2.1
scipy                 1.17.1
einops                0.8.2
yacs                  0.1.8
matplotlib            3.10.3
```

**注意事项：**
- `numpy` 是 **2.x**。本地开发若装 numpy 1.x，部分行为（如 `np.percentile` 返回类型、cv2 兼容性）可能有差异，请对齐 2.2.6。
- `yacs` 仅被 TruFor 的配置系统使用，不可省。
- TruFor 子模块额外需要 `tqdm`、`matplotlib`（已装）。
- **不要引入新的重型依赖**（如 detectron2、mmcv、transformers）。当前所有模型都是纯 torch + timm 手写架构，装 mmcv 会破环境。
- 建议本地用 `requirements.txt` 锁定上述精确版本。

---

## 3. 目录结构与调用路径

**项目根目录（唯一工作目录）：`/root/autodl-tmp/sys_all/`**

`sys.py` 第 1211 行用 `_BASE_DIR = os.path.dirname(os.path.abspath(__file__))` 取自身目录，**所有权重和静态目录都是相对这个目录拼出来的**。这意味着：只要整个 `sys_all/` 文件夹结构不变，放在任何路径都能跑。

```
/root/autodl-tmp/sys_all/
├── sys.py                          # 主程序（56 KB / 1412 行）v5.0
├── trufor_infer.py                 # TruFor 推理封装（即插即用）
│
├── yolo11n.pt                      #   5.6 MB  YOLO11-nano 目标检测
├── SAE_best.pth                    # 237.5 MB  SAEv1  (EfficientNet-B4 + CBAM + 频域分支)
├── SAE_v2.pth                      #   1.2 MB  SAEv2  (MobileNet-like + SE)
├── mesorch-98.pth                  # 1023.9 MB Mesorch  (epoch 98, 8 专家 + DCT-MoE)
├── mesorch_p-118.pth               # 812.7 MB  MesorchP (epoch 118, 5 专家剪枝版)
│
├── TruFor/                         # TruFor 官方仓库（CVPR 2023）
│   └── TruFor_train_test/
│       ├── lib/                    # 模型代码，被 sys.path.insert 动态加载
│       │   ├── config/
│       │   │   ├── default.py
│       │   │   └── trufor_ph3.yaml # 推理配置（backbone=mit_b2, DETECTION=confpool）
│       │   ├── models/
│       │   └── utils.py            # get_model(cfg) 入口
│       ├── weights/trufor_ph3/
│       │   └── best.pth.tar        # 281.5 MB  TruFor 主权重
│       └── pretrained_models/
│           ├── noiseprint++/noiseprint++.th   #  2.3 MB
│           └── segformers/mit_b2.pth          # 98.9 MB
│
├── static/
│   ├── uploads/                    # 用户上传原图（Flask 直接对外可访问）
│   └── results/                    # 所有推理产物（当前已堆积 402 个文件）
│
├── evaluate.py                     # 评测脚本（与网页产品无关）
├── generate_roc_curves.py          # 出 ROC 曲线（与网页产品无关）
└── sys.py.backup / sys_backup_*.py # 旧版本备份，勿动
```

**权重合计约 2.29 GiB（2.46 GB）**，共 8 个文件（5 个主模型 + TruFor 主权重 + noiseprint++ + mit_b2）。

### 3.1 硬编码路径说明

`trufor_infer.py` 第 21-24 行的 TruFor 路径是相对 `trufor_infer.py` 自身目录计算的：

```python
TRUFOR_ROOT = os.path.join(os.path.dirname(__file__), 'TruFor', 'TruFor_train_test')
WEIGHTS_DIR = os.path.join(TRUFOR_ROOT, 'weights', 'trufor_ph3')
CONFIG_YAML = 'lib/config/trufor_ph3.yaml'
sys.path.insert(0, TRUFOR_ROOT)     # 动态加进 sys.path 才能 import lib.*
```

**重构时如果移动 `trufor_infer.py`，必须同步保证 `TruFor/` 在它旁边**，否则 `import lib.config.default` 会失败。

> 注：`trufor_infer.py` 的 docstring 里写的绝对路径 `/root/TruFor/...` 是过期注释，实际生效的是上面这段相对路径逻辑。

---

## 4. 模型加载细节（重构时必须逐条照抄）

所有模型在 **进程启动时（模块导入期）全部加载并常驻**，TruFor 例外（懒加载）。

### 4.1 六个模型的加载方式

| 模型 | 权重文件 | 加载代码要点 |
|------|---------|------------|
| **YOLO11n** | `yolo11n.pt` | `YOLO(path)`，ultralytics 自己管理 device |
| **SAEv1** | `SAE_best.pth` | `ForgeryNetV1(pretrained=False)`；`ckpt['model'] if 'model' in ckpt else ckpt` |
| **SAEv2** | `SAE_v2.pth` | `ForgeryNetV2()`；权重就是裸 `state_dict`，直接 load |
| **Mesorch** | `mesorch-98.pth` | `torch.load(..., weights_only=False)` → 取 `ckpt['model']`；**需 key remap，见 4.2** |
| **MesorchP** | `mesorch_p-118.pth` | 同上，`ckpt['model']` |
| **TruFor** | `best.pth.tar` | 懒加载，首次推理时才 `get_model(cfg)` + `ckpt['state_dict']` |

关键点：
- `ForgeryNetV1` 内部 `timm.create_model('efficientnet_b4', features_only=True, pretrained=pretrained)`。**生产环境必须传 `pretrained=False`**，否则 timm 会联网下载预训练权重（服务器可能无外网 / 下载失败）。sys.py 已正确传 False。
- `Mesorch` / `MesorchP` 内部 `timm.create_model('convnext_tiny', pretrained=False, in_chans=6)`，同样不联网。
- **结论：启动过程完全离线，不需要外网。**

### 4.2 Mesorch 的 key remap（易踩坑）

checkpoint 里 ConvNeXt 的 key 前缀是 `convnext.*`，但代码里包了一层 `_ConvNeXt._model`，所以 `Mesorch.load_state_dict` 重写了加载逻辑：

```python
def load_state_dict(self, state_dict, strict=True):
    new_sd = {}
    for k, v in state_dict.items():
        if k.startswith('convnext.') and not k.startswith('convnext._model.'):
            new_sd['convnext._model.' + k[len('convnext.'):]] = v
        else:
            new_sd[k] = v
    return super().load_state_dict(new_sd, strict=False)   # 注意 strict=False
```

**必须保留 `strict=False`**：checkpoint 里天然缺两个 key，属正常现象，不是权重损坏：
- `segformer.patch_embed1.proj.bias`
- `convnext._model.stem.0.bias`

### 4.3 显存 / 内存占用与已知缺陷

当前实现**完全没有内存调度策略**，这是重构时最值得改进的点：

- 全部 6 个模型 **FP32 常驻**，无 `autocast`、无 fp16、无量化。
- 无 `torch.cuda.empty_cache()`，无 offload，无并发锁 / 信号量。
- 权重本体约 2.3 GB，加上激活值，**GPU 建议 ≥ 8 GB 显存**（TruFor 按原图分辨率推理，大图激活值很大）。
- **TruFor 不 resize**：`trufor_infer.infer()` 把原图整张送进网络（仅 `/256.0` 归一化）。上传 4K 图会直接 OOM。**新版必须加最大边长限制**（建议长边 ≤ 1536 并记录缩放比）。
- **已知 bug：`sys.py` 第 1241-1246 行加载 `mesorch_p_model` 后漏调用 `.eval()`**，模型停留在 train 模式（其余 5 个模型都调了 eval）。重构时请补上 `mesorch_p_model.eval()`。
- Flask 的 `app.run()` 默认 `threaded=True`，多请求会并发进入同一批模型对象，**没有任何互斥**。新版应加请求队列或信号量（并发度 1-2）。

---

## 5. 推理管线（业务逻辑，必须完整保留）

### 5.1 预处理

```python
_norm_mean = [0.485, 0.456, 0.406]      # ImageNet
_norm_std  = [0.229, 0.224, 0.225]

transform_v1 = Resize((256,256)) → ToTensor → Normalize      # SAEv1
transform_v2 = Resize((256,256)) → ToTensor → Normalize      # SAEv2
transform_mesorch = Resize(512) → CenterCrop(512) → ToTensor → Normalize   # Mesorch 与 MesorchP 共用
TruFor:  不 resize，np.array(img).transpose(2,0,1) / 256.0
YOLO:    PIL → np.array → cv2.cvtColor(RGB2BGR)，交给 ultralytics 自己处理
```

**注意 Mesorch 是 `Resize(512)` 短边缩放 + 中心裁切**，所以非正方形图片的边缘区域根本没被 Mesorch 看到。这是既有行为，若要改成整图推理需要重新验证效果。

### 5.2 前向输出签名

```python
sae_v1(x)          → (score, mask, aux_mask)     # 三个返回值
sae_v2(x)          → (score, mask)
mesorch_model(x)   → (score, mask)               # 内部把 3ch cat 成 6ch
mesorch_p_model(x) → (score, mask)
trufor.infer(pil)  → (score, loc_map, conf_map)  # numpy, 原图尺寸
```

Mesorch 系列的 `score` 是 **mask 全图均值**（`mask.flatten(1).mean()`），不是分类头输出，数值天然偏低。这会让它们在 0.5 阈值下倾向判「真」，属既有设计。

### 5.3 判决逻辑（原样保留）

```
第 1 步  SAEv2 / SAEv1 / Mesorch / MesorchP 各出一个 prob
第 2 步  TruFor 出 prob（失败则整体降级，跳过，不报错）
第 3 步  SAEv2 置信度修正：
        若 (prob_v2 > 0.5) 与 (prob_trufor > 0.5) 结论相反
        则 prob_v2 = (prob_v2 + prob_trufor) / 2
第 4 步  多数投票：
        scores = [prob_v2, prob_v1, prob_meso, prob_meso_p]  (+ prob_trufor 若可用)
        votes_fake = count(s > 0.5)
        is_fake    = votes_fake > len(scores) / 2
```

TruFor 推理被 `try/except` 包住，失败只打日志、`prob_trufor = None`，投票退化为 4 模型。**这个降级路径要保留**。

### 5.4 热力图后处理

`_save_heatmap()` 对每个 mask 做：

```
resize 到原图尺寸 → 取 1%/99% 百分位裁剪（增强对比度）→ min-max 归一化到 [0,1]
→ cv2.applyColorMap(COLORMAP_JET) 存热力图
→ (m > 0.5) 二值化 ×255 存掩码
```

**TruFor 的热力图走单独分支**（不做百分位裁剪，直接 `applyColorMap`），行为与其他 4 个模型不一致。要不要统一由产品决定。

---

## 6. 当前对外接口（这是要被替换的部分）

### 6.1 路由

**只有一个路由：**

```python
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files.get('file')          # 表单字段名固定为 "file"
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        ctx = process_image(filepath, filename)
        return render_template_string(HTML_TEMPLATE, **ctx)
    return render_template_string(HTML_TEMPLATE)
```

- GET `/` → 返回上传页
- POST `/` → `multipart/form-data`，字段名 **`file`** → 返回整页结果 HTML
- 静态文件：`/static/results/<filename>`、`/static/uploads/<filename>`（Flask 默认 static 路由）
- **没有 JSON API，没有 `/api/*`，没有健康检查，没有 CORS 配置**

### 6.2 `process_image()` 返回的完整字段（照抄可直接做 JSON schema）

```python
{
  "yolo_res":      "yolo_<stem>.jpg",          # YOLO 检测框可视化
  "heat_v1":       "heat_v1_<stem>.jpg",       "mask_v1":       "mask_v1_<stem>.jpg",
  "heat_v2":       "heat_v2_<stem>.jpg",       "mask_v2":       "mask_v2_<stem>.jpg",
  "heat_meso":     "heat_meso_<stem>.jpg",     "mask_meso":     "mask_meso_<stem>.jpg",
  "heat_meso_p":   "heat_meso_p_<stem>.jpg",   "mask_meso_p":   "mask_meso_p_<stem>.jpg",
  "trufor_res":    "trufor_<stem>.jpg",        "trufor_mask":   "mask_trufor_<stem>.jpg",
  "verdict_text":  "⚠️ 检测到明显篡改迹象" | "✅ 图像未见明显伪造特征",
  "logic_info":    "高风险：4/5 个模型判定为篡改。",
  "conf_v2":       "87.35%",                   # 字符串，已格式化
  "conf_meso":     "12.04%",
  "conf_meso_p":   "9.88%",
  "conf_trufor":   "91.20%" | "—",             # 不可用时是全角破折号
  "is_fake_bool":  true
}
```

**文件命名规则：** `out_stem = 原文件名去扩展名 + '.jpg'`（`_stem_jpg()`，统一转 jpg 保证浏览器可显示）。二值掩码文件名由热力图名 `name.replace('heat_', 'mask_')` 得到。

**注意：`conf_v1` 没有返回**，SAEv1 的分数参与了投票但前端不展示。

### 6.3 前端现状

`HTML_TEMPLATE` 是 sys.py 里第 664-1204 行的一个巨大 Python 字符串（Jinja2 语法），包含：
- 顶部导航、上传区、加载遮罩、判决条幅、置信度徽章组、2 列结果卡片网格
- 标题写「图像智能取证系统 v5.0 · 三模型置信度版」（文案与实际 6 模型不符，可改）
- **外链两个 CDN**：`cdn.jsdelivr.net/npm/bootstrap@5.3.0` 和 `fonts.googleapis.com`

> **重要：新前端不要依赖 Google Fonts。** 服务器所在网络环境访问 `fonts.googleapis.com` 通常会超时，导致首屏字体阻塞。请把 CSS/字体本地化，放进 `static/`。

---

## 7. 端口与网络配置

| 项目 | 值 |
|------|-----|
| 监听地址 | `0.0.0.0`（全网卡） |
| 端口 | **6006** |
| 启动方式 | `app.run(host='0.0.0.0', port=6006)` — Werkzeug 开发服务器 |
| debug | 未开启（默认 False，正确） |
| threaded | Flask 默认 `True`（隐式） |
| 进程模型 | 单进程 |

**端口 6006 是这台服务器唯一对外映射的端口**，通过平台的 HTTP 隧道访问。开发新版时：

- **必须继续监听 6006**，换端口会导致外网访问不到。
- 如果前后端分离，**不要**让前端跑在 3000/5173 等另一个端口——只有一个端口能出网。正确做法：前端 `npm run build` 产出静态文件，由后端（6006）统一托管；或用 nginx 在 6006 上做路径分流。
- WebSocket 能否穿透平台隧道**未经验证**，建议长任务用轮询而非 WS。

### 7.1 生产化建议

`app.run()` 是开发服务器，不适合正式产品。建议：

```bash
# 单 worker（模型常驻，不能多 worker，否则显存 ×N）
gunicorn -w 1 -k gthread --threads 2 -b 0.0.0.0:6006 --timeout 300 app:app
```

- `-w 1` 是硬约束：每个 worker 都会完整加载 2.3 GB 权重。
- `--timeout 300`：CPU 环境单张图可能超过默认 30 秒超时。
- `gunicorn` **当前未安装**，需要 `pip install gunicorn`。

---

## 8. 安全与健壮性缺口（新版应补齐）

当前实现是实验原型，以下问题在做成产品前需要处理：

1. **无身份认证** — 服务对 `0.0.0.0` 全开，任何拿到 URL 的人都能上传图片并消耗 GPU。若要公开访问，至少加一层 token 或登录。
2. **无上传大小限制** — 没设 `MAX_CONTENT_LENGTH`，配合 TruFor 的原图推理，一张大图就能打爆显存。
3. **文件名碰撞** — 同名文件直接覆盖（`secure_filename` 只做消毒不做去重）。多用户会互相覆盖结果。**建议改用 UUID 或时间戳前缀。**
4. **上传目录 web 可读** — `static/uploads/` 下的原图任何人可直接 URL 访问，存在隐私泄露。
5. **无文件类型校验** — 只靠前端 `accept="image/*"`，后端未校验实际内容。应加 magic number 校验。
6. **结果文件无清理** — `static/results/` 已积累 402 个文件，系统盘只剩 16 GB。**需要定期清理或 TTL 机制。**
7. **无请求并发控制** — 见 §4.3。

### 8.1 许可证提醒

`ultralytics`（YOLO11）是 **AGPL-3.0** 许可。如果这个网页产品要商业化或闭源分发，AGPL 会要求你开源整个服务端代码。请评估：换成其他检测模型，或购买 Ultralytics 商业授权。TruFor 的许可条款也需自行确认（学术用途为主）。

---

## 9. 建议的重构方向

给出一个不破坏现有推理逻辑的分层方案：

```
sys_all/
├── app.py                  # Flask 入口，只放路由和应用装配
├── api/
│   ├── routes.py           # POST /api/v1/detect、GET /api/v1/health
│   └── schema.py           # 请求/响应校验
├── core/
│   ├── models/
│   │   ├── sae_v1.py       # 从 sys.py 第 26-213 行原样搬出
│   │   ├── sae_v2.py       # 第 215-294 行
│   │   └── mesorch.py      # 第 296-657 行（含 MesorchP）
│   ├── registry.py         # 模型单例加载 + device 管理 + eval()
│   ├── pipeline.py         # process_image() 的逻辑，改为返回纯 dict
│   └── postprocess.py      # _save_heatmap()、_stem_jpg()
├── trufor_infer.py         # 不动
├── TruFor/                 # 不动
├── web/                    # 新前端（构建产物进 static/）
├── static/{uploads,results}
└── *.pth / *.pt            # 权重不动，路径不变
```

建议的 API 契约：

```
GET  /api/v1/health
     → 200 {"status":"ok","device":"cuda","models":{"sae_v1":true,...,"trufor":"lazy"}}

POST /api/v1/detect        multipart/form-data, field="file"
     → 200 {
         "task_id": "uuid",
         "verdict": {"is_fake": true, "text": "...", "votes": "4/5"},
         "scores": {"sae_v1":0.87,"sae_v2":0.91,"mesorch":0.12,"mesorch_p":0.09,"trufor":0.88},
         "artifacts": {
           "yolo":       "/static/results/<uuid>/yolo.jpg",
           "sae_v1":     {"heat":"...","mask":"..."},
           "sae_v2":     {"heat":"...","mask":"..."},
           "mesorch":    {"heat":"...","mask":"..."},
           "mesorch_p":  {"heat":"...","mask":"..."},
           "trufor":     {"heat":"...","mask":"..."}   // 可能为 null
         },
         "elapsed_ms": 3820
       }
```

**注意 scores 返回 float 而非格式化字符串**，格式化交给前端。当前 `conf_*` 是字符串，属于把展示逻辑混进了后端。

---

## 10. 本地开发注意事项（无 GPU / 无权重环境）

本地个人电脑大概率没有这 2.3 GB 权重，也可能没有 GPU。为了让代码「本地能写、上传就能跑」：

1. **权重路径全部走配置**，不要硬编码。用环境变量或 `config.py`，默认值指向 `_BASE_DIR`。
2. **加 mock 模式**：`DETECT_MOCK=1` 时跳过真实模型加载，`pipeline` 返回假数据。这样本地可以完整开发调试前端。
3. **模型加载做成惰性 + 容错**：权重不存在时打警告并标记该模型不可用，而不是崩溃（现有代码用 `if os.path.exists()` 已部分实现这点，请保持）。
4. **device 由环境决定**：`os.getenv('DEVICE') or ('cuda' if torch.cuda.is_available() else 'cpu')`。
5. **不要在本地跑 `pip freeze > requirements.txt`**，会把本地 CPU 版 torch 写进去。手写 requirements，torch 那行注明服务器已装 `2.7.0+cu128`，部署时用 `--no-deps` 或直接跳过 torch。

上传后的启动检查清单：

```bash
cd /root/autodl-tmp/sys_all
python3 -c "import torch;print(torch.cuda.is_available())"    # 确认 GPU
ls -la *.pth *.pt                                             # 确认 5 个权重在位
ls -la TruFor/TruFor_train_test/weights/trufor_ph3/           # 确认 TruFor 权重
python3 app.py                                                # 启动，观察加载日志
curl -s localhost:6006/api/v1/health                          # 健康检查
```

预期启动日志（现有版本）：

```
[Mesorch] 权重加载成功 (epoch 98)
[MesorchP] 权重加载成功 (epoch 118)
 * Running on http://0.0.0.0:6006
[TruFor] 权重已加载 (epoch=?)      ← 首次推理时才出现
```

---

## 11. 不可变更清单（触碰会导致上传后跑不起来）

- 监听端口 **6006**，地址 `0.0.0.0`
- 5 个权重文件名与所在目录（`sys_all/` 根下）
- `TruFor/TruFor_train_test/` 整个目录结构，及 `trufor_infer.py` 与它的相对位置
- Mesorch/MesorchP 的 `convnext.*` → `convnext._model.*` key remap 与 `strict=False`
- 各模型的输入尺寸与归一化参数（256/256/512，ImageNet mean-std）
- `timm.create_model(..., pretrained=False)` — 改成 True 会触发联网下载
- torch 2.7.0+cu128 / numpy 2.2.6 这套版本组合
