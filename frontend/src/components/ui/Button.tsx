"use client";

// ─────────────────────────────────────────────────────────────────────────────
// Button — Reusable button with variants: primary, ghost, danger, icon
// ─────────────────────────────────────────────────────────────────────────────

import React from "react";
import { Loader2 } from "lucide-react";

type ButtonVariant = "primary" | "ghost" | "danger" | "icon";
type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  fullWidth?: boolean;
}

const variantStyles: Record<ButtonVariant, string> = {
  primary: [
    "bg-[#EFF3F4] text-[#0F1419]",
    "hover:bg-[#D7DBDC]",
    "font-semibold",
    "border border-transparent",
  ].join(" "),

  ghost: [
    "bg-transparent text-[#E7E9EA]",
    "hover:bg-[rgba(239,243,244,0.1)]",
    "border border-[#2F3336]",
    "font-medium",
  ].join(" "),

  danger: [
    "bg-transparent text-[#F4212E]",
    "hover:bg-[rgba(244,33,46,0.1)]",
    "border border-[#F4212E]",
    "font-medium",
  ].join(" "),

  icon: [
    "bg-transparent text-[#71767B]",
    "hover:bg-[rgba(239,243,244,0.1)] hover:text-[#E7E9EA]",
    "border border-transparent",
    "p-2",
  ].join(" "),
};

const sizeStyles: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-[13px] gap-1.5",
  md: "h-9 px-4 text-[14px] gap-2",
  lg: "h-11 px-6 text-[15px] gap-2",
};

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  leftIcon,
  rightIcon,
  fullWidth = false,
  children,
  disabled,
  className = "",
  ...props
}: ButtonProps) {
  const isDisabled = disabled || loading;

  return (
    <button
      {...props}
      disabled={isDisabled}
      className={[
        // Base
        "inline-flex items-center justify-center",
        "rounded-full",
        "transition-all duration-150 ease-out",
        "cursor-pointer select-none",
        "whitespace-nowrap",
        // Variant
        variantStyles[variant],
        // Size (icon variant uses its own padding)
        variant !== "icon" ? sizeStyles[size] : "rounded-full",
        // Full width
        fullWidth ? "w-full" : "",
        // Disabled
        isDisabled ? "opacity-40 cursor-not-allowed pointer-events-none" : "",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {loading ? (
        <Loader2 className="animate-spin" size={14} />
      ) : (
        leftIcon
      )}
      {children && <span>{children}</span>}
      {!loading && rightIcon}
    </button>
  );
}
