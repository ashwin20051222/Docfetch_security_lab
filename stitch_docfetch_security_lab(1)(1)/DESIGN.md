---
name: Verdant Cipher
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#3d4a42'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#6d7a72'
  outline-variant: '#bccac0'
  surface-tint: '#006c4a'
  primary: '#006948'
  on-primary: '#ffffff'
  primary-container: '#00855d'
  on-primary-container: '#f5fff7'
  inverse-primary: '#68dba9'
  secondary: '#565e74'
  on-secondary: '#ffffff'
  secondary-container: '#dae2fd'
  on-secondary-container: '#5c647a'
  tertiary: '#00685f'
  on-tertiary: '#ffffff'
  tertiary-container: '#008378'
  on-tertiary-container: '#f4fffc'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#85f8c4'
  primary-fixed-dim: '#68dba9'
  on-primary-fixed: '#002114'
  on-primary-fixed-variant: '#005137'
  secondary-fixed: '#dae2fd'
  secondary-fixed-dim: '#bec6e0'
  on-secondary-fixed: '#131b2e'
  on-secondary-fixed-variant: '#3f465c'
  tertiary-fixed: '#89f5e7'
  tertiary-fixed-dim: '#6bd8cb'
  on-tertiary-fixed: '#00201d'
  on-tertiary-fixed-variant: '#005049'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  headline-xl:
    fontFamily: Space Grotesk
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-xl-mobile:
    fontFamily: Space Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-lg:
    fontFamily: Space Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Space Grotesk
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Space Grotesk
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: 0em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
    letterSpacing: -0.01em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
    letterSpacing: 0em
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: 0em
  code-body:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.03em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-desktop: 1.5rem
  margin: 1rem
  margin-tablet: 1.5rem
  margin-desktop: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1.25rem
  space-xl: 2rem
---

## Brand & Style

This design system establishes an academic cybersecurity research environment prioritizing forensic precision, empirical clarity, and cognitive endurance. Designed for threat analysts, university researchers, and security engineering students, the aesthetic merges technical rigor with modern institutional restraint.

The style unites **Minimalism** and **Technical Editorial**:
- Surfaces are clinically clean and structured without visual noise, skeuomorphic excess, or theatrical dark-mode "hacker" clichés.
- High-contrast typography and explicit information density enable rapid visual scanning during vulnerability triage and diff analysis.
- Emotionally, the interface evokes calm authority, verifiable truth, and operational safety. Emerald and deep jade greens serve as symbols of system health, analytical confirmation, and focused execution, while alert hues remain strictly compartmentalized to threat indicators.

## Colors

The palette emphasizes purposeful color restraint, dedicating functional greens to intentional operations and reserving chromatic warmth solely for verified threat levels.

### Core Architecture
- **Primary Canvas Background**: `#f6f9f8` (Subtle cool mint-gray canvas reducing retinal fatigue across dense data sets).
- **Surface & Cards**: `#ffffff` (Crisp, surgical white baseline for reports, analysis frames, and code modules).
- **Surface Subtle**: `#edf3f1` (Recessed containers, table header rows, code gutter strips).
- **Border Default**: `#d1ded9` (Low-contrast, cool-tinted framing lines ensuring structure without visual obstruction).
- **Border Strong**: `#94a3b8` (Dividers for active split panels, focus boundaries, and data grid headers).

### Typography Tones
- **Primary Text**: `#0f172a` (High-contrast slate for headlines, active data points, and code tokens).
- **Secondary Text**: `#334155` (Balanced body copy, metadata labels, and structural table headers).
- **Tertiary / Muted Text**: `#64748b` (Timestamps, secondary hashes, column indicators, and inactive states).

### Primary Accents & Interaction
- **Primary Base**: `#059669` (Primary CTAs, active laboratory states, confirmed security verifications).
- **Primary Hover**: `#047857` (Direct action hover states, active tab strokes).
- **Primary Vibrant**: `#10b981` (Live network telemetry indicators, real-time pulse dots, positive diff additions).
- **Primary Subtle Fill**: `#ecfdf5` (Selected row background, verified entity tag fill).

### Security Severity Scale (Strict Usage)
- **Critical (CVSS 9.0–10.0)**: `#b91c1c` fill / `#fef2f2` tint / `#dc2626` text (Buffer overflows, remote code execution).
- **High (CVSS 7.0–8.9)**: `#c2410c` fill / `#fff7ed` tint / `#ea580c` text (Privilege escalation, auth bypass).
- **Medium (CVSS 4.0–6.9)**: `#b45309` fill / `#fffbeb` tint / `#d97706` text (Information disclosure, CORS misconfigurations).
- **Low (CVSS 0.1–3.9)**: `#475569` fill / `#f1f5f9` tint / `#64748b` text (Hardening suggestions, benign discrepancies).
- **Informational**: `#0f766e` fill / `#f0fdfa` tint / `#0d9488` text (Architecture notes, standard telemetry).

## Typography

The type ecosystem relies on a three-tier typographic hierarchy:
1. **Space Grotesk** for module titles, experiment headings, and system labels: provides structured, geometric legibility that echoes scientific instruments.
2. **Inter** for research documentation, analytical explanations, and forms: offers pristine, neutral readability across variable pixel densities and prolonged reading intervals.
3. **JetBrains Mono** for all data-first artifacts: packet captures, assembly/hex viewports, diff comparisons, CVE references, raw network payloads, and hash values.

Numerical tabular alignments must always use tabular figures (`font-variant-numeric: tabular-nums`) within data matrices and telemetry feeds to eliminate column drift.

