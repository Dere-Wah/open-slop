import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OpenSlop | The First Ever Open Source Movie",
  description:
    "A movie written by its audience, screened around the clock. The screenplay is a branch on GitHub: add a scene in a pull request, get it approved, and it is on air in the next screening.",
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
