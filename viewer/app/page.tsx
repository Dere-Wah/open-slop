import { ShowApp } from "./ShowApp";
import { SetupRequired } from "./SetupRequired";

export const dynamic = "force-dynamic";

export default function Page() {
  const configured =
    process.env.LIVEKIT_URL &&
    process.env.LIVEKIT_API_KEY &&
    process.env.LIVEKIT_API_SECRET;
  return configured ? <ShowApp /> : <SetupRequired />;
}
