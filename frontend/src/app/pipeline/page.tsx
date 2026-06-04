"use client";

import { useCallback } from 'react';
import { motion, useMotionValue, useSpring } from 'framer-motion';
import { Bot, Clock, Activity, Loader2 } from 'lucide-react';
import ParticleField from '@/components/ParticleField';
import Navbar from '@/components/Navbar';

import { usePipelineSession } from './hooks/usePipelineSession';
import BrdInputArea from '@/components/pipeline/BrdInputArea';
import PipelineSidebar from '@/components/pipeline/PipelineSidebar';
import DataViewerTabs from '@/components/pipeline/DataViewerTabs';

export default function PipelineView() {
  const pipeline = usePipelineSession();

  // Mouse parallax for the header orb
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const springX = useSpring(mouseX, { stiffness: 100, damping: 30 });
  const springY = useSpring(mouseY, { stiffness: 100, damping: 30 });

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    const { innerWidth: w, innerHeight: h } = window;
    mouseX.set(((e.clientX / w) - 0.5) * 20);
    mouseY.set(((e.clientY / h) - 0.5) * 20);
  }, [mouseX, mouseY]);

  const passRate: number = (() => {
    const results = (pipeline.stateData.execution_results as { status?: string }[] | undefined) || [];
    if (!results.length) return 0;
    return Math.round(results.filter(r => r?.status === 'passed').length / results.length * 100);
  })();

  const totalSteps = 8; // STEPS.length - 1

  return (
    <div className="relative min-h-screen flex flex-col" onMouseMove={onMouseMove}>
      <Navbar />

      {/* ── Ambient 3D particle field ── */}
      <ParticleField active={pipeline.isProcessing} />

      {/* ── Radial glow blobs ── */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <motion.div
          className="absolute -top-32 -left-32 w-[600px] h-[600px] rounded-full"
          animate={{ opacity: [0.3, 0.5, 0.3], scale: [1, 1.05, 1] }}
          transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
          style={{
            background: 'radial-gradient(circle, rgba(59,130,246,0.15) 0%, transparent 70%)',
            x: springX, y: springY
          }}
        />
        <motion.div
          className="absolute -bottom-32 -right-32 w-[500px] h-[500px] rounded-full"
          animate={{ opacity: [0.2, 0.4, 0.2], scale: [1, 1.08, 1] }}
          transition={{ duration: 10, repeat: Infinity, ease: 'easeInOut', delay: 2 }}
          style={{ background: 'radial-gradient(circle, rgba(139,92,246,0.15) 0%, transparent 70%)' }}
        />
      </div>

      {/* ── Main content ── */}
      <div className="relative z-10 flex flex-col min-h-screen pt-16 p-6 lg:p-8 max-w-[1400px] mx-auto w-full">

        {/* ── Header ── */}
        <motion.header
          initial={{ opacity: 0, y: -24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className="flex items-center justify-between mb-8"
        >
          <div className="flex items-center gap-4">
            <div className="relative">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center shadow-lg shadow-blue-500/30">
                <Bot size={20} className="text-white" />
              </div>
              {pipeline.isProcessing && (
                <span className="absolute -top-1 -right-1 w-3 h-3 bg-emerald-400 rounded-full border-2 border-[#020817]">
                  <span className="absolute inset-0 bg-emerald-400 rounded-full animate-ping opacity-75" />
                </span>
              )}
            </div>
            <div>
              <h1 className="text-2xl lg:text-3xl font-bold tracking-tight">
                <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-violet-400 to-purple-400">
                  QAgent Nexus
                </span>
              </h1>
              <p className="text-slate-500 text-xs lg:text-sm">AI-Powered QA Automation Pipeline</p>
            </div>
          </div>

          {/* Status badges */}
          <div className="hidden md:flex items-center gap-3">
            {pipeline.currentStep > 0 && (
              <motion.div
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full glass text-xs font-medium"
              >
                <Clock size={11} className="text-blue-400" />
                <span className="text-slate-300">Step {pipeline.currentStep}/{totalSteps}</span>
              </motion.div>
            )}
            {pipeline.isProcessing && (
              <motion.div
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-xs text-indigo-300"
              >
                <Loader2 size={11} className="animate-spin" />
                {pipeline.elapsedSecs}s elapsed
              </motion.div>
            )}
            {passRate > 0 && !pipeline.isProcessing && (
              <motion.div
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium ${
                  passRate === 100
                    ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-300'
                    : 'bg-amber-500/10 border border-amber-500/30 text-amber-300'
                }`}
              >
                <Activity size={11} />
                {passRate}% pass rate
              </motion.div>
            )}
          </div>
        </motion.header>

        {/* ── Body ── */}
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-[280px_1fr] xl:grid-cols-[300px_1fr] gap-6">
          
          <PipelineSidebar 
            isProcessing={pipeline.isProcessing}
            currentStep={pipeline.currentStep}
            brdInput={pipeline.brdInput}
            entryStep={pipeline.entryStep}
            entryInput={pipeline.entryInput}
            seededFromStep={pipeline.seededFromStep}
            runNextStep={pipeline.runNextStep}
            seedAndStart={pipeline.seedAndStart}
          />

          <motion.main
            initial={{ opacity: 0, x: 24 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.6, delay: 0.15, ease: [0.22, 1, 0.36, 1] }}
            className="flex flex-col gap-5 min-h-0"
          >
            <BrdInputArea 
              currentStep={pipeline.currentStep}
              brdInput={pipeline.brdInput}
              setBrdInput={pipeline.setBrdInput}
              brdMode={pipeline.brdMode}
              setBrdMode={pipeline.setBrdMode}
              isDragOver={pipeline.isDragOver}
              setIsDragOver={pipeline.setIsDragOver}
              uploadedFile={pipeline.uploadedFile}
              setUploadedFile={pipeline.setUploadedFile}
              isUploading={pipeline.isUploading}
              uploadError={pipeline.uploadError}
              handleFileUpload={pipeline.handleFileUpload}
              entryStep={pipeline.entryStep}
              setEntryStep={pipeline.setEntryStep}
              entryInput={pipeline.entryInput}
              setEntryInput={pipeline.setEntryInput}
            />

            <DataViewerTabs 
              currentStep={pipeline.currentStep}
              isProcessing={pipeline.isProcessing}
              activeTab={pipeline.activeTab}
              setActiveTab={pipeline.setActiveTab}
              logs={pipeline.logs}
              streamBuffer={pipeline.streamBuffer}
              stateData={pipeline.stateData}
            />
          </motion.main>
        </div>
      </div>
    </div>
  );
}
