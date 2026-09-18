import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '../lib/api.js';
import { useAuth } from '../lib/auth.jsx';
import { Mark } from '../components/chrome.jsx';

const STAGES = ['DISCOVER', 'INVESTIGATE', 'VERIFY', 'MATCH', 'PREPARE', 'APPROVE', 'ACT', 'MONITOR'];
const STATUS_TONE = {
  DISCOVERED: 'text-smoke border-ink/25', INVESTIGATING: 'bg-sun/60 border-ink/25',
  VERIFIED: 'bg-moss text-paper border-moss', MATCHED: 'bg-ink text-paper border-ink',
  SHORTLISTED: 'bg-signal/15 border-signal/60', APPLICATION_READY: 'bg-moss text-paper border-moss',
  AWAITING_APPROVAL: 'bg-signal text-ink border-signal', OUTREACH_SENT: 'bg-moss text-paper border-moss',
  MONITORING: 'bg-ink text-paper border-ink', CHANGED: 'bg-red-600 text-paper border-red-600',
  EARLY_SIGNAL: 'bg-sun text-ink border-ink/25',
  CLOSED: 'text-smoke border-ink/25',
};

function initials(name) {
  return (name || '?').split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase();
}
function SystemState({ health }) {
  const st = !health ? ['OFFLINE', 'bg-red-600'] : (health.serpapi_configured && health.openrouter_configured) ? ['OPERATIONAL', 'bg-moss'] : ['DEGRADED', 'bg-signal'];
  return (
    <span className="flex items-center gap-1.5 font-mono text-[11px] font-bold mt-0.5">
      <span className={`w-1.5 h-1.5 rounded-full ${st[1]}`} />{st[0]}
    </span>
  );
}
function Palette({ open, q, setQ, close, go, refresh, signout, user }) {
  const items = [
    ['Chat', 'chat'], ['New search', 'dashboard'], ['Jobs', 'feed'], ['Details', 'detail'],
    ['Activity', 'activity'], ['Approvals', 'approvals'], ['Watching', 'monitoring'], ['Profile', 'setup'],
  ].filter(([l]) => l.toLowerCase().includes(q.toLowerCase()));
  useEffect(() => { if (open) setQ(''); }, [open ]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[60] bg-ink/40 grid justify-items-center pt-[18vh] px-4" onClick={close}>
      <div className="w-full max-w-md bg-sheet border border-ink rounded-2xl shadow-lift overflow-hidden h-fit" onClick={(e) => e.stopPropagation()}>
        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Type a command…"
          className="w-full px-5 py-4 font-mono text-sm bg-transparent focus:outline-none border-b border-ink/15 placeholder:text-smoke/60"
          onKeyDown={(e) => { if (e.key === 'Enter' && items[0]) go(items[0][1]); }} />
        <div className="py-1.5">
          {items.map(([l, t]) => (
            <button key={l} onClick={() => go(t)} className="w-full text-left px-5 py-2.5 text-sm font-head font-semibold hover:bg-paper flex justify-between">Go to {l.toLowerCase()}<span className="text-ink/25">↵</span></button>
          ))}
          <button onClick={() => { refresh(); close(); }} className="w-full text-left px-5 py-2.5 text-sm font-head font-semibold hover:bg-paper">Refresh data</button>
          {user && <button onClick={() => { signout(); close(); }} className="w-full text-left px-5 py-2.5 text-sm font-semibold text-red-700 hover:bg-red-50">Sign out</button>}
          {items.length === 0 && <div className="px-5 py-3 text-sm text-smoke">No matching command.</div>}
        </div>
      </div>
    </div>
  );
}
function MoreMenu({ go, active }) {
  const [open, setOpen] = useState(false);
  const items = [['activity', 'Activity'], ['approvals', 'Approvals'], ['setup', 'Profile']];
  const isMore = items.some(([k]) => k === active);
  return (
    <div className="relative">
      <button onClick={() => setOpen((v) => !v)}
        className={`py-1 font-mono text-[12px] uppercase tracking-[0.1em] transition-colors duration-150 ${isMore ? 'text-ink' : 'text-smoke hover:text-ink'}`}>
        {isMore && <span className="absolute -top-1 left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full bg-signal" />}
        <span className={isMore ? 'border-b-2 border-signal pb-0.5' : ''}>More ▾</span>
      </button>
      {open && (
        <div className="absolute left-1/2 -translate-x-1/2 top-8 w-44 bg-sheet border border-ink/20 rounded-xl shadow-lift overflow-hidden z-50">
          {items.map(([k, l]) => (
            <button key={k} onClick={() => { go(k); setOpen(false); }}
              className={`w-full text-left px-4 py-2.5 font-mono text-[11px] uppercase tracking-[0.12em] hover:bg-paper ${k === active ? 'text-ink font-bold' : 'text-smoke'}`}>{l}</button>
          ))}
        </div>
      )}
    </div>
  );
}
function Tag({ status }) {
  return <span className={`tag ${STATUS_TONE[status] || 'text-smoke border-ink/25'}`}>{status === 'EARLY_SIGNAL' ? 'early signal' : status || 'n/a'}</span>;
}
function VerifyTicks({ v }) {
  const f = v.fields || {};
  const ticks = [];
  if (f.organization?.state === 'VERIFIED' || (f.status && f.status.state !== 'UNKNOWN')) ticks.push('role found elsewhere');
  if ((v.cross_check?.jobs || v.cross_check?.company_site)) ticks.push('company checked');
  if (!ticks.length && f.deadline?.state === 'VERIFIED') ticks.push('details checked');
  return ticks.length ? <span className="font-mono text-[10px] text-moss">✓ {ticks.join(' · ✓ ')}</span> : null;
}
function Meter({ v, tone = 'bg-signal' }) {
  return (
    <span className="inline-block w-24 h-1.5 rounded-full bg-ink/10 overflow-hidden align-middle">
      <span className={`block h-full rounded-full ${tone}`} style={{ width: `${Math.round(Math.min(1, Math.max(0, v)) * 100)}%` }} />
    </span>
  );
}
function Section({ kicker, title, children, action }) {
  return (
    <section className="panel-flat !p-0 overflow-hidden">
      <div className="flex items-center justify-between gap-2 px-5 pt-4 pb-3 border-b border-ink/10">
        <div>
          {kicker && <div className="label">{kicker}</div>}
          <h3 className="console-h text-lg font-bold leading-tight">{title}</h3>
        </div>
        {action}
      </div>
      <div className="px-5 py-4">{children}</div>
    </section>
  );
}
function Lifecycle({ active, compact }) {
  const idx = Math.max(0, STAGES.indexOf(active));
  if (compact) {
    return (
      <div className="flex items-center gap-2" title={STAGES.join(' → ')}>
        <div className="flex items-center gap-1">
          {STAGES.map((s, i) => (
            <span key={s} title={s} className={`h-1.5 rounded-full transition-all ${i < idx ? 'w-4 bg-moss' : i === idx ? 'w-6 bg-signal' : 'w-2.5 bg-ink/15'}`} />
          ))}
        </div>
        <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-smoke">Step {idx + 1}/8 · {STAGES[idx]}</span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {STAGES.map((s, i) => (
        <React.Fragment key={s}>
          <span className={`tag !text-[10px] ${i <= idx ? 'bg-ink text-paper border-ink' : 'text-smoke border-ink/20'}`}>{s}</span>
          {i < STAGES.length - 1 && <span className="text-ink/25 text-[10px]">›</span>}
        </React.Fragment>
      ))}
    </div>
  );
}

