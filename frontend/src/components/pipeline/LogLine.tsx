"use client";

import React from 'react';
import { motion } from 'framer-motion';

interface LogLineProps {
  log: string;
}

const LogLine = React.memo(({ log }: LogLineProps) => {
  const isError = log.includes('❌') || log.toLowerCase().includes('error');
  const isSuccess = log.includes('✅') || log.includes('passed') || log.includes('complete');
  const isWarn = log.includes('⚠️') || log.toLowerCase().includes('warn');

  return (
    <motion.div
      initial={{ opacity: 0, x: -8, filter: 'blur(4px)' }}
      animate={{ opacity: 1, x: 0, filter: 'blur(0px)' }}
      transition={{ duration: 0.25 }}
      className={`flex gap-2 mb-1 items-start font-mono text-[12px] leading-relaxed ${
        isError ? 'text-red-400' :
        isSuccess ? 'text-emerald-400' :
        isWarn ? 'text-amber-400' :
        'text-green-300/80'
      }`}
    >
      <span className="text-slate-600 shrink-0 select-none mt-[1px]">›</span>
      <span>{log}</span>
    </motion.div>
  );
});

LogLine.displayName = 'LogLine';

export default LogLine;
