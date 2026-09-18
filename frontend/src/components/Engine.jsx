import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { api } from '../lib/api.js';

const NODES = [
  ['PLANNER', 'Decides what to search.'],
  ['DISCOVERY', 'Finds relevant live opportunities.'],
  ['INVESTIGATOR', 'Researches the organization.'],
  ['VERIFIER', 'Cross-checks critical facts.'],
  ['MATCH', 'Checks your fit.'],
  ['APPLICATION', 'Prepares your application.'],
  ['OUTREACH', 'Finds people, drafts cold mail.'],
  ['MONITOR', 'Tracks changes after discovery.'],
];
const LOOP = ['DISCOVER', 'INVESTIGATE', 'VERIFY', 'MATCH', 'PREPARE', 'ACT', 'MONITOR'];
const CARDS = [
  ['LIVE SEARCH', '47 opportunities found', 'left-0 top-4 sm:top-8'],
  ['MATCH', '8 / 10 requirements', 'right-0 top-16 sm:top-24'],
  ['SKILL GAP', 'CUDA detected', 'left-0 sm:left-2 bottom-24 sm:bottom-28'],
  ['CHANGE', 'Deadline moved → re-verified', 'right-0 sm:right-2 bottom-10 sm:bottom-14'],
  ['OUTREACH', 'Researcher identified', 'left-1/2 -translate-x-1/2 bottom-0 hidden lg:flex'],
];

// hexagon track geometry (flattened for a slight isometric read)
const CX = 320, CY = 285, R = 205, SQ = 0.74;
const VERTS = Array.from({ length: 6 }, (_, k) => {
  const a = (k / 6) * Math.PI * 2 - Math.PI / 2;
  return [CX + R * Math.cos(a), CY + R * SQ * Math.sin(a)];
});
function pointAt(frac) {
  const f = ((frac % 1) + 1) % 1 * 6;
  const i = Math.floor(f) % 6, t = f - Math.floor(f);
  const [x1, y1] = VERTS[i], [x2, y2] = VERTS[(i + 1) % 6];
  return [x1 + (x2 - x1) * t, y1 + (y2 - y1) * t];
}
const TRACK_D = `M ${VERTS.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join(' L ')} Z`;
const NODE_PTS = Array.from({ length: 8 }, (_, i) => pointAt(i / 8));

// opportunity lineage nodes fanning off the working agents
const LEAVES = [
  { from: 1, x: 560, y: 120 }, { from: 1, x: 590, y: 180 }, { from: 1, x: 545, y: 235 },
  { from: 2, x: 592, y: 300 }, { from: 2, x: 560, y: 360 },
  { from: 6, x: 70, y: 150 }, { from: 6, x: 48, y: 230 },
  { from: 7, x: 62, y: 330 }, { from: 7, x: 84, y: 400 },
];
const STEP_NODE = [0, 1, 2, 3, 3, 4, 6, 7]; // LOOP step -> agent index (approx)

/** Schematic agent loop: hexagon track, 8 diamond agents, a token that
 *  travels node-to-node dwelling at each, lineage lines to opportunities. */