export default function Console() {
  const { user, logout, uid } = useAuth();
  const [tab, setTab] = useState('chat');
  const [health, setHealth] = useState(null);
  const [opps, setOpps] = useState([]);
  const [detail, setDetail] = useState(null);
  const [activity, setActivity] = useState([]);
  const [approvals, setApprovals] = useState([]);
  const [monitoring, setMonitoring] = useState([]);
  const [notifs, setNotifs] = useState([]);
  const [goal, setGoal] = useState('Find AI research internships in India that match my profile and help me apply.');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [outreach, setOutreach] = useState(null);
  const [profile, setProfile] = useState(null);
  const [detailTab, setDetailTab] = useState('overview');
  const [appData, setAppData] = useState(null);
  const [checked, setChecked] = useState({});
  const [menuOpen, setMenuOpen] = useState(false);
  const [palOpen, setPalOpen] = useState(false);
  const [palQ, setPalQ] = useState('');
  const [whoOpen, setWhoOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);

  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setPalOpen(true); }
      if (e.key === 'Escape') { setPalOpen(false); setMenuOpen(false); setWhoOpen(false); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const id = uid();
  const load = async (silent) => {
    try {
      if (!silent) setBusy('loading');
      const [h, o, a, ap, m, n] = await Promise.all([
        api.health(), api.listOpps(id).catch(() => ({ data: [] })),
        api.activity().catch(() => ({ data: [] })), api.approvals().catch(() => ({ data: [] })),
        api.monitoring(id).catch(() => ({ data: [] })), api.notifications(id).catch(() => ({ data: [] })),
      ]);
      setHealth(h); setOpps(o.data || []); setActivity((a.data || []).slice(-80).reverse());
      setApprovals(ap.data || []); setMonitoring(m.data || []); setNotifs(n.data || []);
      try { setProfile((await api.profile(id)).data); } catch { setProfile(null); }
      setError('');
    } catch (e) { setError(e.message); } finally { setBusy(''); }
  };
  useEffect(() => { load(); }, [user]);

  const run = async (label, fn) => {
    try { setBusy(label); setError(''); setMsg(''); await fn(); setMsg(label + ' done'); await load(true); }
    catch (e) { setError(e.message); } finally { setBusy(''); }
  };
  const openDetail = async (oid) => {
    try {
      setBusy('opening'); setAppData(null); setChecked({});
      const d = await api.getOpp(oid);
      setDetail(d.data); setDetailTab('overview'); setTab('detail');
      try {
        const apps = await api.listApps(id);
        const mine = (apps.data || []).find((a) => a.opportunity_id === oid);
        if (mine) setAppData({ application_id: mine._id, materials: mine.materials });
      } catch {}
    }
    catch (e) { setError(e.message); } finally { setBusy(''); }
  };

  const strong = opps.filter((o) => (o.match?.score || 0) >= 0.4);
  const used = health ? health.budget.budget - health.budget.remaining : 0;
  const usedFrac = health ? used / health.budget.budget : 0;
  const tabs = [['chat', 'Chat'], ['dashboard', 'Home'], ['feed', 'Jobs'], ['detail', 'Details'], ['activity', 'Activity'], ['approvals', 'Approvals'], ['monitoring', 'Watching'], ['setup', 'Profile']];
  const SOURCE_LABEL = { linkedin_post: 'LinkedIn post', linkedin_job: 'LinkedIn job', google_jobs: 'Google Jobs', web: 'Web', company_page: 'Company site', scholar: 'Scholar' };
  const srcOf = (o) => SOURCE_LABEL[o.source_type] || SOURCE_LABEL[{ google_jobs: 'google_jobs', google: 'web', google_scholar: 'scholar' }[o.source_engine]] || 'Web';
  const freshOf = (o) => o.freshness?.detail && o.freshness.detail !== 'DATE UNKNOWN' ? o.freshness.detail : (o.freshness?.label && o.freshness.label !== 'UNKNOWN' ? o.freshness.label.toLowerCase() : 'date unknown');

  return (
    <div className="min-h-screen bg-paper">
      {/* console navbar — minimal */}
      <header className="sticky top-0 z-40 bg-paper/95 backdrop-blur border-b border-ink/15">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-[76px] flex items-center gap-5">
          {/* LEFT */}
          <div className="flex items-center gap-3 w-[270px] shrink-0">
            <Link to="/"><Mark /></Link>
          </div>
          {/* CENTER */}
          <nav className="hidden md:flex flex-1 justify-center items-center gap-7">
            {[['chat', 'Chat'], ['dashboard', 'Home'], ['feed', 'Jobs'], ['detail', 'Details'], ['monitoring', 'Watching']].map(([k, l]) => (
              <button key={k} onClick={() => setTab(k)}
                className={`relative py-1 font-mono text-[12px] uppercase tracking-[0.1em] transition-colors duration-150 ${tab === k ? 'text-ink' : 'text-smoke hover:text-ink'}`}>
                {tab === k && <span className="absolute -top-1 left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full bg-signal" />}
                <span className={tab === k ? 'border-b-2 border-signal pb-0.5' : 'hover:border-b-2 hover:border-signal/60 hover:pb-0.5'}>{l}</span>
              </button>
            ))}
            <MoreMenu go={(t) => setTab(t)} active={tab} />
          </nav>
          {/* RIGHT */}
          <div className="flex items-center gap-4 ml-auto">
            <span className="hidden lg:flex items-center gap-1.5" title={health ? `SerpApi ${health.serpapi_configured ? 'connected' : 'not configured'} · Models ${health.openrouter_configured ? 'connected' : 'not configured'}` : 'Waiting for backend'}>
              <span className={`w-1.5 h-1.5 rounded-full ${health?.serpapi_configured ? 'bg-moss' : 'bg-ink/20'}`} />
              <span className={`w-1.5 h-1.5 rounded-full ${health?.openrouter_configured ? 'bg-moss' : 'bg-ink/20'}`} />
            </span>
            <span className="hidden sm:block leading-tight" title={health ? `${health.budget.remaining} searches remaining this month` : ''}>
              <span className="font-mono text-[9px] uppercase tracking-[0.18em] text-smoke">Search</span>
              <span className="flex items-center gap-1.5 mt-0.5">
                <span className="w-10 h-1 rounded-full bg-ink/10 overflow-hidden"><span className="block h-full bg-signal rounded-full" style={{ width: `${Math.round(usedFrac * 100)}%` }} /></span>
                <span className="font-mono text-[11px]">{health ? `${health.budget.remaining}/${health.budget.budget}` : '…'}</span>
              </span>
            </span>
            <button onClick={() => setPalOpen(true)} title="Command palette (⌘K)"
              className="hidden sm:block font-mono text-[11px] text-smoke border border-ink/20 rounded-md px-1.5 py-0.5 hover:text-ink hover:border-ink transition-colors">⌘K</button>
            {user ? (
              <div className="relative">
                <button onClick={() => { setWhoOpen((v) => !v); }} className="flex items-center gap-2 py-1 hover:opacity-80 transition-opacity">
                  <span className="w-7 h-7 rounded-full bg-ink text-paper grid place-items-center font-head font-bold text-xs ring-2 ring-signal/70">{initials(user.name)}</span>
                  <span className="hidden lg:block font-head font-medium text-sm max-w-[110px] truncate">{user.name}</span>
                  <span className="text-[10px] text-smoke">▾</span>
                </button>
                {whoOpen && (
                  <div className="absolute right-0 top-10 w-52 bg-sheet border border-ink/20 rounded-xl shadow-lift overflow-hidden z-50">
                    <div className="px-4 py-3 border-b border-ink/10">
                      <div className="font-head font-semibold text-sm truncate">{user.name}</div>
                      <div className="font-mono text-[11px] text-smoke truncate">{user.email}</div>
                    </div>
                    {[['Profile', 'setup'], ['Settings', 'setup'], ['API connections', 'setup']].map(([l, t]) => (
                      <button key={l} onClick={() => { setTab(t); setWhoOpen(false); }} className="w-full text-left px-4 py-2.5 text-sm hover:bg-paper transition-colors">{l}</button>
                    ))}
                    <button onClick={() => { logout(); setWhoOpen(false); }} className="w-full text-left px-4 py-2.5 text-sm font-semibold text-red-700 hover:bg-red-50 transition-colors border-t border-ink/10">Sign out</button>
                  </div>
                )}
              </div>
            ) : (
              <Link to="/login" className="font-head font-semibold text-sm underline decoration-signal decoration-2 underline-offset-4">Log in</Link>
            )}
            <button onClick={() => setMenuOpen((v) => !v)} className="md:hidden flex flex-col gap-1 p-2" aria-label="Menu">
              <span className="w-5 h-[2px] bg-ink" /><span className="w-5 h-[2px] bg-ink" /><span className="w-5 h-[2px] bg-signal" />
            </button>
          </div>
        </div>
        {/* mobile menu */}
        {menuOpen && (
          <div className="md:hidden border-t border-ink/10 bg-paper px-4 py-3 space-y-1">
            {tabs.map(([k, l]) => (
              <button key={k} onClick={() => { setTab(k); setMenuOpen(false); }}
                className={`w-full text-left px-3 py-2.5 rounded-lg font-mono text-xs uppercase tracking-[0.14em] ${tab === k ? 'bg-ink text-paper' : 'text-smoke'}`}>{l}</button>
            ))}
            <div className="px-3 py-2 font-mono text-[11px] text-smoke border-t border-ink/10 mt-1 pt-3">
              QUOTA {health ? `${health.budget.remaining}/${health.budget.budget}` : '…'}
            </div>
            {user
              ? <button onClick={() => logout()} className="w-full text-left px-3 py-2.5 text-sm font-semibold text-red-700">Sign out ({user.name})</button>
              : <Link to="/login" className="block px-3 py-2.5 text-sm font-semibold">Log in →</Link>}
          </div>
        )}
      </header>
      <Palette open={palOpen} q={palQ} setQ={setPalQ} close={() => setPalOpen(false)}
        go={(t) => { setTab(t); setPalOpen(false); }} refresh={() => load(true)} signout={logout} user={user} />

      {tab === 'chat' ? (
        <div className="h-[calc(100vh-77px)] min-h-[480px]">
          {error && <div className="mx-auto max-w-3xl px-4 pt-3"><div className="bg-red-50 border border-red-700/60 text-red-800 rounded-xl px-4 py-2 text-sm font-medium">⚠ {error}</div></div>}
          <div className={error ? 'h-[calc(100%-52px)]' : 'h-full'}>
            <ChatView uid={id} onOpen={openDetail} onNav={(t) => setTab(t)} />
          </div>
        </div>
      ) : (
      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-6 space-y-5">
        {!user && (
          <div className="flex items-center justify-between gap-3 bg-sun/40 border border-ink/15 rounded-xl px-5 py-3 text-sm">
            <span><b className="font-head">Guest session</b> — missions reset unless you save them.</span>
            <Link to="/signup" className="font-head font-semibold underline decoration-signal decoration-2 underline-offset-4 shrink-0">Create account</Link>
          </div>
        )}
        {error && <div className="bg-red-50 border border-red-700/60 text-red-800 rounded-xl px-5 py-3 text-sm font-medium">⚠ {error}</div>}
        {msg && <div className="bg-moss/10 border border-moss/40 text-moss rounded-xl px-5 py-3 text-sm font-medium">● {msg}</div>}
        {busy && <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-smoke">Working — {busy}…</div>}

        {tab === 'dashboard' && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
            <div className="deck blueprint-dark">
              <div className="label !text-paper/50">Find jobs</div>
              <h2 className="console-h text-2xl sm:text-3xl font-bold text-paper mt-1">What job do you want?</h2>
              <div className="flex gap-2 flex-col sm:flex-row mt-4">
                <input className="field-deck" value={goal} onChange={(e) => setGoal(e.target.value)} placeholder="e.g. AI research internships in India for me…"
                  aria-label="Job search" onKeyDown={(e) => { if (e.key === 'Enter' && !busy) run('Searching', () => api.discover(goal, 12, id)); }} />
                <button disabled={!!busy} className="btnk btnk-signal whitespace-nowrap !px-7" onClick={() => run('Searching', () => api.discover(goal, 12, id))}>Search →</button>
                <button className="btnk btnk-paper whitespace-nowrap" onClick={() => run('Loading examples', () => api.seed())}>Examples</button>
              </div>
              <div className="mt-5 opacity-90"><Lifecycle active="MATCH" /></div>
            </div>

            <div className="panel-flat !p-0 overflow-hidden">
              <div className="grid grid-cols-2 sm:grid-cols-4 divide-x divide-ink/10">
                {[['Jobs found', opps.length], ['Good fits', strong.length], ['Watching', monitoring.length], ['To approve', approvals.length]].map(([k, v]) => (
                  <div key={k} className="px-5 py-4">
                    <div className="font-head font-bold text-3xl tracking-tight">{v}</div>
                    <div className="label mt-0.5">{k}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="grid lg:grid-cols-2 gap-5">
              <Section kicker="Signals" title="Updates" action={<button className="font-mono text-[11px] uppercase tracking-widest text-smoke hover:text-ink" onClick={() => setTab('monitoring')}>Watching →</button>}>
                {notifs.length === 0 ? <p className="text-sm text-smoke">Quiet. Jobs you watch will report changes here.</p> :
                  notifs.slice(0, 5).map((n, i) => <div key={i} className="rowline py-2 text-sm"><span className="inline-block w-1.5 h-1.5 rounded-full bg-signal mr-2" />{n.message}</div>)}
              </Section>
              <Section kicker="App log" title="What the app did" action={<button className="font-mono text-[11px] uppercase tracking-widest text-smoke hover:text-ink" onClick={() => setTab('activity')}>Activity →</button>}>
                {activity.slice(0, 6).map((r, i) => (
                  <div key={i} className="rowline py-2 flex gap-3 items-baseline">
                    <span className="font-mono text-[10px] uppercase tracking-widest text-moss font-bold w-20 shrink-0">{r.agent}</span>
                    <span className="text-[13px] text-ink/75 truncate">{r.action} — {r.summary}</span>
                  </div>
                ))}
                {activity.length === 0 && <p className="text-sm text-smoke">No runs yet — launch a mission above.</p>}
              </Section>
            </div>
          </motion.div>
        )}

        {tab === 'feed' && (
          <section className="panel-flat !p-0 overflow-hidden">
            <div className="hidden sm:grid grid-cols-[1fr_110px_130px_28px] gap-3 px-5 py-2.5 border-b border-ink/10 label">
              <span>Job</span><span>Fit</span><span>Status</span><span />
            </div>
            {opps.map((o, i) => (
              <button key={o._id} onClick={() => openDetail(o._id)} className="w-full text-left grid sm:grid-cols-[1fr_110px_130px_28px] gap-1 sm:gap-3 items-center px-5 py-3.5 rowline hover:bg-paper transition-colors">
                <span className="flex gap-3 items-baseline min-w-0">
                  <span className="font-mono text-[11px] text-smoke w-6 shrink-0">{String(i + 1).padStart(2, '0')}</span>
                  <span className="min-w-0">
                    <span className="block font-head font-semibold text-[15px] leading-snug truncate">{o.title}</span>
                    <span className="block font-mono text-[11px] text-smoke truncate">{o.organization || 'Company unknown'} · {o.location || 'n/a'}</span>
                    <span className="flex items-center gap-1.5 mt-1 flex-wrap">
                      <span className={`tag !text-[10px] ${o.source_type?.startsWith('linkedin') ? '!border-signal text-ink' : ''}`}>{srcOf(o)} · {freshOf(o)}</span>
                      {o.is_early_signal && <span className="tag !text-[10px] bg-sun">early signal</span>}
                      {o.match && <span className="font-mono text-[10px] text-smoke">{(o.match.skill_match?.matched?.length || 0)}/{(o.match.skill_match?.matched?.length || 0) + (o.match.skill_match?.gaps?.length || 0)} skills fit</span>}
                      {(o.match?.skill_match?.gaps || []).slice(0, 2).map((g) => <span key={g} className="font-mono text-[10px] text-smoke">⚠ {g}</span>)}
                      {o.verification && <VerifyTicks v={o.verification} />}
                    </span>
                  </span>
                </span>
                <span className="flex items-center gap-2">
                  <Meter v={o.match ? o.match.score : 0} tone={o.match && o.match.score >= 0.4 ? 'bg-moss' : 'bg-signal'} />
                  <span className="font-mono text-[11px] text-smoke w-8">{o.match ? Math.round(o.match.score * 100) : '—'}</span>
                </span>
                <span><Tag status={o.status} /></span>
                <span className="text-ink/30 text-lg leading-none">›</span>
              </button>
            ))}
            {opps.length === 0 && <p className="px-5 py-8 text-sm text-smoke">No jobs yet. Search above or load examples.</p>}
          </section>
        )}

        {tab === 'detail' && (
          !detail ? <div className="panel-flat px-5 py-10 text-sm text-smoke text-center">Pick a job from the list to see details.</div> : (
          <div className="space-y-5">
            <div className="panel-flat !p-0 overflow-hidden">
              <div className="px-5 pt-5 pb-4">
                {(detail.status === 'EARLY_SIGNAL' || detail.is_early_signal) && (
                  <div className="bg-sun/40 border border-ink/20 rounded-xl px-4 py-2.5 text-sm mb-4">
                    <b className="font-head">Early signal</b> — spotted on {srcOf(detail)}{detail.author ? ` by ${detail.author}` : ''}, no formal listing found yet.
                    {detail.freshness?.detail && detail.freshness.detail !== 'DATE UNKNOWN' && <span className="font-mono text-xs"> · {detail.freshness.detail}.</span>}
                    <span> Investigate or Watch below.</span>
                  </div>
                )}
                <div className="flex justify-between items-start gap-3 flex-wrap">
                  <div className="min-w-0">
                    <div className="label">{detail.organization || 'Company unknown'} · {detail.location || 'n/a'} · {srcOf(detail)} · {freshOf(detail)}</div>
                    <h2 className="console-h text-2xl sm:text-[2rem] font-bold leading-tight mt-1">{detail.title}</h2>
                  </div>
                  <Tag status={detail.status} />
                </div>
                <div className="mt-3"><Lifecycle compact active="PREPARE" /></div>
              </div>
              <div className="flex gap-2 px-5 py-3 border-t border-ink/10 bg-paper/60 flex-wrap items-center">
                {[['investigate', 'Investigate', 'evidence'], ['match', 'Check fit', 'match'], ['prepare', 'Prepare', 'prepare']].map(([k, l, go]) => (
                  <button key={k} disabled={!!busy} className="btnk btnk-line !py-1.5 !px-4 !text-[13px]" onClick={() => run(l, async () => {
                    if (k === 'investigate') await api.investigate(detail._id);
                    if (k === 'match') await api.match(detail._id);
                    if (k === 'prepare') { const r = await api.prepareApp(detail._id); setAppData(r.data); }
                    setDetail((await api.getOpp(detail._id)).data);
                    if (go) setDetailTab(go);
                  })}>{busy === l ? <span className="spinner" /> : l}</button>
                ))}
                {detail.application?.found
                  ? <a className="btnk btnk-signal !py-1.5 !px-4 !text-[13px]" href={detail.application.url} target="_blank" rel="noreferrer">Apply here ↗</a>
                  : detail.source_url ? <a className="btnk btnk-ink !py-1.5 !px-4 !text-[13px]" href={detail.source_url} target="_blank" rel="noreferrer">Open posting ↗</a> : null}
                <span className="flex-1" />
                <div className="relative">
                  <button onClick={() => setMoreOpen((v) => !v)} className="btnk btnk-line !py-1.5 !px-3.5 !text-[13px]" aria-label="More actions">···</button>
                  {moreOpen && (
                    <>
                      <div className="fixed inset-0 z-40" onClick={() => setMoreOpen(false)} />
                      <div className="absolute right-0 top-10 z-50 w-52 bg-sheet border border-ink/20 rounded-xl shadow-lift overflow-hidden">
                        <button disabled={!!busy} className="w-full text-left px-4 py-2.5 text-sm hover:bg-paper disabled:opacity-50" onClick={() => { setMoreOpen(false); run('Check facts', async () => { await api.verify(detail._id); setDetail((await api.getOpp(detail._id)).data); }); }}>Check facts</button>
                        {(detail.source_type?.startsWith('linkedin')) && (
                          <button disabled={!!busy} className="w-full text-left px-4 py-2.5 text-sm hover:bg-paper disabled:opacity-50" onClick={() => { setMoreOpen(false); run('Cross-checking post', async () => { await fetch(`/api/opportunities/${detail._id}/verify-linkedin`, { method: 'POST' }); setDetail((await api.getOpp(detail._id)).data); }); }}>Cross-check post</button>
                        )}
                        <button className="w-full text-left px-4 py-2.5 text-sm hover:bg-paper" onClick={() => { setMoreOpen(false); run('Watching', () => api.watch(detail._id, id)); }}>Watch for changes</button>
                        <button className="w-full text-left px-4 py-2.5 text-sm hover:bg-paper" onClick={() => { setMoreOpen(false); run('Checking', async () => { const r = await api.checkNow(detail._id); setMsg(r.data?.changes?.length ? `Changed: ${r.data.changes.map((c) => c.field).join(', ')}` : 'No changes'); }); }}>Check now</button>
                      </div>
                    </>
                  )}
                </div>
              </div>
              <div className="px-5 flex border-t border-ink/10 overflow-x-auto">
                {[['overview', 'About'], ['match', 'Fit'], ['prepare', 'Prepare'], ['evidence', `Proof · ${(detail.evidence || []).length}`], ['outreach', 'Outreach'], ['activity', 'Log']].map(([k, l]) => (
                  <button key={k} onClick={() => setDetailTab(k)} className={`tabk ${detailTab === k ? 'tabk-on' : 'tabk-off'}`}>{l}</button>
                ))}
              </div>
              <div className="px-5 py-5 space-y-5">
                <AnimatePresence mode="wait">
                  <motion.div key={detailTab} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                    {detailTab === 'overview' && (
                      <div>
                        <p className="text-[15px] leading-relaxed text-ink/80 max-w-3xl">{detail.description || (detail.data_completeness === 'partial' ? 'Only a short public snippet is available — partial information.' : 'n/a')}</p>
                        <dl className="grid sm:grid-cols-3 gap-4 mt-5">
                          {[['Needs', (detail.requirements || []).join('; ') || 'not listed'], ['Deadline', detail.deadline || 'not listed'], ['Apply link', detail.application?.found ? 'found ✓' : 'not found']].map(([k, v]) => (
                            <div key={k} className="border-t-2 border-ink pt-2">
                              <dt className="label">{k}</dt>
                              <dd className="text-sm mt-1 text-ink/80">{v} {k === 'Apply link' && detail.application?.found && <a className="text-signal font-semibold" href={detail.application.url} target="_blank" rel="noreferrer">↗</a>}
                                {k === 'Apply link' && !detail.application?.found && <button className="text-signal font-semibold text-xs ml-1 underline underline-offset-2" onClick={() => run('Finding apply link', async () => {
                                  await fetch(`/api/opportunities/${detail._id}/extract-application-link`, { method: 'POST' });
                                  setDetail((await api.getOpp(detail._id)).data);
                                })}>Find it</button>}</dd>
                            </div>
                          ))}
                        </dl>
                        <div className="mt-5">
                          <div className="label mb-2">Seen on — one job, every source</div>
                          <div className="space-y-1.5">
                            {(detail.sources?.length ? detail.sources : [{ type: detail.source_type || 'web', url: detail.source_url }]).map((s, i) => (
                              <div key={i} className="flex items-center gap-2 text-sm">
                                <span className="tag !text-[10px]">{SOURCE_LABEL[s.type] || s.type}</span>
                                {s.url ? <a className="text-signal text-xs font-semibold truncate max-w-[420px]" href={s.url} target="_blank" rel="noreferrer">{s.url.replace(/^https?:\/\//, '').slice(0, 70)}</a>
                                  : <span className="font-mono text-xs text-smoke">no link stored</span>}
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    )}
                    {detailTab === 'match' && (
                      !detail.match ? (busy === 'Check fit'
                        ? <div className="space-y-4" aria-live="polite">
                          <div className="flex items-center gap-2 text-sm text-smoke"><span className="spinner" /> Scoring your fit — comparing skills, education and preferences…</div>
                          <div className="skel h-7 w-2/3" />
                          {[92, 64, 78].map((w, i) => <div key={i}><div className="skel h-4 w-28 mb-2" /><div className="skel h-2.5" style={{ width: `${w}%` }} /></div>)}
                          <div className="skel h-24" />
                        </div>
                        : <p className="text-sm text-smoke">No score yet — hit Check fit above.</p>)                         : (
                        <div className="space-y-4">
                          <div className="flex items-center gap-3 bg-paper border border-ink/15 rounded-xl px-4 py-3">
                            <span className="font-head font-bold text-3xl">{Math.round((detail.match.score || 0) * 100)}<span className="text-base">%</span></span>
                            <p className="text-[13px] text-ink/70 leading-snug">{detail.match.rationale}</p>
                          </div>
                          <div className="space-y-3">
                            {[
                              ['Skills', (detail.match.skill_match?.matched?.length || 0) / Math.max(1, (detail.match.skill_match?.matched?.length || 0) + (detail.match.skill_match?.gaps?.length || 0)), `${(detail.match.skill_match?.matched || []).join(', ') || '—'}`],
                              ['Research fit', Math.min(1, (detail.match.research_alignment || []).length / 3), `${(detail.match.research_alignment || []).join(', ') || '—'}`],
                              ['Eligibility', detail.match.eligibility?.status === 'likely_eligible' ? 1 : detail.match.eligibility?.status === 'needs_review' ? 0.55 : 0.2, (detail.match.eligibility?.status || '').replaceAll('_', ' ')],
                            ].map(([k, v, sub]) => (
                              <div key={k}>
                                <div className="flex justify-between items-baseline"><span className="text-sm font-semibold">{k}</span><span className="font-mono text-xs text-smoke">{Math.round(v * 100)}%</span></div>
                                <div className="h-1.5 rounded-full bg-ink/10 mt-1 overflow-hidden"><div className={`h-full rounded-full ${v >= 0.6 ? 'bg-moss' : 'bg-signal'}`} style={{ width: `${Math.round(v * 100)}%` }} /></div>
                                <div className="text-xs text-smoke mt-0.5">{sub}</div>
                              </div>
                            ))}
                          </div>
                          {(detail.match.skill_match?.gaps || []).length > 0 && (
                            <div className="text-[13px]"><b className="font-head">Gaps:</b> <span className="text-ink/70">{detail.match.skill_match.gaps.join(', ')}</span></div>
                          )}
                          {!!(detail.match.why_shown || []).length && (
                            <div className="font-mono text-[11px] text-smoke">Shown because: {(detail.match.why_shown || []).join(' · ')}</div>
                          )}
                        </div>
                      )
                    )}
                    {detailTab === 'prepare' && (
                      !appData ? (
                        <div className="flex items-center justify-between gap-3 flex-wrap">
                          <p className="text-sm text-smoke max-w-md">No prep pack yet. The agent will build your roadmap: what to fix on your resume, a cover letter, checklists and a week-by-week gap plan.</p>
                          <button className="btnk btnk-signal !py-2 !text-sm" onClick={() => run('Preparing', async () => { const r = await api.prepareApp(detail._id); setAppData(r.data); })}>Build my roadmap →</button>
                        </div>
                      ) : (
                        <>
                          <ResumeBuilder oid={detail._id} uid={id} gaps={detail.match?.skill_match?.gaps || []} />
                          <PrepRoadmap key={appData.application_id} materials={appData.materials} gaps={detail.match?.skill_match?.gaps || []} checked={checked} setChecked={setChecked} />
                        </>
                      )
                    )}
                    {detailTab === 'evidence' && (
                      <div>
                        {(detail.evidence || []).map((e, i) => (
                          <div key={i} className="rowline py-3 grid sm:grid-cols-[1fr_140px] gap-2">
                            <div>
                              <div className="font-head font-semibold text-[15px]">{e.claim}</div>
                              <div className="text-[13px] text-ink/60 mt-0.5">{e.evidenceText}</div>
                              {e.sourceUrl && <a className="text-signal text-xs font-semibold" href={e.sourceUrl} target="_blank" rel="noreferrer">View source ↗</a>}
                            </div>
                            <div className="sm:text-right"><Tag status={e.confidenceState} /></div>
                          </div>
                        ))}
                        {(detail.evidence || []).length === 0 && <p className="text-sm text-smoke">No evidence yet — run Investigate.</p>}
                      </div>
                    )}
                    {detailTab === 'outreach' && (
                      <div>
                        {!outreach ? (
                          <div className="flex items-center justify-between gap-3 flex-wrap">
                            <p className="text-sm text-smoke max-w-md">The agent finds a real public contact — never invents one — and drafts a personal note.</p>
                            <button className="btnk btnk-signal !py-2 !text-sm" onClick={() => run('Drafting outreach', async () => { const r = await api.genOutreach(detail._id); setOutreach(r.data || r); })}>Find contact + draft →</button>
                          </div>
                        ) : outreach.found === false ? <p className="text-red-700 font-medium text-sm">{outreach.reason}</p> : (
                          <div className="grid lg:grid-cols-[1fr_300px] gap-5">
                            <div className="bg-paper border border-ink/15 rounded-xl p-5">
                              <div className="label">Subject</div>
                              <div className="font-head font-semibold text-lg mt-0.5">{outreach.subject}</div>
                              <pre className="text-sm whitespace-pre-wrap font-body text-ink/80 mt-3 leading-relaxed">{outreach.body}</pre>
                            </div>
                            <aside className="space-y-3">
                              <div className="bg-sheet border border-ink/15 rounded-xl p-4 font-mono text-[11px] text-smoke">STATUS <b className="text-ink">{outreach.status || 'draft'}</b><br />APPROVAL <b className="text-ink">{outreach.approval_id ? 'pending' : '—'}</b></div>
                              {outreach.outreach_id && <button className="btnk btnk-ink w-full !py-2 !text-sm" onClick={() => run('Approving', () => api.approveOutreach(outreach.outreach_id))}>Approve</button>}
                              {outreach.outreach_id && <button className="btnk btnk-line w-full !py-2 !text-sm" onClick={() => run('Creating Gmail draft', async () => { const r = await api.draftOutreach(outreach.outreach_id); setMsg(JSON.stringify(r.data || r).slice(0, 300)); })}>Gmail draft / .eml</button>}
                              {outreach.outreach_id && outreach.approval_id && <button className="btnk btnk-line w-full !py-2 !text-sm" onClick={() => run('Sending', () => api.sendOutreach(outreach.outreach_id, outreach.approval_id))}>Send (approved only)</button>}
                              <p className="text-xs text-smoke">Nothing sends before approval. No Gmail OAuth → use the .eml.</p>
                            </aside>
                          </div>
                        )}
                      </div>
                    )}
                    {detailTab === 'activity' && <ActivityList oppId={detail._id} />}
                  </motion.div>
                </AnimatePresence>
                <InvestigationFull detail={detail} />
              </div>
            </div>
          </div>
          )
        )}

        {tab === 'activity' && (
          <section className="panel-flat !p-0 overflow-hidden">
            <div className="px-5 pt-4 pb-3 border-b border-ink/10"><div className="label">Crew log</div><h3 className="console-h text-lg font-bold">Timeline</h3></div>
            <div className="px-5 py-2">
              {activity.map((r, i) => (
                <div key={i} className="flex gap-4 py-2.5 rowline">
                  <div className="flex flex-col items-center pt-1">
                    <span className="w-2 h-2 rounded-full bg-signal shrink-0" />
                    {i < activity.length - 1 && <span className="w-px flex-1 bg-ink/15 mt-1" />}
                  </div>
                  <div className="min-w-0 pb-1">
                    <div className="font-mono text-[10px] uppercase tracking-widest text-smoke">{r.agent} · {r.ts}</div>
                    <div className="font-head font-semibold text-[15px]">{r.action}</div>
                    <div className="text-[13px] text-ink/60 truncate">{r.summary} {r.tool && <span className="font-mono text-[11px]">· {r.tool} {r.latency_ms}ms</span>}</div>
                  </div>
                </div>
              ))}
              {activity.length === 0 && <p className="py-6 text-sm text-smoke">No activity yet.</p>}
            </div>
          </section>
        )}

        {tab === 'approvals' && (
          <section className="panel-flat !p-0 overflow-hidden">
            <div className="px-5 pt-4 pb-3 border-b border-ink/10"><div className="label">Gate</div><h3 className="console-h text-lg font-bold">Nothing external happens before you approve</h3></div>
            {approvals.map((a) => (
              <div key={a._id} className="grid lg:grid-cols-[1fr_220px] gap-4 px-5 py-4 rowline">
                <div className="min-w-0">
                  <div className="font-head font-semibold">{a.summary}</div>
                  <div className="font-mono text-[11px] text-smoke mt-0.5">{a.type} · {a.status}</div>
                  {a.payload?.body && <p className="text-[13px] text-ink/60 mt-2 line-clamp-2">{a.payload.body}</p>}
                </div>
                <div className="flex lg:flex-col gap-2 lg:justify-center">
                  <button className="btnk btnk-ink flex-1 !py-2 !text-sm" onClick={() => run('Approving', () => api.decideApproval(a._id, 'approved'))}>Approve</button>
                  <button className="btnk btnk-line flex-1 !py-2 !text-sm" onClick={() => run('Rejecting', () => api.decideApproval(a._id, 'rejected'))}>Reject</button>
                </div>
              </div>
            ))}
            {approvals.length === 0 && <p className="px-5 py-8 text-sm text-smoke">Inbox zero. Drafts waiting on you will land here.</p>}
          </section>
        )}

        {tab === 'monitoring' && (
          <div className="grid lg:grid-cols-2 gap-5">
            <Section kicker="Watchlist" title="Jobs you watch">
              {monitoring.map((m) => (
                <div key={m._id} className="rowline py-2.5 flex justify-between items-center gap-2">
                  <span className="font-mono text-xs truncate">{m.opportunity_id} <span className="text-smoke">· {m.last_checked ? `checked ${m.last_checked.slice(0, 10)}` : 'never checked'}</span></span>
                  <button className="btnk btnk-line !py-1 !px-3 !text-xs shrink-0" onClick={() => run('Checking', () => api.checkNow(m.opportunity_id))}>Check</button>
                </div>
              ))}
              {monitoring.length === 0 && <p className="text-sm text-smoke">Empty — open a job and hit Watch.</p>}
            </Section>
            <Section kicker="Signals" title="Updates">
              {notifs.map((n, i) => <div key={i} className="rowline py-2 text-sm"><span className="inline-block w-1.5 h-1.5 rounded-full bg-signal mr-2" />{n.message}</div>)}
              {notifs.length === 0 && <p className="text-sm text-smoke">No signals.</p>}
            </Section>
          </div>
        )}

        {tab === 'setup' && <Setup profile={profile} health={health} onDone={() => load(true)} run={run} uid={id} />}
      </main>
      )}
      {tab !== 'chat' && (
      <footer className="max-w-6xl mx-auto px-6 pb-8 font-mono text-[10px] uppercase tracking-[0.2em] text-smoke flex justify-between">
        <span>Pursuit console</span><span>evidence-backed · approval-gated</span>
      </footer>
      )}
    </div>
  );
}

const GREET = "Hey — tell me what job you want and I'll go find it. Try: 'Find AI internships in India for me'.";
const chatKey = (uid) => `oi_chats_${uid}`;

function ChatView({ uid, onOpen, onNav }) {
  const [convos, setConvos] = useState(() => {
    try {
      const raw = JSON.parse(localStorage.getItem(chatKey(uid)) || '[]');
      if (Array.isArray(raw) && raw.length) return raw;
    } catch {}
    return [{ id: 'c' + Date.now(), title: 'New chat', updated: Date.now(),
              messages: [{ role: 'assistant', text: GREET }] }];
  });
  const [activeId, setActiveId] = useState(null);
  const [box, setBox] = useState('');
  const [sending, setSending] = useState(false);
  const [stage, setStage] = useState(0);
  const [left, setLeft] = useState(null);
  const [sideOpen, setSideOpen] = useState(false);
  const [rail, setRail] = useState(false);
  const [copied, setCopied] = useState(-1);
  const bottom = useRef(null);
  const abortRef = useRef(null);

  const active = convos.find((c) => c.id === (activeId || convos[0]?.id)) || convos[0];
  const thread = active?.messages || [];

  useEffect(() => { api.health().then((h) => setLeft(h.budget.remaining)).catch(() => {}); }, []);
  useEffect(() => {
    try { localStorage.setItem(chatKey(uid), JSON.stringify(convos.slice(0, 20))); } catch {}
  }, [convos]);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [thread, sending, activeId]);

  const patch = (id, fn) => setConvos((cs) => cs.map((c) => c.id === id ? { ...c, messages: fn(c.messages), updated: Date.now() } : c));
  const newChat = () => {
    const c = { id: 'c' + Date.now(), title: 'New chat', updated: Date.now(),
                messages: [{ role: 'assistant', text: GREET }] };
    setConvos((cs) => [c, ...cs]);
    setActiveId(c.id);
    setSideOpen(false);
  };
  const delChat = (id) => setConvos((cs) => {
    const rest = cs.filter((c) => c.id !== id);
    if (!rest.length) return [{ id: 'c' + Date.now(), title: 'New chat', updated: Date.now(), messages: [{ role: 'assistant', text: GREET }] }];
    if (id === (activeId || cs[0]?.id)) setActiveId(rest[0].id);
    return rest;
  });
  const titleOf = (c) => {
    const u = c.messages.find((m) => m.role === 'user');
    return u ? (u.text.length > 34 ? u.text.slice(0, 34) + '…' : u.text) : 'New chat';
  };

  const send = async (raw, regen) => {
    const t = (raw ?? box).trim();
    if (!t || sending || !active) return;
    const id = active.id;
    let hist;
    if (regen) {
      const idx = [...active.messages].map((m) => m.role).lastIndexOf('user');
      const keep = idx >= 0 ? active.messages.slice(0, idx) : active.messages;
      hist = keep.filter((m) => m.text).map((m) => ({ role: m.role, content: m.text })).slice(-10);
      setConvos((cs) => cs.map((c) => c.id === id ? { ...c, messages: [...keep, { role: 'user', text: t }], updated: Date.now() } : c));
    } else {
      hist = thread.filter((m) => m.text).map((m) => ({ role: m.role, content: m.text })).slice(-10);
      patch(id, (ms) => [...ms, { role: 'user', text: t }]);
    }
    setBox('');
    setSending(true);
    setStage(0);
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    const timers = [
      setTimeout(() => setStage(1), 4000),
      setTimeout(() => setStage(2), 15000),
      setTimeout(() => setStage(3), 35000),
    ];
    try {
      const r = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: t, user_id: uid, history: hist }), signal: ctrl.signal }).then((x) => x.json());
      if (r.detail) throw new Error(r.detail);
      let cards = [];
      if ((r.data?.cards || []).length) {
        const all = await api.listOpps(uid);
        cards = (all.data || []).filter((o) => r.data.cards.includes(o._id));
      }
      if (typeof r.data?.budget?.remaining === 'number') setLeft(r.data.budget.remaining);
      const tools = (r.data?.tool_calls || []).filter((x) => x.status !== 'error');
      patch(id, (ms) => [...ms, { role: 'assistant', text: r.data.reply, cards, tools }]);
      if (r.data?.navigate && onNav) setTimeout(() => onNav(r.data.navigate), 650);
    } catch (e) {
      if (e?.name === 'AbortError') {
        patch(id, (ms) => [...ms, { role: 'assistant', text: 'Stopped. Anything already saved is still under Jobs.' }]);
      } else {
        patch(id, (ms) => [...ms, { role: 'assistant', text: `Something broke: ${e.message} — try Search on Home instead.` }]);
      }
    } finally {
      timers.forEach(clearTimeout);
      abortRef.current = null;
      setSending(false);
    }
  };
  const stop = () => abortRef.current?.abort();
  const regen = () => {
    const u = [...thread].reverse().find((m) => m.role === 'user');
    if (u) send(u.text, true);
  };
  const copy = async (text, i) => {
    try { await navigator.clipboard.writeText(text); } catch {
      const ta = document.createElement('textarea');
      ta.value = text; document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); } catch {}
      ta.remove();
    }
    setCopied(i);
    setTimeout(() => setCopied(-1), 1200);
  };
  const chatJobs = thread.flatMap((m) => m.cards || []).filter((o, i, a) => a.findIndex((x) => x._id === o._id) === i);

  return (
    <div className="flex h-full min-h-0">
      {/* sidebar — closable to a slim rail */}
      <aside className={`${sideOpen ? 'absolute inset-y-0 left-0 z-30 w-64 shadow-lift bg-[#ECE7DB]' : 'hidden'} md:flex ${rail ? 'md:w-14' : 'md:w-64'} shrink-0 flex-col bg-[#ECE7DB] border-r border-ink/10 transition-all duration-200`}>
        {rail ? (
          <div className="hidden md:flex flex-col items-center py-3 gap-2">
            <button onClick={() => setRail(false)} aria-label="Expand sidebar" className="font-mono text-sm border border-ink/20 rounded-lg w-9 h-9 grid place-items-center hover:border-ink transition-colors">›</button>
            <button onClick={newChat} aria-label="New chat" className="font-head font-bold text-lg bg-ink text-paper rounded-lg w-9 h-9 grid place-items-center hover:bg-moss transition-colors">+</button>
            {chatJobs.length > 0 && <span className="font-mono text-[10px] bg-signal rounded-full min-w-[20px] h-5 px-1 grid place-items-center">{chatJobs.length}</span>}
          </div>
        ) : (
          <>
            <div className="p-3 border-b border-ink/10 flex gap-2">
              <button onClick={newChat} className="btnk btnk-ink flex-1 !py-2 !text-sm">+ New chat</button>
              <button onClick={() => setRail(true)} aria-label="Collapse sidebar" className="hidden md:block font-mono text-sm border border-ink/20 rounded-xl px-2.5 hover:border-ink transition-colors">‹</button>
              <button onClick={() => setSideOpen(false)} aria-label="Close chats" className="md:hidden font-mono text-sm border border-ink/20 rounded-xl px-2.5">✕</button>
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
              <div className="label px-2 pt-1 pb-1.5">Chats</div>
              {convos.map((c) => (
              <div key={c.id} className={`group flex items-center rounded-lg ${c.id === active?.id ? 'bg-[#E8E3D9]' : 'hover:bg-[#E8E3D9]/60'}`}>
                <button onClick={() => { setActiveId(c.id); setSideOpen(false); }} className={`flex-1 text-left px-3 py-2 text-[13px] truncate ${c.id === active?.id ? 'font-semibold' : 'font-medium'}`}>
                  {titleOf(c)}
                </button>
                <button onClick={() => delChat(c.id)} aria-label="Delete chat"
                  className="px-2 text-xs opacity-0 group-hover:opacity-100 text-smoke">✕</button>
              </div>
              ))}
              <div className="label px-2 pt-3 pb-1.5">Jobs in this chat · {chatJobs.length}</div>
              {chatJobs.map((o) => (
                <button key={o._id} onClick={() => onOpen(o._id)} className="w-full text-left px-3 py-2 rounded-lg hover:bg-[#E8E3D9]/70 transition-colors">
                  <div className="font-head font-semibold text-[13px] truncate">{o.title}</div>
                  <div className="font-mono text-[10px] text-smoke truncate">{o.organization || 'Company unknown'}{o.match ? ` · ${Math.round(o.match.score * 100)}% fit` : ''}</div>
                </button>
              ))}
              {!chatJobs.length && <div className="px-3 py-1 text-xs text-smoke">Jobs I find here will pin to this list.</div>}
            </div>
            <div className="p-3 border-t border-ink/10 font-mono text-[10px] text-smoke">Budget {left !== null ? `${left} left` : '…'} · history on this device</div>
          </>
        )}
      </aside>

      {/* thread */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex md:hidden items-center gap-2 px-3 py-2 border-b border-ink/10">
          <button onClick={() => setSideOpen((v) => !v)} className="font-mono text-xs border border-ink/20 rounded-lg px-2.5 py-1">☰ Chats</button>
          <span className="text-xs text-smoke truncate">{active ? titleOf(active) : ''}</span>
        </div>
        <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-5 space-y-4">
          {thread.map((m, i) => (
            <div key={i} className={`mx-auto w-full max-w-3xl flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[88%] sm:max-w-[78%] ${m.role === 'user'
                ? 'bg-[#E8E3D9] text-ink rounded-2xl rounded-br-md px-4 py-2.5 text-[15px]'
                : 'bg-[#FAF9F5] border border-ink/15 rounded-2xl rounded-bl-md px-4 py-3 text-[15px] leading-relaxed shadow-card'}`}>
                <p className="whitespace-pre-wrap">{m.text}</p>
                {!!(m.tools || []).length && (
                  <div className="font-mono text-[11px] text-smoke mt-2 pt-2 border-t border-ink/10">
                    {m.tools.map((t, j) => <span key={j} className="mr-2">✓ {t.tool.replaceAll('search_', '').replaceAll('_', ' ')}</span>)}
                  </div>
                )}
                {!!(m.cards || []).length && (
                  <div className="mt-2.5 space-y-1.5">
                    {m.cards.map((o) => (
                      <button key={o._id} onClick={() => onOpen(o._id)}
                        className="w-full text-left bg-sheet border border-ink/15 rounded-xl px-3.5 py-2.5 hover:border-ink transition-colors">
                        <div className="font-head font-semibold text-sm truncate">{o.title}</div>
                        <div className="font-mono text-[11px] text-smoke truncate">{o.organization || 'Company unknown'}{o.match ? ` · ${Math.round(o.match.score * 100)}% fit` : ''}</div>
                      </button>
                    ))}
                  </div>
                )}
                {m.role === 'assistant' && m.text !== GREET && (
                  <div className="flex gap-1.5 mt-2">
                    <button onClick={() => copy(m.text, i)} className="font-mono text-[10px] uppercase tracking-widest text-smoke hover:text-ink">
                      {copied === i ? 'copied ✓' : 'copy'}
                    </button>
                    {i === thread.length - 1 && <button onClick={regen} disabled={sending} className="font-mono text-[10px] uppercase tracking-widest text-smoke hover:text-ink">↻ retry</button>}
                  </div>
                )}
              </div>
            </div>
          ))}
          {sending && (
            <div className="mx-auto w-full max-w-3xl flex justify-start">
              <div className="bg-paper border border-ink/15 rounded-2xl rounded-bl-md px-4 py-3">
                <div className="flex gap-1.5">
                  {[0, 1, 2].map((d) => <span key={d} className="w-2 h-2 rounded-full bg-ink/30 animate-blink" style={{ animationDelay: `${d * 0.25}s` }} />)}
                </div>
                <div className="font-mono text-[11px] text-smoke mt-1.5" aria-live="polite">
                  {['Thinking…', 'Searching live sources…', 'Reading results…', 'Checking fit & writing…'][stage]}
                </div>
              </div>
            </div>
          )}
          <div ref={bottom} />
        </div>
        {thread.length <= 1 && (
          <div className="mx-auto w-full max-w-3xl px-4 sm:px-6 pb-2 flex gap-1.5 flex-wrap">
            {['Find AI internships in India for me', 'Any new ML jobs this week?', 'Show my best fits'].map((s) => (
              <button key={s} onClick={() => send(s)} className="tag hover:bg-sun transition-colors">{s}</button>
            ))}
          </div>
        )}
        <div className="border-t border-ink/10 px-4 sm:px-6 py-3">
          <div className="flex gap-2 mx-auto w-full max-w-3xl">
            <input value={box} onChange={(e) => setBox(e.target.value)} placeholder="Ask for jobs like you'd ask a friend…"
              aria-label="Chat message" className="field"
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }} />
            <button disabled={sending || !box.trim()} onClick={() => send()} className="btnk btnk-signal !px-6 shrink-0" aria-label="Send">↑</button>
            {sending && <button onClick={stop} className="btnk btnk-line !px-4 shrink-0" aria-label="Stop response">■</button>}
          </div>
          <div className="font-mono text-[10px] text-smoke mt-1.5 mx-auto w-full max-w-3xl">Live searches spend SerpApi budget{left !== null ? ` · ${left} left` : ''} · links are real postings, never made up</div>
        </div>
      </div>
    </div>
  );
}

