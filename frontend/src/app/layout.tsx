import type { Metadata } from 'next';
import './globals.css';
import Providers from '@/components/Providers';

export const metadata: Metadata = {
  title: 'EduVerse — AI Tutoring Platform',
  description: 'Your personalized AI tutor powered by Google Classroom. Ask questions, explore concepts, and master your courses.',
  keywords: ['AI tutor', 'Google Classroom', 'education', 'EduVerse'],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <body>
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  );
}
