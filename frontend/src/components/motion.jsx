import React, { useEffect, useRef, useState } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

export function Reveal({ children, delay = 0, y = 36, className = '' }) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    const ctx = gsap.context(() => {
      gsap.fromTo(el, { y, opacity: 0 }, {
        y: 0, opacity: 1, duration: 1, delay, ease: 'expo.out',
        scrollTrigger: { trigger: el, start: 'top 88%' },
      });
    }, ref);
    return () => ctx.revert();
  }, []);
  return <div ref={ref} className={className} style={{ opacity: 0 }}>{children}</div>;
}

export function Ticker({ items, dark, fast }) {
  const row = [...items, ...items];
  return (
    <div className={`overflow-hidden border-y-[1.5px] ${dark ? 'border-paper/25 bg-ink text-paper' : 'border-ink bg-sun text-ink'}`}>
      <div className="flex whitespace-nowrap py-2.5" style={{ animation: `marquee ${fast ? 18 : 30}s linear infinite` }}>
        {[0, 1].map((h) => (
          <div key={h} className="flex shrink-0">
            {row.map((t, i) => (
              <span key={i} className="mx-5 font-mono text-xs uppercase tracking-[0.2em] flex items-center gap-5">
                {t} <span className="inline-block w-2 h-2 rounded-full bg-signal" />
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export function CountUp({ to, suffix = '', duration = 1.6 }) {
  const ref = useRef(null);
  const [n, setN] = useState(0);
  useEffect(() => {
    const el = ref.current;
    const obj = { v: 0 };
    const ctx = gsap.context(() => {
      gsap.to(obj, {
        v: to, duration, ease: 'expo.out',
        scrollTrigger: { trigger: el, start: 'top 90%' },
        onUpdate: () => setN(Math.round(obj.v)),
      });
    }, ref);
    return () => ctx.revert();
  }, [to]);
  return <span ref={ref}>{n.toLocaleString()}{suffix}</span>;
}
