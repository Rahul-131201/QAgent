"use client";

import { useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ScrollText, AlignLeft, Upload, FileText, FileSpreadsheet,
  X as XIcon, AlertTriangle, CheckCircle2, Loader2,
  GitBranch, Code, Layers
} from 'lucide-react';

// â”€â”€ Entry point definitions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export const ENTRY_POINTS = [
  {
    step: 1,
    label: "Full Pipeline",
    shortLabel: "BRD",
    desc: "Start with a BRD â€” run all 8 agents",
    icon: ScrollText,
    color: "blue",
    inputLabel: "Business Requirement Document",
    inputHint: "Paste your BRD hereâ€¦\n\nExample: As a user I want to log in with email and password so that I can access my dashboard securely.",
    acceptsUpload: true,
  },
  {
    step: 2,
    label: "From Requirements",
    shortLabel: "Requirements",
    desc: "Have user stories? Skip Requirement Agent",
    icon: FileText,
    color: "indigo",
    inputLabel: "User Stories / Requirements",
    inputHint: "Paste your user stories or requirements text hereâ€¦\n\nExample:\nUS-1: As a user I want to log in with email and password.\nUS-2: As a user I want to reset my password via email link.",
    acceptsUpload: false,
  },
  {
    step: 4,
    label: "From Test Cases",
    shortLabel: "Test Cases",
    desc: "Have test cases? Skip to Coverage Agent",
    icon: GitBranch,
    color: "violet",
    inputLabel: "Test Cases (JSON or plain text)",
    inputHint: `Paste test cases as JSON array or plain text (blank-line separated).\n\nJSON example:\n[\n  {"id":"TC-1","title":"Login test","steps":["Open app","Enter creds"],"expected_result":"Dashboard shown"}\n]`,
    acceptsUpload: false,
  },
  {
    step: 6,
    label: "From Test Scripts",
    shortLabel: "Scripts",
    desc: "Have Playwright scripts? Skip to Execution",
    icon: Code,
    color: "fuchsia",
    inputLabel: "Test Script File Paths",
    inputHint: "One absolute file path per line.\n\nExample:\nC:\\projects\\tests\\test_login.py\nC:\\projects\\tests\\test_checkout.py",
    acceptsUpload: false,
  },
] as const;

const COLOR_MAP: Record<string, { tab: string; active: string; border: string }> = {
  blue:    { tab: "text-blue-300",    active: "bg-blue-600/20 border-blue-500/40 text-blue-300",    border: "border-blue-500/60 ring-blue-500/30" },
  indigo:  { tab: "text-indigo-300",  active: "bg-indigo-600/20 border-indigo-500/40 text-indigo-300",  border: "border-indigo-500/60 ring-indigo-500/30" },
  violet:  { tab: "text-violet-300",  active: "bg-violet-600/20 border-violet-500/40 text-violet-300",  border: "border-violet-500/60 ring-violet-500/30" },
  fuchsia: { tab: "text-fuchsia-300", active: "bg-fuchsia-600/20 border-fuchsia-500/40 text-fuchsia-300", border: "border-fuchsia-500/60 ring-fuchsia-500/30" },
};

interface BrdInputAreaProps {
  currentStep: number;
  // BRD (entry step 1) props
  brdInput: string;
  setBrdInput: (val: string) => void;
  brdMode: 'paste' | 'upload';
  setBrdMode: (mode: 'paste' | 'upload') => void;
  isDragOver: boolean;
  setIsDragOver: (val: boolean) => void;
  uploadedFile: { name: string; chars: number } | null;
  setUploadedFile: (val: { name: string; chars: number } | null) => void;
  isUploading: boolean;
  uploadError: string | null;
  handleFileUpload: (file: File) => void;
  // Intermediate entry props
  entryStep: number;
  setEntryStep: (step: number) => void;
  entryInput: string;
  setEntryInput: (val: string) => void;
}

