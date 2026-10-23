"use client";

import { AssistantModalPrimitive, AssistantRuntimeProvider, useLocalRuntime } from "@assistant-ui/react";
import { BookOpen, ChevronDown, MessageCircle } from "lucide-react";
import { Thread } from "@/components/chat/Thread";
import { Badge } from "@/components/ui/badge";
import { IS_MOCK_AGENT, booklyAgentAdapter } from "@/lib/agent";

export default function ChatWidget() {
  const runtime = useLocalRuntime(booklyAgentAdapter);

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <AssistantModalPrimitive.Root>
        <AssistantModalPrimitive.Anchor className="fixed right-5 bottom-5 z-50">
          <AssistantModalPrimitive.Trigger asChild>
            <button
              type="button"
              className="group flex h-14 items-center gap-2 rounded-full bg-primary px-5 font-medium text-primary-foreground shadow-lg transition-all hover:scale-105 hover:shadow-xl data-[state=open]:px-4"
              aria-label="Open support chat"
            >
              <MessageCircle className="size-5 group-data-[state=open]:hidden" />
              <span className="group-data-[state=open]:hidden">Support</span>
              <ChevronDown className="hidden size-6 group-data-[state=open]:block" />
            </button>
          </AssistantModalPrimitive.Trigger>
        </AssistantModalPrimitive.Anchor>

        <AssistantModalPrimitive.Content
          side="top"
          align="end"
          sideOffset={12}
          className="z-50 flex h-[min(600px,calc(100dvh-7rem))] w-[min(400px,calc(100vw-2rem))] flex-col overflow-hidden rounded-2xl border bg-background shadow-2xl data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=open]:slide-in-from-bottom-4"
        >
          <header className="flex items-center gap-3 bg-primary px-4 py-3 text-primary-foreground">
            <span className="relative flex size-9 items-center justify-center rounded-full bg-primary-foreground/15">
              <BookOpen className="size-4" />
              <span className="absolute right-0 bottom-0 size-2.5 rounded-full border-2 border-primary bg-emerald-300" />
            </span>
            <div className="flex-1">
              <p className="font-heading leading-tight font-semibold">Bookly Support</p>
              <p className="text-xs text-primary-foreground/75">Typically replies instantly</p>
            </div>
            {IS_MOCK_AGENT && (
              <Badge variant="secondary" className="text-[10px]" title="Replies come from a local mock until the agent is deployed">
                Demo mode
              </Badge>
            )}
          </header>
          <div className="min-h-0 flex-1">
            <Thread />
          </div>
        </AssistantModalPrimitive.Content>
      </AssistantModalPrimitive.Root>
    </AssistantRuntimeProvider>
  );
}
