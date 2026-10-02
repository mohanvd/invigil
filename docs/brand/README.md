# Invigil brand

Everything the project makes (poster, portfolio, logbook, slides, badges, the dashboard and the digital twin) uses this one look.

## Files here

| File | What it is |
|---|---|
| `logo/invigil-logo.svg`, `logo/invigil-logo-dark.svg` | The mark and wordmark, for light and dark grounds |
| `logo/invigil-mark*.svg` | The mark alone: color, dark, one-color navy, one-color white |
| `icons/*.svg` | Phone, earpiece, smartwatch, allowed, unit. 24 px grid, 2 px stroke, navy |
| `tokens.json` | The source of truth: colors in both themes, type styles, spacing, radii |
| `tokens.css` | The same tokens as CSS custom properties (`.dark` or `[data-theme="dark"]` for dark) |
| `shadcn-theme.css` | The tokens mapped onto shadcn/ui's theme variables for Tailwind CSS v4 |

Fonts: Archivo, IBM Plex Sans and IBM Plex Mono, all under the SIL Open Font License. Get them from fonts.google.com for documents, or from the `@fontsource` npm packages in code.

The Invigil name and logo identify this project and are not covered by the repository's MIT license. You may show them when referring to Invigil; please don't use them for your own product.

Invigil detects hidden phones, earpieces and smartwatches in exam halls by listening to the 2.4 GHz radio band. One unit sits on the invigilator's desk, hears every device's signal, and a model says what the device is and how far it is. This system is the one look for everything the project makes: the poster, the portfolio, the logbook, the slides, the exhibition badges, the dashboard and the digital twin.

## The one idea

Color means signal strength, and signal strength means distance. The three heat colors are the three distance bands, everywhere:

| Band | Distance from the unit | Token |
|---|---|---|
| Near | under 1 m (strongest signal) | `near` |
| Mid | 1 to 2 m | `mid` |
| Far | 2 to 3.5 m (weakest signal) | `far` |

- Use `near`, `mid` and `far` only to mean a distance band: an alert's band, a ring on the hall map, a bar in an RSSI chart. Never as decoration, never for a heading, never for device types.
- Always put the band's word next to its color (BandChip does). The poster may be printed in grayscale and some judges may be color blind.
- Red is not "error" here. A failed test or a broken unit uses words and icons on neutrals, never `near`.
- The picture behind it all is the hall seen from above: the unit on the front wall, the bands spreading into the room. The logo, SignalRings, the badge and the poster figures all draw that same picture.

## Voice and writing