function InvestigationFull({ detail }) {
  const inv = detail.investigation || {};
  const ver = detail.verification?.fields || {};
  const people = inv.people_found || [];
  const news = inv.recent_developments || [];
  const missing = inv.missing_information || [];
  const hasAny = inv.organization_summary || people.length || news.length || Object.keys(ver).length;
  if (!hasAny) return null;
  return (
    <section className="border-t border-ink/10 pt-4">
      <div className="flex items-center justify-between gap-2 mb-3">
        <h4 className="font-head font-bold text-lg">Investigation</h4>
        {!!Object.keys(ver).length && (
          <div className="flex gap-1.5 flex-wrap justify-end">
            {Object.entries(ver).map(([f, v]) => (
              <span key={f} title={f} className="tag !text-[10px]">{f.slice(0, 4)} · {v.state}</span>
            ))}
          </div>
        )}
      </div>
      {inv.organization_summary && (
        <p className="text-[15px] leading-relaxed text-ink/80 max-w-4xl">{inv.organization_summary}</p>
      )}
      <div className="grid sm:grid-cols-2 gap-4 mt-4">
        {!!people.length && (
          <div>
            <div className="label mb-1.5">People</div>
            {people.slice(0, 4).map((p, i) => (
              <div key={i} className="rowline py-2">
                <div className="font-semibold text-sm">{p.name}</div>
                <div className="text-xs text-ink/60">{p.context}</div>
                {p.url && <a className="text-signal text-xs font-semibold" href={p.url} target="_blank" rel="noreferrer">open ↗</a>}
              </div>
            ))}
          </div>
        )}
        {!!news.length && (
          <div>
            <div className="label mb-1.5">Fresh signals</div>
            {news.slice(0, 4).map((n, i) => (
              <a key={i} href={n.url} target="_blank" rel="noreferrer" className="rowline py-2 block hover:text-ink">
                <div className="font-semibold text-sm">{n.title}</div>
                <div className="font-mono text-[11px] text-smoke">{n.date || ''}</div>
              </a>
            ))}
          </div>
        )}
      </div>
      {!!missing.length && (
        <div className="mt-3 flex flex-wrap gap-1.5 items-center">
          <span className="font-mono text-[11px] text-smoke">Still unknown:</span>
          {missing.map((m) => <span key={m} className="tag !text-[10px]">{m}</span>)}
        </div>
      )}
    </section>
  );
}

