import Link from "next/link";
import { BookOpen, PackageSearch, ShoppingBag } from "lucide-react";

export default function Header() {
  return (
    <header className="sticky top-0 z-40 border-b bg-background/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link href="/" className="flex items-center gap-2">
          <span className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <BookOpen className="size-5" />
          </span>
          <span className="font-heading text-2xl font-semibold tracking-tight">Bookly</span>
        </Link>
        <nav className="flex items-center gap-1 text-sm">
          <Link href="/" className="rounded-md px-3 py-2 text-muted-foreground hover:bg-muted hover:text-foreground">
            Shop
          </Link>
          <Link
            href="/orders"
            className="flex items-center gap-1.5 rounded-md px-3 py-2 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <PackageSearch className="size-4" />
            <span className="hidden sm:inline">Track an order</span>
          </Link>
          <span className="flex items-center rounded-md px-3 py-2 text-muted-foreground" aria-label="Cart">
            <ShoppingBag className="size-4" />
          </span>
        </nav>
      </div>
    </header>
  );
}
