"use client";

import { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Terminal, Database, Code, Activity, ScrollText
} from 'lucide-react';
import LogLine from './LogLine';

const TABS = [
  { id: 'terminal', label: 'Live Stream',      icon: Terminal,  color: 'text-blue-400' },
  { id: 'data',     label: 'Extracted Data',   icon: Database,  color: 'text-purple-400' },
  { id: 'scripts',  label: 'Scripts',          icon: Code,      color: 'text-green-400' },
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

// Memoized data card to prevent re-renders on token streams
const UserStoryCard = React.memo(({ story }: { story: Record<string, unknown> }) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass rounded-xl p-4 hover:border-purple-500/30 transition-all duration-300 group"
    >
      <div className="flex items-center justify-between mb-2">
        <span className="font-mono text-[11px] text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded-full">
          {String(story.story_id ?? '')}
        </span>
        {story.qa_confidence !== undefined && (
          <div className="flex items-center gap-1.5">
            <div className="w-16 h-1 rounded-full bg-slate-700 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${(story.qa_confidence as number) > 0.8 ? 'bg-emerald-400' : 'bg-amber-400'}`}
                style={{ width: `${(story.qa_confidence as number) * 100}%` }}
              />
            </div>
            <span className={`text-[10px] ${(story.qa_confidence as number) > 0.8 ? 'text-emerald-400' : 'text-amber-400'}`}>
              {Math.round((story.qa_confidence as number) * 100)}%
            </span>
          </div>
        )}
      </div>
      <p className="text-slate-200 text-sm font-medium">{String(story.title ?? '')}</p>
      {!!story.story && (
        <p className="text-slate-500 text-xs mt-1 leading-relaxed">{String(story.story)}</p>
      )}
    </motion.div>
  );
});
UserStoryCard.displayName = 'UserStoryCard';

const TestCaseCard = React.memo(({ tc }: { tc: Record<string, unknown> }) => {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      className="glass rounded-xl p-3.5 hover:border-indigo-500/30 transition-all duration-300"
    >
      <div className="flex items-center justify-between mb-2">
        <span className="font-mono text-[11px] text-violet-400 bg-violet-500/10 px-2 py-0.5 rounded-full">
          {String(tc.tc_id ?? '')}
        </span>
        <span className={`text-[10px] uppercase px-2 py-0.5 rounded-full font-medium ${
          tc.type === 'positive' ? 'text-emerald-400 bg-emerald-500/10' :
          tc.type === 'negative' ? 'text-red-400 bg-red-500/10' :
          'text-amber-400 bg-amber-500/10'
        }`}>
          {String(tc.type ?? '')}
        </span>
      </div>
      <p className="text-slate-300 text-xs leading-relaxed">{String(tc.title ?? '')}</p>
      {!!tc.priority && (
        <span className="mt-2 inline-block text-[10px] text-slate-600">{String(tc.priority)}</span>
      )}
    </motion.div>
  );
});
TestCaseCard.displayName = 'TestCaseCard';

import React from 'react'; // moving this up

export default function DataViewerTabs({
  currentStep, isProcessing, activeTab, setActiveTab,
  logs, streamBuffer, stateData
}: DataViewerTabsProps) {
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll logs (also triggers on new stream tokens)
  useEffect(() => {
    if (activeTab === 'terminal') {
      logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, streamBuffer, activeTab]);

  const testCases = (stateData.test_cases as unknown[]) || [];
  const userStories = (stateData.user_stories as unknown[] | undefined) || 
                      (stateData.reviewed_stories as unknown[]) || [];
  const testScripts = (stateData.test_scripts as string[]) || [];

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
            {testCases.length > 0 && (
              <span className="text-[11px] text-slate-500 flex items-center gap-1">
                <Activity size={11} className="text-violet-400" />
                {testCases.length} tests
              </span>
            )}
            {testScripts.length > 0 && (
              <span className="text-[11px] text-slate-500 flex items-center gap-1">
                <Code size={11} className="text-green-400" />
                {testScripts.length} scripts
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
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="absolute inset-0 overflow-y-auto p-5"
              >
                {/* Terminal chrome */}
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

                {/* 1.2 — live LLM token stream */}
                {streamBuffer && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
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
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.25 }}
                className="absolute inset-0 overflow-y-auto p-5"
              >
                {Object.keys(stateData).length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-slate-600 gap-3">
                    <Database size={36} className="opacity-30" />
                    <p className="text-sm">No data extracted yet</p>
                  </div>
                ) : (
                  <div className="flex flex-col gap-6">
                    {userStories.length > 0 && (
                      <section>
                        <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-slate-500 mb-3">
                          <ScrollText size={12} className="text-purple-400" />
                          User Stories
                          <span className="ml-auto px-1.5 py-0.5 rounded-full bg-purple-500/10 text-purple-400 text-[10px] normal-case tracking-normal">
                            {userStories.length}
                          </span>
                        </h3>
                        <div className="grid gap-3">
                          {(userStories as Record<string, unknown>[]).map((story, idx) => (
                            <UserStoryCard key={idx} story={story} />
                          ))}
                        </div>
                      </section>
                    )}

                    {testCases.length > 0 && (
                      <section>
                        <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-slate-500 mb-3">
                          <Activity size={12} className="text-blue-400" />
                          Test Cases
                          <span className="ml-auto px-1.5 py-0.5 rounded-full bg-blue-500/10 text-blue-400 text-[10px] normal-case tracking-normal">
                            {testCases.length}
                          </span>
                        </h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          {(testCases as Record<string, unknown>[]).map((tc, idx) => (
                            <TestCaseCard key={idx} tc={tc} />
                          ))}
                        </div>
                      </section>
                    )}
                  </div>
                )}
              </motion.div>
            )}

            {/* ── SCRIPTS ── */}
            {activeTab === 'scripts' && (
              <motion.div
                key="scripts"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.25 }}
                className="absolute inset-0 overflow-y-auto p-5"
              >
                {testScripts.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-slate-600 gap-3">
                    <Code size={36} className="opacity-30" />
                    <p className="text-sm">No scripts generated yet</p>
                    <p className="text-xs text-slate-700">Run the Script Agent to generate Playwright tests</p>
                  </div>
                ) : (
                  <div className="flex flex-col gap-4">
                    {testScripts.map((path, i) => {
                      const fname = path.split(/[/\\]/).pop() ?? path;
                      return (
                        <motion.div
                          key={i}
                          initial={{ opacity: 0, y: 8 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: i * 0.07 }}
                          className="glass rounded-xl overflow-hidden"
                        >
                          <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-800/60 bg-black/20">
                            <div className="flex items-center gap-2">
                              <span className="w-2 h-2 rounded-full bg-green-400" />
                              <span className="font-mono text-xs text-green-300">{fname}</span>
                            </div>
                            <span className="text-[10px] text-slate-600">Written to disk</span>
                          </div>
                          <div className="p-4 font-mono text-xs text-slate-500 bg-black/30">
                            <span className="text-slate-700"># </span>
                            <span className="text-slate-500">Open in editor: </span>
                            <span className="text-blue-400">{path}</span>
                          </div>
                        </motion.div>
                      );
                    })}
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
