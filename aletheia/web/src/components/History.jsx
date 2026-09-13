import React, { useEffect, useState } from 'react';
import { api, formatDate, statuses } from '../api.js';
import Icon from './Icon.jsx';
import Surface from './Surface.jsx';

export default function History({ onClose, onTask, onConversation }) {
  const [tab, setTab] = useState('tasks');
  const [items, setItems] = useState([]);
  const [next, setNext] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [confirm, setConfirm] = useState(null);
  const [removing, setRemoving] = useState(false);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const abort = new AbortController(); setLoading(true); setItems([]); setError(''); setConfirm(null);
    api(`/${tab}`, { signal: abort.signal }).then(data => { setItems(data.items); setNext(data.next_offset); }).catch(e => { if (e.name !== 'AbortError') setError(e.message); }).finally(() => { if (!abort.signal.aborted) setLoading(false); });
    return () => abort.abort();
  }, [tab, refresh]);
  async function loadMore() {
    setLoading(true);
    try { const data = await api(`/${tab}?offset=${next}`); setItems(prev => [...prev, ...data.items]); setNext(data.next_offset); }
    catch (e) { setError(e.message); } finally { setLoading(false); }
  }
  async function remove(id) {
    setRemoving(true);
    try { await api(`/${tab}/${id}`, { method: 'DELETE' }); setItems(items => items.filter(item => item.id !== id)); setConfirm(null); }
    catch (e) { setError(e.message); } finally { setRemoving(false); }
  }
  return <Surface title="来过的痕迹" onClose={onClose} fullScreen className="history-page">
    <div className="tab-strip history-tabs" role="tablist" aria-label="历史类型">{[['tasks', '图像鉴别'], ['conversations', '历史对话']].map(([key, label]) => <button role="tab" aria-selected={tab === key} className={tab === key ? 'selected' : ''} key={key} onClick={() => setTab(key)}>{label}</button>)}</div>
    <div className="history-body">
      {!loading && !items.length && !error ? <div className="empty-state"><Icon name={tab === 'tasks' ? 'image' : 'chat'} size={32} /><h3>这里还没有留下痕迹。</h3><p>{tab === 'tasks' ? '每一次鉴别，都会在这里被记住。' : '与光说过的话，将在这里延续。'}</p></div> : null}
      {items.map(item => <div className="history-row" key={item.id}><button className="history-open" onClick={() => tab === 'tasks' ? onTask(item.id) : onConversation(item.id)}><Icon name={tab === 'tasks' ? 'image' : 'chat'} /><span><strong>{tab === 'tasks' ? item.filename : item.title}</strong><small>{formatDate(item.created_at)}{tab === 'tasks' && ` · ${statuses[item.status]}`}</small></span></button>{confirm === item.id ? <div className="delete-confirm"><span>永久删除？</span><button disabled={removing} onClick={() => remove(item.id)}>删除</button><button disabled={removing} onClick={() => setConfirm(null)}>取消</button></div> : <button className="icon-button delete-button" aria-label={`删除${tab === 'tasks' ? item.filename : item.title}`} disabled={['queued', 'running'].includes(item.status)} onClick={() => setConfirm(item.id)}><Icon name="trash" size={16} /></button>}</div>)}
      {loading && <p className="muted loading-text" role="status">正在拾起记忆…</p>}
      {next != null && !loading && <button className="outline-button load-more" onClick={loadMore}>更早的记录</button>}
      {error && <p className="error-message" role="alert">{error}<button className="text-button" onClick={() => setRefresh(value => value + 1)}>重试</button></p>}
    </div>
    <p className="history-note">记录属于当前浏览器会话。清除 Cookie 后无法找回；图片记录到期自动清理。</p>
  </Surface>;
}
