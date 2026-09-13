import React, { useEffect, useRef } from 'react';

function random(seed) {
  let n = seed;
  return () => { n = (n * 1664525 + 1013904223) >>> 0; return n / 4294967296; };
}

export function Starfield({ reduced }) {
  const ref = useRef(null);
  useEffect(() => {
    const canvas = ref.current, ctx = canvas.getContext('2d');
    if (!ctx) return;
    const rand = random(87);
    let width = 1, height = 1, frame, last = 0;
    const stars = Array.from({ length: 1700 }, () => ({ x: (rand() - .5) * 2500, y: (rand() - .5) * 1800, z: rand() * 1700 + 80, size: rand() * 1.3 + .2 }));
    // Group stars by brightness so a frame costs a handful of fills instead of
    // one path per star. Reused across frames; only the lengths reset.
    const TAU = Math.PI * 2, LEVELS = 7;
    const layers = Array.from({ length: LEVELS }, () => ({ dots: [], trails: [], weight: 0, count: 0 }));
    const resize = () => {
      width = innerWidth; height = innerHeight;
      const ratio = Math.min(devicePixelRatio, 1.8);
      canvas.width = width * ratio; canvas.height = height * ratio;
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      if (reduced) draw(0);
    };
    const draw = timestamp => {
      const dt = Math.min((timestamp - last) / 1000, .04); last = timestamp;
      ctx.clearRect(0, 0, width, height);
      const cx = width / 2, cy = height * .4, focal = Math.min(width, 1500) * .64;
      for (const layer of layers) { layer.dots.length = 0; layer.trails.length = 0; layer.weight = 0; layer.count = 0; }
      for (const s of stars) {
        if (!reduced) s.z -= dt * 55;
        if (s.z < 30) s.z = 1750;
        const px = s.x / s.z * focal + cx, py = s.y / s.z * focal + cy;
        if (px < -50 || px > width + 50 || py < -50 || py > height + 50) continue;
        const fade = Math.min(1, (1750 - s.z) / 500);
        const radius = Math.min(1.8, s.size * 500 / s.z);
        const layer = layers[Math.min(LEVELS - 1, fade * LEVELS | 0)];
        layer.dots.push(px, py, radius);
        layer.weight += fade; layer.count++;
        if (s.z < 520) layer.trails.push(px, py, s.x / (s.z + 17) * focal + cx, s.y / (s.z + 17) * focal + cy, radius);
      }
      for (const layer of layers) {
        if (!layer.count) continue;
        const fade = layer.weight / layer.count;
        ctx.fillStyle = `rgba(255,255,255,${(.72 * fade).toFixed(3)})`;
        ctx.beginPath();
        for (let i = 0; i < layer.dots.length; i += 3) {
          const x = layer.dots[i], y = layer.dots[i + 1], r = layer.dots[i + 2];
          ctx.moveTo(x + r, y); ctx.arc(x, y, r, 0, TAU);
        }
        ctx.fill();
        if (!layer.trails.length) continue;
        ctx.strokeStyle = `rgba(255,255,255,${(.50 * fade).toFixed(3)})`;
        // Trail widths within a brightness layer vary too little to see; one
        // stroke per layer replaces one per star.
        ctx.lineWidth = Math.max(.3, layer.trails[4] * .55);
        ctx.beginPath();
        for (let i = 0; i < layer.trails.length; i += 5) {
          ctx.moveTo(layer.trails[i], layer.trails[i + 1]);
          ctx.lineTo(layer.trails[i + 2], layer.trails[i + 3]);
        }
        ctx.stroke();
      }
      if (!reduced && !document.hidden) frame = requestAnimationFrame(draw);
    };
    const visibility = () => { cancelAnimationFrame(frame); last = performance.now(); if (!document.hidden) draw(last); };
    resize(); if (!reduced) frame = requestAnimationFrame(draw);
    window.addEventListener('resize', resize); document.addEventListener('visibilitychange', visibility);
    return () => { cancelAnimationFrame(frame); window.removeEventListener('resize', resize); document.removeEventListener('visibilitychange', visibility); };
  }, [reduced]);
  return <canvas ref={ref} className="starfield" aria-hidden="true" />;
}

