"use client";

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { motion, useInView } from 'framer-motion';
import {
  Cpu, Shield, GitBranch, BarChart3, Code, Zap,
  AlertTriangle, Sparkles, Database, Activity,
  ChevronRight, Bot, ArrowRight, CheckCircle2,
  ScrollText, Terminal, TrendingUp, GitPullRequest,
} from 'lucide-react';
import ParticleField from '@/components/ParticleField';
import Navbar from '@/components/Navbar';

// ── Data ──────────────────────────────────────────────────────────────────────

const FEATURES = [
  {
    icon: Cpu,
    color: 'text-blue-400', bg: 'bg-blue-500/10 border-blue-500/20',
    glow: 'hover:shadow-blue-500/10',
    title: 'AI Test Generation',
    description: 'Converts BRDs into structured test cases with positive, negative, and edge-case scenarios — fully automated.',
  },
  {
    icon: Shield,
    color: 'text-indigo-400', bg: 'bg-indigo-500/10 border-indigo-500/20',
    glow: 'hover:shadow-indigo-500/10',
    title: 'Smart QA Review',
    description: 'Each user story is reviewed for clarity, completeness, and testability before a single test is written.',
  },
  {
    icon: BarChart3,
    color: 'text-violet-400', bg: 'bg-violet-500/10 border-violet-500/20',
    glow: 'hover:shadow-violet-500/10',
    title: 'Coverage Analysis',
    description: 'Identify functional, boundary, and integration gaps in your test suite before any code ships to production.',
  },
  {
    icon: Code,
    color: 'text-purple-400', bg: 'bg-purple-500/10 border-purple-500/20',
    glow: 'hover:shadow-purple-500/10',
    title: 'Playwright Script Gen',
    description: 'Production-ready Playwright test scripts generated and written to disk — ready to run in your CI/CD pipeline.',
  },
  {
    icon: Sparkles,
    color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/20',
    glow: 'hover:shadow-amber-500/10',
    title: 'Self-Healing Tests',
    description: 'Detects failures, classifies root causes across 11 error types, and auto-generates fixed scripts without manual intervention.',
  },
  {
    icon: Database,
    color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/20',
    glow: 'hover:shadow-emerald-500/10',
    title: 'FAISS Memory',
    description: 'Learns from every past run. Retrieves similar test cases to avoid duplication and continuously improve quality.',
  },
];

const PIPELINE_STEPS = [
  { num: 1, icon: ScrollText,    color: 'text-slate-300',   bg: 'bg-slate-500/15',   name: 'BRD Input',           desc: 'Paste your business requirements document' },
  { num: 2, icon: Cpu,           color: 'text-blue-400',    bg: 'bg-blue-500/15',    name: 'Requirement Agent',   desc: 'Extracts structured user stories from the BRD' },
  { num: 3, icon: Shield,        color: 'text-indigo-400',  bg: 'bg-indigo-500/15',  name: 'QA Review Agent',     desc: 'Reviews stories for completeness and clarity' },
  { num: 4, icon: GitBranch,     color: 'text-violet-400',  bg: 'bg-violet-500/15',  name: 'Test Case Agent',     desc: 'Generates comprehensive test cases in parallel' },
  { num: 5, icon: BarChart3,     color: 'text-purple-400',  bg: 'bg-purple-500/15',  name: 'Coverage Agent',      desc: 'Identifies test coverage gaps across all layers' },
  { num: 6, icon: Code,          color: 'text-fuchsia-400', bg: 'bg-fuchsia-500/15', name: 'Script Agent',        desc: 'Writes Playwright automation scripts to disk' },
  { num: 7, icon: Zap,           color: 'text-pink-400',    bg: 'bg-pink-500/15',    name: 'Execution Agent',     desc: 'Runs the generated test suite end-to-end' },
  { num: 8, icon: AlertTriangle, color: 'text-rose-400',    bg: 'bg-rose-500/15',    name: 'Failure Analysis',    desc: 'Classifies failures by root cause (11 types)' },
  { num: 9, icon: Sparkles,      color: 'text-amber-400',   bg: 'bg-amber-500/15',   name: 'Healing Agent',       desc: 'Auto-fixes broken scripts and re-runs the suite' },
];

