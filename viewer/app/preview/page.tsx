import { notFound } from "next/navigation";
import { PreviewApp } from "./PreviewApp";

/**
 * A fixture-driven copy of the page for working on the design without a
 * projector: `/preview?state=live|loading|intermission|downtime|warming|offair&episodes=120&chat=80`.
 * Development only — in a production build it does not exist.
 */
export const dynamic = "force-dynamic";

export default async function PreviewPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  if (process.env.NODE_ENV === "production") notFound();
  const params = await searchParams;
  const state = typeof params.state === "string" ? params.state : "live";
  const episodes = Number(typeof params.episodes === "string" ? params.episodes : 3) || 3;
  const chat = Number(typeof params.chat === "string" ? params.chat : 3) || 3;
  return <PreviewApp state={state} episodes={episodes} chatCount={chat} />;
}
