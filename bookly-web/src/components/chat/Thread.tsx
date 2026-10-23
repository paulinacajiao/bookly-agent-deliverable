"use client";

import {
  AuiIf,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
} from "@assistant-ui/react";
import { ArrowDownIcon, BookOpen, PackageSearch, RotateCcw, SendHorizontal, Square, Truck } from "lucide-react";
import type { FC } from "react";
import { MarkdownText } from "@/components/chat/markdown-text";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";

const QUICK_REPLIES = [
  { label: "Track an order", prompt: "I'd like to track my order.", icon: PackageSearch },
  { label: "Return a book", prompt: "I want to return a book.", icon: RotateCcw },
  { label: "Shipping info", prompt: "What are your shipping options?", icon: Truck },
];

const AssistantAvatar: FC = () => (
  <Avatar className="size-8 shrink-0">
    <AvatarFallback className="bg-primary text-primary-foreground">
      <BookOpen className="size-4" />
    </AvatarFallback>
  </Avatar>
);

export const Thread: FC = () => (
  <ThreadPrimitive.Root className="flex h-full flex-col bg-background">
    <ThreadPrimitive.Viewport className="flex flex-1 flex-col overflow-y-auto scroll-smooth px-4 pt-4">
      <AuiIf condition={(s) => s.thread.messages.length === 0}>
        <Welcome />
      </AuiIf>

      <div className="flex flex-col gap-4 pb-4">
        <ThreadPrimitive.Messages components={{ UserMessage, AssistantMessage }} />
      </div>

      <ThreadPrimitive.ViewportFooter className="sticky bottom-0 mt-auto flex flex-col gap-2 bg-background pb-3">
        <ThreadPrimitive.ScrollToBottom asChild>
          <Button
            variant="outline"
            size="icon"
            className="absolute -top-10 self-center rounded-full shadow-sm disabled:invisible"
            aria-label="Scroll to bottom"
          >
            <ArrowDownIcon />
          </Button>
        </ThreadPrimitive.ScrollToBottom>
        <AuiIf condition={(s) => s.thread.messages.length > 0 && !s.thread.isRunning}>
          <QuickReplies />
        </AuiIf>
        <Composer />
      </ThreadPrimitive.ViewportFooter>
    </ThreadPrimitive.Viewport>
  </ThreadPrimitive.Root>
);

const Welcome: FC = () => (
  <div className="flex flex-1 flex-col items-center justify-center gap-3 py-6 text-center">
    <Avatar className="size-14">
      <AvatarFallback className="bg-primary text-primary-foreground">
        <BookOpen className="size-6" />
      </AvatarFallback>
    </Avatar>
    <div>
      <p className="font-heading text-xl font-semibold">Hi, I&apos;m Page 👋</p>
      <p className="mt-1 text-sm text-muted-foreground">
        Bookly&apos;s support assistant. I can track orders, handle returns, and answer shipping questions.
      </p>
    </div>
    <div className="mt-2 flex flex-col gap-2 self-stretch">
      {QUICK_REPLIES.map(({ label, prompt, icon: Icon }) => (
        <ThreadPrimitive.Suggestion key={label} prompt={prompt} send asChild>
          <Button variant="outline" className="h-auto justify-start gap-3 py-3 text-left">
            <Icon className="text-primary" />
            {label}
          </Button>
        </ThreadPrimitive.Suggestion>
      ))}
    </div>
  </div>
);

const QuickReplies: FC = () => (
  <div className="flex gap-2 overflow-x-auto pb-1">
    {QUICK_REPLIES.map(({ label, prompt, icon: Icon }) => (
      <ThreadPrimitive.Suggestion key={label} prompt={prompt} send asChild>
        <button
          type="button"
          className="flex shrink-0 items-center gap-1.5 rounded-full border bg-card px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:border-primary hover:bg-accent"
        >
          <Icon className="size-3.5 text-primary" />
          {label}
        </button>
      </ThreadPrimitive.Suggestion>
    ))}
  </div>
);

const Composer: FC = () => (
  <ComposerPrimitive.Root className="flex items-end gap-2 rounded-xl border bg-card p-1.5 shadow-sm focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/15">
    <ComposerPrimitive.Input
      rows={1}
      autoFocus
      placeholder="Ask about an order, return, or shipping…"
      className="max-h-32 min-h-9 flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none placeholder:text-muted-foreground"
    />
    <AuiIf condition={(s) => !s.thread.isRunning}>
      <ComposerPrimitive.Send asChild>
        <Button size="icon" className="size-9 rounded-lg" aria-label="Send message">
          <SendHorizontal />
        </Button>
      </ComposerPrimitive.Send>
    </AuiIf>
    <AuiIf condition={(s) => s.thread.isRunning}>
      <ComposerPrimitive.Cancel asChild>
        <Button size="icon" variant="secondary" className="size-9 rounded-lg" aria-label="Stop">
          <Square className="fill-current" />
        </Button>
      </ComposerPrimitive.Cancel>
    </AuiIf>
  </ComposerPrimitive.Root>
);

const UserMessage: FC = () => (
  <MessagePrimitive.Root className="flex justify-end">
    <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-primary px-3.5 py-2 text-sm text-primary-foreground">
      <MessagePrimitive.Parts />
    </div>
  </MessagePrimitive.Root>
);

const TypingIndicator: FC = () => (
  <div className="flex items-center gap-1 py-1.5" aria-label="Assistant is typing" role="status">
    {[0, 150, 300].map((delay) => (
      <span
        key={delay}
        className="size-1.5 animate-bounce rounded-full bg-muted-foreground/60"
        style={{ animationDelay: `${delay}ms` }}
      />
    ))}
  </div>
);

const AssistantMessage: FC = () => (
  <MessagePrimitive.Root className="flex items-end gap-2">
    <AssistantAvatar />
    <div className="max-w-[85%] rounded-2xl rounded-bl-sm border bg-card px-3.5 py-2 text-card-foreground shadow-sm">
      <AuiIf condition={(s) => s.message.status?.type === "running" && s.message.parts.length === 0}>
        <TypingIndicator />
      </AuiIf>
      <MessagePrimitive.Parts components={{ Text: MarkdownText }} />
    </div>
  </MessagePrimitive.Root>
);
