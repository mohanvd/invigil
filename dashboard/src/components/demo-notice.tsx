import { DEMO_ONLY, REPO_URL, SITE_URL } from "@/app/build"

/** The strip at the top of the public demo build. Nothing renders in a normal build. */
export function DemoNotice() {
  if (!DEMO_ONLY) return null

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b bg-paper-sunken px-4 py-2 text-[13px] lg:px-6">
      <p className="min-w-0">
        <span className="font-medium">Demo with sample data. </span>
        <span className="text-muted-foreground">The real dashboard runs offline on the laptop next to the unit.</span>
      </p>
      <div className="flex items-center gap-4 font-medium sm:ml-auto">
        <a href={SITE_URL} className="underline underline-offset-2">
          invigil.xyz
        </a>
        <a href={REPO_URL} className="underline underline-offset-2">
          GitHub
        </a>
      </div>
    </div>
  )
}
