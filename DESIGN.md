# Colonial Archives Design System

## 1. Atmosphere & Identity

Colonial Archives feels like a quiet archival command room: dense enough for research, restrained enough for long reading sessions, and warm enough to avoid the sterile feel of database tooling. The signature is an ink-on-stone graph surface, where evidence, entities, and communities are separated through muted tonal depth and warm gold interaction cues.

## 2. Color

### Palette

| Role | Token | Light | Dark | Usage |
|------|-------|-------|------|-------|
| Surface/primary | `--surface-primary` | `#F8F5EF` | `#0C0A09` | App background |
| Surface/secondary | `--surface-secondary` | `#EFE9DD` | `#1C1917` | Graph and chat panels |
| Surface/elevated | `--surface-elevated` | `#FFFFFF` | `#292524` | Sidebars, popovers, controls |
| Text/primary | `--text-primary` | `#1C1917` | `#F5F5F4` | Main text |
| Text/secondary | `--text-secondary` | `#57534E` | `#A8A29E` | Secondary text |
| Text/tertiary | `--text-tertiary` | `#78716C` | `#78716C` | Captions, inactive controls |
| Border/default | `--border-default` | `#D6D3D1` | `#44403C` | Panel dividers |
| Border/subtle | `--border-subtle` | `#E7E5E4` | `#292524` | Soft separations |
| Accent/primary | `--accent-primary` | `#A37C3C` | `#D4AD6A` | Focus, selected graph nodes, primary actions |
| Accent/hover | `--accent-hover` | `#8A6832` | `#E3C48C` | Hover and active states |
| Graph/general | `--graph-general` | `#2563EB` | `#3B82F6` | General and Establishment nodes |
| Graph/defence | `--graph-defence` | `#DC2626` | `#EF4444` | Defence and Military nodes |
| Graph/economic | `--graph-economic` | `#059669` | `#10B981` | Economic and Financial nodes |
| Graph/internal | `--graph-internal` | `#7C3AED` | `#8B5CF6` | Internal Relations and Research nodes |
| Graph/social | `--graph-social` | `#D97706` | `#F59E0B` | Social Services nodes |
| Graph/unknown | `--graph-unknown` | `#6B7280` | `#6B7280` | Unknown or uncategorized nodes |
| Status/error | `--status-error` | `#DC2626` | `#EF4444` | Error states |

### Rules

- Use stone surfaces and warm ink accents as the dominant system.
- Category colors are semantic graph tokens, not general decoration.
- Raw graph canvases should stay darker than their controls so selected evidence reads clearly.

## 3. Typography

### Scale

| Level | Size | Weight | Line Height | Tracking | Usage |
|-------|------|--------|-------------|----------|-------|
| H1 | 36px | 600 | 1.2 | 0 | Rare page-level headings |
| H2 | 24px | 600 | 1.3 | 0 | Panel titles |
| H3 | 18px | 600 | 1.4 | 0 | Sidebar sections |
| Body | 14px | 400 | 1.5 | 0 | Default app text |
| Body/sm | 13px | 400 | 1.45 | 0 | Dense metadata |
| Caption | 12px | 500 | 1.4 | 0.02em | Labels and graph metadata |
| Mono | 12px | 400 | 1.4 | 0 | Canonical ids and numeric counts |

### Font Stack

- Primary: `Plus Jakarta Sans, system-ui, sans-serif`
- Display: `Crimson Pro, Georgia, serif`
- Mono: `IBM Plex Mono, ui-monospace, monospace`

### Rules

- Use the display serif sparingly for product identity and calm archival tone.
- Use tabular or mono figures for graph counts.
- Keep dense panels at body or caption scale; do not use hero-scale text inside tools.

## 4. Spacing & Layout

### Base Unit

All spacing derives from 4px.

| Token | Value | Usage |
|-------|-------|-------|
| `--space-1` | 4px | Icon-to-label spacing |
| `--space-2` | 8px | Compact controls |
| `--space-3` | 12px | Control padding |
| `--space-4` | 16px | Panel padding |
| `--space-5` | 20px | Sidebar groups |
| `--space-6` | 24px | Large panel groups |
| `--space-8` | 32px | Major horizontal gaps |

### Grid

- Desktop app shell: graph workspace, splitter, chat panel.
- Mobile app shell: tabbed graph/chat panels with full-height content.
- Graph controls float inside the graph workspace and must not cover the sidebar.

### Rules

- Tool surfaces should be dense, aligned, and scannable.
- Use fixed dimensions for icon buttons and graph counters to avoid layout shift.
- Do not nest cards inside cards.

## 5. Components

### Graph Explorer

- **Structure**: full-bleed Sigma canvas with floating search, graph mode controls, community filters, and a node details sidebar.
- **Variants**: community overview, entity subgraph.
- **Spacing**: `--space-2` through `--space-4` for controls; `--space-5` for sidebar groups.
- **States**: loading, retryable error, empty result, selected node, hovered node, focused community.
- **Accessibility**: buttons require visible focus rings and descriptive text or titles.
- **Motion**: camera focus uses standard 200-300ms easing; no layout animations.

### Node Sidebar

- **Structure**: right slide-over with identity, categories, attributes, source, neighbors, and ask action.
- **Variants**: overview node, subgraph node with neighbors.
- **Spacing**: `--space-4` padding, `--space-5` group separation.
- **States**: open, closed, missing metadata, source document available.
- **Accessibility**: close button has an accessible label; neighbor buttons are keyboard reachable.

## 6. Motion & Interaction

| Type | Duration | Easing | Usage |
|------|----------|--------|-------|
| Micro | 120ms | ease-out | Button press, hover color |
| Standard | 240ms | ease-in-out | Sidebar and panel transitions |
| Emphasis | 450ms | cubic-bezier(0.16, 1, 0.3, 1) | Graph camera focus |

### Rules

- Animate `transform` and `opacity`; graph camera motion is handled by Sigma.
- Hovering or selecting a node highlights the node and its one-hop neighbors while dimming unrelated entities.
- Respect the canvas as the primary surface; controls should be legible but visually secondary.

## 7. Depth & Surface

### Strategy

Mixed: tonal-shift for app panels, subtle borders for tool controls, and minimal shadows only for overlays.

| Level | Value | Usage |
|-------|-------|-------|
| Overlay | `0 18px 50px rgba(0, 0, 0, 0.28)` | Sidebar and floating panels |
| Control border | `1px solid var(--border-default)` | Search, filters, buttons |
| Soft border | `1px solid var(--border-subtle)` | Internal separators |

### Rules

- Prefer translucent stone controls over bright cards.
- Keep graph edges low contrast until selected or hovered.
- Do not use decorative gradient orbs or unrelated imagery inside the research tool.