const STATS = [
  { value: 9,   suffix: '',   label: 'AI Agents',       color: 'text-blue-400'    },
  { value: 100, suffix: '%',  label: 'Autonomous',      color: 'text-violet-400'  },
  { value: 10,  suffix: 'x',  label: 'Faster QA',       color: 'text-emerald-400' },
  { value: 3,   suffix: '',   label: 'LLM Providers',   color: 'text-amber-400'   },
];

const LOG_LINES = [
  { text: '> Connecting to pipeline...', delay: 0 },
  { text: '> BRD parsed: 4 user stories found', delay: 0.6 },
  { text: '> QA review: avg confidence 94%', delay: 1.2 },
  { text: '> Generated 16 test cases', delay: 1.8 },
  { text: '> Coverage gap detected: boundary tests', delay: 2.4 },
  { text: '> Writing Playwright scripts to /tests/', delay: 3.0 },
  { text: '> Execution: 14/16 passed', delay: 3.6 },
  { text: '> Healing 2 failed scripts...', delay: 4.2 },
  { text: '> All 16 tests passing [OK]', delay: 4.8 },
];

// ── Utilities ─────────────────────────────────────────────────────────────────

function CountUp({ end, suffix = '' }: { end: number; suffix?: string }) {
  const [count, setCount] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });

  useEffect(() => {
    if (!inView) return;
    const steps = 40;
    const increment = end / steps;
    let current = 0;
    const timer = setInterval(() => {
      current += increment;
      if (current >= end) { setCount(end); clearInterval(timer); }
      else setCount(Math.floor(current));
    }, 1600 / steps);
    return () => clearInterval(timer);
  }, [inView, end]);

  return <span ref={ref}>{count}{suffix}</span>;
}

const fadeUp = {
  hidden:  { opacity: 0, y: 24 },
  visible: (i: number) => ({
    opacity: 1, y: 0,
    transition: { duration: 0.55, delay: i * 0.09, ease: 'easeOut' as const },
  }),
};

// ── Page ──────────────────────────────────────────────────────────────────────

