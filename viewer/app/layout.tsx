import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Open Slop — a film that never stops playing, that anyone can write",
  description:
    "An open-source film screened around the clock. The screenplay is a branch on GitHub; merge a pull request and it plays.",
};

export const viewport: Viewport = {
  themeColor: "#0d1117",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-dvh bg-canvas text-fg antialiased">{children}</body>
    </html>
  );
}
