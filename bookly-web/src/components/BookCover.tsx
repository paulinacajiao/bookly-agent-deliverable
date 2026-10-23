"use client";

import { useState } from "react";

// Fallback tiles if a cover image is missing or fails to load.
const PALETTES = [
  "from-emerald-800 to-emerald-950",
  "from-indigo-700 to-indigo-950",
  "from-rose-700 to-rose-950",
  "from-amber-600 to-amber-800",
  "from-sky-700 to-sky-950",
  "from-stone-600 to-stone-900",
  "from-violet-700 to-violet-950",
  "from-teal-600 to-teal-900",
];

type Props = { id: number; title: string; author: string; coverUrl: string | null };

export default function BookCover({ id, title, author, coverUrl }: Props) {
  const [failed, setFailed] = useState(false);

  if (coverUrl && !failed) {
    return (
      // Open Library redirects to archive.org hosts, so a plain <img> is simpler than next/image here.
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={coverUrl}
        alt={`Cover of ${title} by ${author}`}
        loading="lazy"
        onError={() => setFailed(true)}
        className="aspect-[2/3] w-full rounded-md bg-muted object-cover shadow-md ring-1 ring-black/5 transition-transform duration-300 group-hover:-translate-y-1 group-hover:shadow-xl"
      />
    );
  }

  const palette = PALETTES[id % PALETTES.length];
  return (
    <div
      className={`relative flex aspect-[2/3] flex-col justify-between overflow-hidden rounded-md bg-gradient-to-br ${palette} p-4 text-white shadow-md transition-transform duration-300 group-hover:-translate-y-1 group-hover:shadow-xl`}
    >
      <div className="absolute inset-y-0 left-0 w-2 bg-black/20" />
      <h3 className="pl-2 font-heading text-lg font-semibold leading-snug">{title}</h3>
      <p className="pl-2 text-xs uppercase tracking-widest text-white/80">{author}</p>
    </div>
  );
}
