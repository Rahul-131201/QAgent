"use client";

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { Bot, Menu, X, ChevronRight, Zap } from 'lucide-react';

const NAV_LINKS = [
  { href: '/#features',  label: 'Features'      },
  { href: '/#pipeline',  label: 'How It Works'  },
  { href: '/#about',     label: 'About'         },
];

export default function Navbar() {
  const [scrolled,    setScrolled]    = useState(false);
  const [mobileOpen,  setMobileOpen]  = useState(false);
  const pathname = usePathname();
  const isPipeline = pathname === '/pipeline';

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', handler, { passive: true });
    return () => window.removeEventListener('scroll', handler);
  }, []);

  // Close mobile menu on route change
  useEffect(() => { setMobileOpen(false); }, [pathname]);

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${
        scrolled || mobileOpen
          ? 'glass border-b border-white/[0.06] shadow-xl shadow-black/20'
          : 'bg-transparent'
      }`}
      role="banner"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">

        {/* Logo */}
        <div className="flex-1">
          {!isPipeline && (
            <Link
              href="/"
              className="flex items-center gap-2.5 group w-fit"
              aria-label="QAgent Nexus – Home"
            >
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center shadow-lg shadow-blue-500/30 group-hover:shadow-blue-500/50 group-hover:scale-105 transition-all duration-300">
                <Bot size={17} className="text-white" />
              </div>
              <span className="font-bold text-base tracking-tight">
                <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-violet-400">
                  QAgent
                </span>
                <span className="text-slate-300"> Nexus</span>
              </span>
            </Link>
          )}
        </div>

        {/* Desktop Nav */}
        <nav className="hidden md:flex items-center gap-1" aria-label="Primary navigation">
          {!isPipeline && NAV_LINKS.map(link => (
            <Link
              key={link.href}
              href={link.href}
              className="px-4 py-2 text-sm text-slate-400 hover:text-slate-100 rounded-xl hover:bg-slate-800/50 transition-all duration-200"
            >
              {link.label}
            </Link>
          ))}

          {isPipeline ? (
            <Link
              href="/"
              className="flex items-center gap-1.5 px-4 py-2 text-sm text-slate-400 hover:text-slate-100 rounded-xl hover:bg-slate-800/50 transition-all duration-200"
            >
              ← Home
            </Link>
          ) : (
            <Link
              href="/pipeline"
              className="ml-2 flex items-center gap-1.5 px-4 py-2 rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 text-white text-sm font-semibold hover:shadow-lg hover:shadow-blue-500/30 hover:scale-[1.02] active:scale-[0.98] transition-all duration-200"
            >
              <Zap size={13} />
              Launch App
              <ChevronRight size={13} />
            </Link>
          )}
        </nav>

        {/* Mobile toggle */}
        <button
          onClick={() => setMobileOpen(v => !v)}
          className="md:hidden w-9 h-9 flex items-center justify-center rounded-xl hover:bg-slate-800/50 transition-all text-slate-400 hover:text-slate-200"
          aria-expanded={mobileOpen}
          aria-label="Toggle navigation menu"
        >
          {mobileOpen ? <X size={18} /> : <Menu size={18} />}
        </button>
      </div>

      {/* Mobile menu */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.nav
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
            className="md:hidden overflow-hidden border-t border-white/[0.06]"
            aria-label="Mobile navigation"
          >
            <div className="px-4 py-4 flex flex-col gap-1">
              {!isPipeline && NAV_LINKS.map(link => (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => setMobileOpen(false)}
                  className="px-4 py-3 rounded-xl text-sm text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 transition-all"
                >
                  {link.label}
                </Link>
              ))}
              {isPipeline ? (
                <Link
                  href="/"
                  onClick={() => setMobileOpen(false)}
                  className="px-4 py-3 rounded-xl text-sm text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 transition-all"
                >
                  ← Back to Home
                </Link>
              ) : (
                <Link
                  href="/pipeline"
                  onClick={() => setMobileOpen(false)}
                  className="mt-1 flex items-center justify-center gap-1.5 px-4 py-3 rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 text-white text-sm font-semibold"
                >
                  <Zap size={14} /> Launch App
                </Link>
              )}
            </div>
          </motion.nav>
        )}
      </AnimatePresence>
    </header>
  );
}
