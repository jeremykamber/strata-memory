<!-- SEED: re-run /impeccable document once there's code to capture the actual tokens and components. -->

---
name: Strata
description: CLI-first tiered memory system for AI agents — a geological metaphor rendered as a museum specimen
---

# Design System: Strata

## 1. Overview

**Creative North Star: "The Core Sample"**

A drill core displayed in a natural history museum: clean vitrine, measured depth marks, each stratum numbered and annotated in a precise hand. The page treats Strata as a specimen under glass — something to be examined, not evangelized. The visitor is a peer (an AI engineer who ships code), and the page earns trust through clarity, specificity, and the quiet authority of something that works.

The system is restrained and legible. No decoration, no theatrical entrance, no hype. Layout follows a visible logic — like a stratigraphic column or a field notebook spread. Sans-serif headings provide structure; serif body text carries the reading. Color is used sparingly and intentionally: warm neutrals for the rock (backgrounds, surfaces), a single accent as a marker (like a red depth notation on a core log). White space is generous; the page breathes like a specimen on an otherwise empty table.

**Key Characteristics:**
- Specimen-like presentation: clean, examinable, unhurried
- Geological precision: stratigraphic rhythm, measured spacing, annotated details
- CLI-native confidence: shows terminal output as evidence, not decoration
- Restrained color: warm earth neutrals, single accent ≤10%
- Responsive motion: transitions serve comprehension, not entertainment

## 2. Colors

**Color Strategy: Restrained.** Warm earth neutrals carry the surfaces; a single accent (oxidized iron / sandstone red-orange) is used on ≤10% of any given screen — its rarity is the point.

### Primary
- **Oxide Marker** (`[to be resolved during implementation]`): The sole accent. Used for CLI output highlights, measurement markers, active states, and small UI signals. Never for large surfaces.

### Neutral
- **Shale Ground** (`[to be resolved during implementation]`): Primary background. Warm, deep, sedimentary — the rock the core was pulled from.
- **Lime-sand Surface** (`[to be resolved during implementation]`): Foreground / container background. One stratum above ground.
- **Fault-line Stroke** (`[to be resolved during implementation]`): Subtle borders and dividers. Fine as a crack.
- **Deep Core** (`[to be resolved during implementation]`): High-emphasis text. Near-black but warm.
- **Fossil Trace** (`[to be resolved during implementation]`): Low-emphasis text / metadata. Faded like an imprint.

### Named Rules

**The Marker Rule.** The accent covers ≤10% of any viewport. It exists to mark, not to decorate. If a screen reads as "orange," the rule is broken.

**The Stratum Rule.** Backgrounds shift in visible layers. Each surface occupies exactly one stratum — never two. No nested surfaces share the same tone.

## 3. Typography

**Display Font:** `[to be chosen at implementation — grotesk or neo-grotesk sans, tight tracking, authoritative]`
**Body Font:** `[to be chosen at implementation — readable serif, humanist or old-style, warm but precise]`

**Character:** A sans-serif display face with tight, confident letter spacing (like a USGS map legend or a terminal emulator title bar) paired with a serif body face that carries extended reading (like a field notebook entry or a museum caption). The contrast between structural headings and contemplative body text IS the voice.

### Hierarchy
- **Display** (`[weight]`, `[clamp]`, `[line-height]`): Hero section headings only. Large, authoritative, quiet.
- **Headline** (`[weight]`, `[size]`, `[line-height]`): Section titles. Legible at a glance.
- **Title** (`[weight]`, `[size]`, `[line-height]`): Subsection heads, card labels.
- **Body** (`[weight]`, `[size]`, `[line-height]`): Paragraph text. Capped at 70ch. The primary reading experience.
- **Label** (`[weight]`, `[size]`, `[letter-spacing]`, `uppercase`): CLI output, measurement marks, code blocks, metadata. Tightly tracked uppercase — like stratum labels on a core diagram.

### Named Rules

**The Field-Notes Rule.** Body text reads like a geologist's log: precise, complete sentences, no exclamation. The serif face carries this voice — it signals "written by someone who measured twice."

## 4. Elevation

Flat by default — like a specimen on a white table or a diagram on paper. Depth is conveyed through the stratum system: layered backgrounds recede by lightness, not by shadow. The only shadows, if any, are fine and tight (≤4px, low opacity) — like the shadow cast by a physical core sample on its display surface.

## 5. Components

*[Omitted — no components exist yet. Re-run `/impeccable document` once there is code to capture real tokens and component patterns.]*

## 6. Do's and Don'ts

### Do:
- **Do** use warm earth neutrals as the foundation. The palette should feel like rock, not like paper.
- **Do** show real CLI output — terminal logs, `strata init` success, latency tables. This is proof, not decoration.
- **Do** treat each fold as one decisive idea. The page paces deliberately, like inspecting a core sample section by section.
- **Do** use the single accent sparingly — as a marker, like a red notation on a measured section log.
- **Do** let the page breathe. Generous white space around each section; the specimen needs room to be examined.
- **Do** use sans-serif for structure and serif for reading. The contrast IS the voice.

### Don't:
- **Don't** use gradient text, glassmorphism, or hero metrics (big number + small label + gradient bar). These are the generic SaaS landing page template.
- **Don't** default to dark mode. Dark is a choice earned by the metaphor (deep rock feels dark), not because "dev tools are dark."
- **Don't** use identical card grids with icons above headings. Cards are the lazy answer; explore alternatives.
- **Don't** include testimonials carousels, "trusted by" bars, or social proof widgets. The page earns trust through evidence, not logos.
- **Don't** write like a marketer. No exclamation points, no startup buzz, no "revolutionize." Write like a geologist who built the tool and knows it works.
- **Don't** use side-stripe borders or all-caps body copy.
- **Don't** restate a heading in the paragraph below it. Every word earns its place.
