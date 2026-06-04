"use client";

import { motion } from 'framer-motion';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Environment } from '@react-three/drei';
import {
  Play, CheckCircle2, Loader2, ScrollText, Cpu, Shield, GitBranch,
  BarChart3, Code, Zap, AlertTriangle, Sparkles, ChevronRight, SkipForward
} from 'lucide-react';
import ThreeAvatar from '@/components/ThreeAvatar';
import { ENTRY_POINTS } from '@/components/pipeline/BrdInputArea';

const STEPS = [
  { label: "BRD Input",          icon: ScrollText, color: "from-slate-500 to-slate-400" },
  { label: "Requirement Agent",  icon: Cpu,        color: "from-blue-600 to-blue-400" },
  { label: "QA Review Agent",    icon: Shield,     color: "from-indigo-600 to-indigo-400" },
  { label: "Test Case Agent",    icon: GitBranch,  color: "from-violet-600 to-violet-400" },
  { label: "Coverage Agent",     icon: BarChart3,  color: "from-purple-600 to-purple-400" },
  { label: "Script Agent",       icon: Code,       color: "from-fuchsia-600 to-fuchsia-400" },
  { label: "Execution Agent",    icon: Zap,        color: "from-pink-600 to-pink-400" },
  { label: "Failure Analysis",   icon: AlertTriangle, color: "from-rose-600 to-rose-400" },
  { label: "Healing Agent",      icon: Sparkles,   color: "from-orange-600 to-amber-400" },
];

function StepNode({ step, idx, currentStep, isProcessing, seededFromStep }: {
  step: typeof STEPS[0]; idx: number; currentStep: number; isProcessing: boolean; seededFromStep: number;
}) {
  const Icon = step.icon;
  const isDone    = idx < currentStep;
  const isActive  = idx === currentStep;
  const isPending = idx > currentStep;
  // A step is "skipped" when it was bypassed by starting from an intermediate entry point
  const isSkipped = seededFromStep > 1 && idx > 0 && idx < seededFromStep && currentStep >= seededFromStep - 1;

  return (
    <motion.div
      initial={{ opacity: 0, x: -16 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: idx * 0.05 }}
      className="relative flex items-center gap-3 group"
    >
      {/* Connector line */}
      {idx < STEPS.length - 1 && (
        <div className="absolute left-[18px] top-[36px] w-0.5 h-6 z-0">
          <div className={`w-full h-full transition-all duration-700 rounded-full ${
            isSkipped ? 'bg-gradient-to-b from-amber-600/50 to-amber-700/30'
            : isDone ? 'bg-gradient-to-b from-green-500 to-blue-500 opacity-80'
            : 'bg-slate-700/50'
          }`} />
        </div>
      )}

      {/* Icon node */}
      <div className={`relative z-10 w-9 h-9 rounded-xl flex items-center justify-center shrink-0 transition-all duration-500 ${
        isSkipped
          ? 'bg-amber-900/30 border border-amber-700/40'
          : isDone
          ? 'step-complete'
          : isActive
          ? 'step-active pulse-ring'
          : 'bg-slate-800/60 border border-slate-700/50'
      }`}>
        {isSkipped ? (
          <SkipForward size={13} className="text-amber-600/70" />
        ) : isDone ? (
          <CheckCircle2 size={15} className="text-green-400" />
        ) : isActive && isProcessing ? (
          <Loader2 size={15} className="text-indigo-400 animate-spin" />
        ) : (
          <Icon size={15} className={isPending ? 'text-slate-600' : 'text-indigo-400'} />
        )}
      </div>

      {/* Label */}
      <div className="flex-1 min-w-0">
        <p className={`text-sm leading-tight truncate transition-all duration-300 ${
          isSkipped
            ? 'text-amber-700/70 line-through text-xs'
            : isActive
            ? 'text-white font-semibold'
            : isDone
            ? 'text-slate-400'
            : 'text-slate-600'
        }`}>
          {step.label}
        </p>
        {isSkipped && (
          <p className="text-amber-700/50 text-[10px] mt-0.5">skipped</p>
        )}
        {isActive && isProcessing && (
          <motion.p
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="text-indigo-400 text-[10px] mt-0.5 typewriter-cursor"
          >
            Processing
          </motion.p>
        )}
      </div>

      {isDone && !isSkipped && (
        <ChevronRight size={12} className="text-green-500/60 shrink-0" />
      )}
    </motion.div>
  );
}

