import React, { useEffect, useRef, useState } from 'react';
import { api, modelNames, statuses, uploadImage } from '../api.js';
import Icon from './Icon.jsx';
import Surface from './Surface.jsx';

function Result({ task }) {
  const [model, setModel] = useState('sae_v2');
  const [view, setView] = useState('heatmap');
  const [opacity, setOpacity] = useState(.55);
  const result = task.result;
  const artifact = result.artifacts.find(a => a.model === model && a.kind === view);
  const score = result.scores[model];
  return <div className="result-layout">
    <div className="visualization">
      <div className="tab-strip" role="tablist" aria-label="图像视图">
        {[['original', '原始图像'], ['heatmap', '关注区域'], ['mask', '二值掩码']].map(([key, label]) => <button key={key} role="tab" aria-selected={view === key} className={view === key ? 'selected' : ''} onClick={() => setView(key)}>{label}</button>)}
      </div>
      <div className="image-stage">
        <img src={task.original_url} alt="上传的原始图像" />
        {view !== 'original' && artifact && <img className="overlay-image" src={artifact.url} alt={`${modelNames[model]} ${view === 'heatmap' ? '热力图' : '二值掩码'}`} style={{ opacity: view === 'mask' ? 1 : opacity }} />}
        {view !== 'original' && !artifact && <div className="image-unavailable">此模型暂未返回{view === 'heatmap' ? '热力图' : '掩码'}</div>}
      </div>
      {view === 'heatmap' && artifact && <label className="opacity-control"><span>热力图叠加</span><input type="range" min="0" max="1" step=".01" value={opacity} onChange={e => setOpacity(Number(e.target.value))} /><span>{Math.round(opacity * 100)}%</span></label>}
      <p className="caption">{task.image_width} × {task.image_height} · {task.filename}</p>
    </div>
    <div className="result-information">
      <p className="section-label">鉴别结果</p>
      <h3 className="verdict">{result.is_fake ? '发现了异常的痕迹。' : '暂未发现明显异常。'}</h3>
      {result.votes && <p className="muted">{result.votes.fake} / {result.votes.total} 个模型认为存在伪造特征</p>}
      <div className="confidence"><span className="confidence-value">{score == null ? '—' : (score * 100).toFixed(1)}{score != null && <small>%</small>}</span><span>{modelNames[model]} 伪造分数</span></div>
      <div className="model-list" aria-label="选择模型">
        {Object.entries(modelNames).map(([key, name]) => <button key={key} onClick={() => setModel(key)} aria-pressed={key === model} className={key === model ? 'model-selected' : ''}><span>{name}</span><span>{result.scores[key] == null ? '未返回' : `${(result.scores[key] * 100).toFixed(2)}%`}</span></button>)}
      </div>
      {result.degraded && <p className="notice">TruFor 暂未参与本次判定。</p>}
      <p className="caption">模型分数并非经过校准的事实概率。关注区域展示模型响应，不等同于已经证实的篡改区域。</p>
      {model.startsWith('mesorch') && <p className="caption">Mesorch 系列仅分析中心裁切区域；关注图被映射回整图显示，不能代表边缘也经过检测。</p>}
      <p className="caption">推理耗时 {(result.elapsed_ms / 1000).toFixed(1)} 秒</p>
    </div>
  </div>;
}

