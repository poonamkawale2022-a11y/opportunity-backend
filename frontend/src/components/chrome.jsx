import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../lib/auth.jsx';

export function LoopMark({ size = 30, light }) {
  const ring = light ? '#F6F3EC' : '#16150F';
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden>
      <circle cx="16" cy="16" r="13.5" stroke={ring} strokeWidth="3.4" strokeDasharray="3.5 7.1" opacity="0.9" />
      <circle cx="16" cy="16" r="9" stroke="#FF4D00" strokeWidth="3" pathLength="100" strokeDasharray="32 68" strokeLinecap="round" transform="rotate(-90 16 16)" />
      <circle cx="24.2" cy="19.8" r="2.7" fill="#FF4D00" />
      <circle cx="16" cy="16" r="3.2" fill={ring} />
    </svg>
  );
}

export function Mark({ light }) {
  return (
    <span className="flex items-center gap-2.5">
      <LoopMark light={light} />
      <span className="font-display text-[17px] tracking-tight leading-none">PURSUIT</span>
    </span>
  );
}

export function Navbar() {
  const { user, logout } = useAuth();
  return (
    <header className="fixed top-0 inset-x-0 z-50 border-b-[1.5px] border-ink bg-paper/90 backdrop-blur">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-3">
        <Link to="/"><Mark /></Link>
        <nav className="hidden md:flex items-center gap-7 font-mono text-xs uppercase tracking-widest">
          <a href="#pipeline" className="hover:text-signal">Pipeline</a>
          <a href="#agents" className="hover:text-signal">Agents</a>
          <a href="#proof" className="hover:text-signal">Proof</a>
          <a href="#quota" className="hover:text-signal">Quota</a>
        </nav>
        <div className="flex items-center gap-2">
          {user ? (
            <>
              <Link to="/app" className="btnk btnk-ink !py-2 text-sm">Console →</Link>
              <button onClick={logout} className="btnk btnk-line !py-2 text-sm">Out</button>
            </>
          ) : (
            <>
              <Link to="/login" className="btnk btnk-line !py-2 text-sm">Log in</Link>
              <Link to="/app" className="btnk btnk-ink !py-2 text-sm">Live demo</Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

export function Footer() {
  return (
    <footer className="bg-ink text-paper">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-14 grid md:grid-cols-4 gap-10">
        <div className="md:col-span-2">
          <Mark light />
          <p className="mt-4 max-w-sm text-paper/70 text-sm leading-relaxed">
            An autonomous career-opportunity operating system. Eight agents, one approval gate,
            zero invented facts. Built on SerpApi live intelligence for the SerpApi India Hackathon 2026.
          </p>
        </div>
        <div>
          <div className="font-mono text-xs uppercase tracking-widest text-paper/50 mb-3">System</div>
          <div className="flex flex-col gap-2 text-sm">
            <Link to="/app" className="hover:text-sun">Console</Link>
            <Link to="/login" className="hover:text-sun">Log in</Link>
            <Link to="/signup" className="hover:text-sun">Sign up</Link>
          </div>
        </div>
        <div>
          <div className="font-mono text-xs uppercase tracking-widest text-paper/50 mb-3">Stack</div>
          <div className="flex flex-col gap-2 text-sm text-paper/80">
            <span>SerpApi · 7 engines</span><span>OpenRouter tool-calling</span><span>Gmail OAuth drafts</span><span>MongoDB memory</span>
          </div>
        </div>
      </div>
      <div className="border-t border-paper/20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex justify-between font-mono text-[11px] uppercase tracking-widest text-paper/50">
          <span>Pursuit v1.0 // Hackathon build</span>
          <span>Human-approved actions only</span>
        </div>
      </div>
    </footer>
  );
}
