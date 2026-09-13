import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';

const TransitionContext = createContext((event, action) => action());
const FLIGHT_MS = 720;

export function StarTransitionProvider({ children }) {
  const [flight, setFlight] = useState(null);
  const timer = useRef(null);
  const sequence = useRef(0);
  const finish = useCallback(() => {
    clearTimeout(timer.current);
    setFlight(null);
  }, []);

  useEffect(() => {
    const preference = matchMedia('(prefers-reduced-motion: reduce)');
    const motion = event => { if (event.matches) finish(); };
    const visibility = () => { if (document.hidden) finish(); };
    preference.addEventListener('change', motion);
    document.addEventListener('visibilitychange', visibility);
    return () => {
      clearTimeout(timer.current);
      preference.removeEventListener('change', motion);
      document.removeEventListener('visibilitychange', visibility);
    };
  }, [finish]);

  const travel = useCallback((event, action) => {
    clearTimeout(timer.current);
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setFlight(null);
    } else {
      const source = event.currentTarget;
      const rect = (source.querySelector('.star-heart') || source).getBoundingClientRect();
      const x = rect.x + rect.width / 2, y = rect.y + rect.height / 2;
      setFlight({ id: ++sequence.current, x, y, dx: innerWidth / 2 - x, dy: innerHeight * .43 - y });
      timer.current = setTimeout(() => setFlight(null), FLIGHT_MS);
    }
    // Navigation happens immediately. Animation never gates an action or replays it later.
    action();
  }, []);

  return <TransitionContext.Provider value={travel}>
    {children}
    {flight && <div className="star-transit" key={flight.id} aria-hidden="true" style={{
      '--from-x': `${flight.x}px`, '--from-y': `${flight.y}px`,
      '--flight-x': `${flight.dx}px`, '--flight-y': `${flight.dy}px`,
    }}>
      <span className="transit-origin" />
      <span className="transit-traveler"><span className="transit-swirl"><i /><i /><i /></span><span className="transit-core" /></span>
      <span className="transit-echo echo-one" /><span className="transit-echo echo-two" />
    </div>}
  </TransitionContext.Provider>;
}

export default function StarButton({ onClick, label, name, className = '', returning = false, orbit = false }) {
  const travel = useContext(TransitionContext);
  return <button type="button" className={`stellar-button ${returning ? 'return-star' : 'navigation-star'} ${className}`}
    aria-label={label} aria-haspopup={returning ? undefined : 'dialog'}
    onClick={event => travel(event, onClick)}>
    <span className="star-aura" aria-hidden="true" />
    {orbit && <span className="star-orbit" aria-hidden="true" />}
    <span className="star-rays" aria-hidden="true" />
    <span className="star-heart" aria-hidden="true" />
    {name && <span className="star-name" aria-hidden="true">{name}</span>}
  </button>;
}

export function ReturnStar({ onClick, label = '关闭，返回星空' }) {
  const corner = useRef(null);
  const pointer = useRef('');
  const [revealed, setRevealed] = useState(false);
  useEffect(() => {
    const outside = event => {
      if (event.pointerType === 'touch' && !corner.current?.contains(event.target)) setRevealed(false);
    };
    document.addEventListener('pointerdown', outside);
    return () => document.removeEventListener('pointerdown', outside);
  }, []);
  return <div ref={corner} className={`return-corner ${revealed ? 'touch-revealed' : ''}`}
    onPointerDownCapture={event => { pointer.current = event.pointerType; }}
    onClickCapture={event => {
      // A touch device has no hover: first tap discovers the star, next tap activates it.
      if (pointer.current === 'touch' && event.detail !== 0 && !revealed) {
        event.preventDefault(); event.stopPropagation(); setRevealed(true);
      }
    }}>
    <StarButton returning onClick={onClick} label={label} />
  </div>;
}