export default function Detection({ onClose, initialTask, health }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [task, setTask] = useState(null);
  const [taskId, setTaskId] = useState(initialTask || null);
  const [error, setError] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadPercent, setUploadPercent] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [retry, setRetry] = useState(0);
  const input = useRef(null), controller = useRef(null);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    if (!file) { setPreview(null); return; }
    const url = URL.createObjectURL(file); setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  useEffect(() => {
    if (!taskId) return;
    const abort = new AbortController(); let timer;
    async function poll() {
      try {
        const row = await api(`/tasks/${taskId}`, { signal: abort.signal }); setTask(row); setError('');
        if (row.status === 'queued' || row.status === 'running') timer = setTimeout(poll, 1800);
      } catch (e) { if (e.name !== 'AbortError') setError(e.message); }
    }
    poll(); return () => { abort.abort(); clearTimeout(timer); };
  }, [taskId, retry]);
  function selectFile(next) {
    setError(''); if (!next) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(next.type)) { setError('请选择 JPG、PNG 或 WebP 图片。'); return; }
    if (next.size > (health?.max_upload_bytes || 10 * 1024 * 1024)) { setError('图片不能超过 10 MB。'); return; }
    setFile(next); setTask(null); setTaskId(null);
  }
  async function submit() {
    setError(''); setUploading(true); controller.current = new AbortController();
    try {
      const created = await uploadImage(file, setUploadPercent, controller.current.signal);
      setTaskId(created.task_id);
    } catch (e) { if (e.name !== 'AbortError') setError(e.message); }
    finally { setUploading(false); }
  }
  const busy = uploading || (taskId && !task) || ['queued', 'running'].includes(task?.status);
  return <Surface title={task?.status === 'completed' ? '看见图像的另一面' : '让光，穿透表象。'} onClose={onClose} className={task?.status === 'completed' ? 'result-surface' : 'upload-surface'}>
    {task?.status === 'completed' ? <><Result task={task} /><footer className="surface-footer"><button className="text-button" onClick={() => { setTask(null); setTaskId(null); setFile(null); }}>鉴别另一张图片 <Icon name="arrow" size={16} /></button></footer></> : <>
      {busy ? <div className="processing" role="status"><div className="processing-orb" /><h3>{uploading ? '图像正在抵达…' : task?.status === 'queued' ? '正在等待光的回应…' : '正在寻找图像中的线索…'}</h3><p>{uploading ? `已上传 ${uploadPercent}%` : '你可以关闭窗口，稍后在历史中查看。'}</p><span className="caption">{task && statuses[task.status]}{!uploading && ' · 模型运行可能需要数分钟'}</span></div> : task?.status === 'failed' ? <div className="empty-state"><Icon name="image" size={36} /><h3>这一次，尚未看清。</h3><p>{task.error_message}</p><button className="outline-button" onClick={() => { setTask(null); setTaskId(null); }}>重新选择图片</button></div> : <>
        <p className="surface-description">放入一张图像，探索那些不易察觉的痕迹。</p>
        <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" aria-label="上传图片" onChange={e => { selectFile(e.target.files[0]); e.target.value = ''; }} />
        <button className={`dropzone ${dragging ? 'dragging' : ''} ${preview ? 'has-preview' : ''}`} onClick={() => input.current.click()} onDragOver={e => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={e => { e.preventDefault(); setDragging(false); selectFile(e.dataTransfer.files[0]); }} aria-label="选择或拖入图片">
          {preview ? <><img src={preview} alt="待鉴别图片预览" /><span className="replace-image">点击更换图片</span></> : <><div className="upload-symbol"><Icon name="upload" size={28} /></div><span className="dropzone-title">放入一张图像</span><span>拖拽到这里，或轻触选择</span><small>JPG / PNG / WebP · 最大 10 MB</small></>}
        </button>
        {file && <p className="filename">{file.name} <span>{(file.size / 1024 / 1024).toFixed(2)} MB</span></p>}
        {health && !health.inference.available && <p className="notice">模型尚未连接。可以预览图片，完成服务器配置后即可鉴别。</p>}
        <footer className="surface-footer"><span className="caption">鉴别记录保存 {health?.retention_days || 30} 天，可随时删除。</span><button className="outline-button" disabled={!file || health?.inference.available === false} onClick={submit}>开始鉴别 <Icon name="arrow" size={16} /></button></footer>
      </>}
    </>}
    {error && <div className="error-message" role="alert">{error}{taskId && <button className="text-button" onClick={() => setRetry(x => x + 1)}>重试连接</button>}</div>}
  </Surface>;
}