function GlowButton({
  onClick, disabled, isProcessing, currentStep, entryStep,
}: {
  onClick: () => void; disabled: boolean; isProcessing: boolean; currentStep: number; entryStep: number;
}) {
  const isComplete = currentStep >= 8;
  const isIntermediate = entryStep > 1 && currentStep === 0;
  const ep = ENTRY_POINTS.find(e => e.step === entryStep);

  const label = isProcessing
    ? 'Processing…'
    : isComplete
    ? 'Pipeline Complete'
    : isIntermediate
    ? `Initialize from ${ep?.shortLabel ?? 'Step ' + entryStep}`
    : `Run ${STEPS[(currentStep + 1) % STEPS.length]?.label || 'Pipeline'}`;

  return (
    <motion.button
      onClick={onClick}
      disabled={disabled}
      whileHover={disabled ? {} : { scale: 1.02 }}
      whileTap={disabled ? {} : { scale: 0.97 }}
      className={`relative w-full py-3.5 rounded-2xl font-semibold text-sm transition-all overflow-hidden
        ${disabled
          ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
          : isComplete
          ? 'bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-lg shadow-emerald-500/20'
          : isIntermediate
          ? 'bg-gradient-to-r from-amber-600 to-orange-600 text-white shadow-lg shadow-amber-500/20 hover:shadow-amber-500/40'
          : 'bg-gradient-to-r from-blue-600 to-violet-600 text-white shadow-lg shadow-blue-500/20 hover:shadow-blue-500/40'
        }`}
    >
      {!disabled && !isComplete && <span className="absolute inset-0 shimmer" />}
      <span className="relative flex items-center justify-center gap-2">
        {isProcessing ? (
          <><Loader2 size={16} className="animate-spin" /> Processing…</>
        ) : isComplete ? (
          <><CheckCircle2 size={16} /> Pipeline Complete</>
        ) : isIntermediate ? (
          <><SkipForward size={16} /> {label}</>
        ) : (
          <><Zap size={16} /> {label}</>
        )}
      </span>
    </motion.button>
  );
}

interface PipelineSidebarProps {
  isProcessing: boolean;
  currentStep: number;
  brdInput: string;
  entryStep: number;
  entryInput: string;
  seededFromStep: number;
  runNextStep: () => void;
  seedAndStart: () => void;
}

export default function PipelineSidebar({
  isProcessing, currentStep, brdInput,
  entryStep, entryInput, seededFromStep,
  runNextStep, seedAndStart,
}: PipelineSidebarProps) {

  // Decide which function to call and whether the button is disabled
  const isIntermediate = entryStep > 1 && currentStep === 0;
  const handleClick = isIntermediate ? seedAndStart : runNextStep;
  const isDisabled = isProcessing || currentStep >= 8
    || (currentStep === 0 && entryStep === 1 && !brdInput.trim())
    || (currentStep === 0 && entryStep > 1 && !entryInput.trim());

  return (
    <motion.aside
      initial={{ opacity: 0, x: -24 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.6, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
      className="flex flex-col gap-5"
    >
      {/* 3D Avatar card */}
      <div className="glass gradient-border rounded-2xl overflow-hidden relative">
        <div className="h-48 relative">
          <Canvas camera={{ position: [0, 0, 3.2], fov: 50 }}>
            <ambientLight intensity={0.3} />
            <Environment preset="city" />
            <ThreeAvatar active={isProcessing} />
            <OrbitControls
              enableZoom={false}
              enablePan={false}
              autoRotate={!isProcessing}
              autoRotateSpeed={1.5}
            />
          </Canvas>
          <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex items-center gap-1.5 px-3 py-1.5 rounded-full glass text-xs font-medium">
            <span className={`w-1.5 h-1.5 rounded-full ${isProcessing ? 'bg-violet-400 animate-pulse' : 'bg-blue-400'}`} />
            <span className="text-slate-300">{isProcessing ? 'Processing…' : 'Idle'}</span>
          </div>
        </div>
      </div>

      {/* Pipeline steps */}
      <div className="glass rounded-2xl p-5 flex flex-col gap-1">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-500 mb-4 flex items-center gap-2">
          <Play size={11} className="text-blue-400" />
          Pipeline Progress
        </h2>
        <div className="flex flex-col gap-3">
          {STEPS.map((step, idx) => (
            <StepNode
              key={idx} step={step} idx={idx}
              currentStep={currentStep} isProcessing={isProcessing}
              seededFromStep={seededFromStep}
            />
          ))}
        </div>

        <div className="mt-5">
          <GlowButton
            onClick={handleClick}
            disabled={isDisabled}
            isProcessing={isProcessing}
            currentStep={currentStep}
            entryStep={entryStep}
          />
        </div>
      </div>
    </motion.aside>
  );
}
