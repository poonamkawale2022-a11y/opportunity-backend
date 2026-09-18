import React, { Suspense, lazy } from 'react';
import { Link } from 'react-router-dom';
import { Navbar, Footer } from '../components/chrome.jsx';
import { Reveal, Ticker, CountUp } from '../components/motion.jsx';
import Pipeline from '../components/Pipeline.jsx';

const Engine = lazy(() => import('../components/Engine.jsx'));

const AGENTS = [
  ['PLANNER', 'Turns a vague goal into a research mission: types, domains, locations, verticals.', 'plan output · JSON schema'],
  ['DISCOVERY', 'One broad sweep, then shortlist. Refines the query only when results are weak.', 'search_jobs · search_web · search_scholar'],
  ['INVESTIGATOR', 'Second-hop digs on the shortlist: org, lab, people, news, maps. Minimum useful set.', 'search_news · search_maps · evidence'],
  ['VERIFIER', 'Cross-checks deadline, status, requirements. Conflict becomes a state, not a guess.', 'VERIFIED / CONFLICTING / UNKNOWN'],
  ['MATCH', 'Eligibility × skills × preferences × research fit. Transparent, dimension by dimension.', 'skill gaps · why-shown'],
  ['APPLICATION', 'Resume emphasis, cover letter, checklist, gap plan. Truthful or nothing.', 'materials · checklist'],
  ['OUTREACH', 'Finds a real public contact, drafts a personal note. Mass mail is refused.', 'find_contact · draft'],
  ['MONITOR', 'Watches, diffs deterministically, re-verifies, alerts. The loop never sleeps.', 'watch · change detect'],
];

