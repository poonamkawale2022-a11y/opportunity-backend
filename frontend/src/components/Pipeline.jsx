import React, { useEffect, useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

export const STAGES = [
  ['DISCOVER', 'One broad SerpApi sweep across Jobs, Search and Scholar. Dedupe by canonical URL, org and title.', '01'],
  ['INVESTIGATE', 'Second-hop research on the shortlist only: labs, people, news, maps. Never every vertical by default.', '02'],
  ['VERIFY', 'Deadlines, status and requirements cross-checked. Conflicts surface as CONFLICTING, never silently picked.', '03'],
  ['MATCH', 'Eligibility, skill gaps and research fit against your profile. Missing data reads UNKNOWN, never guessed.', '04'],
  ['PREPARE', 'Resume emphasis, truthful cover letter, checklist and a gap-closing plan. Nothing invented, ever.', '05'],
  ['APPROVE', 'Every email and submission pauses here. You see recipient, body, evidence — then decide.', '06'],
  ['ACT', 'Gmail drafts and sends through your OAuth account, or downloads as .eml when offline.', '07'],
  ['MONITOR', 'Watched roles are re-checked. Deterministic diffs trigger re-verification and alerts.', '08'],
];

/** Pinned horizontal-scroll pipeline on desktop; stacked dossier on mobile. */
export default function Pipeline() {
  const root = useRef(null);
  const track = useRef(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      const getX = () => -(track.current.scrollWidth - window.innerWidth);
      gsap.to(track.current, {
        x: getX, ease: 'none',
        scrollTrigger: {
          trigger: root.current, start: 'top top',
          end: () => `+=${track.current.scrollWidth - window.innerWidth}`,
          scrub: 1, pin: true, invalidateOnRefresh: true,
          anticipatePin: 1,
        },
      });
    }, root);
    return () => ctx.revert();
  }, []);

  return (
    <section ref={root} id="pipeline" className="bg-moss text-paper overflow-hidden">
      <div ref={track} className="flex items-stretch min-h-[92vh] w-max">
        <div className="w-[88vw] md:w-[38vw] shrink-0 flex flex-col justify-center px-6 md:px-14 blueprint-dark">
          <div className="font-mono text-xs uppercase tracking-[0.25em] text-sun">The operating loop</div>
          <h2 className="display text-[13vw] md:text-[4.6rem] leading-[0.95] mt-4">
            EIGHT<br />STAGES.<br />ONE LOOP.
          </h2>
          <p className="mt-5 max-w-sm text-paper/70">Scroll on — the pipeline rides sideways. Each stage is a real agent with real tools, not a slide.</p>
          <div className="mt-6 font-mono text-xs text-paper/50">SCROLL →</div>
        </div>
        {STAGES.map(([name, body, num]) => (
          <article key={name} className="w-[84vw] md:w-[30vw] shrink-0 border-l border-paper/25 px-6 md:px-10 flex flex-col justify-center py-16">
            <div className="font-mono text-sm text-sun">{num} / 08</div>
            <h3 className="display text-4xl md:text-5xl mt-3">{name}</h3>
            <div className="mt-4 h-[3px] w-16 bg-signal" />
            <p className="mt-4 text-paper/75 leading-relaxed max-w-xs">{body}</p>
          </article>
        ))}
        <div className="w-[80vw] md:w-[26vw] shrink-0 flex flex-col justify-center px-6 md:px-10">
          <a href="/app" className="btnk bg-signal text-ink text-lg !px-8 !py-4">Run the loop →</a>
          <div className="mt-4 font-mono text-xs text-paper/50">LIVE IN THE CONSOLE</div>
        </div>
      </div>
    </section>
  );
}
