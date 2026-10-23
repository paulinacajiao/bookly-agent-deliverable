import type { ChatModelAdapter, ThreadMessage } from "@assistant-ui/react";
import { supabase, type OrderLookup } from "@/lib/supabase";

const AGENT_URL = process.env.NEXT_PUBLIC_AGENT_URL ?? "";

// Until the agent is deployed (Phase 7) the widget talks to a local mock that mimics
// the /chat contract. Set NEXT_PUBLIC_AGENT_URL to the real agent to switch over.
export const IS_MOCK_AGENT = !AGENT_URL || AGENT_URL === "mock" || AGENT_URL.endsWith(".invalid");

const SESSION_KEY = "bookly_conversation_id";

// One conversation_id per browser session so the agent's checkpointer threads memory correctly.
function getConversationId(): string {
  try {
    const existing = sessionStorage.getItem(SESSION_KEY);
    if (existing) return existing;
    const id = crypto.randomUUID();
    sessionStorage.setItem(SESSION_KEY, id);
    return id;
  } catch {
    return crypto.randomUUID();
  }
}

function setConversationId(id: string) {
  try {
    sessionStorage.setItem(SESSION_KEY, id);
  } catch {}
}

function textOf(message: ThreadMessage | undefined): string {
  if (!message) return "";
  return message.content
    .map((part) => (part.type === "text" ? part.text : ""))
    .join("")
    .trim();
}

const sleep = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    const t = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      clearTimeout(t);
      reject(new DOMException("Aborted", "AbortError"));
    });
  });

// Reveal a complete reply a few words at a time so JSON replies still feel streamed.
async function* typeOut(reply: string, signal: AbortSignal) {
  const tokens = reply.match(/\S+\s*|\s+/g) ?? [reply];
  let text = "";
  for (let i = 0; i < tokens.length; i += 2) {
    text += tokens.slice(i, i + 2).join("");
    yield text;
    await sleep(28, signal);
  }
}

async function* streamFromAgent(message: string, signal: AbortSignal) {
  const res = await fetch(`${AGENT_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: getConversationId() }),
    signal,
  });
  if (!res.ok) throw new Error(`Agent returned ${res.status}`);

  // Contract (§5): JSON `{ reply, conversation_id }`. A plain-text streamed body is also accepted.
  if (res.headers.get("content-type")?.includes("application/json")) {
    const data: { reply: string; conversation_id?: string } = await res.json();
    if (data.conversation_id) setConversationId(data.conversation_id);
    yield* typeOut(data.reply, signal);
    return;
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let text = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    text += decoder.decode(value, { stream: true });
    yield text;
  }
}

// --- Mock agent -------------------------------------------------------------

const STATUS_COPY: Record<string, string> = {
  processing: "is **being prepared** — it hasn't shipped yet",
  shipped: "has **shipped** and is on its way",
  delivered: "was **delivered**",
  return_initiated: "has a **return in progress**",
  returned: "was **returned** and refunded",
};

function describeOrder(order: OrderLookup, wantsReturn: boolean): string {
  const lines = [`Thanks! Order **${order.order_id}** ${STATUS_COPY[order.status] ?? order.status}.`, ""];
  lines.push(`- **Items:** ${order.items.join(", ")}`);
  lines.push(`- **Total:** $${Number(order.total).toFixed(2)}`);
  if (order.delivered_at) lines.push(`- **Delivered:** ${new Date(order.delivered_at).toLocaleDateString()}`);
  if (order.tracking) lines.push(`- **Tracking:** \`${order.tracking}\``);

  if (wantsReturn) {
    lines.push("");
    if (order.status !== "delivered" || !order.delivered_at) {
      lines.push("This order hasn't been delivered yet, so it isn't eligible for a return. You can start one once it arrives.");
    } else {
      const days = Math.floor((Date.now() - new Date(order.delivered_at).getTime()) / 86_400_000);
      if (days > 30) {
        lines.push(`It was delivered ${days} days ago, which is outside our *30-day return window*, so I can't refund it.`);
      } else if (Number(order.total) <= 50) {
        lines.push("Good news — it's within the 30-day window and eligible for a **full refund**. Shall I go ahead?");
      } else {
        lines.push("It's within the 30-day window. Refunds over $50 need a quick review by our team — want me to submit it?");
      }
    }
  }
  return lines.join("\n");
}

async function mockReply(messages: readonly ThreadMessage[]): Promise<string> {
  const userTexts = messages.filter((m) => m.role === "user").map(textOf);
  const latest = (userTexts.at(-1) ?? "").toLowerCase();
  const all = userTexts.join(" ");

  const orderId = all.match(/ord-?\s?(\d{4})/i);
  const email = all.match(/[\w.+-]+@[\w-]+\.[\w.]+/);
  const wantsReturn = /return|refund/i.test(all);

  if (/shipping|deliver(y|ies)|how long/.test(latest) && !orderId) {
    return [
      "Here's how shipping works at Bookly:",
      "",
      "- **Standard (free over $35):** 3–5 business days",
      "- **Express ($9.99):** 1–2 business days",
      "- Orders placed before 2pm ET ship the *same day*",
      "",
      "Want me to check on a specific order?",
    ].join("\n");
  }

  if (orderId && email) {
    const { data, error } = await supabase.rpc("lookup_order", {
      p_order_id: `ORD-${orderId[1]}`,
      p_email: email[0],
    });
    if (error) return "Sorry — I couldn't reach our order system just now. Please try again in a moment.";
    if (!data?.length) {
      return "I couldn't find an order matching that order number and email. Could you double-check both?";
    }
    return describeOrder(data[0] as OrderLookup, wantsReturn);
  }

  if (wantsReturn) {
    return [
      "I can help with a return. Our policy in short:",
      "",
      "- Returns are accepted within *30 days of delivery*",
      "- Refunds go back to your original payment method",
      "",
      "What's your **order number** (e.g. `ORD-1001`) and the **email** on the order?",
    ].join("\n");
  }

  if (/track|where|order|status/.test(latest) || orderId || email) {
    if (orderId) return "Got the order number — what's the **email address** on the order?";
    if (email) return "Thanks — and what's the **order number**? It looks like `ORD-1001`.";
    return "Happy to track it down! What's your **order number** (e.g. `ORD-1001`) and the **email** you used at checkout?";
  }

  if (/^(hi|hey|hello)\b/.test(latest)) {
    return "Hi there! I can help you **track an order**, **start a return**, or answer **shipping questions**. What do you need?";
  }

  return "I can help with **orders**, **returns & refunds**, and **shipping**. Could you tell me a bit more about what you need?";
}

async function* streamFromMock(messages: readonly ThreadMessage[], signal: AbortSignal) {
  await sleep(500 + Math.random() * 400, signal); // let the typing indicator show
  yield* typeOut(await mockReply(messages), signal);
}

// ---------------------------------------------------------------------------

export const booklyAgentAdapter: ChatModelAdapter = {
  async *run({ messages, abortSignal }) {
    try {
      const stream = IS_MOCK_AGENT
        ? streamFromMock(messages, abortSignal)
        : streamFromAgent(textOf(messages.at(-1)), abortSignal);
      for await (const text of stream) {
        yield { content: [{ type: "text", text }] };
      }
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      yield {
        content: [{ type: "text", text: "Sorry, I can't reach support right now. Please try again in a moment." }],
      };
    }
  },
};
