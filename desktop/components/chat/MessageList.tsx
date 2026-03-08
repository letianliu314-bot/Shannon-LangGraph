"use client";

import { ChatMessage } from "@/lib/types";

interface MessageListProps {
  messages: ChatMessage[];
  emptyText?: string;
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString();
}

export function MessageList({ messages, emptyText = "开始提问吧。" }: MessageListProps) {
  if (!messages.length) {
    return <div className="empty-state">{emptyText}</div>;
  }

  return (
    <ul className="message-list" aria-label="chat-messages">
      {messages.map((message) => (
        <li key={message.id} className={`message-row ${message.role}`}>
          <div className={`message-bubble ${message.role}`}>
            <div className="message-meta">
              <span>{message.role === "user" ? "You" : "Assistant"}</span>
              <span>{formatTime(message.timestamp)}</span>
            </div>
            <div>{message.content}</div>
            {message.status === "running" ? <div className="typing-dot">typing...</div> : null}
          </div>
        </li>
      ))}
    </ul>
  );
}
