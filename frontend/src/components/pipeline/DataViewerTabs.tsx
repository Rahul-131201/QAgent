"use client";

import React, { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Terminal, Database, Code, Activity, ScrollText, BarChart3,
  AlertTriangle, Sparkles, Download, ChevronDown, CheckCircle2,
  XCircle, Clock, Shield
} from 'lucide-react';
import LogLine from './LogLine';

const TABS = [
  { id: 'terminal', label: 'Live Stream',    icon: Terminal, color: 'text-blue-400' },
  { id: 'data',     label: 'Extracted Data', icon: Database, color: 'text-purple-400' },
  { id: 'scripts',  label: 'Scripts',        icon: Code,     color: 'text-green-400' },
];

interface DataViewerTabsProps {
  currentStep: number;
  isProcessing: boolean;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  logs: string[];
  streamBuffer: { agent: string; text: string } | null;
  stateData: Record<string, unknown>;
}

// ── Download helper ────────────────────────────────────────────────────────────
function downloadJson(data: unknown, filename: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

// ── Collapsible Section wrapper ────────────────────────────────────────────────
function Section({
  title, icon: Icon, iconColor, count, countColor, downloadData, downloadName, children
}: {
  title: string;
  icon: React.ElementType;
  iconColor: string;
  count: number;
  countColor: string;
  downloadData: unknown;
  downloadName: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = React.useState(true);
  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass rounded-2xl overflow-hidden border border-slate-800/60"
    >
      {/* Header */}
      <div
        className="flex items-center gap-2 px-4 py-3 cursor-pointer hover:bg-slate-800/30 transition-colors select-none"
        onClick={() => setOpen(o => !o)}
      >
        <Icon size={13} className={iconColor} />
        <span className="text-xs font-semibold uppercase tracking-widest text-slate-400">{title}</span>
        <span className={`ml-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium ${countColor}`}>{count}</span>
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={e => { e.stopPropagation(); downloadJson(downloadData, downloadName); }}
            className="flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-700/40 hover:bg-slate-700/80 text-slate-400 hover:text-white text-[10px] font-medium transition-all"
            title={`Download ${downloadName}`}
          >
            <Download size={10} />
            Download
          </button>
          <ChevronDown
            size={13}
            className={`text-slate-600 transition-transform duration-200 ${open ? '' : '-rotate-90'}`}
          />
        </div>
      </div>
      {/* Content */}
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 pt-1">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.section>
  );
}

// ── User Story Card ────────────────────────────────────────────────────────────
const UserStoryCard = React.memo(({ story }: { story: Record<string, unknown> }) => {
  const [expanded, setExpanded] = React.useState(false);
  const priorityColor = story.priority === 'High' ? 'text-red-400 bg-red-500/10 border-red-500/20'
    : story.priority === 'Medium' ? 'text-amber-400 bg-amber-500/10 border-amber-500/20'
    : 'text-slate-400 bg-slate-500/10 border-slate-500/20';

  return (
    <div className="glass rounded-xl overflow-hidden hover:border-purple-500/30 transition-all duration-300">
      <div
        className="flex items-start gap-3 p-4 cursor-pointer"
        onClick={() => setExpanded(e => !e)}
      >
        <span className="font-mono text-[11px] text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded-full shrink-0 mt-0.5">
          {String(story.story_id ?? '')}
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-slate-200 text-sm font-medium">{String(story.title ?? '')}</p>
          {story.story && (
            <p className="text-slate-500 text-xs mt-1 leading-relaxed">{String(story.story)}</p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {story.priority && (
            <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${priorityColor}`}>
              {String(story.priority)}
            </span>
          )}
          {story.estimation && (
            <span className="text-[10px] text-slate-500 font-mono bg-slate-800 px-1.5 py-0.5 rounded">
              {String(story.estimation)}pts
            </span>
          )}
          {story.qa_confidence !== undefined && (
            <span className={`text-[10px] font-mono ${(story.qa_confidence as number) > 0.8 ? 'text-emerald-400' : 'text-amber-400'}`}>
              {Math.round((story.qa_confidence as number) * 100)}%
            </span>
          )}
          <ChevronDown size={12} className={`text-slate-600 transition-transform ${expanded ? '' : '-rotate-90'}`} />
        </div>
      </div>
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }}
            transition={{ duration: 0.2 }} className="overflow-hidden"
          >
            <div className="border-t border-slate-800/60 px-4 pb-4 pt-3 space-y-3">
              {story.description && (
                <p className="text-slate-400 text-xs leading-relaxed">{String(story.description)}</p>
              )}
              {Array.isArray(story.acceptance_criteria) && story.acceptance_criteria.length > 0 && (
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-slate-600 mb-2">Acceptance Criteria</p>
                  <ul className="space-y-1.5">
                    {(story.acceptance_criteria as string[]).map((ac, i) => (
                      <li key={i} className="flex gap-2 text-xs text-slate-400 leading-relaxed">
                        <span className="text-violet-500 shrink-0 mt-0.5">›</span>
                        {ac}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {story.review_comments && (
                <div className="mt-2 p-2 rounded-lg bg-amber-500/5 border border-amber-500/15">
                  <p className="text-[10px] uppercase tracking-wider text-amber-600 mb-1">Review Comments</p>
                  <p className="text-xs text-amber-400/80 leading-relaxed">{String(story.review_comments)}</p>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
});
UserStoryCard.displayName = 'UserStoryCard';

// ── Test Case Card ─────────────────────────────────────────────────────────────
const TestCaseCard = React.memo(({ tc }: { tc: Record<string, unknown> }) => {
  const [expanded, setExpanded] = React.useState(false);
  return (
    <div className="glass rounded-xl overflow-hidden hover:border-indigo-500/30 transition-all duration-300">
      <div className="flex items-center gap-3 p-3.5 cursor-pointer" onClick={() => setExpanded(e => !e)}>
        <span className="font-mono text-[11px] text-violet-400 bg-violet-500/10 px-2 py-0.5 rounded-full shrink-0">
          {String(tc.tc_id ?? '')}
        </span>
        <p className="text-slate-300 text-xs flex-1 leading-relaxed">{String(tc.title ?? '')}</p>
        <div className="flex items-center gap-2 shrink-0">
          <span className={`text-[10px] uppercase px-2 py-0.5 rounded-full font-medium ${
            tc.type === 'positive' ? 'text-emerald-400 bg-emerald-500/10' :
            tc.type === 'negative' ? 'text-red-400 bg-red-500/10' :
            'text-amber-400 bg-amber-500/10'
          }`}>{String(tc.type ?? '')}</span>
          <ChevronDown size={12} className={`text-slate-600 transition-transform ${expanded ? '' : '-rotate-90'}`} />
        </div>
      </div>
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }}
            transition={{ duration: 0.2 }} className="overflow-hidden"
          >
            <div className="border-t border-slate-800/60 px-4 pb-4 pt-3 space-y-2">
              {Array.isArray(tc.steps) && (
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-slate-600 mb-1.5">Steps</p>
                  <ol className="space-y-1">
                    {(tc.steps as string[]).map((s, i) => (
                      <li key={i} className="flex gap-2 text-xs text-slate-400">
                        <span className="text-slate-600 shrink-0 w-4">{i + 1}.</span>{s}
                      </li>
                    ))}
                  </ol>
                </div>
              )}
              {tc.expected_result && (
                <p className="text-xs text-emerald-400/80 bg-emerald-500/5 border border-emerald-500/15 rounded-lg px-3 py-2">
                  <span className="text-slate-600 text-[10px] uppercase tracking-wider block mb-1">Expected</span>
                  {String(tc.expected_result)}
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
});
TestCaseCard.displayName = 'TestCaseCard';

// ── Execution Result Row ───────────────────────────────────────────────────────
const ExecResultRow = ({ r }: { r: Record<string, unknown> }) => (
  <div className="flex items-center gap-3 py-2 border-b border-slate-800/40 last:border-0">
    {r.status === 'passed'
      ? <CheckCircle2 size={14} className="text-emerald-400 shrink-0" />
      : <XCircle size={14} className="text-red-400 shrink-0" />
    }
    <span className="font-mono text-[11px] text-slate-400 shrink-0">{String(r.tc_id ?? '')}</span>
    <span className="text-xs text-slate-500 flex-1 truncate">{String(r.file ?? '').split(/[/\\]/).pop()}</span>
    {r.duration !== undefined && (
      <span className="flex items-center gap-1 text-[10px] text-slate-600 shrink-0">
        <Clock size={10} />{(r.duration as number).toFixed(2)}s
      </span>
    )}
    {r.error_message && (
      <span className="text-[10px] text-red-400/80 truncate max-w-[200px]">{String(r.error_message)}</span>
    )}
  </div>
);

// ── Main Component ─────────────────────────────────────────────────────────────
export default function DataViewerTabs({
  currentStep, isProcessing, activeTab, setActiveTab,
  logs, streamBuffer, stateData
}: DataViewerTabsProps) {
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (activeTab === 'terminal') {
      logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, streamBuffer, activeTab]);

  // Extract all data fields
  const userStories     = (stateData.user_stories     as Record<string, unknown>[] | undefined) || [];
  const reviewedStories = (stateData.reviewed_stories as Record<string, unknown>[] | undefined) || [];
  const testCases       = (stateData.test_cases       as Record<string, unknown>[] | undefined) || [];
  const coverageGaps    = (stateData.coverage_gaps    as unknown[] | undefined) || [];
  const testScripts     = (stateData.test_scripts     as string[]  | undefined) || [];
  const execResults     = (stateData.execution_results as Record<string, unknown>[] | undefined) || [];
  const failureAnalysis = (stateData.failure_analysis as Record<string, unknown>[] | undefined) || [];
  const healedScripts   = (stateData.healed_scripts   as string[]  | undefined) || [];

  // Pick best stories array — prefer reviewed (has qa_confidence) over raw
  const displayStories = reviewedStories.length > 0 ? reviewedStories : userStories;

  const hasAnyData = displayStories.length > 0 || testCases.length > 0 || coverageGaps.length > 0
    || execResults.length > 0 || failureAnalysis.length > 0;

  const totalTests  = testCases.length;
  const totalScripts = testScripts.length + healedScripts.length;

  if (currentStep === 0 && !isProcessing) return null;

  return (
    <AnimatePresence>
      <motion.div
        key="viewer"
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        className="glass-bright rounded-2xl overflow-hidden flex flex-col flex-1 min-h-[520px]"
      >
        {/* Tab bar */}
        <div className="flex items-center gap-1 px-4 pt-3 pb-0 border-b border-slate-800/80 bg-black/20">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`relative flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium rounded-t-lg transition-all duration-200 ${
                activeTab === tab.id
                  ? `${tab.color} bg-slate-800/60 tab-active`
                  : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800/30'
              }`}
            >
              <tab.icon size={13} />
              {tab.label}
            </button>
          ))}

          {/* Right side metrics */}
          <div className="ml-auto flex items-center gap-3 pb-2 pr-1">
            {totalTests > 0 && (
              <span className="text-[11px] text-slate-500 flex items-center gap-1">
                <Activity size={11} className="text-violet-400" />
                {totalTests} tests
              </span>
            )}
            {totalScripts > 0 && (
              <span className="text-[11px] text-slate-500 flex items-center gap-1">
                <Code size={11} className="text-green-400" />
                {totalScripts} scripts
              </span>
            )}
          </div>
        </div>

        {/* Tab content */}
        <div className="flex-1 relative holo-grid">
          <AnimatePresence mode="wait">

            {/* ── TERMINAL ── */}
            {activeTab === 'terminal' && (
              <motion.div
                key="terminal"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="absolute inset-0 overflow-y-auto p-5"
              >
                <div className="flex items-center gap-1.5 mb-4">
                  <span className="w-2.5 h-2.5 rounded-full bg-red-500/70" />
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-500/70" />
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/70" />
                  <span className="ml-2 text-[10px] text-slate-600 font-mono">qagent — live log stream</span>
                </div>
                {logs.length === 0 ? (
                  <p className="text-slate-700 font-mono text-xs">
                    Waiting for pipeline to start<span className="typewriter-cursor" />
                  </p>
                ) : (
                  logs.map((log, i) => <LogLine key={i} log={log} />)
                )}
                {streamBuffer && (
                  <motion.div
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                    className="flex gap-2 items-start font-mono text-[12px] leading-relaxed text-violet-300/90 mb-1"
                  >
                    <span className="text-slate-600 shrink-0 select-none mt-[1px]">›</span>
                    <span>
                      {streamBuffer.agent && (
                        <span className="text-violet-500/70 mr-1.5 text-[10px] uppercase tracking-wider">
                          [{streamBuffer.agent.replace(/_agent$/, '')}]
                        </span>
                      )}
                      {streamBuffer.text}
                      <span className="typewriter-cursor" />
                    </span>
                  </motion.div>
                )}
                <div ref={logsEndRef} />
              </motion.div>
            )}

            {/* ── DATA ── */}
            {activeTab === 'data' && (
              <motion.div
                key="data"
                initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.25 }}
                className="absolute inset-0 overflow-y-auto p-5"
              >
                {!hasAnyData ? (
                  <div className="h-full flex flex-col items-center justify-center text-slate-600 gap-3">
                    <Database size={36} className="opacity-30" />
                    <p className="text-sm">No data extracted yet</p>
                    <p className="text-xs text-slate-700">Run an agent step to see outputs here</p>
                  </div>
                ) : (
                  <div className="flex flex-col gap-4">

                    {/* User / Reviewed Stories */}
                    {displayStories.length > 0 && (
                      <Section
                        title={reviewedStories.length > 0 ? 'Reviewed User Stories' : 'User Stories'}
                        icon={reviewedStories.length > 0 ? Shield : ScrollText}
                        iconColor={reviewedStories.length > 0 ? 'text-indigo-400' : 'text-purple-400'}
                        count={displayStories.length}
                        countColor={reviewedStories.length > 0 ? 'bg-indigo-500/10 text-indigo-400' : 'bg-purple-500/10 text-purple-400'}
                        downloadData={displayStories}
                        downloadName={reviewedStories.length > 0 ? 'reviewed_stories.json' : 'user_stories.json'}
                      >
                        <div className="flex flex-col gap-2">
                          {displayStories.map((story, idx) => (
                            <UserStoryCard key={idx} story={story} />
                          ))}
                        </div>
                      </Section>
                    )}

                    {/* Test Cases */}
                    {testCases.length > 0 && (
                      <Section
                        title="Test Cases"
                        icon={Activity}
                        iconColor="text-blue-400"
                        count={testCases.length}
                        countColor="bg-blue-500/10 text-blue-400"
                        downloadData={testCases}
                        downloadName="test_cases.json"
                      >
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                          {testCases.map((tc, idx) => (
                            <TestCaseCard key={idx} tc={tc} />
                          ))}
                        </div>
                      </Section>
                    )}

                    {/* Coverage Gaps */}
                    {coverageGaps.length > 0 && (
                      <Section
                        title="Coverage Gaps"
                        icon={BarChart3}
                        iconColor="text-orange-400"
                        count={coverageGaps.length}
                        countColor="bg-orange-500/10 text-orange-400"
                        downloadData={coverageGaps}
                        downloadName="coverage_gaps.json"
                      >
                        <ul className="space-y-2">
                          {(coverageGaps as Record<string, unknown>[]).map((gap, i) => (
                            <li key={i} className="flex gap-2 text-xs text-slate-400 leading-relaxed bg-slate-800/30 rounded-lg px-3 py-2">
                              <span className="text-orange-500/60 shrink-0">›</span>
                              {typeof gap === 'string' ? gap : (gap.description ? String(gap.description) : JSON.stringify(gap))}
                            </li>
                          ))}
                        </ul>
                      </Section>
                    )}

                    {/* Execution Results */}
                    {execResults.length > 0 && (
                      <Section
                        title="Execution Results"
                        icon={Activity}
                        iconColor="text-pink-400"
                        count={execResults.length}
                        countColor="bg-pink-500/10 text-pink-400"
                        downloadData={execResults}
                        downloadName="execution_results.json"
                      >
                        <div className="bg-black/20 rounded-xl px-4 py-2">
                          {execResults.map((r, i) => <ExecResultRow key={i} r={r} />)}
                        </div>
                      </Section>
                    )}

                    {/* Failure Analysis */}
                    {failureAnalysis.length > 0 && (
                      <Section
                        title="Failure Analysis"
                        icon={AlertTriangle}
                        iconColor="text-rose-400"
                        count={failureAnalysis.length}
                        countColor="bg-rose-500/10 text-rose-400"
                        downloadData={failureAnalysis}
                        downloadName="failure_analysis.json"
                      >
                        <div className="flex flex-col gap-2">
                          {(failureAnalysis as Record<string, unknown>[]).map((fa, i) => (
                            <div key={i} className="glass rounded-xl p-3">
                              <div className="flex items-center gap-2 mb-2">
                                <span className="font-mono text-[11px] text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded-full">{String(fa.tc_id ?? '')}</span>
                                {fa.error_type && <span className="text-[10px] text-slate-500">{String(fa.error_type)}</span>}
                              </div>
                              {fa.root_cause && <p className="text-xs text-slate-400 leading-relaxed mb-1"><span className="text-slate-600">Root cause: </span>{String(fa.root_cause)}</p>}
                              {fa.suggestion && <p className="text-xs text-emerald-400/70 leading-relaxed"><span className="text-slate-600">Fix: </span>{String(fa.suggestion)}</p>}
                            </div>
                          ))}
                        </div>
                      </Section>
                    )}

                    {/* Healed Scripts */}
                    {healedScripts.length > 0 && (
                      <Section
                        title="Healed Scripts"
                        icon={Sparkles}
                        iconColor="text-amber-400"
                        count={healedScripts.length}
                        countColor="bg-amber-500/10 text-amber-400"
                        downloadData={healedScripts}
                        downloadName="healed_scripts.json"
                      >
                        <div className="flex flex-col gap-2">
                          {healedScripts.map((path, i) => (
                            <div key={i} className="flex items-center gap-2 bg-black/20 rounded-lg px-3 py-2">
                              <Sparkles size={11} className="text-amber-400 shrink-0" />
                              <span className="font-mono text-xs text-amber-300">{path.split(/[/\\]/).pop()}</span>
                              <span className="text-[10px] text-slate-600 ml-auto truncate">{path}</span>
                            </div>
                          ))}
                        </div>
                      </Section>
                    )}

                  </div>
                )}
              </motion.div>
            )}

            {/* ── SCRIPTS ── */}
            {activeTab === 'scripts' && (
              <motion.div
                key="scripts"
                initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.25 }}
                className="absolute inset-0 overflow-y-auto p-5"
              >
                {testScripts.length === 0 && healedScripts.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-slate-600 gap-3">
                    <Code size={36} className="opacity-30" />
                    <p className="text-sm">No scripts generated yet</p>
                    <p className="text-xs text-slate-700">Run the Script Agent to generate Playwright tests</p>
                  </div>
                ) : (
                  <div className="flex flex-col gap-4">
                    {/* Test Scripts */}
                    {testScripts.length > 0 && (
                      <div>
                        <div className="flex items-center justify-between mb-3">
                          <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-slate-500">
                            <Code size={12} className="text-green-400" />
                            Test Scripts
                            <span className="px-1.5 py-0.5 rounded-full bg-green-500/10 text-green-400 text-[10px]">{testScripts.length}</span>
                          </h3>
                          <button
                            onClick={() => downloadJson(testScripts, 'test_scripts.json')}
                            className="flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-700/40 hover:bg-slate-700/80 text-slate-400 hover:text-white text-[10px] transition-all"
                          >
                            <Download size={10} /> Download all paths
                          </button>
                        </div>
                        <div className="flex flex-col gap-2">
                          {testScripts.map((path, i) => {
                            const fname = path.split(/[/\\]/).pop() ?? path;
                            return (
                              <motion.div
                                key={i}
                                initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: i * 0.05 }}
                                className="glass rounded-xl overflow-hidden"
                              >
                                <div className="flex items-center justify-between px-4 py-2.5">
                                  <div className="flex items-center gap-2">
                                    <span className="w-2 h-2 rounded-full bg-green-400" />
                                    <span className="font-mono text-xs text-green-300">{fname}</span>
                                  </div>
                                  <span className="text-[10px] text-slate-600 truncate max-w-[260px]">{path}</span>
                                </div>
                              </motion.div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Healed Scripts */}
                    {healedScripts.length > 0 && (
                      <div>
                        <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-slate-500 mb-3">
                          <Sparkles size={12} className="text-amber-400" />
                          Healed Scripts
                          <span className="px-1.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 text-[10px]">{healedScripts.length}</span>
                        </h3>
                        <div className="flex flex-col gap-2">
                          {healedScripts.map((path, i) => (
                            <div key={i} className="glass rounded-xl px-4 py-2.5 flex items-center gap-2">
                              <Sparkles size={11} className="text-amber-400" />
                              <span className="font-mono text-xs text-amber-300">{path.split(/[/\\]/).pop()}</span>
                              <span className="text-[10px] text-slate-600 ml-auto truncate max-w-[260px]">{path}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </motion.div>
            )}

          </AnimatePresence>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