export default function Landing() {
  return (
    <div className="bg-paper text-ink overflow-x-clip">
      <Navbar />

      {/* ---------- HERO: manifesto + Opportunity Engine ---------- */}
      <section className="relative blueprint overflow-hidden">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 pt-28 lg:pt-36 pb-10 grid lg:grid-cols-[52%_48%] gap-10 lg:gap-4 items-center min-h-[94svh]">
          <div>
            <Reveal>
              <div className="flex items-center gap-2.5 flex-wrap">
                <span className="tag bg-ink text-paper !border-ink">SerpApi Hackathon 2026</span>
                <span className="tag bg-signal !border-signal">8 agents · 1 autonomous loop</span>
              </div>
            </Reveal>
            <Reveal delay={0.08}>
              <h1 className="display leading-[0.9] mt-6 text-[clamp(3rem,7.2vw,6.25rem)]">
                DON'T FIND<br />OPPORTUNITIES.<br /><span className="text-signal">RUN THEM.</span>
              </h1>
            </Reveal>
            <Reveal delay={0.16}>
              <p className="mt-6 max-w-md text-base leading-relaxed text-ink/75">
                An autonomous opportunity agent that discovers roles, investigates
                organizations, verifies facts, matches you honestly, prepares
                applications, drafts personalized outreach, and keeps watching
                after you act.
              </p>
            </Reveal>
            <Reveal delay={0.24}>
              <div className="mt-7 flex gap-3 flex-wrap">
                <Link to="/app" className="btnk btnk-signal text-base !px-7 !py-3.5">Enter the console →</Link>
                <a href="#pipeline" className="btnk btnk-line text-base !px-7 !py-3.5">Watch it work</a>
              </div>
            </Reveal>
            <Reveal delay={0.3}>
              <div className="mt-7 font-mono text-[11px] uppercase tracking-[0.2em] text-smoke">
                Live web intelligence · SerpApi · human approval for actions
              </div>
            </Reveal>
          </div>
          <Reveal delay={0.15} y={28}>
            <Suspense fallback={<div className="w-full h-[440px] sm:h-[520px] lg:h-[620px] blueprint" />}>
              <Engine />
            </Suspense>
          </Reveal>
        </div>
      </section>

      <Ticker items={['Discover', 'Investigate', 'Verify', 'Match', 'Prepare', 'Approve', 'Act', 'Monitor', 'SerpApi live', 'Human-approved']} />

      {/* ---------- PROOF, NOT PROMISES ---------- */}
      <section id="proof" className="max-w-7xl mx-auto px-4 sm:px-6 py-20 md:py-28">
        <Reveal>
          <h2 className="display text-4xl sm:text-6xl leading-[0.95] max-w-3xl">NOT A JOB BOARD.<br />A MISSION LOG.</h2>
        </Reveal>
        <div className="mt-10 grid md:grid-cols-5 gap-6">
          <Reveal className="md:col-span-3">
            <div className="bg-sheet border-[1.5px] border-ink rounded-2xl shadow-card overflow-hidden">
              <div className="flex items-center justify-between border-b-[1.5px] border-ink px-5 py-3">
                <span className="font-mono text-xs uppercase tracking-widest">Illustrated run · AI research intern, India</span>
                <span className="tag bg-moss text-paper !border-moss">synthetic demo</span>
              </div>
              <div className="divide-y divide-ink/10 font-mono text-[13px]">
                {[
                  ['PLANNER', 'mission set: research internship · AI/ML · India', 'ok'],
                  ['DISCOVERY', '47 found → 12 relevant → 5 strong · 12 dupes cut', 'ok'],
                  ['INVESTIGATOR', 'lab page + researcher + 2 news hits attached', 'ok'],
                  ['VERIFIER', 'deadline VERIFIED · stipend CONFLICTING → flagged', 'warn'],
                  ['MATCH', '8/10 requirements · gap: CUDA · research fit strong', 'ok'],
                  ['APPROVAL', 'cold mail to Dr. Rao — waiting on you', 'wait'],
                ].map(([a, b, s]) => (
                  <div key={a} className="flex items-center gap-4 px-5 py-3">
                    <span className="w-32 shrink-0 font-bold">{a}</span>
                    <span className="flex-1 text-ink/75">{b}</span>
                    <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${s === 'ok' ? 'bg-moss' : s === 'warn' ? 'bg-signal' : 'bg-sun animate-blink'}`} />
                  </div>
                ))}
              </div>
            </div>
          </Reveal>
          <div className="md:col-span-2 flex flex-col gap-6">
            <Reveal delay={0.1}>
              <div className="bg-ink text-paper rounded-2xl p-7 shadow-lift">
                <div className="font-mono text-xs uppercase tracking-widest text-sun">Why it beats search</div>
                <p className="mt-3 text-lg leading-snug">Search gives you <em>information</em>. This runs the <em>workflow</em> — verification, matching, drafting, watching — until the opportunity closes or you win it.</p>
              </div>
            </Reveal>
            <Reveal delay={0.18}>
              <div className="grid grid-cols-2 gap-4">
                {[['250', 'free SerpApi searches / mo, budgeted'], ['7', 'search engines wired'], ['18', 'lifecycle states tracked'], ['0', 'facts invented, ever']].map(([n, l]) => (
                  <div key={l} className="bg-sheet border-[1.5px] border-ink rounded-2xl p-5 shadow-card">
                    <div className="display text-4xl"><CountUp to={parseInt(n, 10)} /></div>
                    <div className="mt-1 text-xs text-smoke leading-snug">{l}</div>
                  </div>
                ))}
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      <Pipeline />

      {/* ---------- AGENT DOSSIER ---------- */}
      <section id="agents" className="max-w-7xl mx-auto px-4 sm:px-6 py-20 md:py-28">
        <Reveal>
          <div className="flex flex-wrap items-end justify-between gap-4">
            <h2 className="display text-4xl sm:text-6xl leading-[0.95]">THE CREW.<br />EIGHT DEEP.</h2>
            <p className="max-w-sm text-ink/70">Fewer agents, deeper. Each owns one stage, calls real tools, and stops when evidence is enough.</p>
          </div>
        </Reveal>
        <div className="mt-10 border-t-[1.5px] border-ink">
          {AGENTS.map(([name, role, tools], i) => (
            <Reveal key={name} y={20}>
              <div className="group grid md:grid-cols-12 gap-2 md:gap-6 items-baseline border-b-[1.5px] border-ink py-5 hover:bg-sheet transition-colors px-2 -mx-2 rounded-lg">
                <div className="md:col-span-1 font-mono text-sm text-smoke">A{i + 1}</div>
                <div className="md:col-span-3 font-display text-2xl group-hover:text-signal transition-colors">{name}</div>
                <div className="md:col-span-5 text-[15px] text-ink/75">{role}</div>
                <div className="md:col-span-3 font-mono text-xs text-smoke md:text-right">{tools}</div>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ---------- QUOTA BAND ---------- */}
      <section id="quota" className="bg-sun border-y-[1.5px] border-ink">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-16 md:py-20 grid md:grid-cols-2 gap-10 items-center">
          <Reveal>
            <h2 className="display text-4xl sm:text-5xl leading-[0.95]">BUILT FOR THE FREE TIER, NOT IN SPITE OF IT.</h2>
            <p className="mt-4 max-w-md text-ink/75">One broad sweep, shortlist, then selective deep dives. Responses cached for an hour, identical searches never re-fired, every call counted against a visible budget.</p>
            <Link to="/app" className="btnk btnk-ink mt-6">See the budget meter live →</Link>
          </Reveal>
          <Reveal delay={0.1}>
            <div className="bg-ink text-paper rounded-2xl p-7 font-mono text-sm shadow-lift">
              <div className="text-paper/50 text-xs uppercase tracking-widest">search doctrine</div>
              <div className="mt-3 space-y-2.5">
                <div>1 broad discovery search</div>
                <div className="text-paper/40">↓ shortlist</div>
                <div>→ selective deep investigation</div>
                <div className="text-paper/40">→ selective verification</div>
                <div className="text-signal">✕ never 50 opps × 10 searches</div>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ---------- CLOSE ---------- */}
      <section className="bg-moss text-paper blueprint-dark">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-20 md:py-28 text-center">
          <Reveal>
            <h2 className="display text-[11vw] sm:text-7xl leading-[0.92]">STOP SCROLLING<br />JOB BOARDS.</h2>
            <p className="mt-5 text-paper/70 max-w-xl mx-auto">Spin up a mission in one sentence. The crew handles the rest — and pings you only when something really changes.</p>
            <div className="mt-8 flex justify-center gap-3 flex-wrap">
              <Link to="/signup" className="btnk bg-signal text-ink text-base !px-8 !py-4">Start free →</Link>
              <Link to="/app" className="btnk border-[1.5px] border-paper text-paper text-base !px-8 !py-4 hover:bg-paper hover:text-ink">Live demo, no signup</Link>
            </div>
          </Reveal>
        </div>
      </section>

      <Footer />
    </div>
  );
}
