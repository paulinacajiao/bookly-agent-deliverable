import type { Metadata } from "next";
import { Fraunces, Inter } from "next/font/google";
import "./globals.css";
import Header from "@/components/Header";
import ChatWidget from "@/components/chat/ChatWidget";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Bookly — Online Bookstore",
  description: "Books, delivered. Free shipping over $35 and 30-day returns.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} ${fraunces.variable}`}>
      <body className="antialiased">
        <Header />
        {children}
        <footer className="mt-20 border-t py-8 text-center text-sm text-muted-foreground">
          © Bookly — a demo bookstore. No real orders are placed.
        </footer>
        <ChatWidget />
      </body>
    </html>
  );
}
