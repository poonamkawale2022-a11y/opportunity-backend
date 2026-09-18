import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Mark } from '../components/chrome.jsx';
import { useAuth } from '../lib/auth.jsx';

function Shell({ title, blurb, children }) {
  return (
    <div className="min-h-[100svh] grid md:grid-cols-2">
      <div className="bg-moss text-paper blueprint-dark relative hidden md:flex flex-col justify-between p-12">
        <Link to="/"><Mark light /></Link>
        <div>
          <div className="display text-5xl leading-[0.95]">THE CONSOLE<br />IS WARM.</div>
          <p className="mt-5 max-w-sm text-paper/70">Eight agents on standby. Discover, verify, match, draft — then you call the shots.</p>
          <div className="mt-8 flex gap-2 font-mono text-[11px] uppercase tracking-widest text-paper/60">
            <span>DISCOVER →</span><span>VERIFY →</span><span className="text-sun">APPROVE →</span><span>MONITOR</span>
          </div>
        </div>
        <div className="font-mono text-[11px] uppercase tracking-widest text-paper/50">Pursuit // human-approved actions only</div>
      </div>
      <div className="flex flex-col justify-center px-6 sm:px-14 py-14 blueprint">
        <div className="md:hidden mb-8"><Link to="/"><Mark /></Link></div>
        <h1 className="display text-4xl sm:text-5xl">{title}</h1>
        <p className="mt-3 text-smoke max-w-sm">{blurb}</p>
        <div className="mt-8 max-w-md w-full">{children}</div>
      </div>
    </div>
  );
}

export function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [f, setF] = useState({ email: '', password: '' });
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const go = async (e) => {
    e.preventDefault();
    setErr('');
    if (!f.email.includes('@') || !f.password) { setErr('Enter the email and password you registered with.'); return; }
    try { setBusy(true); await login(f); nav('/app'); }
    catch (ex) { setErr(ex.message + ' — check the email, or sign up below.'); }
    finally { setBusy(false); }
  };
  return (
    <Shell title="LOG BACK IN." blurb="Your missions, watchlists and drafts are where you left them.">
      <form onSubmit={go} className="space-y-4">
        <input className="field" placeholder="you@university.edu" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} autoComplete="email" />
        <input className="field" type="password" placeholder="Password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} autoComplete="current-password" />
        {err && <div className="text-sm font-medium text-red-700 bg-red-50 border-[1.5px] border-red-700 rounded-xl px-4 py-2.5">{err}</div>}
        <button disabled={busy} className="btnk btnk-ink w-full !py-3">{busy ? 'Checking…' : 'Log in →'}</button>
      </form>
      <div className="mt-5 text-sm text-smoke">New here? <Link to="/signup" className="font-semibold text-ink underline decoration-signal decoration-2 underline-offset-4">Create an account</Link> or <Link to="/app" className="font-semibold text-ink underline decoration-moss decoration-2 underline-offset-4">skip with the live demo</Link>.</div>
    </Shell>
  );
}

export function Signup() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [f, setF] = useState({ name: '', email: '', password: '' });
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const go = async (e) => {
    e.preventDefault();
    setErr('');
    if (f.name.trim().length < 2) { setErr('Tell us your name — 2+ characters.'); return; }
    if (!f.email.includes('@')) { setErr('That email does not look valid.'); return; }
    if (f.password.length < 6) { setErr('Password needs at least 6 characters.'); return; }
    try { setBusy(true); await register(f); nav('/profile'); }
    catch (ex) { setErr(ex.message + ' — try logging in instead.'); }
    finally { setBusy(false); }
  };
  return (
    <Shell title="ENLIST." blurb="One account. Every mission, watchlist and approval in one place. Free, no card.">
      <form onSubmit={go} className="space-y-4">
        <input className="field" placeholder="Full name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} autoComplete="name" />
        <input className="field" placeholder="you@university.edu" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} autoComplete="email" />
        <input className="field" type="password" placeholder="Password (6+ characters)" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} autoComplete="new-password" />
        {err && <div className="text-sm font-medium text-red-700 bg-red-50 border-[1.5px] border-red-700 rounded-xl px-4 py-2.5">{err}</div>}
        <button disabled={busy} className="btnk btnk-signal w-full !py-3 text-base">{busy ? 'Enlisting…' : 'Create account →'}</button>
      </form>
      <div className="mt-5 text-sm text-smoke">Already enlisted? <Link to="/login" className="font-semibold text-ink underline decoration-signal decoration-2 underline-offset-4">Log in</Link>.</div>
    </Shell>
  );
}
