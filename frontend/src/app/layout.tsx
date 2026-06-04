import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default:  'QAgent Nexus — AI-Powered QA Automation',
    template: '%s | QAgent Nexus',
  },
  description:
    'Transform your Business Requirement Documents into complete, self-healing Playwright test suites using a 9-step autonomous AI pipeline.',
  keywords: ['QA automation', 'AI testing', 'Playwright', 'LangGraph', 'test generation', 'self-healing tests'],
  openGraph: {
    title:       'QAgent Nexus — AI-Powered QA Automation',
    description: 'From BRD to self-healing Playwright scripts in minutes.',
    type:        'website',
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