export default function LandingPage() {
  const [logVisible, setLogVisible] = useState(false);
  const terminalRef  = useRef<HTMLDivElement>(null);
  const terminalInView = useInView(terminalRef, { once: true, margin: '-100px' });

  useEffect(() => { if (terminalInView) setLogVisible(true); }, [terminalInView]);

  return (
    <>
      <Navbar />
      <ParticleField active={false} />

      {/* Ambient blobs */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden" aria-hidden="true">
        <div className="absolute -top-40 -left-40 w-[700px] h-[700px] rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(59,130,246,0.12) 0%, transparent 65%)' }} />
        <div className="absolute -bottom-40 -right-40 w-[600px] h-[600px] rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(139,92,246,0.12) 0%, transparent 65%)' }} />
      </div>

      <main className="relative z-10">

        {/* ─────────────────────────── HERO ─────────────────────────── */}
        <section
          id="hero"
          aria-label="Hero"
          className="relative min-h-screen flex flex-col items-center justify-center text-center px-4 pt-24 pb-20 max-w-5xl mx-auto"
        >
          {/* Badge */}
          <motion.div
            initial={{ opacity: 0, y: -12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
            className="mb-8"
          >
            <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full glass border border-blue-500/30 text-xs font-semibold text-blue-300 tracking-wider uppercase">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
              AI-Powered QA Automation
              <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
            </span>
          </motion.div>

          {/* Headline */}
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
            className="text-5xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight leading-[1.08] mb-6"
          >
            <span className="text-slate-50">Ship Software with</span>
            <br />
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-violet-400 to-purple-500">
              Unwavering Quality
            </span>
          </motion.h1>

          {/* Subtitle */}
          <motion.p
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
            className="text-slate-400 text-lg sm:text-xl max-w-2xl mx-auto leading-relaxed mb-10"
          >
            QAgent transforms your Business Requirement Document into a complete test suite
            using a{' '}<strong className="text-slate-200 font-semibold">9-step AI pipeline</strong>.
            From user stories to self-healing Playwright scripts — fully autonomous.
          </motion.p>

          {/* CTAs */}
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3, ease: [0.22, 1, 0.36, 1] }}
            className="flex flex-col sm:flex-row items-center gap-4 mb-14"
          >
            <Link
              href="/pipeline"
              className="group flex items-center gap-2 px-7 py-3.5 rounded-2xl bg-gradient-to-r from-blue-600 to-violet-600 text-white font-semibold text-base hover:shadow-2xl hover:shadow-blue-500/30 hover:scale-[1.03] active:scale-[0.98] transition-all duration-300"
            >
              Launch Pipeline
              <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />
            </Link>
            <a
              href="#features"
              className="flex items-center gap-2 px-7 py-3.5 rounded-2xl glass border border-slate-700/60 text-slate-300 font-semibold text-base hover:text-white hover:border-slate-500/60 transition-all duration-300"
            >
              See Features
              <ChevronRight size={16} />
            </a>
          </motion.div>

          {/* Social proof */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.45 }}
            className="flex items-center gap-3 text-slate-500 text-sm"
          >
            <div className="flex -space-x-2">
              {(['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b'] as const).map((c, i) => (
                <div
                  key={i}
                  className="w-7 h-7 rounded-full border-2 border-[#020817] flex items-center justify-center text-[10px] font-bold text-white"
                  style={{ background: c }}
                >
                  {['R', 'S', 'A', 'M'][i]}
                </div>
              ))}
            </div>
            <span>Trusted by QA teams worldwide</span>
            <span className="flex items-center gap-0.5 text-amber-400">
              {'★★★★★'}
              <span className="text-slate-500 ml-1">4.9/5</span>
            </span>
          </motion.div>

          {/* Scroll mouse indicator */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.2 }}
            className="absolute bottom-10 left-1/2 -translate-x-1/2 hidden lg:flex flex-col items-center gap-2 text-slate-600"
            aria-hidden="true"
          >
            <div className="w-5 h-8 rounded-full border border-slate-700 flex items-start justify-center pt-1.5">
              <motion.div
                className="w-1 h-2 bg-slate-500 rounded-full"
                animate={{ y: [0, 6, 0] }}
                transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
              />
            </div>
            <span className="text-[10px] tracking-widest uppercase">Scroll</span>
          </motion.div>
        </section>

        {/* ─────────────────────────── STATS ─────────────────────────── */}
        <section aria-label="Key metrics" className="px-4 pb-20">
          <div className="max-w-4xl mx-auto grid grid-cols-2 lg:grid-cols-4 gap-4">
            {STATS.map((stat, i) => (
              <motion.div
                key={stat.label}
                custom={i}
                variants={fadeUp}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true, margin: '-60px' }}
                className="glass rounded-2xl p-6 text-center hover:border-slate-600/60 transition-all duration-300"
              >
                <div className={`text-3xl font-extrabold mb-1 ${stat.color}`}>
                  <CountUp end={stat.value} suffix={stat.suffix} />
                </div>
                <div className="text-slate-500 text-xs font-medium uppercase tracking-wider">
                  {stat.label}
                </div>
              </motion.div>
            ))}
          </div>
        </section>

        {/* ─────────────────────────── FEATURES ─────────────────────────── */}
        <section id="features" className="px-4 pb-28" aria-labelledby="features-heading">
          <div className="max-w-6xl mx-auto">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
              className="text-center mb-16"
            >
              <span className="inline-block mb-4 px-3 py-1 rounded-full bg-violet-500/10 border border-violet-500/20 text-violet-400 text-xs font-semibold uppercase tracking-wider">
                Capabilities
              </span>
              <h2 id="features-heading" className="text-3xl sm:text-4xl lg:text-5xl font-bold text-slate-50 mb-4">
                Everything your QA team needs
              </h2>
              <p className="text-slate-500 max-w-xl mx-auto text-base leading-relaxed">
                A complete, autonomous QA engineering platform powered by large language models.
              </p>
            </motion.div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
              {FEATURES.map((feat, i) => (
                <motion.div
                  key={feat.title}
                  custom={i}
                  variants={fadeUp}
                  initial="hidden"
                  whileInView="visible"
                  viewport={{ once: true, margin: '-50px' }}
                  className={`glass rounded-2xl p-6 border hover:border-slate-600/60 transition-all duration-300 hover:shadow-xl ${feat.glow} group cursor-default`}
                >
                  <div className={`w-10 h-10 rounded-xl ${feat.bg} border flex items-center justify-center mb-4 group-hover:scale-110 transition-transform duration-300`}>
                    <feat.icon size={20} className={feat.color} />
                  </div>
                  <h3 className="text-slate-100 font-semibold text-base mb-2">{feat.title}</h3>
                  <p className="text-slate-500 text-sm leading-relaxed">{feat.description}</p>
                </motion.div>
              ))}
            </div>
          </div>
        </section>

        {/* ─────────────────────────── PIPELINE ─────────────────────────── */}
        <section id="pipeline" className="px-4 pb-28" aria-labelledby="pipeline-heading">
          <div className="max-w-6xl mx-auto">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
              className="text-center mb-16"
            >
              <span className="inline-block mb-4 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-semibold uppercase tracking-wider">
                Workflow
              </span>
              <h2 id="pipeline-heading" className="text-3xl sm:text-4xl lg:text-5xl font-bold text-slate-50 mb-4">
                9-step autonomous pipeline
              </h2>
              <p className="text-slate-500 max-w-xl mx-auto text-base leading-relaxed">
                Every agent runs in sequence, with parallel processing and intelligent routing
                to handle failures and edge cases automatically.
              </p>
            </motion.div>

            {/* Grid + terminal side-by-side */}
            <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-8 items-start">
              {/* Steps */}
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                {PIPELINE_STEPS.map((step, i) => (
                  <motion.div
                    key={step.num}
                    custom={i}
                    variants={fadeUp}
                    initial="hidden"
                    whileInView="visible"
                    viewport={{ once: true, margin: '-40px' }}
                    className="glass rounded-2xl p-4 hover:border-slate-600/60 transition-all duration-300 group"
                  >
                    <div className="flex items-center gap-3 mb-3">
                      <div className={`w-9 h-9 rounded-xl ${step.bg} flex items-center justify-center shrink-0 group-hover:scale-110 transition-transform duration-300`}>
                        <step.icon size={17} className={step.color} />
                      </div>
                      <span className="text-slate-600 text-xs font-mono font-semibold">
                        STEP {String(step.num).padStart(2, '0')}
                      </span>
                    </div>
                    <h3 className="text-slate-200 font-semibold text-sm mb-1.5">{step.name}</h3>
                    <p className="text-slate-600 text-xs leading-relaxed">{step.desc}</p>
                  </motion.div>
                ))}
              </div>

              {/* Demo terminal */}
              <motion.div
                ref={terminalRef}
                initial={{ opacity: 0, x: 24 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
                className="glass-bright rounded-2xl overflow-hidden sticky top-24"
                aria-label="Live pipeline demo"
              >
                <div className="flex items-center gap-1.5 px-4 py-3 border-b border-slate-800/80 bg-black/20">
                  <span className="w-2.5 h-2.5 rounded-full bg-red-500/70" />
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-500/70" />
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/70" />
                  <span className="ml-2 text-[10px] text-slate-600 font-mono flex items-center gap-1.5">
                    <Terminal size={10} />
                    qagent — pipeline demo
                  </span>
                </div>

                <div className="p-5 min-h-[300px] holo-grid font-mono text-[12px]">
                  {LOG_LINES.map((line, i) => (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, x: -8 }}
                      animate={logVisible ? { opacity: 1, x: 0 } : { opacity: 0, x: -8 }}
                      transition={{ duration: 0.3, delay: line.delay }}
                      className={`flex gap-2 mb-2 leading-relaxed ${
                        line.text.includes('[OK]')    ? 'text-emerald-400' :
                        line.text.includes('gap')     ? 'text-amber-400'   :
                        line.text.includes('Healing') ? 'text-orange-400'  :
                        'text-green-300/80'
                      }`}
                    >
                      <span className="text-slate-700 shrink-0">›</span>
                      <span>{line.text}</span>
                    </motion.div>
                  ))}
                  <motion.span
                    animate={logVisible ? { opacity: [0, 1, 0] } : { opacity: 0 }}
                    transition={{ delay: 5.2, duration: 1, repeat: Infinity, repeatDelay: 2 }}
                    className="text-slate-700 font-mono"
                  >
                    _
                  </motion.span>
                </div>

                <div className="px-4 py-3 border-t border-slate-800/80 bg-black/20 flex items-center justify-between">
                  <span className="text-xs text-slate-600 font-mono flex items-center gap-1">
                    <Activity size={11} className="text-slate-600" /> 18.4s
                  </span>
                  <span className="flex items-center gap-1.5 text-xs text-emerald-400 font-medium">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    16/16 passed
                  </span>
                </div>
              </motion.div>
            </div>
          </div>
        </section>

        {/* ─────────────────────────── ABOUT / TECH ─────────────────────────── */}
        <section id="about" className="px-4 pb-28" aria-labelledby="about-heading">
          <div className="max-w-6xl mx-auto">
            <motion.div
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
              className="glass-bright gradient-border rounded-3xl p-8 lg:p-12"
            >
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
                <div>
                  <span className="inline-block mb-4 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold uppercase tracking-wider">
                    About
                  </span>
                  <h2 id="about-heading" className="text-3xl lg:text-4xl font-bold text-slate-50 mb-4 leading-tight">
                    Built on modern AI infrastructure
                  </h2>
                  <p className="text-slate-400 text-base leading-relaxed mb-6">
                    QAgent uses{' '}
                    <strong className="text-slate-200">LangGraph StateGraph</strong> to orchestrate
                    a multi-agent pipeline with intelligent 4-way routing, self-healing loops,
                    and full observability. Every step is timed, every failure is classified,
                    and every fix is remembered.
                  </p>
                  <ul className="flex flex-col gap-2.5">
                    {[
                      'GPT-4o → Groq → OpenRouter fallback chain',
                      'FAISS vector memory across 3 namespaces',
                      'Parallel execution with ThreadPoolExecutor',
                      'FastAPI + WebSocket real-time log streaming',
                      'Next.js 16 + Three.js + Framer Motion frontend',
                    ].map(item => (
                      <li key={item} className="flex items-start gap-2.5 text-slate-400 text-sm">
                        <CheckCircle2 size={15} className="text-emerald-400 mt-0.5 shrink-0" />
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  {[
                    { name: 'LangGraph',   tag: 'Orchestration',  from: 'from-blue-600/20',    to: 'to-blue-500/10',    border: 'border-blue-500/20'    },
                    { name: 'GPT-4o-mini', tag: 'Primary LLM',    from: 'from-violet-600/20',  to: 'to-violet-500/10',  border: 'border-violet-500/20'  },
                    { name: 'Playwright',  tag: 'Test Runner',    from: 'from-green-600/20',   to: 'to-green-500/10',   border: 'border-green-500/20'   },
                    { name: 'FAISS',       tag: 'Vector Memory',  from: 'from-amber-600/20',   to: 'to-amber-500/10',   border: 'border-amber-500/20'   },
                    { name: 'FastAPI',     tag: 'Backend API',    from: 'from-teal-600/20',    to: 'to-teal-500/10',    border: 'border-teal-500/20'    },
                    { name: 'Next.js 16',  tag: 'Frontend',       from: 'from-slate-600/20',   to: 'to-slate-500/10',   border: 'border-slate-500/20'   },
                    { name: 'Three.js',    tag: '3D Rendering',   from: 'from-pink-600/20',    to: 'to-pink-500/10',    border: 'border-pink-500/20'    },
                    { name: 'Groq',        tag: 'LLM Fallback',   from: 'from-orange-600/20',  to: 'to-orange-500/10',  border: 'border-orange-500/20'  },
                  ].map(tech => (
                    <div
                      key={tech.name}
                      className={`rounded-xl p-3.5 bg-gradient-to-br ${tech.from} ${tech.to} border ${tech.border}`}
                    >
                      <p className="text-slate-200 font-semibold text-sm">{tech.name}</p>
                      <p className="text-slate-500 text-xs mt-0.5">{tech.tag}</p>
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          </div>
        </section>

        {/* ─────────────────────────── CTA ─────────────────────────── */}
        <section className="px-4 pb-28" aria-label="Call to action">
          <div className="max-w-3xl mx-auto">
            <motion.div
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
              className="glass-bright gradient-border rounded-3xl p-10 lg:p-14 text-center"
            >
              <div className="relative inline-flex mb-6">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center shadow-2xl shadow-blue-500/30">
                  <Bot size={30} className="text-white" />
                </div>
                <span className="absolute inset-0 rounded-2xl animate-ping opacity-20 bg-blue-500" aria-hidden="true" />
              </div>

              <h2 className="text-3xl sm:text-4xl font-bold text-slate-50 mb-4">
                Ready to automate your QA?
              </h2>
              <p className="text-slate-400 text-base leading-relaxed mb-8 max-w-md mx-auto">
                Paste your BRD and let QAgent generate, execute, and heal your entire test suite
                in minutes — not days.
              </p>

              <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                <Link
                  href="/pipeline"
                  className="group flex items-center gap-2 px-8 py-4 rounded-2xl bg-gradient-to-r from-blue-600 to-violet-600 text-white font-semibold text-base hover:shadow-2xl hover:shadow-blue-500/30 hover:scale-[1.03] active:scale-[0.98] transition-all duration-300"
                >
                  <Zap size={17} />
                  Launch Pipeline
                  <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />
                </Link>
                <a
                  href="https://github.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 px-8 py-4 rounded-2xl glass border border-slate-700/60 text-slate-300 font-semibold text-base hover:text-white hover:border-slate-500/60 transition-all duration-300"
                >
                  <GitPullRequest size={17} />
                  View Source
                </a>
              </div>
            </motion.div>
          </div>
        </section>

      </main>

      {/* ─────────────────────────── FOOTER ─────────────────────────── */}
      <footer className="relative z-10 border-t border-slate-800/60" role="contentinfo">
        <div className="max-w-6xl mx-auto px-4 py-10 flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center">
              <Bot size={14} className="text-white" />
            </div>
            <div>
              <span className="font-bold text-sm text-slate-200">QAgent Nexus</span>
              <p className="text-slate-600 text-xs mt-0.5">AI-Powered QA Automation</p>
            </div>
          </div>

          <nav className="flex items-center gap-6" aria-label="Footer links">
            {[
              { href: '/#features', label: 'Features'     },
              { href: '/#pipeline', label: 'How It Works' },
              { href: '/pipeline',  label: 'App'          },
            ].map(link => (
              <Link key={link.href} href={link.href}
                className="text-slate-500 hover:text-slate-300 text-sm transition-colors">
                {link.label}
              </Link>
            ))}
            <a href="https://github.com" target="_blank" rel="noopener noreferrer"
              className="text-slate-500 hover:text-slate-300 transition-colors" aria-label="GitHub">
              <GitPullRequest size={16} />
            </a>
          </nav>

          <p className="text-slate-600 text-xs text-center sm:text-right">
            © {new Date().getFullYear()} QAgent Nexus.
            <br className="sm:hidden" /> All rights reserved.
          </p>
        </div>
      </footer>
    </>
  );
}
