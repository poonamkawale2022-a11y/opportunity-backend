# DESIGN.md — Opportunity Intelligence frontend

World: **mission-operations manual**. Paper ground, ink rules, signal-orange actions,
deep-green field bands. No gradients, no purple, no glass, no icon-card grids.

## Tokens

- paper `#F6F3EC` (ground) · sheet `#FFFDF8` (raised panels) · ink `#16150F`
- smoke `#5C574A` (secondary text, 7:1 on paper) · signal `#FF4D00` (primary action only)
- moss `#0C3B2E` (pipeline + footer bands) · sun `#FFC91A` (badges, warnings)
- Display: Archivo Black · UI: Inter · Data/mono: JetBrains Mono (data + measurements only)
- Borders 1.5px ink on panels; shadows offset + blurred (`lift`, `card`)
- Radius: 16px panels, full pills for buttons/tags

## Surfaces

- **Landing (Persuade):** two-column hero — left manifesto (48–100px Archivo Black
  headline, black + signal pills, trust line), right schematic Opportunity Loop
  (SVG line-art hexagon track, 8 diamond agent nodes, token dwelling node to
  node in sync with the LOOP pill, lineage lines to opportunity nodes,
  micro-cards, annotations; static when reduced-motion).
  Sun ticker, live backend status strip (real `/api/health`), illustrated mission log
  (labeled synthetic demo), GSAP-pinned horizontal 8-stage pipeline on moss,
  agent dossier as ledger rows, quota band on sun, moss close with dual CTA.
- **Auth:** split screen — moss brand rail + paper form; errors name problem + recovery.
- **Console (Operate):** same tokens; bordered panels, mono ledger rows, tag chips,
  ink/signal buttons; Lenis smooth scroll; content visible by default, motion is
  entrance-only (expo.out) plus the radar and marquee as the two authored moments.

## Motion

Lenis (lerp 0.1) drives GSAP ScrollTrigger. One horizontal pin (pipeline).
Three.js DPR-capped ≤1.75, pointer parallax, full dispose on unmount.
Routes lazy-split: main / Console / Radar(three) chunks.