export default function BrdInputArea({
  currentStep, brdInput, setBrdInput, brdMode, setBrdMode,
  isDragOver, setIsDragOver, uploadedFile, setUploadedFile,
  isUploading, uploadError, handleFileUpload,
  entryStep, setEntryStep, entryInput, setEntryInput,
}: BrdInputAreaProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (currentStep !== 0) return null;

  const selected = ENTRY_POINTS.find(ep => ep.step === entryStep) ?? ENTRY_POINTS[0];
  const colors = COLOR_MAP[selected.color];
  const activeInput = entryStep === 1 ? brdInput : entryInput;
  const setActiveInput = entryStep === 1 ? setBrdInput : setEntryInput;

  return (
    <AnimatePresence mode="popLayout">
      <motion.div
        key="brd"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -16, scale: 0.97 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        className="glass gradient-border rounded-2xl p-6 relative"
      >
        {/* â”€â”€ Entry point selector â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
        <div className="mb-5">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-6 h-6 rounded-lg bg-slate-700/60 flex items-center justify-center">
              <Layers size={13} className="text-slate-400" />
            </div>
            <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-500">
              Pipeline Entry Point
            </h2>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
            {ENTRY_POINTS.map((ep) => {
              const Icon = ep.icon;
              const isActive = entryStep === ep.step;
              const c = COLOR_MAP[ep.color];
              return (
                <button
                  key={ep.step}
                  onClick={() => setEntryStep(ep.step)}
                  className={`relative flex flex-col items-start gap-1.5 p-3 rounded-xl border text-left transition-all duration-200 ${
                    isActive
                      ? `${c.active} shadow-sm`
                      : 'bg-slate-900/40 border-slate-700/50 text-slate-500 hover:border-slate-600 hover:text-slate-400'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <Icon size={13} className={isActive ? c.tab : 'text-slate-600'} />
                    <span className="text-xs font-semibold">{ep.shortLabel}</span>
                  </div>
                  <p className="text-[10px] leading-tight opacity-70">{ep.desc}</p>
                  {isActive && (
                    <motion.div
                      layoutId="entry-pip"
                      className="absolute bottom-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-current opacity-70"
                    />
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* â”€â”€ Input area header â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-lg flex items-center justify-center" style={{ background: 'rgba(99,102,241,0.15)' }}>
              <selected.icon size={13} className={colors.tab} />
            </div>
            <h2 className="text-sm font-semibold text-slate-200">{selected.inputLabel}</h2>
          </div>

          {/* Paste / Upload toggle â€” only for Full Pipeline (step 1) */}
          {entryStep === 1 && (
            <div className="flex items-center gap-0.5 p-0.5 rounded-lg bg-slate-900/70 border border-slate-700/50">
              <button
                onClick={() => setBrdMode('paste')}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-all duration-200 ${
                  brdMode === 'paste' ? 'bg-blue-600/30 text-blue-300' : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                <AlignLeft size={11} /> Paste
              </button>
              <button
                onClick={() => setBrdMode('upload')}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-all duration-200 ${
                  brdMode === 'upload' ? 'bg-violet-600/30 text-violet-300' : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                <Upload size={11} /> Upload
              </button>
            </div>
          )}
        </div>

        {/* â”€â”€ Input content â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
        <AnimatePresence mode="wait">
          {entryStep === 1 && brdMode === 'upload' ? (
            /* Upload mode â€” BRD only */
            <motion.div key="upload" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,.csv"
                className="hidden"
                onChange={e => { const f = e.target.files?.[0]; if (f) handleFileUpload(f); e.target.value = ''; }}
              />
              <div
                onDragOver={e => { e.preventDefault(); setIsDragOver(true); }}
                onDragLeave={() => setIsDragOver(false)}
                onDrop={e => {
                  e.preventDefault(); setIsDragOver(false);
                  const f = e.dataTransfer.files?.[0];
                  if (f) handleFileUpload(f);
                }}
                onClick={() => !isUploading && fileInputRef.current?.click()}
                className={`relative flex flex-col items-center justify-center h-44 rounded-xl border-2 border-dashed cursor-pointer transition-all duration-300 ${
                  isDragOver
                    ? 'border-violet-500/70 bg-violet-500/10'
                    : uploadedFile
                    ? 'border-emerald-500/50 bg-emerald-500/5 cursor-default'
                    : 'border-slate-700/60 bg-black/20 hover:border-slate-600 hover:bg-slate-800/20'
                }`}
              >
                {isUploading ? (
                  <div className="flex flex-col items-center gap-2">
                    <Loader2 size={28} className="text-violet-400 animate-spin" />
                    <p className="text-slate-400 text-sm">Extracting textâ€¦</p>
                  </div>
                ) : uploadedFile ? (
                  <div className="flex flex-col items-center gap-2 px-4 text-center">
                    <div className="flex items-center gap-2">
                      {/\.(xls|xlsx)$/i.test(uploadedFile.name)
                        ? <FileSpreadsheet size={26} className="text-emerald-400" />
                        : <FileText size={26} className="text-emerald-400" />
                      }
                      <button
                        onClick={e => { e.stopPropagation(); setUploadedFile(null); setBrdInput(''); }}
                        className="p-0.5 rounded-md text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-all"
                        title="Remove file"
                      >
                        <XIcon size={14} />
                      </button>
                    </div>
                    <p className="text-emerald-300 text-sm font-medium truncate max-w-xs">{uploadedFile.name}</p>
                    <p className="text-slate-500 text-xs">{uploadedFile.chars.toLocaleString()} characters extracted</p>
                    <p className="text-slate-600 text-[10px]">Click to replace</p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2 pointer-events-none">
                    <Upload size={28} className={`transition-colors ${isDragOver ? 'text-violet-400' : 'text-slate-600'}`} />
                    <p className="text-slate-400 text-sm">Drop file here or <span className="text-violet-400 underline">browse</span></p>
                    <p className="text-slate-600 text-xs">PDF Â· DOC Â· DOCX Â· XLS Â· XLSX Â· TXT Â· CSV â€” max 10 MB</p>
                  </div>
                )}
              </div>
              {uploadError && (
                <motion.p initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} className="mt-2 text-red-400 text-xs flex items-center gap-1">
                  <AlertTriangle size={11} /> {uploadError}
                </motion.p>
              )}
              {uploadedFile && brdInput && (
                <div className="mt-3">
                  <p className="text-slate-600 text-[10px] uppercase tracking-wider mb-1">Preview</p>
                  <div className="h-16 overflow-y-auto bg-black/30 border border-slate-700/40 rounded-lg p-2 text-slate-500 text-[11px] font-mono leading-relaxed">
                    {brdInput.slice(0, 500)}{brdInput.length > 500 && 'â€¦'}
                  </div>
                </div>
              )}
            </motion.div>
          ) : (
            /* Textarea â€” used for all entry points in paste mode */
            <motion.div key={`paste-${entryStep}`} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
              <textarea
                value={activeInput}
                onChange={e => setActiveInput(e.target.value)}
                placeholder={selected.inputHint}
                className={`w-full h-44 bg-black/30 border rounded-xl p-4 text-slate-300 placeholder-slate-600 focus:outline-none focus:ring-1 transition-all resize-none text-sm font-mono leading-relaxed ${colors.border}`}
              />
            </motion.div>
          )}
        </AnimatePresence>

        {/* â”€â”€ Footer â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
        <div className="flex items-center justify-between mt-3">
          <span className="text-slate-600 text-xs">{activeInput.length} characters</span>
          {activeInput.trim() && (
            <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-emerald-400 text-xs flex items-center gap-1">
              <CheckCircle2 size={11} /> Ready
              {entryStep > 1 && (
                <span className="text-slate-500 ml-1">
                  Â· starts at <span className={colors.tab}>{selected.label}</span>
                </span>
              )}
            </motion.span>
          )}
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
