import { Plus } from "lucide-react";
import BookCover from "@/components/BookCover";
import { Button } from "@/components/ui/button";
import type { Book } from "@/lib/supabase";

export default function BookCard({ book }: { book: Book }) {
  return (
    <article className="group flex flex-col">
      <BookCover id={book.book_id} title={book.title} author={book.author} coverUrl={book.cover_url} />
      <div className="mt-4 flex flex-1 flex-col">
        <h3 className="line-clamp-2 font-heading text-base font-semibold leading-snug">{book.title}</h3>
        <p className="mt-0.5 text-sm text-muted-foreground">{book.author}</p>
        <div className="mt-auto flex items-center justify-between pt-3">
          <span className="font-semibold">${Number(book.price).toFixed(2)}</span>
          <Button size="sm" variant="outline" aria-label={`Add ${book.title} to cart`}>
            <Plus /> Add
          </Button>
        </div>
      </div>
    </article>
  );
}
