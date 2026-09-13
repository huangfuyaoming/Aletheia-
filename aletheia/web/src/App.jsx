import React, { useCallback, useEffect, useRef, useState } from 'react';
import { api, initSession } from './api.js';
import { LightOrb, Starfield } from './components/Cosmos.jsx';
import Detection from './components/Detection.jsx';
import Chat from './components/Chat.jsx';
import History from './components/History.jsx';
import StarNavigation from './components/StarNavigation.jsx';

export default function App() {
  const [stage, setStage] = useState(0);
  const [panel, setPanel] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [hovered, setHovered] = useState(false);
  const [health, setHealth] = useState(null);
  const [connectionError, setConnectionError] = useState(false);
  const [reduced, setReduced] = useState(() => matchMedia('(prefers-reduced-motion: reduce)').matches);
  const entry = useRef(null);
  const close = useCallback(() => {
    setPanel(null);
    queueMicrotask(() => { if (entry.current?.isConnected) entry.current.focus(); });
  }, []);
  useEffect(() => {
    let alive = true;
    Promise.all([api('/health'), initSession()]).then(([status]) => { if (alive) setHealth(status); }).catch(() => { if (alive) setConnectionError(true); });
    return () => { alive = false; };
  }, []);
  useEffect(() => {
    const query = matchMedia('(prefers-reduced-motion: reduce)');
    const update = event => setReduced(event.matches);
    query.addEventListener('change', update); return () => query.removeEventListener('change', update);
  }, []);
  function open(name, id = null) {
    if (!panel) entry.current = document.activeElement;
    setSelectedId(id); setPanel(name);
  }
  return <div className={`universe ${panel ? 'panel-open' : ''} ${reduced ? 'reduced-motion' : ''}`}>
    <Starfield reduced={reduced} />
    <div className="universe-vignette" aria-hidden="true" />
    <div className="world-content" inert={panel ? true : undefined}>
      <StarNavigation onChat={() => open('chat')} onHistory={() => open('history')} />
      <main className={`encounter stage-${stage}`}>
        <button className="orb-button" aria-label={stage === 0 ? '轻触光芒，开始探索' : '与光对话'} onClick={() => stage === 0 ? setStage(1) : open('chat')} onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}><LightOrb reduced={reduced} paused={Boolean(panel)} active={hovered || stage > 0} /></button>
        <div className="encounter-dialogue" aria-live="polite"><h1 key={stage}>{stage === 0 ? '你觉得这个世界是真实的吗？' : '请选择你想感受的真相'}</h1></div>
        {stage === 1 && <button className="truth-choice" onClick={() => open('detect')} aria-label="图像鉴别，上传图片"><span className="little-light" /><span>图像鉴别</span><small>触碰微光，探寻真实</small></button>}
      </main>
      {connectionError && <div className="connection-note" role="status">服务暂未连接。请启动后端后刷新页面。</div>}
    </div>
    {panel === 'detect' && <Detection onClose={close} initialTask={selectedId} health={health} />}
    {panel === 'chat' && <Chat onClose={close} initialConversation={selectedId} health={health} />}
    {panel === 'history' && <History onClose={close} onTask={id => open('detect', id)} onConversation={id => open('chat', id)} />}
  </div>;
}
