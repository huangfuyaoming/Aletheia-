import React, { useEffect, useRef, useState } from 'react';
import { api } from '../api.js';
import Surface from './Surface.jsx';
import Icon from './Icon.jsx';

export default function Chat({ onClose, initialConversation }) {
  const [cid, setCid] = useState(initialConversation || null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [error, setError] = useState('');
  const [sending, setSending] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const end = useRef(null);
  useEffect(() => {
    if (!cid) return;
    let timer; const controller = new AbortController();
    async function poll() {
      try {
        const result = await api(`/conversations/${cid}`, { signal: controller.signal });
        setMessages(result.messages);
        if (result.messages.some(m => ['pending', 'running'].includes(m.status))) timer = setTimeout(poll, 1300);
      } catch (e) { if (e.name !== 'AbortError') setError(e.message); }
    }
    poll(); return () => { clearTimeout(timer); controller.abort(); };
  }, [cid, refresh]);
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'instant', block: 'nearest' }); }, [messages.length, messages.at(-1)?.status]);
  const busy = sending || messages.some(m => ['pending', 'running'].includes(m.status));
  async function send(event) {
    event.preventDefault(); if (!input.trim() || busy) return;
    setSending(true); setError('');
    try {
      let id = cid;
      if (!id) { id = (await api('/conversations', { method: 'POST', json: {} })).id; setCid(id); }
      await api(`/conversations/${id}/messages`, { method: 'POST', json: { content: input } });
      setInput(''); setRefresh(value => value + 1);
    } catch (e) { setError(e.message); }
    finally { setSending(false); }
  }
  return <Surface title="与光对话" onClose={onClose} fullScreen hideTitle className="chat-page">
    <div className="message-list">
      {!messages.length && <div className="chat-intro"><div className="little-light" /><h3>你眼中的真实，<br />是什么模样？</h3><p>关于图像、感知，或一个尚未解答的问题。</p></div>}
      {messages.map(message => <article key={message.id} className={`message ${message.role}`}><span className="message-author">{message.role === 'user' ? '你' : '观真'}</span><p>{['pending', 'running'].includes(message.status) ? <span className="thinking">光正在回应…</span> : message.content}</p>{message.status === 'failed' && <span className="caption">{message.error_code === 'LLM_NOT_CONFIGURED' ? '等待配置对话服务' : '回应未完成'}</span>}</article>)}
      <div ref={end} />
    </div>
    {error && <p className="error-message" role="alert">{error}<button className="text-button" onClick={() => { setError(''); setRefresh(x => x + 1); }}>重新连接</button></p>}
    <form className="chat-composer" onSubmit={send}><textarea value={input} onChange={e => setInput(e.target.value)} aria-label="对话消息" placeholder="向光提出一个问题…" maxLength={4000} rows={2} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(e); } }} /><button className="send-button" disabled={!input.trim() || busy} aria-label="发送消息"><Icon name="arrow" /></button></form>
    <p className="composer-note">Enter 发送 · Shift + Enter 换行</p>
  </Surface>;
}
