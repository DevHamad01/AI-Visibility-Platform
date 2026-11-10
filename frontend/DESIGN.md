> Earlier Claude Code design proposal, retained for context. The implemented Signal design is documented in `docs/design-direction.md` at the repository root.

# Frontend visual direction

Decided before any screen was built (Phase 4). Everything below lives as CSS
custom properties in `src/styles/_tokens.scss`; components only reference tokens.

## Concept — "instrument panel", not "marketing site"

A paid SEO/AI-visibility analytics tool is read for minutes at a time, dense with
numbers. The direction is **technical precision**: a confident near-black navy
base (dark-mode first), hairline borders instead of drop shadows, one single
accent used sparingly for the thing that matters on each screen, and a
monospace face for every number so scores, costs and trace ids read as
instrument readouts. No gradients-on-white, no stock Material look, no
rounded-blob cards.

## Typography

| Role | Face | Why |
|---|---|---|
| UI text, headings | **IBM Plex Sans** 400/500/600 | distinctive but highly legible at 13–15px; not Inter/Roboto/Arial |
| Numbers, scores, ids, code | **IBM Plex Mono** 400/500 | tabular figures; same family so the pairing is cohesive |

Scale (px): 12 · 13 · 15 (body) · 17 · 20 · 24 · 30 · 38. Body is 15px, not 16 —
dashboards are denser than prose. Line-height 1.5 body, 1.15 headings.

## Color

One accent: **coral `#FF6B4A`** (dark surfaces: `#FF7A5C`). It is used only for
the primary action, active nav, focus rings, and the opportunity-score emphasis —
never as a background wash.

| Token | Dark (default) | Light |
|---|---|---|
| `--bg` | `#0B0E14` | `#F7F8FA` |
| `--surface` | `#12161F` | `#FFFFFF` |
| `--surface-2` | `#171C27` | `#F1F3F7` |
| `--border` | `rgba(255,255,255,.10)` | `rgba(11,14,20,.10)` |
| `--text-1` | `#F2F4F8` | `#0B0E14` |
| `--text-2` | `#B6BBD0` | `#52586A` |
| `--text-3` | `#6C7288` | `#8A8FA3` |

Status (always paired with an icon + label, never color alone):
good `#22C98E`/`#1BAF7A`, warning `#F5A623`/`#D97706`, critical `#F87171`/`#DC2626`.

## Chart palette (validated with the dataviz palette validator)

Categorical, **fixed order** (the order is the colour-blind-safety mechanism —
adjacent pairs pass CVD ΔE ≥ 8 and normal-vision ΔE ≥ 15 in both modes against
our card surfaces):

| Slot | Channel | Light | Dark |
|---|---|---|---|
| 1 | google_organic | `#2a78d6` | `#3987e5` |
| 2 | google_ai_overview | `#eda100` | `#c98500` |
| 3 | llm_chatgpt | `#1baf7a` | `#199e70` |
| 4 | llm_google_ai | `#4a3aa7` | `#9085e9` |

Light-mode slots 2 and 3 sit under 3:1 contrast on white, so every chart that
uses them also carries direct labels and a table view (the validator's "relief"
rule). Sequential (opportunity score 0–100) is a single-hue coral ramp — lighter
= lower on light surfaces, darker/muted = lower on dark surfaces. Diverging
(compare view, improved vs declined) uses status good vs status critical with a
neutral gray midpoint.

## Spacing, radius, elevation

4px grid: 4 · 8 · 12 · 16 · 24 · 32 · 48 · 64. Radius 4px (controls), 8px (cards),
12px only for the drawer. Elevation is a 1px hairline border; a shadow is used
only on the slide-over drawer and toasts.

## Motion

Only two moments: a staggered fade-up on page content (60ms per block) and the
live-run stage timeline's pulsing "running" dot. Everything else is a 120ms
color/opacity transition. `prefers-reduced-motion` turns both off.

## Breakpoints

≥1280px: sidebar + content. ≥768px: sidebar collapses to a top bar, tables keep
scrolling horizontally inside their card instead of breaking the page.

