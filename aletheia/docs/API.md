# 观真 API 契约

版本：`/api/v1`。此文档与交付代码对应；实际接口已实现，不是未落地的路由草案。

## 1. 通用规则

- 前端与 Flask 同源，由 6006 端口提供；生产不需要 CORS，也不使用 WebSocket。
- 所有 JSON 字段使用 snake_case；时间为带 UTC 偏移的 ISO 8601；ID 是随机 UUID。
- 图片上传用 multipart/form-data，字段固定 `file`；其它写操作使用 JSON。
- 服务端以签名、HttpOnly、SameSite=Lax Cookie 识别浏览器会话；不把大模型密钥放入 localStorage。
- 先 `GET /session` 获取 `csrf_token`；后续 POST/DELETE 必须携带 `X-CSRF-Token`，建立会话的 POST 除外。每个写请求验证 Origin。
- 所有任务、会话、图片访问都校验 owner_id。访问其它会话的资源一律 404，不暴露其存在性。
- **没有访问密钥门禁**（已按要求移除）：打开页面即获得访客会话，每个访客只能看到自己的任务与对话。CSRF 与 Origin 校验仍然生效。
- 列表 `limit` 默认 20、上限 50；`offset` 默认 0；响应包含 `next_offset`，null 表示结束。新增记录可能导致分页边界移动，刷新重读即可。
- 不将运行耗时猜测成进度百分比。前端只显示实际上传进度，以及 queued/running/completed/failed 状态。

统一错误格式：

```json
{"error":{"code":"MODEL_UNAVAILABLE","message":"尚未连接服务器模型。图片不会上传，请完成服务器配置后再试。"}}
```

代码 | HTTP | 含义
--- | --- | ---
UNAUTHENTICATED | 401 | 未建立 Cookie 会话
CSRF_REJECTED / ORIGIN_REJECTED | 403 | CSRF 或来源不匹配
NOT_FOUND | 404 | 资源不存在、不属于本会话或已被清理
FILE_REQUIRED / INVALID_MESSAGE | 400 | 输入缺失或消息长度不合法
FILE_TOO_LARGE / IMAGE_TOO_LARGE | 413 | 文件超过配置限制 / 解码像素数过大
INVALID_IMAGE / UNSUPPORTED_IMAGE | 415 | 文件内容不合法或类型不支持
QUEUE_FULL / CHAT_BUSY | 429 | 队列容量已满
TASK_BUSY / CONVERSATION_BUSY | 409 | 正在运行，不允许删除或重复发起同会话回复
CONVERSATION_FULL | 409 | 单个会话达到 400 条消息，应新建
MODEL_UNAVAILABLE | 503 | 未找到配置的服务器入口

## 2. 健康与会话

### GET /health

```json
{
  "status":"ok",
  "inference":{"available":false,"state":"not_configured","device":"not_loaded","mode":"legacy","message":"尚未连接服务器模型"},
  "chat":{"available":false},
  "retention_days":30,
  "max_upload_bytes":10485760
}
```

`available=true` 仅表示检测到入口文件；真实模型在首个任务中惰性加载，加载失败将该任务置 failed。不是权重已经通过验证的声明。state 包括 not_configured、not_loaded、loading、ready、error。

### GET /session

自动建立会话、写入 visitors 表并设置 Cookie。返回：

```json
{"visitor_id":"uuid","csrf_token":"random-token","authenticated":true}
```

### POST /session

与 GET 等价，返回同上。访问密钥门禁已移除，因此该请求不需要请求体，也不存在需要校验的密钥。Cookie 保留原 visitor_id，不会合并其它设备的历史。

## 3. 图像鉴别

### POST /detect

`multipart/form-data`：`file`，只接受静态 JPEG、PNG、WebP。服务端检查实际解码格式，不信任扩展名/MIME；最多 10 MiB，默认最多 1600 万像素。拒绝多帧图。

规范化：EXIF 方向校正、RGB 转换、去除元数据，以无损 PNG 保存。不会把输入图像整体缩小；各模型仍执行原有预处理。仅 TruFor 分支限制最长边 1536，随后将响应图恢复到输入尺寸。

返回 HTTP 202：

```json
{"task_id":"uuid","status":"queued","poll_url":"/api/v1/tasks/uuid"}
```

上传不支持幂等键或断点续传。网络在返回 202 前中断时，先查看历史以免重复提交；相同内容再次上传会形成独立记录和文件目录，不会覆盖。

### GET /tasks/{task_id}

前端每 1.8 秒轮询；关闭面板只停止轮询，不取消服务器任务。重新从历史打开可继续查询。出错后显示重试连接按钮，不无限静默重试。