- Write in English, plainly, for a professional reader: judges, teachers, an engineer. Short sentences, active voice.
- No em dashes. Use a comma, a colon or a new sentence.
- Name things the way the project does: "the unit" (not node or sensor box), "device type", "distance band", "near / mid / far". In running text the bands are lowercase; in labels they are UPPERCASE (`label` style).
- Every number carries its unit, with a space: `-58 dBm`, `1.4 s`, `3 m`, `85%` is the exception.
- Addresses appear only as 12-character hashes in mono (`a91f03c2d4e8`). Never a raw MAC, in any document.
- Name the tagline exactly: "Every signal leaves a trace." Sentence case, with the full stop. Use it once per surface at most (poster footer, badge, title slide).
- Headings in title case on the poster and in documents (the Capstone guide's section names: Abstract, Introduction, Materials, Methods, Results, Analysis, Conclusions, Recommendations, Literature Cited). Sentence case everywhere in the dashboard.
- No emoji.

## Logo

The mark is the hall from above: the walls, the unit on the front wall, and the near, mid and far arcs. The wordmark is "invigil" in Archivo Bold, lowercase. In text the name is always "Invigil".

- `invigil-logo.svg` on `paper` and white; `invigil-logo-dark.svg` on `navy` and dark grounds.
- `invigil-mark.svg` alone where space is square or tight (favicon, app icon, slide corners, the unit's sticker); `invigil-mark-dark.svg` on dark.
- One-color jobs (stamps, a one-color print, embroidery): `invigil-mark-navy.svg` on light, `invigil-mark-white.svg` on navy.
- Clear space: one wall thickness times three (about 25% of the mark's width) on every side. Minimum size: the mark 16 px on screen, 8 mm in print.
- Don't recolor the arcs, swap their order, rotate the mark, add effects, or set the wordmark in another font.
- The school logo and the MOE logo are not part of this system. Use the official files where the poster template asks for them.

## Color

Two themes from one set of tokens. `light` is for anything printed or projected (poster, portfolio, logbook, slides, badges). `dark` is the dashboard's default, for long sessions in a hall.

- Ground: `paper`. Cards, panels, table bodies, chips: `paper-raised`. Wells, zebra rows, the hall map floor: `paper-sunken`.
- Text: `ink` for everything you read; `ink-muted` for metadata, captions and axis labels. Both pass 4.5:1 on all three grounds in both themes; `ink` also passes on every `*-soft` tint.
- Lines: `line` for hairlines that only separate; `line-strong` where a border marks a control or a wall (3:1 or more on every ground).
- Brand: `navy` for title bars, chapter openers and the logo; text on it is `on-navy`.
- Actions: the primary button is `action` with `on-action`. Keyboard focus is a 2 px solid `focus` ring with a 2 px offset (3:1 or more on every surface).
- Bands: `near`, `mid`, `far` for marks (arcs, dots, bars, rings; 3:1 or more on every ground); `near-soft`, `mid-soft`, `far-soft` behind a new alert or a zone on the hall map, with `ink` text on them.
- Allowed and healthy: `clear` for an allowed device, a unit that is online and a passed requirement; `clear-soft` behind it. Always with a check or a word.
- Nothing else. No gradients, no extra hues. If you need to tell more things apart, use words, icons or position.

## Typography

Three families, all free from Google Fonts:

- **Archivo** (700, 800) for titles and section headings: `display`, `title`, `heading`, and the poster and document headings.
- **IBM Plex Sans** (400, 500, 600) for everything you read: `subheading`, `body`, `body-sm`, `poster-body`, `doc-body`.
- **IBM Plex Mono** (400, 500) for anything measured or machine-made: `metric`, `data`, `label`. Readings, hashes, timestamps, codes, LO codes, commit hashes.

Rules:

- One `display` per screen or slide. Headings never in Plex Sans, body never in Archivo.
- `label` is always UPPERCASE with its letter spacing; use it for eyebrows, chip text and table column labels.
- Numbers that line up in columns use mono or tabular figures.
- Poster sizes, for the school's 110 x 80 cm landscape sheet (1 pt = 1.333 px in the tokens): title 81 pt (`poster-title`), school line and names 60 pt (`poster-meta`, 26% smaller, as the Capstone guide asks), keywords 44 pt, section titles 36 pt, body 18 pt (`poster-body`, never smaller), captions and tables 14 pt.
- Documents (A4): chapter titles 30 pt, headings 15 pt, body 11 pt with 1.15 line spacing.

For PowerPoint, Word and Canva: download Archivo, IBM Plex Sans and IBM Plex Mono from fonts.google.com and install them before opening a file, or the text falls back to Arial. Canva has all three in its font list. When sending a .pptx to the school, embed the fonts (File, Options, Save, Embed fonts) or export a PDF.

## Layout, spacing and shape

- A 4 px grid: `space-1` 4, `space-2` 8, `space-3` 12, `space-4` 16, `space-6` 24, `space-8` 32, `space-12` 48. The same steps in points on paper.
- Corners stay small: `radius-sm` (2) for chips and cells, `radius-md` (4) for buttons, inputs, alert rows and cards, `radius-lg` (8) only for panels, the hall map and the badge. `radius-pill` is for status dots only.
- Separate with hairlines (`line`) and space, not shadows. No drop shadows anywhere, including slides.
- Align to a column grid: three columns on the poster, a 12-column grid on slides and the dashboard. Text blocks stay under about 70 characters wide on screen.

## Iconography

- The five icons in `assets/Icons` (phone, earpiece, smartwatch, allowed, unit) are drawn on a 24 px grid with a 2 px stroke, square caps and mitered joins, in `navy` ink. Use them for printed and slide work.
- In code, use the `Icon` and `DeviceTag` components: the same drawings in `currentColor`, so they follow the theme.
- Device types are told apart by icon and word, never by color. Only `allowed` gets a color (`clear`).
- Need another icon? Draw it on the same grid and stroke, and add it to both places. Don't mix in an icon set with rounded strokes or fills.

## Charts and figures

- Distance on the x axis reads left to right from near to far, and the bands are shaded with `near-soft`, `mid-soft`, `far-soft` behind the data, labelled NEAR, MID, FAR.
- Marks that belong to a band use its color. Marks that don't (accuracy per device type, latency over time) use `navy` or `ink`, with `ink-muted` for a second series.
- Confusion matrices: one hue, from `paper-sunken` (zero) to `navy` (the largest count), with the count printed in every cell, `on-navy` on the dark cells.
- Gridlines `line`, axes `line-strong`, tick labels `ink-muted` in mono.
- Every table and figure gets a number and a caption, as the Capstone guide asks: "Table (1) Materials" above a table, "Figure (1) ..." below a figure. The text refers to each one by number.

## Surfaces

**Poster.** Use the Poster template: the school's 110 x 80 cm landscape sheet with a 5 cm margin, so the design area is 100 x 70 cm. A `navy` header band runs to the paper's edge with the school logo left, the MOE logo right, and the school's header lines in its exact format ("Alexandria STEM School, G.12, Semester 1, 2026-2027, G.No.12323"). Below it, four `paper-raised` columns on the `paper` sheet in the guide's order, the Invigil logo, tagline and a test plan video QR code at the foot of the last column. `ink` text, `navy` section rules, heat colors only in the band figures. Build it in PowerPoint or Canva with a custom 110 x 80 cm slide and guides at 5 cm.

**Portfolio.** A4, one document named as the portfolio guide asks (year, semester, team number). Each chapter (I to IV, following the EDP) opens with a full-width `navy` band holding the chapter number and title in `doc-chapter`, `on-navy`. Body `doc-body`, headings `doc-heading` in `navy`. Tables use a `navy` header row with `on-navy` labels and `line` rules; no vertical rules. Materials table columns: Item, Quantity, Description, Usage, Cost, Source, Picture.

**Logbook.** One entry per member per week, same layout every time: date and member name as a `label` eyebrow, then three short parts, What I did, Evidence, Next. Evidence names something you can check: a commit hash in mono, a photo, a results folder (`docs/results/2026-10-20-range-test`).

**Slides.** 16:9, `paper` ground. Title and section-divider slides are `navy` with `invigil-logo-dark.svg`. One idea per slide, `display` title top left, `space-12` margins, the mark small in the bottom right corner. Results slides use the Metric pattern: the value, the target, pass or fail.

**Dashboard.** Built with shadcn/ui (React, Tailwind CSS, Radix), themed with these tokens, so it looks like a real product (Vercel, Linear, Unity's cloud dashboard), not a template. Dark theme by default with a light toggle.

- Layout: a collapsible left sidebar (Live, Halls, Sessions, Results, Unit, Settings) with the mark at the top; a slim top bar with breadcrumbs, the unit's status (a `clear` dot and "Online", or "Offline" in `ink-muted`) and the theme toggle. Content on a 12-column grid, `space-6` gutters.
- Live: a row of four KPI cards (active alerts, devices heard, alert latency p50, false alarms per hour), the hall map card (the bands over the seats, `radius-lg`), and the alerts list as DetectionAlert rows or a data table, newest first, filterable by device type and band.
- Results: one Metric card per design requirement, the confusion matrix (navy single-hue scale), and RSSI-by-distance charts with the bands shaded.
- Density: UI text 13 to 14 px in IBM Plex Sans, numbers in Plex Mono with tabular figures, Archivo only for the page title. Borders (`line`), not shadows. Every list has an empty state that says what will appear and why it is empty. Loading uses skeletons, never spinners in the middle of a card.
- Never: gradients, glass blur, glow, emoji, oversized rounded cards, decorative charts, invented numbers. If there is no data yet, say so.

shadcn theme variables, set from the tokens (the same mapping in both themes):

| shadcn variable | Invigil token |
|---|---|
| `--background` / `--foreground` | `paper` / `ink` |
| `--card`, `--popover` (and `-foreground`) | `paper-raised` / `ink` |
| `--primary` / `--primary-foreground` | `action` / `on-action` |
| `--secondary`, `--accent` (and `-foreground`) | `paper-sunken` / `ink` |
| `--muted` / `--muted-foreground` | `paper-sunken` / `ink-muted` |
| `--destructive` | `ink` (destructive buttons are labelled; red means near, not danger) |
| `--border` / `--input` / `--ring` | `line` / `line-strong` / `focus` |
| `--chart-1`, `--chart-2`, `--chart-3` | `far`, `mid`, `near` (band charts only) |
| `--chart-4`, `--chart-5` | `navy`, `ink-muted` (everything else) |
| `--sidebar` | `paper-raised` in light, `paper-sunken` in dark |
| `--radius` | `radius-md` for controls, `radius-lg` for cards |

Also expose `near`, `mid`, `far`, their `-soft` tints and `clear` as Tailwind colors so components can say `bg-near-soft` or `text-clear` instead of hex values.

**Digital twin.** The same hall map at the scale of a building: one unit per hall, each hall a `paper-raised` rectangle with a `line-strong` wall. A hall with a new alert gets its band's soft tint and a SignalRings glyph; quiet halls stay neutral.

**Exhibition badge.** Use the ExhibitionBadge template, 100 x 140 mm, one per member, printed on matte card.

**The unit itself.** Put `invigil-mark.svg` on the enclosure as a sticker, at least 20 mm wide, so the box on the desk carries the same picture as the poster behind it.
