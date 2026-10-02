import { PlusIcon, ShieldIcon } from "lucide-react"
import { useId, useState } from "react"
import type { FormEvent, ReactNode } from "react"

import { useHall } from "@/app/data"
import { HASH_RE, isBrokerUrl, useSettings } from "@/app/settings"
import { THEMES, THEME_LABEL, useTheme } from "@/app/theme"
import { Hash } from "@/components/invigil/device-tag"
import { EmptyState } from "@/components/invigil/empty-state"
import { AllowedIcon } from "@/components/invigil/icons"
import { Page, Panel } from "@/components/page"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { SourceKind } from "@/data/types"
import { cn } from "@/lib/utils"

function Field({ label, hint, error, children }: { label: string; hint?: ReactNode; error?: string | null; children: (id: string) => ReactNode }) {
  const id = useId()
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children(id)}
      {error ? (
        <p className="text-[13px] font-medium" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p className="text-[13px] text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  )
}

interface SegmentedProps<T extends string> {
  label: string
  value: T
  options: readonly { value: T; label: string }[]
  onChange(value: T): void
}

function Segmented<T extends string>({ label, value, options, onChange }: SegmentedProps<T>) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex w-fit gap-0.5 rounded-md border border-line-strong p-0.5">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={option.value === value}
          onClick={() => onChange(option.value)}
          className={cn(
            "h-7 cursor-pointer rounded-sm px-3 text-[13px] font-medium",
            option.value === value ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

const SOURCES: readonly { value: SourceKind; label: string }[] = [
  { value: "demo", label: "Demo" },
  { value: "live", label: "Live" },
]

function DataSourcePanel() {
  const { settings, password, update, setPassword } = useSettings()
  const hall = useHall()
  const [url, setUrl] = useState(settings.brokerUrl)
  const [username, setUsername] = useState(settings.username)
  const [secret, setSecret] = useState(password)
  const [error, setError] = useState<string | null>(null)

  const dirty = url !== settings.brokerUrl || username !== settings.username || secret !== password

  function save(event: FormEvent) {
    event.preventDefault()
    if (!isBrokerUrl(url)) {
      setError("Enter a WebSockets URL that starts with ws:// or wss://, for example ws://localhost:9001")
      return
    }
    setError(null)
    update({ brokerUrl: url, username })
    setPassword(secret)
  }

  return (
    <Panel
      className="col-span-12 xl:col-span-7"
      title="Data source"
      description="Demo makes mock readings in the browser. Live reads the unit through Mosquitto."
    >
      <form onSubmit={save} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Segmented label="Data source" value={settings.source} options={SOURCES} onChange={(source) => update({ source })} />
          <p className="text-[13px] text-muted-foreground">
            {settings.source === "demo" ? "Demo data is active. The top bar says so on every page." : hall.connection.detail}
          </p>
        </div>

        <Field
          label="Broker URL"
          error={error}
          hint="The WebSockets listener in server/mosquitto.conf, port 9001. The unit itself uses port 1883."
        >
          {(id) => (
            <Input
              id={id}
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              className="data max-w-md"
              spellCheck={false}
              autoComplete="off"
              aria-invalid={error !== null}
            />
          )}
        </Field>

        <div className="grid max-w-md grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Username" hint="Leave empty for a broker without a login.">
            {(id) => (
              <Input id={id} value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
            )}
          </Field>
          <Field label="Password" hint="Kept for this browser tab only.">
            {(id) => (
              <Input
                id={id}
                type="password"
                value={secret}
                onChange={(event) => setSecret(event.target.value)}
                autoComplete="current-password"
              />
            )}
          </Field>
        </div>

        <div>
          <Button type="submit" disabled={!dirty}>
            {settings.source === "live" ? "Save and reconnect" : "Save"}
          </Button>
        </div>
      </form>
    </Panel>
  )
}

function HallPanel() {
  const { settings, update } = useSettings()
  const { theme, setTheme } = useTheme()
  const [name, setName] = useState(settings.hallName)

  return (
    <Panel className="col-span-12 xl:col-span-5" title="Hall and display">
      <div className="flex flex-col gap-4">
        <Field label="Hall name" hint="Shown in the top bar and on the Live page.">
          {(id) => (
            <Input
              id={id}
              value={name}
              maxLength={40}
              onChange={(event) => setName(event.target.value)}
              onBlur={() => {
                const next = name.trim()
                if (next === "") setName(settings.hallName)
                else update({ hallName: next })
              }}
              className="max-w-xs"
            />
          )}
        </Field>
        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">Theme</span>
          <Segmented
            label="Theme"
            value={theme}
            options={THEMES.map((t) => ({ value: t, label: THEME_LABEL[t] }))}
            onChange={setTheme}
          />
          <p className="text-[13px] text-muted-foreground">Dark is the default, for long sessions in a hall.</p>
        </div>
      </div>
    </Panel>
  )
}

function AllowedPanel() {
  const { settings, update } = useSettings()
  const hall = useHall()
  const [addr, setAddr] = useState("")
  const [label, setLabel] = useState("")
  const [error, setError] = useState<string | null>(null)

  const listed = new Set(settings.allowed.map((a) => a.addr))
  const suggestions = Object.values(hall.heard)
    .filter((d) => !listed.has(d.addr))
    .sort((a, b) => b.count - a.count)
    .slice(0, 6)

  function add(event: FormEvent) {
    event.preventDefault()
    const hash = addr.trim().toLowerCase()
    const name = label.trim()
    if (!HASH_RE.test(hash)) {
      setError("Enter the 12-character hash of the device, for example a91f03c2d4e8. Raw addresses are never stored.")
      return
    }
    if (listed.has(hash)) {
      setError("This hash is already on the list.")
      return
    }
    if (name === "") {
      setError("Give the device a label, for example Proctor phone.")
      return
    }
    update({ allowed: [...settings.allowed, { addr: hash, label: name }] })
    setAddr("")
    setLabel("")
    setError(null)
  }

  return (
    <Panel
      className="col-span-12"
      title="Allowed devices"
      description="Proctor devices that may be in the hall. A listed device never raises an alert and is shown as allowed on the map."
      flush
    >
      {settings.allowed.length === 0 ? (
        <EmptyState icon={<ShieldIcon />} title="No allowed devices">
          Devices you add appear here with their hash and label. The list is empty, so every detected device raises an
          alert.
        </EmptyState>
      ) : (
        <ul className="divide-y">
          {settings.allowed.map((device) => (
            <li key={device.addr} className="flex items-center gap-3 px-4 py-2">
              <AllowedIcon className="shrink-0 text-clear" />
              <span className="min-w-0 flex-1 truncate font-medium">{device.label}</span>
              <Hash addr={device.addr} />
              <Button
                variant="ghost"
                size="sm"
                aria-label={`Remove ${device.label} from the allowed devices`}
                onClick={() => update({ allowed: settings.allowed.filter((a) => a.addr !== device.addr) })}
              >
                Remove
              </Button>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={add} className="flex flex-col gap-3 border-t p-4">
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Hash">
            {(id) => (
              <Input
                id={id}
                value={addr}
                onChange={(event) => setAddr(event.target.value)}
                placeholder="a91f03c2d4e8"
                className="data w-44"
                maxLength={12}
                spellCheck={false}
                autoComplete="off"
              />
            )}
          </Field>
          <Field label="Label">
            {(id) => (
              <Input
                id={id}
                value={label}
                onChange={(event) => setLabel(event.target.value)}
                placeholder="Proctor phone"
                className="w-56"
                maxLength={40}
              />
            )}
          </Field>
          <Button type="submit" variant="outline">
            <PlusIcon data-icon="inline-start" />
            Add device
          </Button>
        </div>
        {error ? (
          <p className="text-[13px] font-medium" role="alert">
            {error}
          </p>
        ) : null}
        {suggestions.length > 0 ? (
          <div className="flex flex-wrap items-center gap-2 text-[13px]">
            <span className="text-muted-foreground">Heard now:</span>
            {suggestions.map((d) => (
              <button
                key={d.addr}
                type="button"
                onClick={() => setAddr(d.addr)}
                className="cursor-pointer rounded-sm border px-1.5 py-0.5 data hover:border-line-strong"
              >
                {d.addr}
              </button>
            ))}
          </div>
        ) : null}
      </form>
    </Panel>
  )
}

function ResetPanel() {
  const { reset } = useSettings()
  const { setTheme } = useTheme()

  return (
    <Panel className="col-span-12" title="Reset">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <p className="max-w-[70ch] text-[13px] text-muted-foreground">
          Clears the broker URL, the login, the hall name and the allowed devices stored in this browser, and returns to
          Demo and the dark theme.
        </p>
        <Dialog>
          <DialogTrigger asChild>
            <Button variant="destructive">Reset settings</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Reset all settings?</DialogTitle>
              <DialogDescription>
                The allowed devices list is removed and cannot be recovered. Recorded sessions and results are not
                touched.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline">Cancel</Button>
              </DialogClose>
              <DialogClose asChild>
                <Button
                  variant="destructive"
                  onClick={() => {
                    reset()
                    setTheme("dark")
                  }}
                >
                  Reset settings
                </Button>
              </DialogClose>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Panel>
  )
}

export function SettingsPage() {
  const { settings } = useSettings()
  // Remount the forms after a reset so their fields show the restored values.
  const formKey = `${settings.brokerUrl}|${settings.username}|${settings.hallName}`

  return (
    <Page title="Settings" description="Stored in this browser only. Nothing here is sent to the unit.">
      <DataSourcePanel key={`source-${formKey}`} />
      <HallPanel key={`hall-${formKey}`} />
      <AllowedPanel />
      <ResetPanel />
    </Page>
  )
}