function ResumeBuilder({ oid, uid, gaps }) {
  const [qs, setQs] = useState(null);
  const [answers, setAnswers] = useState({});
  const [resume, setResume] = useState(null);
  const [aid, setAid] = useState(null);
  const [mode, setMode] = useState('');
  const [changes, setChanges] = useState([]);
  const [docx, setDocx] = useState(false);
  const [tpl, setTpl] = useState(null);
  const [keepTpl, setKeepTpl] = useState(true);
  const [busy, setBusy] = useState('');
  const [err, setErr] = useState('');

  useEffect(() => { api.templateInfo(uid).then((r) => setTpl(r.data)).catch(() => {}); }, [uid, oid]);

  const ask = async () => {
    try { setBusy('ask'); setErr(''); const r = await api.resumeQuestions(oid, uid); setQs(r.data.questions || []); setMode(r.data.mode); }
    catch (e) { setErr(e.message); } finally { setBusy(''); }
  };
  const build = async () => {
    try {
      setBusy('build'); setErr('');
      const payload = (qs || []).map((q) => ({ id: q.id, question: q.question, answer: answers[q.id] || '' }));
      const r = await api.buildResume(oid, uid, payload, keepTpl && tpl?.type === 'docx');
      setResume(r.data.resume); setAid(r.data.application_id); setMode(r.data.mode);
      setChanges(r.data.changes || []); setDocx(!!r.data.docx_available);
    } catch (e) { setErr(e.message); } finally { setBusy(''); }
  };
  const download = async (kind) => {
    const ext = kind === 'docx' ? 'docx' : 'pdf';
    const r = await fetch(`/api/applications/${aid}/resume.${ext}`);
    if (!r.ok) { setErr(kind === 'docx' ? 'DOCX not ready — rebuild with template kept.' : 'PDF not ready yet.'); return; }
    const blob = await r.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `Pursuit_${(resume?.name || 'resume').replace(/\s+/g, '_')}${kind === 'docx' ? '_edited' : ''}.${ext}`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  };

  return (
    <div className="bg-ink text-paper rounded-xl p-5 mb-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-sun">Resume builder · LLM only, zero searches</div>
          <h4 className="font-head font-bold text-xl mt-0.5">Get interrogated. Get hired.</h4>
          <p className="text-[13px] text-paper/65 mt-1 max-w-xl">The agent studies the gaps{(gaps || []).length ? `: ${gaps.slice(0, 4).join(', ')}` : ''}, cross-examines you, then writes a resume using <b>only</b> what you confirm. Say no — it stays out.</p>
          {tpl?.has_template && (
            <label className="flex items-center gap-2 mt-2.5 cursor-pointer w-fit">
              <input type="checkbox" checked={keepTpl && tpl.type === 'docx'} disabled={tpl.type !== 'docx'}
                onChange={(e) => setKeepTpl(e.target.checked)} className="accent-[#FF4D00] w-4 h-4" />
              <span className="font-mono text-[11px] text-paper/80">
                {tpl.type === 'docx'
                  ? `Keep my resume's template (${(tpl.sections || []).slice(0, 4).join(' · ')}${(tpl.sections || []).length > 4 ? '…' : ''})`
                  : 'PDF on file — edits come back in your section order + a change list (upload .docx for pixel-true template editing)'}
              </span>
            </label>
          )}
        </div>
        {!qs && <button disabled={busy === 'ask'} onClick={ask} className="btnk btnk-signal shrink-0">{busy === 'ask' ? <span className="spinner" /> : 'Analyze gaps & ask me →'}</button>}
      </div>
      {err && <div className="text-sm text-red-300 mt-3">⚠ {err}</div>}
      {!!(qs || []).length && !resume && (
        <div className="mt-4 space-y-3">
          {qs.map((q, i) => (
            <div key={q.id || i} className="bg-paper/5 border border-paper/15 rounded-xl p-3.5">
              <div className="text-[15px] font-semibold"><span className="font-mono text-xs text-sun mr-2">Q{i + 1}</span>{q.question}</div>
              {q.why && <div className="font-mono text-[11px] text-paper/50 mt-0.5">why: {q.why}</div>}
              {!!(q.options || []).length && (
                <div className="flex gap-1.5 flex-wrap mt-2">
                  {q.options.map((o) => (
                    <button key={o} onClick={() => setAnswers({ ...answers, [q.id]: o })}
                      className={`tag !text-[11px] transition-colors ${answers[q.id] === o ? '!bg-signal !border-signal text-ink' : '!border-paper/30 text-paper/75 hover:!border-signal'}`}>{o}</button>
                  ))}
                </div>
              )}
              <input value={answers[q.id] || ''} onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })}
                placeholder="Or type details (metrics, years, links)…" className="w-full mt-2 bg-transparent border-b border-paper/25 focus:border-signal focus:outline-none text-sm py-1.5 placeholder:text-paper/30" />
            </div>
          ))}
          <button disabled={busy === 'build'} onClick={build} className="btnk btnk-signal w-full !py-3">
            {busy === 'build' ? <span className="spinner" /> : 'Generate my resume →'}
          </button>
        </div>
      )}
      {resume && (
        <div className="mt-4">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <span className="font-mono text-[11px] text-paper/60">built ({mode}) · nothing invented — only your confirmations</span>
            <div className="flex gap-2">
              <button onClick={() => { setResume(null); }} className="font-mono text-[11px] uppercase tracking-widest text-paper/60 hover:text-paper">↻ redo answers</button>
              {docx && <button onClick={() => download('docx')} className="btnk btnk-signal !py-2 !text-sm">My template, edited ↓ .docx</button>}
              {!docx && <button onClick={() => download('pdf')} className="btnk btnk-signal !py-2 !text-sm">Download PDF ↓</button>}
            </div>
          </div>
          {!!changes.length && (
            <div className="mt-3">
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-paper/50 mb-1.5">What changed in your template</div>
              {changes.map((c, i) => (
                <div key={i} className="text-[13px] py-1 border-b border-paper/10 last:border-0">
                  <b className="text-sun">{c.section}</b><span className="text-paper/75"> — {c.change}</span>
                </div>
              ))}
            </div>
          )}
          <div className="mt-3 bg-[#FAF9F5] text-ink rounded-lg p-6 max-h-[420px] overflow-y-auto">
            <div className="text-center font-bold text-lg">{resume.name}</div>
            <div className="text-center font-mono text-[11px] text-smoke mt-0.5">{[resume.email, resume.phone, resume.location].filter(Boolean).join(' · ')}</div>
            {resume.summary && <p className="text-[13px] mt-3 leading-relaxed">{resume.summary}</p>}
            {!!(resume.experience || []).length && <><div className="label mt-3">Experience</div>{resume.experience.map((e, i) => <div key={i} className="text-[13px] mt-1"><b>{e.title}</b>{e.company ? ` — ${e.company}` : ''} <span className="text-smoke">{e.years || ''}</span></div>)}</>}
            {!!(resume.skills || []).length && <><div className="label mt-3">Skills</div><div className="text-[13px]">{resume.skills.join(', ')}</div></>}
            {!!(resume.education || []).length && <><div className="label mt-3">Education</div>{resume.education.map((e, i) => <div key={i} className="text-[13px]">{[e.degree, e.field, e.school, e.years].filter(Boolean).join(' · ')}</div>)}</>}
          </div>
        </div>
      )}
    </div>
  );
}

