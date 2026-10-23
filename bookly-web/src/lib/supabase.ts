import { createClient } from "@supabase/supabase-js";

// Anon key only: RLS limits the browser to reading `books` and calling `lookup_order`.
export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  { auth: { persistSession: false } },
);

export type Book = {
  book_id: number;
  title: string;
  author: string;
  price: number;
  cover_url: string | null;
};

export type OrderLookup = {
  order_id: string;
  status: string;
  delivered_at: string | null;
  total: number;
  items: string[];
  tracking: string | null;
};