## Layout & Spacing

This design system uses a technical multi-pane layout model engineered for dual-stream academic research: simultaneous observation of security documents alongside executable proof-of-concept verification.

### Layout Mechanics
- **Desktop (1280px+)**: A balanced 12-column dynamic grid. Split analysis workspaces lock horizontally: a 4-column diagnostic/metadata inspector alongside an 8-column side-by-side verification canvas (4 columns baseline vs. 4 columns payload/evidence).
- **Tablet (768px - 1279px)**: 8-column grid with collapsible utility sidebar; diff panels transform into tabbed or vertically stacked comparative views.
- **Mobile (< 768px)**: Single-column vertical stream. Data tables activate horizontal swipe locks with fixed freeze-columns for object identifiers.

### Spacing Cadence
- Rhythms strictly follow standard 4px/8px increments.
- Dense visual zones (raw code viewers, packet inspectors) utilize `space-xs` and `space-sm` for dense row spacing and clear structural rhythm.
- Container padding is pinned to `space-md` for side inspectors and `space-lg` for primary diagnostic sheets.

## Elevation & Depth

Visual depth is achieved through **Tonal Surface Layering** with hairline structural borders rather than decorative shadows. In academic security utilities, artificial 3D shadows create visual clutter; sharp tonal contrast maintains legibility.

### Surface Tiers
- **Tier 0 (Canvas Base)**: `#f6f9f8` – The foundational background underneath all tools and frames.
- **Tier 1 (Panels & Workspaces)**: `#ffffff` – Clinical cards, diff comparison viewers, and telemetry matrices bounded by a `1px solid #d1ded9` outline.
- **Tier 2 (Recessed Readouts)**: `#edf3f1` – Terminals, packet payloads, code editors, and immutable historical logs inset within Tier 1 surfaces.
- **Tier 3 (Floating Utilities)**: `#ffffff` elevated via a micro-precise drop: `0 4px 12px -2px rgba(15, 23, 42, 0.08), 0 1px 3px 0 rgba(15, 23, 42, 0.04)`. Applied exclusively to context menus, diagnostic tooltips, and modal verification prompts.

Hover micro-elevations are strictly horizontal or color-based (e.g., border color shift from `#d1ded9` to `#059669`) to prevent spatial instability during rapid analytical workflows.

## Shapes

The interface balances academic precision with contemporary software usability by adhering to a unified **8px to 12px** geometry:

- **Primary Cards & Large Diagnostic Windows**: Standardized at `0.75rem` (12px / `rounded-lg`) to balance clinical density with approachable framing.
- **Form Controls, Buttons, Code Boxes**: Set to `0.5rem` (8px / base radius), reinforcing solid interactive bounds.
- **Severity Chips, Status Indicators, Filter Pills**: Bounded by `0.25rem` (4px) or full capsule curves depending on data cardinality: strict severity chips use crisp 4px corners to communicate algorithmic rigor, whereas interactive category filters use pill profiles.
- **Code Gutter Markers & Diff Blocks**: Square (`0px`) at vertical joints, maintaining uninterrupted terminal lines across multi-line evidence panes.

## Components

### Buttons & Action Triggers
- **Primary Action**: Solid `#059669` fill with white text (`Inter`, 13px, weight 600). Hover state shifts to `#047857`. Focus ring displays an exterior 2px offset in `#10b981`.
- **Secondary Action**: White surface with `1px solid #d1ded9` border and `#0f172a` text. Hover state shifts border to `#94a3b8` and background to `#f6f9f8`.
- **Destructive/Emergency Sandbox Abort**: `#dc2626` text with `#fef2f2` fill, transitioning to solid `#b91c1c` on intent confirmation.

### Status Chips & Threat Badges
- Displayed with `JetBrains Mono`, 11px uppercase, tracking `0.03em`.
- **Anatomy**: `20px` fixed height, `1px solid` border corresponding to threat tier, padded with `6px` horizontal padding.
- Examples:
  - `CRITICAL`: Background `#fef2f2`, border `#fca5a5`, text `#b91c1c`.
  - `ACTIVE EXPLOIT`: Background `#ecfdf5`, border `#a7f3d0`, text `#047857` with an active pulsing 6px dot in `#10b981`.

### Side-by-Side Comparison & Code Panels
- Multi-pane comparison layout featuring line-numbered gutters in `#64748b` typography against an `#edf3f1` track.
- **Deletions / Baseline Flaws**: Highlighted with `#fee2e2` background and `#991b1b` text.
- **Patched / Target Evidence**: Highlighted with `#d1fae5` background and `#065f46` text.
- Top action toolbar houses target file telemetry: MD5/SHA256 checksums, byte counts, and encoding indicators formatted in `JetBrains Mono` at 11px.

### Form Inputs & Search Diagnostics
- Inset padding `8px 12px`, background `#ffffff`, border `1px solid #d1ded9`.
- Typing state locks to `Inter` (14px), with query parameters or regex filters switching to `JetBrains Mono`.
- Active focus state: border shifts to `#059669` accompanied by a distinct, non-blurring box ring: `0 0 0 3px rgba(5, 150, 105, 0.15)`.

### Tabular Evidence Grids
- Flat, highly scannable tables with `#f6f9f8` headers and uppercase `Space Grotesk` (11px, weight 600) labels.
- Rows feature `1px solid #edf3f1` bottom borders, hover-highlighting with `#f0fdf4`.
- Strict column width allocations: Severity Indicator (80px), Vulnerability ID (120px, monospace), Vector (140px), Remediation State (100px), Timestamp (160px).