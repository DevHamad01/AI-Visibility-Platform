/**
 * Signal design system.
 *
 * Colours are declared as space-separated RGB triplets in CSS custom
 * properties (src/styles.scss) and referenced here through
 * `rgb(var(--token) / <alpha-value>)`. That gives one class name
 * (`bg-surface-0`, `text-ink-600`) that resolves correctly in both themes,
 * instead of pairing every utility with a `dark:` twin — and it still lets
 * Tailwind generate opacity modifiers (`bg-brand-500/10`).
 *
 * The scale names are semantic, never literal: `surface` ascends away from
 * the page, `ink` descends in emphasis, `stroke` is for hairlines only.
 */
const rgb = (token) => `rgb(var(${token}) / <alpha-value>)`;

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{html,ts}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        canvas: rgb('--canvas'),
        surface: {
          0: rgb('--surface-0'),
          50: rgb('--surface-50'),
          100: rgb('--surface-100'),
          200: rgb('--surface-200'),
          300: rgb('--surface-300'),
        },
        ink: {
          950: rgb('--ink-950'),
          700: rgb('--ink-700'),
          600: rgb('--ink-600'),
          400: rgb('--ink-400'),
        },
        stroke: {
          200: rgb('--stroke-200'),
          300: rgb('--stroke-300'),
        },
        brand: {
          500: rgb('--brand-500'),
          600: rgb('--brand-600'),
          700: rgb('--brand-700'),
        },
        success: {
          500: rgb('--success-500'),
          700: rgb('--success-700'),
        },
        warning: {
          500: rgb('--warning-500'),
          700: rgb('--warning-700'),
        },
        danger: {
          500: rgb('--danger-500'),
          700: rgb('--danger-700'),
        },
        // Categorical chart slots, fixed order. The order is the
        // colour-blind-safety mechanism: adjacent pairs clear CVD ΔE ≥ 8 and
        // normal-vision ΔE ≥ 15 against both card surfaces (validated with
        // the dataviz palette validator), so they are never re-ordered.
        chart: {
          1: rgb('--chart-1'), // google_organic
          2: rgb('--chart-2'), // google_ai_overview
          3: rgb('--chart-3'), // llm_chatgpt
          4: rgb('--chart-4'), // llm_google_ai
        },
      },
      fontFamily: {
        sans: ['Inter Variable', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      // Semantic type scale. Dashboards are denser than prose, so body text
      // is 14px and the display sizes exist only for KPI figures.
      fontSize: {
        'label-xs': ['12px', { lineHeight: '16px', letterSpacing: '0' }],
        'label-sm': ['14px', { lineHeight: '20px', letterSpacing: '-0.084px' }],
        'label-md': ['16px', { lineHeight: '24px', letterSpacing: '-0.176px' }],
        'label-lg': ['18px', { lineHeight: '24px', letterSpacing: '-0.27px' }],
        'display-sm': ['22px', { lineHeight: '28px', letterSpacing: '-0.44px' }],
        'display-md': ['28px', { lineHeight: '34px', letterSpacing: '-0.62px' }],
        'display-lg': ['34px', { lineHeight: '40px', letterSpacing: '-0.8px' }],
      },
      borderRadius: {
        4: '4px',
        6: '6px',
        8: '8px',
        12: '12px',
        16: '16px',
      },
      borderWidth: {
        hairline: '1.2px',
      },
      boxShadow: {
        card: '0 1px 2px rgb(var(--shadow-rgb) / 0.04)',
        raised: '0 2px 8px -2px rgb(var(--shadow-rgb) / 0.10)',
        drawer: '0 16px 48px -12px rgb(var(--shadow-rgb) / 0.28)',
        tooltip: '0 6px 16px -4px rgb(var(--shadow-rgb) / 0.20)',
      },
      transitionDuration: {
        150: '150ms',
      },
      keyframes: {
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'none' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
        'pulse-ring': {
          '0%': { boxShadow: '0 0 0 0 rgb(var(--brand-500) / 0.45)' },
          '70%': { boxShadow: '0 0 0 6px rgb(var(--brand-500) / 0)' },
          '100%': { boxShadow: '0 0 0 0 rgb(var(--brand-500) / 0)' },
        },
      },
      animation: {
        'fade-up': 'fade-up 220ms ease-out both',
        shimmer: 'shimmer 1.4s infinite',
        'pulse-ring': 'pulse-ring 1.8s ease-out infinite',
      },
    },
  },
  plugins: [],
};
