# Signal — visual direction

Decided before the screens were built, and the app is held to it.

## Why it looks like this

The product is read, not browsed: someone opens it to answer "where am I missing, and what do I
do about it". So the interface is dense, quiet, and typographic. Colour is spent almost entirely
on two things — status and the chart slots — and nothing else competes for attention.

## Tokens

Everything is a CSS custom property on `:root`, redefined under `.dark`. Values are stored as raw
RGB triplets (`--brand-500: 219 118 88`) and consumed through
`rgb(var(--brand-500) / <alpha-value>)`, so one Tailwind utility works in both themes and opacity
modifiers still apply. No screen uses an arbitrary colour value.

| Group | Tokens | Use |
| --- | --- | --- |
| Canvas / surface | `--canvas`, `--surface-0…300` | Page, cards, inset panels, filled controls |
| Ink | `--ink-950/700/600/400` | Headings, body, secondary, muted |
| Stroke | `--stroke-200/300` | Hairline borders and dividers |
| Brand | `--brand-500/600/700` | A single warm terracotta accent: primary actions, active state, focus ring |
| Status | `--success/warning/danger-500/700` | Run and stage outcomes only |
| Chart | `--chart-1…4` | The four measured channels, in fixed order |

Dark mode is not an inversion. Surfaces are near-black with lifted panels, ink is desaturated, and
the accent is brightened so it holds contrast on a dark card.

## Type

Inter Variable with `cv11` and `ss01`, and `font-variant-numeric: tabular-nums` (`.tnum`) on every
figure so columns of scores and costs line up. Dashboards are denser than prose, so body text is
14px/20 and the display sizes exist only for KPI figures. The scale is semantic — `label-xs`
through `label-lg`, `display-sm/md/lg` — so a screen picks a role, not a pixel size.

## Shape and depth

Radii 4/6/8/12/16. The signature is a **1.2px hairline border** plus a very shallow shadow rather
than a heavy card — borders define structure, shadow only lifts things that genuinely float
(drawer, popover, active segment).

## Charts

Trends use ECharts via `ngx-echarts`, tree-shaken from `echarts/core`, reading ink, surface and the
categorical slots from the same CSS variables — so a chart cannot drift from the UI around it and
re-skins on theme toggle.

The categorical order is fixed and is itself the accessibility mechanism: adjacent pairs clear
CVD ΔE ≥ 8 and normal-vision ΔE ≥ 15 against both card surfaces. Slots are never re-ordered.

**The visibility matrix is a table, not a chart.** With four channels and long query labels the
ECharts heatmap truncated its own axis labels and needed a parallel text table for screen readers
anyway. A real `<table>` is sharper, scrolls properly, and is natively accessible. Every cell
carries a glyph as well as a colour (check / dash / dot), so presence never depends on colour
alone, and the three states are kept distinct: **visible**, **measured but absent**, and **never
measured**. Conflating the last two would overstate what the run actually checked.

## States

Loading, empty, error and partial are designed, not afterthoughts.

- **Loading** — skeletons shaped like the content that replaces them, so nothing jumps.
- **Empty** — says why it is empty and names the next action; never a dead end.
- **Error** — a plain sentence, the validation details if any, the trace id to quote, and a retry.
- **Partial** — a banner naming each failed stage, what data is therefore missing, and the fact
  that work other branches finished was kept.

Trends only plot runs that actually produced a measurement; a failed run contributes no point
rather than a zero.

## Layout and input

Fixed 248px sidebar at ≥1024px, slide-over with a scrim below it. Content is capped at 1320px.
Verified at 1280px and 768px in both themes. Visible focus rings on the brand colour,
`prefers-reduced-motion` honoured, native `select` and number-spinner chrome replaced so controls
do not stay light in dark mode.

## Non-negotiable

No mock or placeholder analytics ever ship in the application. Every number on screen came from
DataForSEO or from deterministic Python over it — which is why the failure and partial states had
to be good: with an unverified data account they are what the app honestly has to show.
