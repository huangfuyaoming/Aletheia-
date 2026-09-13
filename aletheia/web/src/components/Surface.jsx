import React, { useEffect, useRef } from 'react';
import { ReturnStar } from './StarTransition.jsx';

export default function Surface({ title, children, onClose, drawer = false, fullScreen = false, hideTitle = false, className = '' }) {
  const ref = useRef(null);
  useEffect(() => {
    const previous = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const el = ref.current;
    el.focus();
    const key = event => {
      if (event.key === 'Escape') onClose();
      if (event.key === 'Tab') {
        const items = [...el.querySelectorAll('button:not(:disabled), input:not(:disabled), textarea:not(:disabled), select, a[href], [tabindex="0"]')].filter(item => item.offsetParent !== null);
        const first = items[0], last = items[items.length - 1];
        if (!first) { event.preventDefault(); return; }
        if (event.shiftKey && (document.activeElement === first || document.activeElement === el || !el.contains(document.activeElement))) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && (document.activeElement === last || document.activeElement === el || !el.contains(document.activeElement))) { event.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener('keydown', key);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', key);
      queueMicrotask(() => { if (previous?.isConnected && !previous.closest('[inert]')) previous.focus(); });
    };
  }, [onClose]);
  return <div ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-label={title} className={`surface-backdrop ${drawer ? 'drawer-backdrop' : ''} ${fullScreen ? 'fullscreen-backdrop' : ''}`} onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
    <ReturnStar onClick={onClose} />
    <section className={`surface ${drawer ? 'drawer' : ''} ${fullScreen ? 'surface-fullscreen' : ''} ${className}`}>
      {!hideTitle && <header className="surface-header"><h2>{title}</h2></header>}
      {children}
    </section>
  </div>;
}
