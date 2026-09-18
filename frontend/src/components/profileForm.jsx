import React, { useState } from 'react';

/** Shared profile-form primitives: identical vocabulary in Setup + /profile onboarding. */
export const LOCATIONS = ['Bengaluru, India', 'Mumbai, India', 'Delhi NCR, India', 'Hyderabad, India', 'Chennai, India', 'Pune, India', 'Kolkata, India', 'Ahmedabad, India', 'Remote', 'Hybrid', 'United States', 'United Kingdom', 'Singapore', 'Germany', 'Canada'];
export const SUGGESTED = ['Python', 'PyTorch', 'SQL', 'Machine Learning', 'NLP', 'React', 'Docker', 'Git', 'Data Analysis', 'Communication'];

export function matchLoc(raw) {
  if (!raw) return '';
  const hit = LOCATIONS.find((l) => raw.toLowerCase().includes(l.split(',')[0].toLowerCase()) || l.toLowerCase().includes(String(raw).toLowerCase().split(',')[0]));
  return hit || String(raw).slice(0, 80);
}

export function Field({ l, v, set, ph, type, valid, hint }) {
  return (
    <label className="block min-w-0">
      <span className="label">{l}</span>
      <span className="relative block mt-1">
        <input type={type || 'text'} className="field !py-2.5 pr-9" placeholder={ph} value={v || ''} onChange={(e) => set(e.target.value)} />
        {valid ? <span className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-moss text-paper grid place-items-center text-[10px]" title="Looks good">✓</span> : null}
      </span>
      {hint ? <span className="block font-mono text-[11px] text-smoke/70 mt-1">e.g. {hint}</span> : null}
    </label>
  );
}

export function Drop({ value, onPick }) {
  const [open, setOpen] = useState(false);
  const [custom, setCustom] = useState('');
  return (
    <div className="relative">
      <button type="button" aria-haspopup="listbox" aria-expanded={open} onClick={() => setOpen((v) => !v)}
        className="field flex justify-between items-center !py-2 text-left">
        <span className={value ? '' : 'text-smoke/60'}>{value || 'Location'}</span><span className="text-[10px] text-smoke">▾</span>
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div role="listbox" className="absolute z-50 mt-1.5 w-full max-h-60 overflow-auto bg-sheet border border-ink/20 rounded-xl shadow-lift py-1"
            onKeyDown={(e) => { if (e.key === 'Escape') setOpen(false); }}>
            {LOCATIONS.map((l) => (
              <button key={l} role="option" aria-selected={value === l} onClick={() => { onPick(l); setOpen(false); }}
                className={`w-full text-left px-4 py-2 text-sm hover:bg-paper ${value === l ? 'font-bold' : ''}`}>{l}</button>
            ))}
            <div className="border-t border-ink/10 mt-1 pt-2 px-3 pb-2 flex gap-1.5">
              <input value={custom} onChange={(e) => setCustom(e.target.value)} placeholder="Other location…"
                className="field !py-1.5 !text-sm" onKeyDown={(e) => { if (e.key === 'Enter' && custom.trim()) { onPick(custom.trim()); setOpen(false); } }} />
              <button onClick={() => { if (custom.trim()) { onPick(custom.trim()); setOpen(false); } }} className="btnk btnk-ink !py-1.5 !px-3 !text-xs shrink-0">Use</button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export function SkillsEditor({ skills, setSkills }) {
  const [inp, setInp] = useState('');
  const add = (s) => {
    const v = (s || '').trim().replace(/,+$/, '');
    if (!v || skills.some((x) => x.toLowerCase() === v.toLowerCase())) return;
    setSkills([...skills, v]);
  };
  return (
    <div>
      <div className="flex gap-1.5">
        <input className="field" placeholder="e.g. CUDA — Enter to add" value={inp}
          onChange={(e) => setInp(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add(inp); setInp(''); } }} />
        <button onClick={() => { add(inp); setInp(''); }} className="btnk btnk-ink !px-4 shrink-0" aria-label="Add skill">+</button>
      </div>
      <div className="flex flex-wrap gap-1.5 mt-2.5 min-h-[2rem]" aria-live="polite">
        {skills.map((s) => (
          <span key={s} className="tag !py-1 bg-ink text-paper !border-ink">
            {s}
            <button onClick={() => setSkills(skills.filter((x) => x !== s))} aria-label={`Remove ${s}`}
              className="ml-1.5 -mr-1 w-4 h-4 rounded-full grid place-items-center text-[10px] hover:bg-signal hover:text-ink transition-colors">✕</button>
          </span>
        ))}
        {!skills.length && <span className="text-sm text-smoke">Empty — matching scores against these.</span>}
      </div>
      <div className="flex flex-wrap gap-1.5 mt-2">
        {SUGGESTED.filter((s) => !skills.some((x) => x.toLowerCase() === s.toLowerCase())).map((s) => (
          <button key={s} onClick={() => add(s)} className="tag hover:bg-sun transition-colors">+ {s}</button>
        ))}
      </div>
    </div>
  );
}

export function EntryList({ items, setItems, fields, addLabel, empty }) {
  const set = (i, k, v) => {
    const c = [...items];
    c[i] = { ...c[i], [k]: v };
    setItems(c);
  };
  return (
    <div>
      {items.map((e, i) => (
        <div key={i} className="grid sm:grid-cols-2 gap-2 border border-ink/10 rounded-xl p-3 mb-2">
          {fields.map(([k, label, ph]) => (
            <Field key={k} l={label} v={e[k]} set={(v) => set(i, k, v)} ph={ph} />
          ))}
          <div className="sm:col-span-2 text-right">
            <button onClick={() => setItems(items.filter((_, j) => j !== i))} className="font-mono text-[11px] text-smoke hover:text-red-700">remove ✕</button>
          </div>
        </div>
      ))}
      {!items.length && <p className="text-[13px] text-smoke border border-dashed border-ink/20 rounded-xl px-3.5 py-2.5 mb-2">{empty}</p>}
      <button onClick={() => setItems([...items, Object.fromEntries(fields.map(([k]) => [k, '']))])}
        className="font-mono text-[11px] uppercase tracking-widest text-smoke hover:text-ink border border-dashed border-ink/30 hover:border-ink rounded-lg px-2.5 py-1.5 transition-colors">+ {addLabel}</button>
    </div>
  );
}
