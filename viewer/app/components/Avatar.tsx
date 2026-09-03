"use client";

import { useState } from "react";
import { avatarUrl, loginFromUrl, loginOf } from "@/lib/github";

/**
 * A contributor's face, the way GitHub draws it. For a `@login` the image is
 * GitHub's own avatar for that login (a CDN image, not an API call), and a
 * display name whose profile `url` names a login gets the same; for anyone
 * else — or when the image fails — a lettered
 * disc in a colour derived from the name, so the same person always gets the
 * same tint.
 */
export function Avatar({
  name,
  url,
  size = 20,
  className = "",
}: {
  name: string;
  url?: string | null;
  size?: number;
  className?: string;
}) {
  const login = loginOf(name) ?? loginFromUrl(url);
  const [broken, setBroken] = useState(false);
  const label = name.replace(/^@/, "");

  if (login && !broken) {
    return (
      <img
        src={avatarUrl(login, size)}
        width={size}
        height={size}
        alt=""
        title={label}
        loading="lazy"
        decoding="async"
        referrerPolicy="no-referrer"
        onError={() => setBroken(true)}
        className={`gh-avatar ${className}`}
        style={{ width: size, height: size }}
      />
    );
  }

  const hue = hashHue(label);
  return (
    <span
      title={label}
      className={`gh-avatar inline-flex items-center justify-center font-semibold uppercase text-fg-on-emphasis ${className}`}
      style={{
        width: size,
        height: size,
        fontSize: Math.max(9, Math.round(size * 0.45)),
        background: `hsl(${hue} 40% 38%)`,
      }}
    >
      {label.slice(0, 1) || "?"}
    </span>
  );
}

function hashHue(text: string): number {
  let hash = 0;
  for (let i = 0; i < text.length; i++) hash = (hash * 31 + text.charCodeAt(i)) >>> 0;
  return hash % 360;
}
