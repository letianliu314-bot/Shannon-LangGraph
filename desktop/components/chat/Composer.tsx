"use client";

import { FormEvent, useState } from "react";

interface ComposerProps {
  disabled?: boolean;
  onSend: (content: string) => Promise<void> | void;
}

export function Composer({ disabled, onSend }: ComposerProps) {
  const [value, setValue] = useState("请给我一个市场调研方案。");

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const content = value.trim();
    if (!content || disabled) return;
    await onSend(content);
    setValue("");
  };

  return (
    <form className="composer" onSubmit={onSubmit}>
      <textarea
        aria-label="composer-input"
        placeholder="继续追问..."
        value={value}
        onChange={(event) => setValue(event.target.value)}
        disabled={disabled}
      />
      <button type="submit" disabled={disabled || !value.trim()}>
        {disabled ? "Running..." : "发送"}
      </button>
    </form>
  );
}
