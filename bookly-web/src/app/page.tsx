import { MessageCircle, RotateCcw, Truck } from "lucide-react";
import BookCard from "@/components/BookCard";
import { supabase, type Book } from "@/lib/supabase";

export const revalidate = 60;

const PERKS = [
  { icon: Truck, title: "Free shipping", body: "On every order over $35" },
  { icon: RotateCcw, title: "30-day returns", body: "Easy refunds on delivered orders" },
  { icon: MessageCircle, title: "Help, instantly", body: "Our support assistant is here 24/7" },
];

export default async function Home() {
  const { data, error } = await supabase
    .from("books")
    .select("book_id, title, author, price, cover_url")
    .order("book_id");
  const books = (data as Book[] | null) ?? [];
  const featured = books.slice(0, 4);

  return (
    <main>
      <section className="border-b bg-gradient-to-b from-accent/60 to-background">
        <div className="mx-auto grid max-w-6xl items-center gap-10 px-4 py-14 md:grid-cols-[1.1fr_1fr] md:py-20">
          <div>
            <p className="text-sm font-medium uppercase tracking-widest text-primary">Autumn reading list</p>
            <h1 className="mt-3 font-heading text-4xl font-semibold leading-tight tracking-tight md:text-5xl">
              Find your next favorite book.
            </h1>
            <p className="mt-4 max-w-md text-lg text-muted-foreground">
              Hand-picked fiction, ideas and memoir — shipped to your door, with returns that don&apos;t make you
              read the fine print.
            </p>
            <a
              href="#catalog"
              className="mt-8 inline-flex h-11 items-center rounded-md bg-primary px-6 font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
            >
              Browse the shelves
            </a>
          </div>
          {featured.length > 0 && (
            <div className="hidden grid-cols-4 items-end gap-3 md:grid" aria-hidden>
              {featured.map((b, i) =>
                b.cover_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    key={b.book_id}
                    src={b.cover_url}
                    alt=""
                    className={`w-full rounded-md object-cover shadow-xl ring-1 ring-black/5 ${i % 2 ? "mb-8" : ""}`}
                  />
                ) : null,
              )}
            </div>
          )}
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-4 px-4 py-8 sm:grid-cols-3">
        {PERKS.map(({ icon: Icon, title, body }) => (
          <div key={title} className="flex items-center gap-3 rounded-lg border bg-card p-4">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-accent text-accent-foreground">
              <Icon className="size-5" />
            </span>
            <div>
              <p className="font-medium">{title}</p>
              <p className="text-sm text-muted-foreground">{body}</p>
            </div>
          </div>
        ))}
      </section>

      <section id="catalog" className="mx-auto max-w-6xl scroll-mt-20 px-4 pt-6">
        <div className="mb-8 flex items-end justify-between">
          <div>
            <h2 className="font-heading text-3xl font-semibold tracking-tight">Staff picks</h2>
            <p className="mt-1 text-muted-foreground">The books our team keeps pressing into friends&apos; hands.</p>
          </div>
          <span className="text-sm text-muted-foreground">{books.length} titles</span>
        </div>

        {error && (
          <p className="rounded-md bg-destructive/10 p-4 text-sm text-destructive">
            Couldn&apos;t load the catalog right now. Please try again shortly.
          </p>
        )}

        <div className="grid grid-cols-2 gap-x-6 gap-y-12 sm:grid-cols-3 lg:grid-cols-5">
          {books.map((book) => (
            <BookCard key={book.book_id} book={book} />
          ))}
        </div>
      </section>
    </main>
  );
}
