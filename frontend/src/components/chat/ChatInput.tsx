"use client";

// ─────────────────────────────────────────────────────────────────────────────
// ChatInput — Auto-resizing textarea with image attachment and submit.
//
// Features:
// - Auto-resize textarea (up to 200px)
// - Image attach button with preview + remove
// - Submit on Enter (Shift+Enter for newline)
// - Disabled state during streaming
// - Character limit enforcement (4000)
// ─────────────────────────────────────────────────────────────────────────────

import {
  useRef,
  useState,
  useCallback,
  useEffect,
  type KeyboardEvent,
  type ChangeEvent,
} from "react";

// ─── Props ───────────────────────────────────────────────────────────────────

interface ChatInputProps {
  onSubmit: (text: string, imageData?: string, imageMimetype?: string) => void;
  onStop?: () => void;
  disabled?: boolean;
  isStreaming?: boolean;
  placeholder?: string;
}

// ─── Constants ───────────────────────────────────────────────────────────────

const MAX_CHARS = 4000;
const MAX_IMAGE_SIZE = 5 * 1024 * 1024; // 5 MB
const ACCEPTED_IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp", "image/gif"];

// ─── Component ───────────────────────────────────────────────────────────────

export function ChatInput({
  onSubmit,
  onStop,
  disabled = false,
  isStreaming = false,
  placeholder = "Ask about your course…",
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [text, setText] = useState("");
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [imageData, setImageData] = useState<string | null>(null);
  const [imageMimetype, setImageMimetype] = useState<string>("image/png");
  const [isFocused, setIsFocused] = useState(false);

  // ── Auto-resize textarea ────────────────────────────────────────────────

  const autoResize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, []);

  useEffect(() => {
    autoResize();
  }, [text, autoResize]);

  // Focus textarea on mount
  useEffect(() => {
    if (!disabled) textareaRef.current?.focus();
  }, [disabled]);

  // ── Submit handler ──────────────────────────────────────────────────────

  const handleSubmit = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;

    onSubmit(trimmed, imageData ?? undefined, imageData ? imageMimetype : undefined);
    setText("");
    setImagePreview(null);
    setImageData(null);

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [text, imageData, imageMimetype, disabled, onSubmit]);

  // ── Keyboard handling ───────────────────────────────────────────────────

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit]
  );

  // ── Image attachment ────────────────────────────────────────────────────

  const handleImageSelect = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) {
      alert("Please upload a PNG, JPEG, WebP, or GIF image.");
      return;
    }
    if (file.size > MAX_IMAGE_SIZE) {
      alert("Image must be under 5 MB.");
      return;
    }

    setImageMimetype(file.type);

    // Preview
    const previewUrl = URL.createObjectURL(file);
    setImagePreview(previewUrl);

    // Base64 encode
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // Strip the data URL prefix
      const base64 = result.split(",")[1];
      setImageData(base64);
    };
    reader.readAsDataURL(file);

    // Reset file input
    e.target.value = "";
  }, []);

  const removeImage = useCallback(() => {
    if (imagePreview) URL.revokeObjectURL(imagePreview);
    setImagePreview(null);
    setImageData(null);
  }, [imagePreview]);

  // ── Render ──────────────────────────────────────────────────────────────

  const charCount = text.length;
  const isOverLimit = charCount > MAX_CHARS;
  const canSubmit = text.trim().length > 0 && !disabled && !isOverLimit;

  return (
    <div className="border-t border-[var(--color-border)] bg-[var(--color-bg)]">
      <div className="max-w-[720px] mx-auto px-4 py-3">
        {/* Image preview */}
        {imagePreview && (
          <div className="mb-2 animate-[fade-in_0.2s_ease-out]">
            <div className="relative inline-block">
              <img
                src={imagePreview}
                alt="Attached"
                className="h-16 w-16 object-cover rounded-[var(--radius-lg)] border border-[var(--color-border)]"
              />
              <button
                onClick={removeImage}
                className="
                  absolute -top-1.5 -right-1.5
                  w-5 h-5 rounded-full
                  bg-[var(--color-panel)] border border-[var(--color-border)]
                  text-[var(--color-text-muted)] text-[10px]
                  flex items-center justify-center
                  hover:bg-[var(--color-danger-dim)] hover:text-[var(--color-danger)]
                  transition-colors duration-150
                "
                aria-label="Remove image"
              >
                ✕
              </button>
            </div>
          </div>
        )}

        {/* Input area */}
        <div
          className={`
            flex items-end gap-2
            bg-[var(--color-panel)]
            border rounded-[20px]
            px-3 py-2
            transition-all duration-200
            ${
              isFocused
                ? "border-[var(--color-border-focus)] shadow-[var(--shadow-focus)]"
                : "border-[var(--color-border)]"
            }
            ${disabled ? "opacity-50 pointer-events-none" : ""}
          `}
        >
          {/* Image attach button */}
          <button
            onClick={() => fileInputRef.current?.click()}
            className="
              flex-shrink-0
              w-8 h-8
              flex items-center justify-center
              rounded-full
              text-[var(--color-text-dim)]
              hover:bg-[rgba(239,243,244,0.08)]
              hover:text-[var(--color-text-muted)]
              transition-colors duration-150
              mb-0.5
            "
            aria-label="Attach image"
            tabIndex={-1}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
              <circle cx="9" cy="9" r="2" />
              <path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21" />
            </svg>
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_IMAGE_TYPES.join(",")}
            onChange={handleImageSelect}
            className="hidden"
            aria-hidden
          />

          {/* Textarea */}
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder={placeholder}
            disabled={disabled}
            rows={1}
            className="
              flex-1 min-h-[36px] max-h-[200px]
              bg-transparent
              text-[var(--color-text-main)] text-[15px]
              placeholder:text-[var(--color-text-dim)]
              leading-[1.5]
              resize-none
              outline-none
              py-1
            "
            id="chat-input-textarea"
          />

          {/* Submit / Stop button */}
          {isStreaming ? (
            <button
              onClick={onStop}
              className="
                flex-shrink-0
                w-8 h-8
                flex items-center justify-center
                rounded-full
                bg-[var(--color-danger-dim)]
                text-[var(--color-danger)]
                hover:bg-[rgba(244,33,46,0.2)]
                transition-all duration-200
                mb-0.5
                cursor-pointer
                animate-[fade-in_0.15s_ease-out]
              "
              aria-label="Stop generating"
              title="Stop generating"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <rect x="6" y="6" width="12" height="12" rx="2" />
              </svg>
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={!canSubmit}
              className={`
                flex-shrink-0
                w-8 h-8
                flex items-center justify-center
                rounded-full
                transition-all duration-200
                mb-0.5
                ${
                  canSubmit
                    ? "bg-[var(--color-primary)] text-[var(--color-bg)] hover:bg-[var(--color-primary-hover)] cursor-pointer"
                    : "bg-[rgba(239,243,244,0.08)] text-[var(--color-text-dim)] cursor-not-allowed"
                }
              `}
              aria-label="Send message"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
              </svg>
            </button>
          )}
        </div>

        {/* Character counter */}
        {charCount > MAX_CHARS * 0.8 && (
          <p
            className={`text-[11px] mt-1 text-right pr-2 ${
              isOverLimit ? "text-[var(--color-danger)]" : "text-[var(--color-text-dim)]"
            }`}
          >
            {charCount}/{MAX_CHARS}
          </p>
        )}
      </div>
    </div>
  );
}