function PrepRoadmap({ materials, gaps, checked, setChecked }) {
  const m = materials || {};
  const tips = m.resume_tips || [];
  const plan = m.prep_plan || [];
  const list = m.checklist || [];
  const toggle = (k) => setChecked((c) => ({ ...c, [k]: !c[k] }));
  const doneCount = list.filter((_, i) => checked['c' + i]).length;
  return (
    <div className="space-y-5">
      {!!gaps.length && (
        <div className="bg-sun/30 border border-ink/15 rounded-xl px-4 py-3 text-sm">
          <b className="font-head">Roadmap target — close these gaps:</b> {gaps.join(', ')}
        </div>
      )}
      {!!plan.length && (
        <div>
          <div className="label mb-2">Week-by-week plan</div>
          <div className="space-y-0">
            {plan.map((p, i) => (
              <div key={i} className="flex gap-3">
                <div className="flex flex-col items-center">
                  <span className="w-7 h-7 rounded-full bg-ink text-paper grid place-items-center font-mono text-[11px] font-bold shrink-0">W{i + 1}</span>
                  {i < plan.length - 1 && <span className="w-px flex-1 bg-ink/20 my-1" />}
                </div>
                <p className="text-sm pb-5 pt-1 text-ink/80">{p}</p>
              </div>
            ))}
          </div>
        </div>
      )}
      {!!tips.length && (
        <div>
          <div className="label mb-2">Resume fixes</div>
          {tips.map((t, i) => (
            <div key={i} className="rowline py-2 text-sm flex gap-2.5">
              <button onClick={() => toggle('t' + i)} aria-label="mark done"
                className={`w-4.5 h-4.5 w-[18px] h-[18px] rounded border mt-0.5 shrink-0 grid place-items-center text-[11px] ${checked['t' + i] ? 'bg-moss text-paper border-moss' : 'border-ink/30'}`}>
                {checked['t' + i] ? '✓' : ''}
              </button>
              <span className={checked['t' + i] ? 'line-through text-smoke' : ''}>{t}</span>
            </div>
          ))}
        </div>
      )}
      {!!list.length && (
        <div>
          <div className="label mb-2">Before you hit send · {doneCount}/{list.length}</div>
          <div className="h-1.5 rounded-full bg-ink/10 overflow-hidden mb-2"><div className="h-full bg-moss rounded-full transition-all" style={{ width: `${Math.round((doneCount / list.length) * 100)}%` }} /></div>
          {list.map((t, i) => (
            <label key={i} className="rowline py-2 text-sm flex gap-2.5 cursor-pointer">
              <input type="checkbox" checked={!!checked['c' + i]} onChange={() => toggle('c' + i)} className="mt-1 accent-[#0C3B2E]" />
              <span className={checked['c' + i] ? 'line-through text-smoke' : ''}>{t}</span>
            </label>
          ))}
        </div>
      )}
      {m.cover_letter && (
        <details className="bg-paper border border-ink/15 rounded-xl overflow-hidden">
          <summary className="px-4 py-3 font-head font-semibold text-sm cursor-pointer hover:bg-sheet">Cover letter — click to read & copy</summary>
          <pre className="px-4 pb-4 text-[13px] whitespace-pre-wrap font-body text-ink/80 leading-relaxed border-t border-ink/10 pt-3">{m.cover_letter}</pre>
        </details>
      )}
      {!plan.length && !tips.length && !list.length && !m.cover_letter && (
        <p className="text-sm text-smoke">Empty pack — hit Prepare again to rebuild it.</p>
      )}
    </div>
  );
}

