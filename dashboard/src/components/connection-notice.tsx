import { TriangleAlertIcon } from "lucide-react"

import { useData, useHall } from "@/app/data"
import { pageHref } from "@/app/routes"

/** Says in words when Live cannot reach the broker. A problem is not a band, so no red. */
export function ConnectionNotice() {
  const { source } = useData()
  const { connection } = useHall()

  if (source.kind !== "live") return null
  if (connection.phase !== "error" && connection.phase !== "reconnecting") return null

  return (
    <div role="status" className="flex items-start gap-3 border-b bg-paper-sunken px-4 py-2.5 text-[13px] lg:px-6">
      <TriangleAlertIcon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <p className="max-w-[90ch]">
        <span className="font-medium">The dashboard cannot reach the broker. </span>
        <span className="text-muted-foreground">
          {connection.detail}. Start Mosquitto with server/mosquitto.conf, which opens the WebSockets listener on port
          9001, and check the URL and login in{" "}
        </span>
        <a href={pageHref("settings")} className="font-medium underline underline-offset-2">
          Settings
        </a>
        <span className="text-muted-foreground">. It retries every 3 s.</span>
      </p>
    </div>
  )
}
