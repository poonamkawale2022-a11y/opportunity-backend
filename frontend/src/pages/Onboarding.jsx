import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Mark } from '../components/chrome.jsx';
import { api } from '../lib/api.js';
import { useAuth } from '../lib/auth.jsx';
import { Drop, EntryList, Field, SkillsEditor, matchLoc } from '../components/profileForm.jsx';

const STEPS = ['Start', 'Personal', 'Links', 'Education', 'Experience', 'Skills', 'Preferences', 'Review'];
const SHORT = ['Start', 'Personal', 'Links', 'Edu', 'Exp', 'Skills', 'Prefs', 'Review'];
const SUBS = [
  'Two minutes now saves twenty per application later.',
  'The two fields every application requires.',
  'Where recruiters verify you. Skip any — blanks stay blank.',
  'Latest first. Expected graduation year counts.',
  'Internships, freelance, serious projects. Thin is fine.',
  'What matching scores against. Honest beats long.',
  'Where the alerts should look.',
  'One glance, then hunt.',
];
const TIPS = [
  'A resume upload fills ~80% of this form. Single-column PDFs parse best.',
  'Use the name recruiters will Google. Email unlocks Next — the rest can wait.',
  'GitHub matters most for SDE roles; LinkedIn matters everywhere.',
  'Put expected graduation in Years — 2028 batch belongs here.',
  'One line per role with a number in it beats three vague lines.',
  '8–15 honest skills. Gaps become your prep plan, not rejections.',
  'Remote × India doubles your surface area for internships.',
  'Everything stays editable later under Profile.',
];

function Tracker({ step, go }) {
  return (
    <div className="flex items-center gap-0 overflow-x-auto py-1" role="list" aria-label="Onboarding progress">
      {SHORT.map((s, i) => (
        <React.Fragment key={s}>
          <button role="listitem" disabled={i >= step} onClick={() => go(i)}
            className={`flex items-center gap-1.5 shrink-0 py-1 ${i >= step ? 'cursor-default' : 'cursor-pointer'}`}>
            <span className={`w-2.5 h-2.5 rotate-45 border-[1.5px] transition-colors ${i < step ? 'bg-ink border-ink' : i === step ? 'bg-signal border-signal' : 'border-ink/30'}`} />
            <span className={`font-mono text-[10px] uppercase tracking-[0.14em] ${i === step ? 'text-ink font-bold' : i < step ? 'text-ink/70' : 'text-smoke/60'}`}>{s}</span>
          </button>
          {i < SHORT.length - 1 && <span className={`mx-2 h-px w-4 sm:w-7 shrink-0 ${i < step ? 'bg-ink/50' : 'bg-ink/15'}`} />}
        </React.Fragment>
      ))}
    </div>
  );
}

