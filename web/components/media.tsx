"use client";

import { useState } from "react";
import { flagUrl, playerPhotoUrl } from "@/lib/flags";

export function PlayerPhoto({
  id,
  name,
  size = 40,
}: {
  id: string | number | null | undefined;
  name: string;
  size?: number;
}) {
  const src = playerPhotoUrl(id);
  const [failed, setFailed] = useState(false);
  const initial = name.trim().split(/\s+/).pop()?.slice(0, 1) ?? "?";

  const h = Math.round(size * 1.25);
  if (!src || failed) {
    return (
      <span className="player-photo fallback" style={{ width: size, height: h }}>
        {initial}
      </span>
    );
  }

  return (
    // FotMob serves fixed portraits; onError swaps to initials.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt=""
      width={size}
      height={h}
      className="player-photo"
      style={{ width: size, height: h }}
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
    />
  );
}

export function Flag({
  code,
  title,
}: {
  code: string | null | undefined;
  title?: string | null;
}) {
  const src = flagUrl(code);
  if (!src) {
    return code ? <span className="flag-code">{code}</span> : null;
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={title ?? code ?? ""}
      title={title ?? code ?? ""}
      className="flag"
      width={20}
      height={14}
    />
  );
}
