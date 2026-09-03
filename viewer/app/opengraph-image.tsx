// Copyright (c) 2026 Reactor Technologies, Inc. All rights reserved.

import { ImageResponse } from "next/og";
import { SITE } from "@/lib/site";

/**
 * The social card, drawn the way GitHub draws a repository's: owner and name
 * top left, the description under them, and a row of facts along the bottom.
 * Rendered once at build, so the two Inter weights are fetched here; when
 * Google Fonts does not answer, the text falls back to the renderer's own
 * sans instead of failing the build.
 */
export const alt = SITE.title;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const canvas = "#0d1117";
const line = "#30363d";
const fg = "#e6edf3";
const muted = "#9198a1";
const red = "#f85149";

export default async function OpenGraphImage() {
  const [regular, bold] = await Promise.all([fetchFont("Inter", 400), fetchFont("Inter", 700)]);
  const fonts = [regular, bold]
    .filter((font): font is NonNullable<typeof font> => font !== null)
    .map(({ weight, data }) => ({ name: "Inter", weight, data, style: "normal" as const }));
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        background: canvas,
        color: fg,
        fontFamily: fonts.length ? "Inter, sans-serif" : "sans-serif",
        padding: 72,
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 32, color: muted }}>
          <RepoGlyph size={32} color={muted} />
          <span>{SITE.owner}</span>
          <span style={{ color: line }}>/</span>
          <span style={{ color: fg, fontWeight: 700 }}>{SITE.repo}</span>
          <span
            style={{
              display: "flex",
              marginLeft: 8,
              padding: "2px 12px",
              border: `2px solid ${line}`,
              borderRadius: 999,
              fontSize: 20,
              color: muted,
            }}
          >
            Public
          </span>
        </div>

        <div
          style={{
            display: "flex",
            marginTop: 48,
            fontSize: 64,
            fontWeight: 700,
            lineHeight: 1.1,
            letterSpacing: -1.5,
          }}
        >
          The First Ever Open Source Movie
        </div>
        <div
          style={{
            display: "flex",
            marginTop: 24,
            fontSize: 28,
            lineHeight: 1.4,
            color: muted,
            maxWidth: 900,
          }}
        >
          Written by its audience in pull requests, screened around the clock. Add a scene, get
          it approved, and it is on air in the next screening.
        </div>

        <div style={{ display: "flex", flex: 1 }} />

        <div style={{ display: "flex", alignItems: "center", gap: 40, fontSize: 24, color: muted }}>
          <Fact>
            <span
              style={{
                display: "flex",
                width: 14,
                height: 14,
                borderRadius: 999,
                background: red,
                boxShadow: `0 0 0 6px rgba(248, 81, 73, 0.25)`,
              }}
            />
            <span style={{ color: fg, fontWeight: 600 }}>On air</span>
            <span>at openslop.live</span>
          </Fact>
          <Fact>
            <BranchGlyph size={24} color={muted} />
            <span style={{ fontFamily: "monospace", color: fg }}>{SITE.branch}</span>
          </Fact>
          <Fact>
            <PullGlyph size={24} color={muted} />
            <span>Add a scene</span>
          </Fact>
        </div>
      </div>

    </div>,
    { ...size, fonts },
  );
}

function Fact({ children }: { children: React.ReactNode }) {
  return <div style={{ display: "flex", alignItems: "center", gap: 12 }}>{children}</div>;
}

/**
 * One weight of a Google font as TTF bytes, or null. The CSS endpoint returns
 * TTF sources for a browser it does not recognise, which is what Satori reads.
 */
async function fetchFont(
  family: string,
  weight: 400 | 700,
): Promise<{ weight: 400 | 700; data: ArrayBuffer } | null> {
  try {
    const css = await fetch(
      `https://fonts.googleapis.com/css2?family=${family}:wght@${weight}&display=swap`,
      { headers: { "User-Agent": "Mozilla/5.0" }, signal: AbortSignal.timeout(5000) },
    ).then((response) => (response.ok ? response.text() : ""));
    const url = css.match(/src: url\(([^)]+)\) format\('(?:truetype|opentype)'\)/)?.[1];
    if (!url) return null;
    const response = await fetch(url, { signal: AbortSignal.timeout(5000) });
    if (!response.ok) return null;
    return { weight, data: await response.arrayBuffer() };
  } catch {
    return null;
  }
}

/* Octicons, inlined: Satori draws SVG but cannot import the site's components. */
function RepoGlyph({ size, color }: { size: number; color: string }) {
  return (
    <svg viewBox="0 0 16 16" width={size} height={size} fill={color}>
      <path d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z" />
    </svg>
  );
}

function BranchGlyph({ size, color }: { size: number; color: string }) {
  return (
    <svg viewBox="0 0 16 16" width={size} height={size} fill={color}>
      <path d="M9.5 3.25a2.25 2.25 0 1 1 3 2.122V6A2.5 2.5 0 0 1 10 8.5H6a1 1 0 0 0-1 1v1.128a2.251 2.251 0 1 1-1.5 0V5.372a2.25 2.25 0 1 1 1.5 0v1.836A2.493 2.493 0 0 1 6 7h4a1 1 0 0 0 1-1v-.628A2.25 2.25 0 0 1 9.5 3.25Zm-6 0a.75.75 0 1 0 1.5 0 .75.75 0 0 0-1.5 0Zm8.25-.75a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5ZM4.25 12a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Z" />
    </svg>
  );
}

function PullGlyph({ size, color }: { size: number; color: string }) {
  return (
    <svg viewBox="0 0 16 16" width={size} height={size} fill={color}>
      <path d="M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25Zm5.677-.177L9.573.677A.25.25 0 0 1 10 .854V2.5h1A2.5 2.5 0 0 1 13.5 5v5.628a2.251 2.251 0 1 1-1.5 0V5a1 1 0 0 0-1-1h-1v1.646a.25.25 0 0 1-.427.177L7.177 3.427a.25.25 0 0 1 0-.354ZM3.75 2.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm0 9.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm8.25.75a.75.75 0 1 0 1.5 0 .75.75 0 0 0-1.5 0Z" />
    </svg>
  );
}