export function LightOrb({ reduced, paused, active }) {
  const ref = useRef(null);
  const activity = useRef(active); activity.current = active;
  // Read through a ref: pausing must not re-run the effect, which would rebuild
  // the dust field and repaint mid-transition.
  const halted = useRef(paused); halted.current = paused;
  useEffect(() => {
    const canvas = ref.current, ctx = canvas.getContext('2d');
    if (!ctx) return;
    const size = 560, ratio = Math.min(devicePixelRatio, 1.7);
    canvas.width = canvas.height = size * ratio; ctx.scale(ratio, ratio);
    const rand = random(192);
    const dust = Array.from({ length: 390 }, () => ({ a: rand() * Math.PI * 2, r: 130 + rand() * 108, size: rand(), phase: rand() * 6 }));
    let frame, start = performance.now(), lastFrame = -100;
    const draw = now => {
      if (halted.current) {
        // Hidden behind a panel: keep the last frame, keep the loop cheap.
        if (!document.hidden) frame = requestAnimationFrame(draw);
        return;
      }
      if (!reduced && now - lastFrame < 32) {
        if (!document.hidden) frame = requestAnimationFrame(draw);
        return;
      }
      lastFrame = now;
      const t = reduced ? 1.7 : (now - start) * .00019;
      ctx.clearRect(0, 0, size, size);
      ctx.globalCompositeOperation = 'source-over';
      const halo = ctx.createRadialGradient(280, 280, 15, 280, 280, 257);
      halo.addColorStop(0, 'rgba(255,255,255,.12)'); halo.addColorStop(.55, 'rgba(255,255,255,.045)'); halo.addColorStop(1, 'rgba(255,255,255,0)');
      ctx.fillStyle = halo; ctx.fillRect(0, 0, size, size);
      ctx.globalCompositeOperation = 'screen';
      for (let j = 0; j < 112; j++) {
        const seed = j * .073;
        const latitude = Math.asin(-.98 + 1.96 * j / 111);
        ctx.beginPath();
        for (let i = 0; i <= 180; i++) {
          const a = i / 180 * Math.PI * 2;
          const wave = Math.cos(latitude);
          const elevation = latitude + wave * (.28 * Math.sin(a * 3 + t * 2 + latitude * 4) + .14 * Math.cos(a * 5 - t + latitude * 6));
          const radius = 180 + Math.sin(a * 3 + seed * 3 + t * 2) * 12 + Math.cos(a * 5 - t + seed) * 7;
          const theta = a + t * .34 + latitude * .8;
          const x = Math.cos(theta) * Math.cos(elevation) * radius;
          const y = Math.sin(elevation) * radius;
          const z = Math.sin(theta) * Math.cos(elevation) * radius;
          const tilt = .85 + Math.sin(t) * .15;
          const py = y * Math.cos(tilt) - z * Math.sin(tilt);
          const pz = y * Math.sin(tilt) + z * Math.cos(tilt);
          const perspective = 620 / (620 - pz);
          const scale = activity.current ? 1.035 : 1;
          const px = 280 + (x * .95 + Math.sin(a * 4 + t + seed) * 4) * perspective * scale;
          const screenY = 280 + py * perspective * scale;
          if (i === 0) ctx.moveTo(px, screenY); else ctx.lineTo(px, screenY);
        }
        ctx.strokeStyle = `rgba(255,255,255,${j % 9 === 0 ? .53 : .15})`;
        ctx.lineWidth = j % 9 === 0 ? 1.4 : .7;
        ctx.shadowColor = 'rgba(255,255,255,.7)'; ctx.shadowBlur = j % 9 === 0 ? 12 : 4; ctx.stroke();
      }
      ctx.shadowBlur = 0;
      const core = ctx.createRadialGradient(267, 261, 0, 275, 270, 80);
      core.addColorStop(0, 'rgba(255,255,255,.5)'); core.addColorStop(.4, 'rgba(255,255,255,.09)'); core.addColorStop(1, 'rgba(255,255,255,0)');
      ctx.fillStyle = core; ctx.fillRect(190, 190, 170, 170);
      for (const p of dust) {
        const a = p.a + t * .15, r = p.r + Math.sin(t * 2 + p.phase) * 5;
        ctx.fillStyle = `rgba(255,255,255,${p.size * .3})`;
        ctx.beginPath(); ctx.arc(280 + Math.cos(a) * r, 280 + Math.sin(a) * r * .95, p.size * .8, 0, Math.PI * 2); ctx.fill();
      }
      if (!reduced && !document.hidden) frame = requestAnimationFrame(draw);
    };
    const visibility = () => { cancelAnimationFrame(frame); if (!document.hidden) draw(performance.now()); };
    draw(performance.now()); document.addEventListener('visibilitychange', visibility);
    return () => { cancelAnimationFrame(frame); document.removeEventListener('visibilitychange', visibility); };
  }, [reduced]);
  return <canvas ref={ref} className="light-orb" aria-hidden="true" />;
}