export default function Engine() {
  const [step, setStep] = useState(0);
  const [budget, setBudget] = useState(null);
  const [hover, setHover] = useState(-1);
  const reduced = useMemo(() => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches, []);

  useEffect(() => { api.health().then((h) => setBudget(`${h.budget.remaining}/${h.budget.budget}`)).catch(() => {}); }, []);
  useEffect(() => {
    if (reduced) return undefined;
    const id = setInterval(() => setStep((s) => (s + 1) % LOOP.length), 2400);
    return () => clearInterval(id);
  }, [reduced]);

  const activeNode = STEP_NODE[step];
  // token dwells at each node: duplicate keyPoints, even keyTimes (19.2s = 8 × 2.4s)
  const arrivals = Array.from({ length: 8 }, (_, i) => (i / 8).toFixed(4));
  const keyPoints = arrivals.flatMap((a) => [a, a]).join(';');
  const keyTimes = Array.from({ length: 16 }, (_, i) => (i / 15).toFixed(4)).join(';');

  return (
    <div className="relative w-full h-[440px] sm:h-[520px] lg:h-[620px] select-none">
      <svg viewBox="0 0 640 570" className="absolute inset-0 w-full h-full" role="img" aria-label="Autonomous agent pipeline loop">
        {/* construction corners */}
        {[[36, 40], [604, 40], [36, 530], [604, 530]].map(([x, y]) => (
          <g key={`${x}${y}`}><rect x={x - 4} y={y - 4} width="8" height="8" fill="none" stroke="#16150F" strokeOpacity="0.3" /><circle cx={x} cy={y} r="1.6" fill="#FF4D00" /></g>
        ))}
        {/* lineage network */}
        {LEAVES.map((L, i) => {
          const [fx, fy] = NODE_PTS[L.from];
          const lit = L.from === activeNode;
          return (
            <g key={i}>
              <line x1={fx} y1={fy} x2={L.x} y2={L.y} stroke={lit ? '#FF4D00' : '#16150F'}
                strokeOpacity={lit ? 0.9 : 0.22} strokeWidth={lit ? 1.6 : 1}
                className={reduced ? '' : 'pulse-line'} style={{ animationDelay: `${(i * 0.9).toFixed(1)}s` }} />
              <rect x={L.x - 4} y={L.y - 4} width="8" height="8" fill={lit ? '#FF4D00' : '#F6F3EC'} stroke="#16150F" strokeWidth="1" />
            </g>
          );
        })}
        {/* track */}
        <path d={TRACK_D} fill="none" stroke="#16150F" strokeWidth="1.5" strokeOpacity="0.75" />
        <path d={TRACK_D} fill="none" stroke="#16150F" strokeWidth="7" strokeOpacity="0.05" />
        {/* center mark */}
        <text x={CX} y={CY - 6} textAnchor="middle" fontSize="13" fontFamily="JetBrains Mono, monospace" fill="#16150F" fontWeight="700">8 → 1 → ∞</text>
        <text x={CX} y={CY + 14} textAnchor="middle" fontSize="10" fontFamily="JetBrains Mono, monospace" fill="#16150F" opacity="0.5" letterSpacing="2">AUTONOMOUS LOOP</text>
        {/* traveling token */}
        {!reduced && (
          <circle r="7" fill="#FF4D00" stroke="#F6F3EC" strokeWidth="2">
            <animateMotion dur="19.2s" repeatCount="indefinite" calcMode="linear" keyPoints={keyPoints} keyTimes={keyTimes} path={TRACK_D} />
          </circle>
        )}
        {/* agent nodes */}
        {NODES.map(([name], i) => {
          const [x, y] = NODE_PTS[i];
          const isActive = i === (reduced ? 0 : activeNode);
          const isHover = i === hover;
          const s = isActive || isHover ? 9 : 6.5;
          return (
            <g key={name} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(-1)} style={{ cursor: 'pointer' }}>
              <rect x={x - 16} y={y - 16} width="32" height="32" fill="transparent" />
              <rect x={x - s} y={y - s} width={s * 2} height={s * 2} transform={`rotate(45 ${x} ${y})`}
                fill={isActive ? '#FF4D00' : '#F6F3EC'} stroke="#16150F" strokeWidth="1.5" />
              {isActive && !reduced && <circle cx={x} cy={y} r="15" fill="none" stroke="#FF4D00" strokeWidth="1" opacity="0.5"><animate attributeName="r" values="11;19" dur="2.4s" repeatCount="indefinite" /><animate attributeName="opacity" values="0.55;0" dur="2.4s" repeatCount="indefinite" /></circle>}
              <text x={x} y={y - 15} textAnchor="middle" fontSize="11" fontFamily="JetBrains Mono, monospace"
                fontWeight={isActive ? 700 : 500} fill={isActive ? '#FF4D00' : '#16150F'}>{name}</text>
            </g>
          );
        })}
      </svg>

      {/* hover readout */}
      <div className="absolute left-1/2 -translate-x-1/2 top-1 z-20 pointer-events-none">
        <div className={`bg-ink text-paper rounded-lg px-3 py-1.5 shadow-lift font-mono text-[11px] transition-opacity ${hover >= 0 ? 'opacity-100' : 'opacity-0'}`}>
          {hover >= 0 ? <span><b className="text-signal">{NODES[hover][0]}</b> · {NODES[hover][1]}</span> : <span>&nbsp;</span>}
        </div>
      </div>

      {/* floating micro-cards (untouched) */}
      {CARDS.map(([k, v, pos], i) => (
        <motion.div key={k} className={`absolute z-10 ${pos}`}
          animate={reduced ? {} : { y: [0, -9, 0] }} transition={{ duration: 5 + i * 0.7, repeat: Infinity, ease: 'easeInOut' }}>
          <div className="bg-sheet border-[1.5px] border-ink rounded-xl px-3 py-2 shadow-card flex items-center gap-2">
            <span className="w-2 h-2 bg-signal shrink-0" />
            <span>
              <span className="block font-mono text-[10px] tracking-[0.18em] text-smoke">{k}</span>
              <span className="block text-[13px] font-semibold leading-tight">{v}</span>
            </span>
          </div>
        </motion.div>
      ))}
      {/* annotations (untouched) */}
      <div className="absolute left-1 top-8 font-mono text-[10px] tracking-[0.18em] text-smoke leading-relaxed">AGENT STATE<br /><span className="text-ink font-bold">ACTIVE ●</span></div>
      <div className="absolute right-1 top-8 font-mono text-[10px] tracking-[0.18em] text-smoke text-right leading-relaxed">SERPAPI<br /><span className="text-ink font-bold">LIVE</span></div>
      <div className="absolute left-1 bottom-8 font-mono text-[10px] tracking-[0.18em] text-smoke leading-relaxed">SEARCH BUDGET<br /><span className="text-ink font-bold">{budget || '···'}</span></div>
      <div className="absolute right-1 bottom-8 font-mono text-[10px] tracking-[0.18em] text-smoke text-right leading-relaxed">LOOP<br /><span className="text-ink font-bold">8 → 1 → ∞</span></div>
      <div className="absolute left-1/2 -translate-x-1/2 bottom-0">
        <span key={step} className="tag bg-ink text-paper">LOOP ▸ {LOOP[step]}</span>
      </div>
    </div>
  );
}