function ActivityList({ oppId }) {
  const [rows, setRows] = useState([]);
  useEffect(() => { api.oppActivity(oppId).then((r) => setRows(r.data || [])).catch(() => {}); }, [oppId]);
  return (
    <div>
      {rows.map((r, i) => <div key={i} className="rowline py-2 font-mono text-xs"><b>{r.agent}</b> · {r.action} — <span className="text-ink/60">{r.summary}</span></div>)}
      {rows.length === 0 && <p className="text-sm text-smoke">No runs for this role yet.</p>}
    </div>
  );
}

import { Drop, Field, SUGGESTED } from '../components/profileForm.jsx';

function FormSec({ n, t, action, children }) {
  return (
    <div className="mt-5 first:mt-4">
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-baseline gap-2.5">
          <span className="font-mono text-[11px] font-bold text-signal">{n}</span>
          <h4 className="font-head font-bold text-[17px]">{t}</h4>
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}
function AddBtn({ onClick, label }) {
  return <button onClick={onClick} className="font-mono text-[11px] uppercase tracking-widest text-smoke hover:text-ink border border-dashed border-ink/30 hover:border-ink rounded-lg px-2.5 py-1 transition-colors">+ {label}</button>;
}
function EmptyNote({ t }) {
  return <p className="text-[13px] text-smoke border border-dashed border-ink/20 rounded-xl px-3.5 py-2.5">{t}</p>;
}
function Setup({ profile, health, onDone, run, uid }) {
  const [personal, setPersonal] = useState({ name: '', email: '', phone: '', location: '', linkedin: '', github: '', website: '' });
  const [edu, setEdu] = useState([]);
  const [exp, setExp] = useState([]);
  const [skills, setSkills] = useState([]);
  const [skillIn, setSkillIn] = useState('');
  const [workTypes, setWorkTypes] = useState([]);
  const [relocate, setRelocate] = useState(false);
  const [seeded, setSeeded] = useState(false);
  const [touched, setTouched] = useState(false);
  const [savedAt, setSavedAt] = useState('');
  const [resume, setResume] = useState('');
  const [resumeNote, setResumeNote] = useState('');
  const [resumeFile, setResumeFile] = useState(null);
  const [fillNote, setFillNote] = useState('');

  const P = (k, v) => { setPersonal((p) => ({ ...p, [k]: v })); setTouched(true); };

  useEffect(() => {
    if (profile && !seeded) {
      setSeeded(true);
      setPersonal({
        name: profile.name || '', email: profile.email || '', phone: profile.phone || '',
        location: profile.location || '', linkedin: profile.links?.linkedin || '',
        github: profile.links?.github || '', website: profile.links?.website || '',
      });
      setEdu((profile.education || []).map((e) => typeof e === 'string'
        ? { school: e, degree: '', field: '', years: '' }
        : { school: e.school || e.raw || '', degree: e.degree || '', field: e.field || '', years: e.years || '' }));
      setExp((profile.experience || []).map((e) => typeof e === 'string'
        ? { title: e, company: '', years: '', summary: '' }
        : { title: e.title || e.raw || '', company: e.company || '', years: e.years || '', summary: e.summary || '' }));
      setSkills(profile.skills || []);
      setWorkTypes(profile.preferences?.work_types || []);
      setRelocate(!!profile.preferences?.relocate);
    }
  }, [profile]);

  const matchLoc = (raw) => {
    if (!raw) return '';
    const hit = LOCATIONS.find((l) => raw.toLowerCase().includes(l.split(',')[0].toLowerCase()) || l.toLowerCase().includes(raw.toLowerCase().split(',')[0]));
    return hit || raw.slice(0, 80);
  };

  const autofill = async (kind) => {
    setFillNote('');
    await run(kind === 'file' ? 'Autofilling from resume' : 'Autofilling from pasted text', async () => {
      const r = kind === 'file' ? await api.resumeFile(uid, resumeFile) : await api.resumeText(uid, resume);
      const p = r.data || {};
      setPersonal({
        name: p.name || '', email: p.email || '', phone: p.phone || '',
        location: matchLoc(p.location || ''), linkedin: p.links?.linkedin || '',
        github: p.links?.github || '', website: p.links?.website || p.links?.portfolio || '',
      });
      setEdu((p.education || []).map((e) => ({ school: e.school || e.raw || '', degree: e.degree || '', field: e.field || '', years: e.years || '' })).slice(0, 4));
      setExp((p.experience || []).map((e) => ({ title: e.title || '', company: e.company || '', years: e.years || '', summary: e.summary || '' })).slice(0, 6));
      setSkills(p.skills || []);
      const conf = p.parse_meta?.confidence || {};
      const verify = Object.entries(conf).filter(([, v]) => v === 'low').map(([k]) => k);
      const bits = [p.name && 'name', p.email && 'email', p.phone && 'phone', (p.skills || []).length && `${p.skills.length} skills`, (p.education || []).length && 'education', (p.experience || []).length && `${p.experience.length} roles`].filter(Boolean);
      setFillNote(bits.length
        ? `Autofilled ${bits.join(' · ')}${verify.length ? ` — verify: ${verify.join(', ')}` : ''}. Review, then save.`
        : 'Could not read much — fill the form manually.');
      setTouched(true);
      if (kind === 'file') setResumeFile(null);
      onDone();
    });
  };

  const addSkill = (s) => {
    const v = (s || '').trim().replace(/,+$/, '');
    if (!v || skills.some((x) => x.toLowerCase() === v.toLowerCase())) return;
    setSkills([...skills, v]); setTouched(true);
  };
  const save = () => run('Saving profile', async () => {
    await api.saveProfile({
      user_id: uid, name: personal.name, email: personal.email, phone: personal.phone,
      location: personal.location, links: { linkedin: personal.linkedin, github: personal.github, website: personal.website },
      education: edu.filter((e) => e.school || e.degree), experience: exp.filter((e) => e.title || e.company),
      skills, preferences: { ...(profile?.preferences || {}), work_types: workTypes, relocate },
    });
    setSavedAt(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
    setTouched(false);
    onDone();
  });
  return (
    <div>
      <Section title="Candidate profile" action={touched
        ? <span className="tag bg-sun">review & save</span>
        : savedAt ? <span className="font-mono text-[11px] text-moss">saved ✓ {savedAt}</span> : null}>
        {/* AUTOFILL */}
        <div className="deck !p-5 blueprint-dark">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-sun">Start here</div>
              <div className="font-head font-bold text-xl text-paper mt-0.5">Autofill from resume</div>
              <div className="text-[13px] text-paper/65 mt-0.5">Upload and watch every section below fill itself. Review, then save.</div>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <label className="btnk btnk-signal !py-2 !text-sm cursor-pointer">
                ↑ Upload resume
                <input type="file" accept=".pdf,.docx,.txt" className="hidden"
                  onChange={(e) => { const f = e.target.files?.[0]; if (f) { setResumeFile(f); } }} />
              </label>
            </div>
          </div>
          {(resumeFile || fillNote) && (
            <div className="flex items-center gap-2 mt-3 flex-wrap">
              {resumeFile && <>
                <span className="font-mono text-xs text-paper/80 truncate max-w-[240px]">{resumeFile.name}</span>
                <button className="btnk btnk-paper !py-1.5 !text-xs" onClick={() => autofill('file')}>Autofill now →</button>
              </>}
              {fillNote && <span className="font-mono text-[11px] text-sun">{fillNote}</span>}
            </div>
          )}
        </div>

        {/* 1 PERSONAL */}
        <FormSec n="01" t="Personal">
          <div className="grid sm:grid-cols-2 gap-2">
            <Field l="Full name *" v={personal.name} set={(v) => P('name', v)} ph="Aarav Sharma" />
            <Field l="Email *" v={personal.email} set={(v) => P('email', v)} ph="you@university.edu" />
            <Field l="Phone" v={personal.phone} set={(v) => P('phone', v)} ph="+91 98765 43210" />
            <div><span className="label">Location</span><div className="mt-1"><Drop value={personal.location} onPick={(l) => P('location', l)} /></div></div>
          </div>
        </FormSec>

        {/* 2 LINKS */}
        <FormSec n="02" t="Links">
          <div className="grid sm:grid-cols-3 gap-2">
            <Field l="LinkedIn" v={personal.linkedin} set={(v) => P('linkedin', v)} ph="linkedin.com/in/…" />
            <Field l="GitHub" v={personal.github} set={(v) => P('github', v)} ph="github.com/…" />
            <Field l="Website" v={personal.website} set={(v) => P('website', v)} ph="https://…" />
          </div>
        </FormSec>

        {/* 3 EDUCATION */}
        <FormSec n="03" t="Education" action={<AddBtn onClick={() => { setEdu([...edu, { school: '', degree: '', field: '', years: '' }]); setTouched(true); }} label="Add school" />}>
          {edu.map((e, i) => (
            <div key={i} className="grid sm:grid-cols-[1fr_1fr] gap-2 border border-ink/10 rounded-xl p-3 mb-2">
              <Field l="School" v={e.school} set={(v) => { const c = [...edu]; c[i] = { ...c[i], school: v }; setEdu(c); setTouched(true); }} ph="IIT Bombay" />
              <Field l="Degree" v={e.degree} set={(v) => { const c = [...edu]; c[i] = { ...c[i], degree: v }; setEdu(c); setTouched(true); }} ph="B.Tech" />
              <Field l="Field" v={e.field} set={(v) => { const c = [...edu]; c[i] = { ...c[i], field: v }; setEdu(c); setTouched(true); }} ph="Computer Science" />
              <div className="flex gap-2 items-end">
                <div className="flex-1"><Field l="Years" v={e.years} set={(v) => { const c = [...edu]; c[i] = { ...c[i], years: v }; setEdu(c); setTouched(true); }} ph="2024 – 2028" /></div>
                <button onClick={() => { setEdu(edu.filter((_, j) => j !== i)); setTouched(true); }} aria-label="Remove school" className="font-mono text-xs text-smoke hover:text-red-700 pb-2.5">✕</button>
              </div>
            </div>
          ))}
          {edu.length === 0 && <EmptyNote t="No schools yet — add one, or autofill from your resume." />}
        </FormSec>

        {/* 4 EXPERIENCE */}
        <FormSec n="04" t="Experience" action={<AddBtn onClick={() => { setExp([...exp, { title: '', company: '', years: '', summary: '' }]); setTouched(true); }} label="Add role" />}>
          {exp.map((e, i) => (
            <div key={i} className="grid sm:grid-cols-[1fr_1fr] gap-2 border border-ink/10 rounded-xl p-3 mb-2">
              <Field l="Title" v={e.title} set={(v) => { const c = [...exp]; c[i] = { ...c[i], title: v }; setExp(c); setTouched(true); }} ph="ML Intern" />
              <Field l="Company" v={e.company} set={(v) => { const c = [...exp]; c[i] = { ...c[i], company: v }; setExp(c); setTouched(true); }} ph="Acme AI" />
              <Field l="Years" v={e.years} set={(v) => { const c = [...exp]; c[i] = { ...c[i], years: v }; setExp(c); setTouched(true); }} ph="2025" />
              <div className="flex gap-2 items-end">
                <div className="flex-1"><Field l="Summary" v={e.summary} set={(v) => { const c = [...exp]; c[i] = { ...c[i], summary: v }; setExp(c); setTouched(true); }} ph="What you shipped" /></div>
                <button onClick={() => { setExp(exp.filter((_, j) => j !== i)); setTouched(true); }} aria-label="Remove role" className="font-mono text-xs text-smoke hover:text-red-700 pb-2.5">✕</button>
              </div>
            </div>
          ))}
          {exp.length === 0 && <EmptyNote t="No roles yet — students often leave this sparse; projects count." />}
        </FormSec>

        {/* 5 SKILLS */}
        <FormSec n="05" t="Skills">
          <div className="flex gap-1.5">
            <input className="field" placeholder="e.g. CUDA — Enter to add" value={skillIn}
              onChange={(e) => setSkillIn(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addSkill(skillIn); setSkillIn(''); } }} />
            <button onClick={() => { addSkill(skillIn); setSkillIn(''); }} className="btnk btnk-ink !px-4 shrink-0" aria-label="Add skill">+</button>
          </div>
          <div className="flex flex-wrap gap-1.5 mt-2.5 min-h-[2rem]" aria-live="polite">
            {skills.map((s) => (
              <span key={s} className="tag !py-1 bg-ink text-paper !border-ink">
                {s}
                <button onClick={() => { setSkills(skills.filter((x) => x !== s)); setTouched(true); }} aria-label={`Remove ${s}`}
                  className="ml-1.5 -mr-1 w-4 h-4 rounded-full grid place-items-center text-[10px] hover:bg-signal hover:text-ink transition-colors">✕</button>
              </span>
            ))}
            {skills.length === 0 && <span className="text-sm text-smoke">Empty — the match engine scores against these.</span>}
          </div>
          <div className="flex flex-wrap gap-1.5 mt-2">
            {SUGGESTED.filter((s) => !skills.some((x) => x.toLowerCase() === s.toLowerCase())).map((s) => (
              <button key={s} onClick={() => addSkill(s)} className="tag hover:bg-sun transition-colors">+ {s}</button>
            ))}
          </div>
        </FormSec>

        {/* 6 PREFERENCES */}
        <FormSec n="06" t="Work preferences">
          <div className="flex gap-2 flex-wrap">
            {['Remote', 'Onsite', 'Hybrid'].map((w) => (
              <button key={w} onClick={() => { setWorkTypes(workTypes.includes(w) ? workTypes.filter((x) => x !== w) : [...workTypes, w]); setTouched(true); }}
                aria-pressed={workTypes.includes(w)}
                className={`tag !py-1.5 !px-4 transition-colors ${workTypes.includes(w) ? 'bg-moss text-paper !border-moss' : 'hover:bg-sun'}`}>{w}</button>
            ))}
            <button onClick={() => { setRelocate(!relocate); setTouched(true); }} aria-pressed={relocate}
              className={`tag !py-1.5 !px-4 transition-colors ${relocate ? 'bg-moss text-paper !border-moss' : 'hover:bg-sun'}`}>Open to relocate</button>
          </div>
        </FormSec>

        <div className="sticky bottom-3 mt-4 flex items-center gap-3 bg-sheet/95 backdrop-blur border border-ink/20 rounded-xl px-4 py-3 shadow-lift">
          <button disabled={!touched} onClick={save} className="btnk btnk-signal !py-2.5 flex-1 !text-[15px]">Save candidate profile →</button>
          {touched
            ? <span className="font-mono text-[11px] text-smoke hidden sm:block">unsaved</span>
            : savedAt ? <span className="font-mono text-[11px] text-moss hidden sm:block">saved ✓ {savedAt}</span> : null}
        </div>

        <div className="mt-4">
          <span className="label">No file handy? Paste resume text instead</span>
          <textarea className="field mt-1" rows={3} placeholder="Paste resume / LinkedIn text…" value={resume} onChange={(e) => setResume(e.target.value)} />
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            <button className="btnk btnk-line !py-2 !text-sm" onClick={() => autofill('text')}>Autofill from pasted text</button>
            {resumeNote && <span className="font-mono text-[11px] text-moss">{resumeNote}</span>}
          </div>
        </div>
      </Section>
    </div>
  );
}
