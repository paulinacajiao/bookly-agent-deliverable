"use client";

import { useState } from "react";
import { supabase, type OrderLookup } from "@/lib/supabase";

const STATUS_LABELS: Record<string, string> = {
  processing: "Processing",
  shipped: "Shipped — in transit",
  delivered: "Delivered",
  return_initiated: "Return initiated",
  returned: "Returned",
};

export default function OrdersPage() {
  const [orderId, setOrderId] = useState("");
  const [email, setEmail] = useState("");
  const [order, setOrder] = useState<OrderLookup | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function lookup(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setOrder(null);
    setMessage(null);
    const { data, error } = await supabase.rpc("lookup_order", { p_order_id: orderId, p_email: email });
    setLoading(false);
    if (error) {
      setMessage("Something went wrong. Please try again.");
    } else if (!data || data.length === 0) {
      setMessage("We couldn't find an order matching that order number and email.");
    } else {
      setOrder(data[0] as OrderLookup);
    }
  }

  return (
    <main className="mx-auto max-w-xl px-4 py-10">
      <h1 className="font-heading text-3xl font-semibold ">Track an order</h1>
      <p className="mt-2 text-muted-foreground">Enter your order number and the email you used at checkout.</p>

      <form onSubmit={lookup} className="mt-6 space-y-4">
        <label className="block">
          <span className="text-sm font-medium text-foreground">Order number</span>
          <input
            required
            value={orderId}
            onChange={(e) => setOrderId(e.target.value)}
            placeholder="ORD-1001"
            className="mt-1 w-full rounded-md border border-input bg-card px-3 py-2 focus:border-primary focus:outline-none"
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-foreground">Email</span>
          <input
            required
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@email.com"
            className="mt-1 w-full rounded-md border border-input bg-card px-3 py-2 focus:border-primary focus:outline-none"
          />
        </label>
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-primary px-4 py-2 font-medium text-white hover:bg-primary/90 disabled:opacity-60"
        >
          {loading ? "Looking up…" : "Look up order"}
        </button>
      </form>

      {message && <p className="mt-6 rounded-md bg-muted p-4 text-sm text-foreground">{message}</p>}

      {order && (
        <section className="mt-6 rounded-lg border bg-card shadow-sm p-5">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold ">{order.order_id}</h2>
            <span className="rounded-full bg-accent px-3 py-1 text-xs font-medium text-accent-foreground">
              {STATUS_LABELS[order.status] ?? order.status}
            </span>
          </div>
          <ul className="mt-3 list-inside list-disc text-sm text-foreground">
            {order.items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <dl className="mt-4 grid grid-cols-2 gap-2 text-sm">
            <dt className="text-muted-foreground">Total</dt>
            <dd className="">${Number(order.total).toFixed(2)}</dd>
            {order.delivered_at && (
              <>
                <dt className="text-muted-foreground">Delivered</dt>
                <dd className="">{new Date(order.delivered_at).toLocaleDateString()}</dd>
              </>
            )}
            {order.tracking && (
              <>
                <dt className="text-muted-foreground">Tracking</dt>
                <dd className="font-mono ">{order.tracking}</dd>
              </>
            )}
          </dl>
        </section>
      )}
    </main>
  );
}
