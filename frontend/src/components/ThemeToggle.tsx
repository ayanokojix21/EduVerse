'use client';

import { Moon, Sun } from 'lucide-react';
import { useTheme } from '@/lib/theme';

interface ThemeToggleProps {
  floating?: boolean;
}

export default function ThemeToggle({ floating }: ThemeToggleProps) {
  const { isDark, toggle } = useTheme();

  if (floating) {
    return (
      <button
        id="theme-toggle-floating"
        onClick={toggle}
        className="btn btn-ghost btn-icon"
        title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
        style={{
          position: 'fixed',
          top: '1.25rem',
          right: '1.25rem',
          zIndex: 100,
          background: 'var(--glass-bg)',
          backdropFilter: 'var(--glass-backdrop)',
          border: '1px solid var(--glass-border)',
          boxShadow: 'var(--shadow-md)',
          width: '40px',
          height: '40px',
          borderRadius: '0.75rem',
          color: 'var(--text-primary)',
          transition: 'all 0.2s',
        }}
      >
        {isDark ? <Sun size={16} /> : <Moon size={16} />}
      </button>
    );
  }

  return (
    <button
      id="theme-toggle"
      onClick={toggle}
      className="btn btn-ghost btn-icon"
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      style={{
        width: '36px',
        height: '36px',
        borderRadius: '0.625rem',
        color: 'var(--text-secondary)',
        transition: 'all 0.2s',
      }}
    >
      {isDark ? <Sun size={15} /> : <Moon size={15} />}
    </button>
  );
}