```json
{
  "id":"uuid",
  "filename":"photo.png",
  "status":"completed",
  "image_width":1024,
  "image_height":768,
  "created_at":"2026-09-11T08:00:00+00:00",
  "started_at":"2026-09-11T08:00:01+00:00",
  "finished_at":"2026-09-11T08:00:06+00:00",
  "expires_at":"2026-10-11T08:00:00+00:00",
  "error_code":null,
  "error_message":null,
  "original_url":"/api/v1/artifacts/original-uuid",
  "result":{
    "is_fake":true,
    "scores":{"sae_v1":null,"sae_v2":0.87,"mesorch":0.12,"mesorch_p":0.1,"trufor":0.91},
    "votes":{"fake":3,"total":5},
    "elapsed_ms":5000,
    "degraded":false,
    "score_semantics":"fake_probability",
    "calibrated":false,
    "pipeline_version":"legacy-v5.0-adapter-1",
    "limitations":["mesorch_center_crop","uncalibrated_scores","sae_v1_score_missing"],
    "artifacts":[{"id":"artifact-uuid","model":"sae_v2","kind":"heatmap","url":"/api/v1/artifacts/artifact-uuid"}]
  }
}
```

以上数值仅为 API 格式示例，不是实验指标。

- result 在 queued/running/failed 时为 null。
- scores 是各模型的伪造倾向分数；默认 SAEv2 分数已经经过原管线与 TruFor 的冲突修正。
- 概率值不会伪装成校准的真实性概率。没有人工构造的「综合置信度」。主判决沿用原 majority vote。
- 原 process_image 缺 conf_v1 时返回 null，页面显示「未返回」。建议服务器返回原始 float scores，具体位置见 CLAUDE_DEPLOY.md。
- votes 从现有 logic_info 中读取；若无法读取为 null，不猜测缺失的 SAEv1 投票。
- YOLO 只负责目标框，不参与真伪多数投票。API 保存 yolo 产物，当前 UI 主要展示 5 个鉴别模型的热力图/掩码。
- TruFor 失败时保留 4 模型降级结果，degraded=true。核心推理/热力图产物缺失时任务 failed。
- 任务失败 code：INFERENCE_FAILED；服务器重启中断：SERVER_RESTARTED。详细异常只记录到服务器日志。

### GET /tasks?limit=20&offset=0

返回 `{"items":[...任务对象],"next_offset":null}`。列表不含 original_url，需要详情接口获得；每条可包含已完成 result。

### DELETE /tasks/{task_id}

删除任务数据库记录及它专属的原图、热力图和掩码文件。成功 204；运行中的任务 409。只删除当前产品的 UUID 目录，绝不清理原服务器 static/results 或权重。

### GET /artifacts/{artifact_id}

按 Cookie 鉴权流式发送图片；仅返回允许的图片 MIME。响应 Cache-Control:no-store 与 nosniff。数据库路径必须位于 DATA_DIR 内，不能请求任意文件路径。不存在匿名 `/static/uploads` 或 `/static/results` 映射。

## 4. 对话与历史

### POST /conversations

空 JSON `{}`；返回 201 `{"id":"uuid","title":"新的对话"}`。

### GET /conversations

返回 `{"items":[{"id":"uuid","title":"问题摘要","created_at":"ISO-8601","updated_at":"ISO-8601"}],"next_offset":null}`。

### GET /conversations/{conversation_id}

```json
{
  "id":"uuid",
  "title":"一张照片能证明真实吗？",
  "messages":[
    {"id":"uuid-1","role":"user","content":"一张照片能证明真实吗？","status":"completed","model":null,"error_code":null,"created_at":"ISO-8601","sequence":1},
    {"id":"uuid-2","role":"assistant","content":"","status":"pending","model":"server-configured-model","error_code":null,"created_at":"ISO-8601","sequence":2}
  ]
}
```

按 sequence 递增，不依赖时间戳或 UUID 排序。每个用户消息和占位回复在同一事务中插入。

### POST /conversations/{conversation_id}/messages

`{"content":"用户输入"}`；1–4000 字。返回 202 `{"message_id":"uuid","status":"pending"}`，前端每 1.3 秒轮询会话详情；回复完成后停止。单会话禁止重叠生成。

没有配置 LLM 时依旧保存用户消息和明确标注 failed/LLM_NOT_CONFIGURED 的系统说明，返回 202/status=failed。该说明不是伪造的大模型输出。配置后可在原会话继续发送消息。

LLM_FAILED 表示网络/提供商/响应异常；用户消息保留。历史上下文只取最近 40 条 completed 消息，另加服务端固定系统指令。每个会话最多 400 条消息。输入不作为系统消息发送。

### DELETE /conversations/{conversation_id}

成功 204，级联删除全部消息；有运行中回复时 409。

## 5. 大模型接口配置

服务器端通过 urllib 调用 Chat Completions 兼容 HTTP 服务：

```json
{"model":"配置值","messages":[{"role":"system","content":"固定系统指令"},{"role":"user","content":"用户问题"}],"stream":false,"max_tokens":1200}
```

期望响应 `choices[0].message.content` 为非空字符串。LLM_URL 是完整地址，如服务商提供的 `https://.../v1/chat/completions`，不是只填主机。LLM_API_KEY（可选，取决于本地模型网关）在服务端 Authorization:Bearer 中发送。LLM_MODEL 必填。默认超时 90 秒。

不绑定某一家供应商。若选择原生 Claude Messages、Gemini 等不兼容服务，应在 `server/jobs.py::ChatJobs.run` 增加对应供应商适配器，不能只改 URL 假定格式兼容。密钥不得写入前端或仓库。

当前聊天仅为文本，不自动上传图像给第三方 LLM，也不把模型检测分数自动加入聊天上下文。此边界可由服务器开发者后续显式扩展。
