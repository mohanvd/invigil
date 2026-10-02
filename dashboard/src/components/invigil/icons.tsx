// The five brand icons from docs/brand/icons, redrawn as components in
// currentColor so they follow the theme. 24 px grid, 2 px stroke, square caps,
// mitered joins. Keep both places in step when an icon changes.

import type { ComponentProps, ReactNode } from "react"

import type { DeviceType } from "@/data/types"

type IconProps = Omit<ComponentProps<"svg">, "children">

function Icon({ children, ...props }: IconProps & { children: ReactNode }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="square"
      strokeLinejoin="miter"
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  )
}

export function PhoneIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <rect x="7" y="2.5" width="10" height="19" rx="2" />
      <path d="M10.5 18h3" />
    </Icon>
  )
}

export function EarpieceIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M12.5 21.5V13.8A5.5 5.5 0 1 1 16 10.8V21.5Z" />
      <circle cx="9.8" cy="8.2" r="1.6" fill="currentColor" stroke="none" />
    </Icon>
  )
}

export function SmartwatchIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <rect x="6.5" y="6" width="11" height="12" rx="2" />
      <path d="M9 6V2.5h6V6M9 18v3.5h6V18M12 9.5V12l1.8 1.2" />
    </Icon>
  )
}

export function AllowedIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M12 2.8l7.5 3V11c0 5.2-3.3 8.7-7.5 10.2C7.8 19.7 4.5 16.2 4.5 11V5.8z" />
      <path d="M8.6 11.8l2.4 2.4 4.4-4.6" />
    </Icon>
  )
}

export function UnitIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <rect x="3.5" y="10.5" width="17" height="10" rx="1.5" />
      <path d="M16.5 10.5V3" />
      <circle cx="16.5" cy="3" r="1" fill="currentColor" stroke="none" />
      <path d="M7 15.5h2M11 15.5h2" />
    </Icon>
  )
}

const DEVICE_ICONS = {
  phone: PhoneIcon,
  earpiece: EarpieceIcon,
  smartwatch: SmartwatchIcon,
  allowed: AllowedIcon,
} satisfies Record<DeviceType, (props: IconProps) => ReactNode>

export function DeviceIcon({ type, ...props }: IconProps & { type: DeviceType }) {
  const Component = DEVICE_ICONS[type]
  return <Component {...props} />
}