export default function Onboarding() {
  const { user, uid } = useAuth();
  const nav = useNavigate();
  const [step, setStep] = useState(0);
  const [personal, setPersonal] = useState({ name: '', email: '', phone: '', location: '', linkedin: '', github: '', website: '' });
  const [edu, setEdu] = useState([]);
  const [exp, setExp] = useState([]);
  const [skills, setSkills] = useState([]);
  const [workTypes, setWorkTypes] = useState([]);
  const [relocate, setRelocate] = useState(false);
  const [busy, setBusy] = useState('');
  const [err, setErr] = useState('');
  const [note, setNote] = useState('');
  const [seeded, setSeeded] = useState(false);

  const P = (k, v) => setPersonal((p) => ({ ...p, [k]: v }));
  const id = uid();
  const digits = (personal.phone.match(/\d/g) || []).length;

  useEffect(() => {
    api.profile(id).then((r) => {
      const p = r.data || {};
      if (!p.name && !p.email && !(p.skills || []).length) return;
      setPersonal({
        name: p.name || '', email: p.email || '', phone: p.phone || '', location: p.location || '',
        linkedin: p.links?.linkedin || '', github: p.links?.github || '', website: p.links?.website || '',
      });
      setEdu((p.education || []).map((e) => typeof e === 'string' ? { school: e, degree: '', field: '', years: '' } : e));
      setExp((p.experience || []).map((e) => typeof e === 'string' ? { title: e, company: '', years: '', summary: '' } : e));
      setSkills(p.skills || []);
      setWorkTypes(p.preferences?.work_types || []);
      setRelocate(!!p.preferences?.relocate);
      setSeeded(true);
    }).catch(() => {});
  }, []);

  const applyParsed = (p) => {
    setPersonal({
      name: p.name || '', email: p.email || '', phone: p.phone || '',
      location: matchLoc(p.location || ''), linkedin: p.links?.linkedin || '',
      github: p.links?.github || '', website: p.links?.website || '',
    });
    setEdu((p.education || []).map((e) => ({ school: e.school || e.raw || '', degree: e.degree || '', field: e.field || '', years: e.years || '' })).slice(0, 4));
    setExp((p.experience || []).map((e) => ({ title: e.title || '', company: e.company || '', years: e.years || '', summary: e.summary || '' })).slice(0, 6));
    setSkills(p.skills || []);
    const bits = [p.name && 'name', p.email && 'email', (p.skills || []).length && `${p.skills.length} skills`].filter(Boolean);
    setNote(bits.length ? `Pulled ${bits.join(' · ')} — walk through and confirm.` : 'Could not read much — continue manually.');
  };

  const autofillFile = async (f) => {
    if (!f) return;
    try { setBusy('reading'); setErr(''); const r = await api.resumeFile(id, f); applyParsed(r.data); }
    catch (e) { setErr(e.message); } finally { setBusy(''); }
  };

  const nameOk = personal.name.trim().length >= 2;
  const emailOk = /.+@.+\..+/.test(personal.email);
  const phoneOk = personal.phone.trim() === '' || digits >= 10;
  const canNext = step !== 1 || (nameOk && emailOk);
  const completeness = Math.round(([
    personal.name && personal.email, personal.location, skills.length > 0,
    edu.length > 0, exp.length > 0, workTypes.length > 0,
  ].filter(Boolean).length / 6) * 100);

  const save = async (done) => {
    try {
      setBusy('saving'); setErr('');
      await api.saveProfile({
        user_id: id, name: personal.name, email: personal.email, phone: personal.phone,
        location: personal.location, links: { linkedin: personal.linkedin, github: personal.github, website: personal.website },
        education: edu.filter((e) => e.school || e.degree), experience: exp.filter((e) => e.title || e.company),
        skills, preferences: { work_types: workTypes, relocate },
      });
      if (done) nav('/app');
    } catch (e) { setErr(e.message); } finally { setBusy(''); }
  };

  const go = (i) => { if (i < step) { save(false); setStep(i); window.scrollTo(0, 0); } };

  return (
    <div className="min-h-[100svh] bg-paper blueprint">
      <header className="border-b border-ink/15 bg-paper/95 backdrop-blur sticky top-0 z-30">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between gap-3">
          <Link to="/"><Mark /></Link>
          <span className="font-mono text-[11px] text-smoke hidden sm:block">Step {step + 1} of {STEPS.length}</span>
        </div>
        <div className="max-w-5xl mx-auto px-4 sm:px-6 pb-2">
          <Tracker step={step} go={go} />
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 sm:px-6">
        <div className="grid lg:grid-cols-[1fr_300px] gap-8 min-h-[calc(100svh-118px-69px)] items-center py-6 pb-28">
          <div className="min-w-0 lg:max-h-[calc(100svh-240px)] lg:overflow-y-auto noscroll lg:pr-3">
            {!user && (
              <div className="bg-sun/40 border border-ink/15 rounded-xl px-4 py-2.5 text-sm mb-4">
                Guest run — <Link to="/signup" className="font-semibold underline decoration-signal decoration-2 underline-offset-4">create an account</Link> to keep this.
              </div>
            )}
            {err && <div className="bg-red-50 border border-red-700/60 text-red-800 rounded-xl px-4 py-2.5 text-sm font-medium mb-4">⚠ {err}</div>}
            {note && <div className="bg-moss/10 border border-moss/40 text-moss rounded-xl px-4 py-2.5 text-sm font-medium mb-4">● {note}</div>}

            <AnimatePresence mode="wait">
              <motion.div key={step} initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -24 }} transition={{ duration: 0.25 }}>
                {step === 0 && (
                  <div className="text-center py-2">
                    <h1 className="font-display text-4xl sm:text-5xl leading-[0.95]">TWO MINUTES,<br />THEN WE HUNT.</h1>
                    <p className="mt-3 text-smoke max-w-md mx-auto">{SUBS[0]}</p>
                    <label className="btnk btnk-signal mt-5 !px-8 !py-3.5 text-base cursor-pointer">
                      {busy === 'reading' ? <span className="spinner" /> : '↑ Upload resume & autofill'}
                      <input type="file" accept=".pdf,.docx,.txt" className="hidden" onChange={(e) => autofillFile(e.target.files?.[0])} />
                    </label>
                    <div><button onClick={() => setStep(1)} className="mt-4 font-mono text-xs uppercase tracking-widest text-smoke hover:text-ink">Fill manually instead →</button></div>
                  </div>
                )}
                {[1, 2, 3, 4, 5, 6, 7].includes(step) && (
                  <div>
                    <h2 className="font-display text-3xl sm:text-4xl">
                      {['', 'Who are you?', 'Where do you live online?', 'Schooling', 'Work so far', 'Your toolkit', 'How do you want to work?', 'Look right?'][step]}
                    </h2>
                    <p className="text-sm text-smoke mt-1.5">{SUBS[step]}</p>
                    <div className="mt-5">
                      {step === 1 && (
                        <div className="grid sm:grid-cols-2 gap-2.5">
                          <Field l="Full name *" v={personal.name} set={(v) => P('name', v)} ph="Aarav Sharma" valid={nameOk} />
                          <Field l="Email *" v={personal.email} set={(v) => P('email', v)} ph="you@university.edu" valid={emailOk} />
                          <Field l="Phone" v={personal.phone} set={(v) => P('phone', v)} ph="+91 98765 43210" valid={personal.phone.trim() !== '' && phoneOk} />
                          <div><span className="label">Location</span><div className="mt-1"><Drop value={personal.location} onPick={(l) => P('location', l)} /></div></div>
                        </div>
                      )}
                      {step === 2 && (
                        <div className="grid sm:grid-cols-3 gap-2.5">
                          <Field l="LinkedIn" v={personal.linkedin} set={(v) => P('linkedin', v)} ph="linkedin.com/in/…" hint="linkedin.com/in/yourname" />
                          <Field l="GitHub" v={personal.github} set={(v) => P('github', v)} ph="github.com/…" hint="github.com/yourname" />
                          <Field l="Website" v={personal.website} set={(v) => P('website', v)} ph="https://…" hint="https://yourportfolio.com" />
                        </div>
                      )}
                      {step === 3 && <EntryList items={edu} setItems={setEdu} addLabel="Add school" empty="No schools yet — most 2028 grads list one."
                        fields={[['school', 'School', 'IIT Bombay'], ['degree', 'Degree', 'B.Tech'], ['field', 'Field', 'Computer Science'], ['years', 'Years', '2024 – 2028']]} />}
                      {step === 4 && <EntryList items={exp} setItems={setExp} addLabel="Add role" empty="Nothing yet — add your first role."
                        fields={[['title', 'Title', 'ML Intern'], ['company', 'Company', 'Acme AI'], ['years', 'Years', '2025'], ['summary', 'One-line win', 'Shipped X, cut Y by Z%']]} />}
                      {step === 5 && <SkillsEditor skills={skills} setSkills={setSkills} />}
                      {step === 6 && (
                        <div className="flex gap-2 flex-wrap">
                          {['Remote', 'Onsite', 'Hybrid'].map((w) => (
                            <button key={w} onClick={() => setWorkTypes(workTypes.includes(w) ? workTypes.filter((x) => x !== w) : [...workTypes, w])} aria-pressed={workTypes.includes(w)}
                              className={`tag !py-2 !px-5 !text-sm transition-colors ${workTypes.includes(w) ? 'bg-moss text-paper !border-moss' : 'hover:bg-sun'}`}>{w}</button>
                          ))}
                          <button onClick={() => setRelocate(!relocate)} aria-pressed={relocate}
                            className={`tag !py-2 !px-5 !text-sm transition-colors ${relocate ? 'bg-moss text-paper !border-moss' : 'hover:bg-sun'}`}>Open to relocate</button>
                        </div>
                      )}
                      {step === 7 && (
                        <div>
                          <div className="font-mono text-xs text-smoke">Profile {completeness}% complete</div>
                          <div className="h-1.5 rounded-full bg-ink/10 overflow-hidden mt-1 mb-4"><div className="h-full bg-moss rounded-full" style={{ width: `${completeness}%` }} /></div>
                          <dl className="grid sm:grid-cols-2 gap-3 text-sm">
                            {[['Name', personal.name], ['Email', personal.email], ['Phone', personal.phone], ['Location', personal.location],
                              ['Schools', edu.map((e) => e.school).filter(Boolean).join(', ')], ['Roles', exp.map((e) => e.title).filter(Boolean).join(', ')],
                              ['Skills', skills.slice(0, 10).join(', ')], ['Work', [...workTypes, relocate && 'relocate'].filter(Boolean).join(', ')]].map(([k, v]) => (
                              <div key={k} className="border-t-2 border-ink pt-1.5"><dt className="label">{k}</dt><dd className="mt-0.5 truncate">{v || '—'}</dd></div>
                            ))}
                          </dl>
                        </div>
                      )}
                    </div>
                    {step === 1 && !canNext && <p className="font-mono text-[11px] text-smoke mt-3">Name + valid email unlocks Next — watch for the green checks.</p>}
                  </div>
                )}
              </motion.div>
            </AnimatePresence>
          </div>

          {/* live preview rail */}
          <aside className="hidden lg:block">
            <div className="sticky top-28 bg-sheet border border-ink/15 rounded-2xl p-5 shadow-card">
              <div className="flex items-center justify-between">
                <span className="label">Live preview</span>
                <span className="font-mono text-[11px] text-moss">{completeness}%</span>
              </div>
              <div className="font-head font-bold text-xl mt-2 truncate">{personal.name || 'Your name'}</div>
              <div className="font-mono text-[11px] text-smoke truncate">{[personal.email, personal.phone, personal.location].filter(Boolean).join(' · ') || 'contact lines appear here'}</div>
              {!!skills.length && <div className="flex flex-wrap gap-1 mt-2.5">{skills.slice(0, 6).map((s) => <span key={s} className="tag !text-[10px] !py-0.5">{s}</span>)}{skills.length > 6 && <span className="font-mono text-[10px] text-smoke">+{skills.length - 6}</span>}</div>}
              {!!(edu[0]?.school || exp[0]?.title) && (
                <div className="font-mono text-[11px] text-smoke mt-2.5 space-y-0.5">
                  {edu[0]?.school && <div>▸ {edu[0].school}</div>}
                  {exp[0]?.title && <div>▸ {exp[0].title}{exp[0]?.company ? ` @ ${exp[0].company}` : ''}</div>}
                </div>
              )}
              <div className="border-t border-ink/10 mt-4 pt-3">
                <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-signal">Tip · {SHORT[step]}</div>
                <p className="text-[13px] text-ink/75 mt-1 leading-relaxed">{TIPS[step]}</p>
              </div>
            </div>
          </aside>
        </div>
      </main>

      <footer className="fixed bottom-0 inset-x-0 bg-paper/95 backdrop-blur border-t border-ink/15">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 py-3 flex items-center gap-2">
          <button disabled={step === 0} onClick={() => { setStep(step - 1); window.scrollTo(0, 0); }} className="btnk btnk-line !py-3 flex-1 disabled:opacity-30">← Back</button>
          {step < STEPS.length - 1
            ? <button disabled={!canNext || busy === 'saving'} onClick={() => { save(false); setStep(step + 1); window.scrollTo(0, 0); }} className="btnk btnk-ink !py-3 flex-[2]">Next →</button>
            : <button disabled={busy === 'saving'} onClick={() => save(true)} className="btnk btnk-ink !py-3 flex-[2] text-base">{busy === 'saving' ? <span className="spinner" /> : 'Save & start hunting →'}</button>}
        </div>
      </footer>
    </div>
  );
}
