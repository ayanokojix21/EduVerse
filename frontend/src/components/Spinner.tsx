'use client';

import React from 'react';

interface SpinnerProps {
  size?: number;
  color?: string;
  className?: string;
}

export default function Spinner({ size = 16, color = 'currentColor', className = '' }: SpinnerProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
      className={`animate-spin ${className}`}
      style={{ color }}
    >
      <path
        d="M12 21C7.02944 21 3 16.9706 3 12C3 7.02944 7.02944 3 12 3C16.9706 3 21 7.02944 21 12"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        fill="none"
      />
    </svg>
  );
}
