import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'ImpactLink — Connecting Resources to Real Needs', description: 'A partnership workspace for NGOs, contributors, and communities. SDG 17.' };
export default function RootLayout({ children }: { children: React.ReactNode }) { return <html lang="en"><body>{children}</body></html>; }
