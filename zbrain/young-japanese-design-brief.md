# Young Japanese Design Culture: Dashboard Design Brief

## The Core Thesis

The goal is not traditional Japanese minimalism (Muji, wabi-sabi, Ma) and not pure cyberpunk chaos. The aesthetic lives in the **tension** between calm and energy -- the same tension that defines contemporary Japan itself. A Ryoji Ikeda data wall next to a Yoshitomo Nara sketch. A teamLab waterfall rendered in Persona 5's typography. The discipline of a tea ceremony applied to the information density of a Tokyo train station display.

---

## 1. Japanese DJ / Electronic Music Culture Visual Design

### Key References

- **Ryoji Ikeda** -- datamatics, test pattern, data-verse trilogy. Converts raw data (hard drive errors, genome sequences, cosmological maps) into immersive black-and-white visual spectacles. His "test pattern" project converts any data type into barcode patterns and binary 0s/1s that strobe across surfaces.
- **Cornelius** -- Fantasma (1997) and Point (2001) album packaging. Art direction by Mitsuo Shindo, design by Masakazu Kitayama. Fantasma's cover perfectly mirrors its maximalist audio collage; Point strips back to precise, clean geometry.
- **Dommune** -- Naohiro Ukawa's "virtual festival" streaming platform. A living room turned broadcast studio that became Japan's most important electronic music venue. Raw, DIY, anti-polished.
- **J-Core flyer culture** -- fused Dutch gabber with anime aesthetics and early gaming visuals. Circuit-bent Game Boys, modified toys, chaotic energy. Not polished -- deliberately frenetic. Colorful, funky, playful -- the opposite of European hardcore's dark severity.

### Actionable Design Principles

**Color Palette: "Data Stream"**
| Swatch | Hex | Name | Usage |
|---------|---------|------|-------|
| | `#000000` | Void Black | Primary background |
| | `#FFFFFF` | Data White | Primary data/text on dark |
| | `#00FF41` | Matrix Green | Active data highlights, live indicators |
| | `#FF0040` | Signal Red | Alerts, critical state |
| | `#0088FF` | Scan Blue | Secondary data, links |
| | `#1A1A1A` | Near Black | Card/surface background |

**Typography:** Monospaced fonts are native to this world. Use `JetBrains Mono`, `IBM Plex Mono`, or `Fira Code` for data displays. Pair with a clean sans-serif (Inter, M PLUS 1) for UI labels.

**Layout Patterns:**
- Data as texture: Background elements rendered as scrolling binary, barcode strips, or waveform visualizations (a la Ikeda's test pattern)
- Information as rhythm: Data updates should pulse at intervals, not appear statically -- echo the BPM-driven nature of electronic music
- Asymmetric grids: Cornelius's Point cover teaches that precision does not require symmetry

**Motion/Animation:**
- Rapid binary flicker for loading states (Ikeda-inspired)
- Waveform oscillation for real-time data feeds
- Stroboscopic flash transitions (use sparingly -- accessibility matters)
- Smooth sine-wave easing curves rather than linear or bounce

**Data Visualization:**
- Render data as barcode strips (Ikeda's test pattern aesthetic)
- Use raw numeric displays alongside charts -- show the data AND the abstraction
- Monochrome base with single-accent-color highlighting

---

## 2. Japanese Underground Art / Design Scene

### Key References

- **Takashi Murakami / Superflat** -- Ultra-flat 2D graphics, no depth/shadow, psychedelic chromatic palette. Flattens hierarchy between fine art and pop culture. Bold outlines, grotesque cuteness, saturated color. The smiling flowers are deceptively simple -- "kawaii" as critique.
- **Yoshitomo Nara** -- Solitary figures on blank backgrounds. Limited palette (one or two dominant colors). Large confrontational eyes. Defiant children holding weapons. Simplicity that amplifies emotional impact rather than diminishing it. Rebellion coded as innocence.
- **BAPE / A Bathing Ape** -- Designed by Sk8thing (Shinichiro Nakamura). APE HEAD logo embedded INTO the camouflage pattern itself -- brand identity as environmental texture. The 1st CAMO (1996) and ABC CAMO variants prove that a single motif, iterated obsessively, builds iconic recognition.
- **Groovisions** -- Founded 1993 in Kyoto, relocated to Tokyo. "Chappie" humanoid character system with no fixed age/gender/nationality. Bold graphic imagery balancing design and illustration. Frameless, pragmatic, fun.
- **Japanese risograph/zine culture** -- Riso Kagaku Corporation's soy-based ink machine (1986) became the substrate of underground publishing. Luminescent colors, printing gaps, screen-print texture, gradient control through hole spacing. Imperfection as aesthetic value. Hand Saw Press (Tokyo) as community hub.

### Actionable Design Principles

**Color Palette: "Superflat Pop"**
| Swatch | Hex | Name | Usage |
|---------|---------|------|-------|
| | `#FF3366` | Murakami Pink | Primary accent, CTAs |
| | `#FFE700` | Neon Yellow | Warnings, highlights |
| | `#00BFFF` | Sky Cyan | Info states, links |
| | `#8B00FF` | Electric Violet | Premium/special indicators |
| | `#FF6B00` | Tangerine | Secondary accent, notifications |
| | `#FFFFFF` | Flat White | Backgrounds, cards |
| | `#1A1A2E` | Deep Navy | Dark mode base |

**Typography:** Display type should be bold, almost aggressive. Consider `Space Grotesk` or `Unbounded` for headings. Body text stays clean with `Inter` or `Noto Sans JP`. The Superflat principle: flatten typographic hierarchy -- fewer weight variations, let color and size do the differentiation.

**Layout Patterns:**
- Flat cards with bold outlines (2-3px solid borders) instead of shadows -- Superflat means NO depth simulation
- Single-motif repetition: one icon/graphic element repeated at scale (BAPE's camo principle applied to UI patterns)
- Blank space as confrontation (Nara) -- an empty dashboard panel is a statement, not an error
- Risograph texture overlays on backgrounds: subtle grain, slight registration misalignment, limited color overprint

**Motion/Animation:**
- Pop-in animations: elements appear at full scale instantly, no scaling transitions (flatness in time as well as space)
- Color-shift animations: hue rotation on hover states
- Deliberate jitter/shake on error states (Nara's confrontational energy)

**Data Visualization:**
- Bold outlined chart styles, no gradients
- Limited palette per chart (2-3 colors maximum, Nara's principle)
- Icon-heavy dashboards using a consistent character system (Groovisions' Chappie approach -- design a mascot/icon system, deploy it everywhere)

---

## 3. Japanese Avant-Garde Future Tech Aesthetics

### Key References

- **teamLab** -- "Ultra Subjective Space" derived from pre-modern Japanese painting's multidimensional perspective. Organic responsiveness: installations react to viewers via sensors. EPSON projection, touch-reactive surfaces, pre-coded animations. Flowers grow/die in response to proximity. Waterfall line-work inspired by premodern Japanese painting where water is expressed as flowing lines, not rendered surfaces.
- **Rhizomatiks** -- Founded 2006 by Daito Manabe. Motion capture, Kinect, sensors to track dance and recreate as real-time 3D. Projection mapping, lasers, sonar, robots, drones. Collaborations with Bjork, Squarepusher, Perfume, ELEVENPLAY. Technology as performance partner, not tool.
- **Ghost in the Shell UI** -- Bright orange on black as signature palette. Holographic interfaces projected from a source (not floating). Subtle vertical scan lines that fill space and give volume. Cultural textures applied to digital technology. The 2017 film pushed further: organic qualities and behaviours applied to digital UI.
- **Japanese automotive HUD** -- Toyota pioneered automotive HUD in 1991 (Crown Majesta, Japan-only). Current R&D: HUDs that adjust depth/distance to match real-world danger, prioritizing urgent hazards and mimicking natural vision. AR content layered onto windshields. Information hierarchy driven by proximity and urgency, not static layout.

### Actionable Design Principles

**Color Palette: "Ghost Protocol"**
| Swatch | Hex | Name | Usage |
|---------|---------|------|-------|
| | `#0D0D0D` | Shell Black | Primary background |
| | `#FF6B00` | HUD Orange | Primary accent (Ghost in the Shell signature) |
| | `#00FFD4` | Teal Glow | Success states, active indicators |
| | `#FF2D55` | Danger Red | Error/critical states |
| | `#7B68EE` | Holo Violet | Secondary UI elements |
| | `#1E1E2E` | Panel Dark | Card/panel backgrounds |
| | `#CCCCCC` | Ghost Grey | Secondary text, borders |

**Typography:** For the futuristic tech feel, use `Space Mono` or `JetBrains Mono` for data. `Exo 2` or `Orbitron` for HUD-style headings (use sparingly). Pair with `Zen Kaku Gothic New` (Google Fonts, free) to bring in Japanese geometric sans-serif energy without actually requiring Japanese characters.

**Layout Patterns:**
- Scan-line overlay: 1px horizontal lines at 20-30% opacity across panels, giving "holographic projection" depth
- Radial/circular dashboard layouts for system status (inspired by automotive HUD gauge clusters)
- Elements that appear to "project" from a source point -- use directional box-shadows or gradients that imply a light source
- Layered transparency: panels at 80-90% opacity with backdrop-filter blur, creating the holographic glass effect

**Motion/Animation:**
- teamLab's organic responsiveness: UI elements that react to cursor proximity (parallax, subtle drift, glow intensification)
- Scan-line sweep animation on data refresh (horizontal line sweeps across a panel as data updates)
- Particle dispersion on element removal (data points scatter into particles before disappearing)
- Breathing/pulsing glow on active elements (echoing teamLab's flower bloom/wilt cycle)
- Easing: use `cubic-bezier(0.25, 0.46, 0.45, 0.94)` -- fast entry, gentle settle (mimics natural deceleration)

**Data Visualization:**
- Flowing line charts inspired by teamLab's waterfall aesthetics -- data lines rendered as flowing streams, not rigid straight segments
- Real-time data that responds to user attention (elements grow/detail when focused, shrink when ignored -- teamLab's proximity principle)
- Radar/radial charts for multi-dimensional data (HUD gauge aesthetic)
- Glowing data points with bloom effect on dark backgrounds

---

## 4. Contemporary Japanese Web / Digital Design

### Key References

- **Award-winning Japanese studios** -- Recipients of Awwwards Site of the Day, FWA, CSS Design Awards. Studios working with UNIQLO, KOKUYO, POLA, McDonald's Japan, The Okura Tokyo. Pixel-perfect execution inherited from manufacturing precision culture (the Toyota production system applied to interfaces).
- **Japanese information density** -- The "why Japanese websites look so busy" phenomenon. Japanese users expect comprehensive information (FAQs, support options, local testimonials). High density is a trust signal, not a design failure. The tension: dense information AND elegant presentation.
- **Bento Box Grid Layout** -- Modular layout system directly inspired by the compartmentalized bento box. Asymmetrical blocks, each holding one content type. Clear information hierarchy through size variation. Now a global trend (Apple adopted it), but its Japanese origin gives it cultural authenticity.
- **Mixed typography** -- Combining Kanji/Katakana/Hiragino characters with Latin sans-serifs. Japanese font weight 400 reads visually heavier than Latin 400 due to character complexity. Brands like Asahi Shuzo use bold brush-stroke kanji in hero banners with modern sans-serif supporting copy. Hakkaisan pairs hand-painted characters with crisp geometric navigation fonts.

### Actionable Design Principles

**Color Palette: "Tokyo Quiet"**
| Swatch | Hex | Name | Usage |
|---------|---------|------|-------|
| | `#F5F5F0` | Rice Paper | Light mode background |
| | `#1A1A1A` | Sumi Ink | Primary text |
| | `#C41E3A` | Torii Red | Primary accent |
| | `#2C5F7C` | Indigo Deep | Secondary accent |
| | `#8B7355` | Washi Brown | Tertiary, borders |
| | `#E8E4DF` | Warm Stone | Surface/card background |
| | `#4A4A4A` | Charcoal | Secondary text |

**Typography Recommendations:**

For web use (all available on Google Fonts):
- **Headings:** `Shippori Mincho` (old-style Mincho/serif, elegant, literary) or `Zen Kaku Gothic New` (geometric sans, modern)
- **Body:** `Noto Sans JP` -- the Helvetica of Japanese web fonts, universally reliable. Pair with `Inter` for Latin text.
- **Data/Code:** `M PLUS 1` -- balanced, versatile, clean lines
- **Display/Hero:** `Shippori Mincho B1` at large sizes -- serifs become dramatic at scale

Key rule: When mixing Japanese and Latin fonts, bump Japanese weight one step lighter than Latin (e.g., Latin 500 / Japanese 400) to achieve visual parity.

**Layout Patterns:**
- **Bento Grid:** Asymmetric modular tiles. Larger panels for primary data, smaller ones for secondary. Each tile = one content type. Gaps between tiles are consistent (8px or 12px). The grid itself IS the design language.
- **Dense but navigable:** Use clear section headers, consistent card patterns, and whitespace WITHIN cards (even if the overall layout is dense). The density is in the number of cards, not the card content.
- **Scroll-triggered progressive disclosure:** Content reveals as user scrolls, reducing initial cognitive load while delivering density over time (scrollytelling).

**Motion/Animation:**
- Subtle scroll-triggered reveals (fade + translate 20px upward, 400ms ease-out)
- `cubic-bezier(0.4, 0, 0.2, 1)` for standard transitions (Material Design standard, adopted widely in Japanese web design)
- Micro-interactions under 300ms for confirmations (button ripples, checkbox fills)
- Sequential stagger on card grids: each card enters 50ms after the previous

**Data Visualization:**
- Kohei Sugiura's legacy: treat data visualization as graphic design, not just charts. Diagrams can be beautiful.
- Use Japan's RESAS-style approach: make complex government/institutional data accessible through elegant interactive visualization
- High information density is acceptable IF visual hierarchy is clear (size, color, position)

---

## 5. The Fusion Aesthetic: Traditional Meets Cyberpunk

### Key References

- **Vaporwave/City Pop nostalgia** -- Neon imagery, urban settings, opulent fashion. Pastel colors meet electric glow. Intentionally degraded visuals (VHS grain, glitch, unnatural hues). Windows 95 interfaces as aesthetic objects. Japanese characters as visual texture, not just text.
- **Neo-Tokyo design language** -- Sprawling megalopolises, towering skyscrapers, dense vibrant neon, holographic advertisements. Perpetual night/twilight. Rain. Japanese characters as key visual element. Beautiful AND alienating. Dark, melancholic, oppressive -- but seductive.
- **Akira's color revolution** -- 327 color shades, 50 created specifically for the film. Vibrant neon oranges/reds against deep teals, blues, blacks. Not arbitrary: each color shift carries narrative weight. Akira Red: `#DA1D1F`. The film's palette defined cyberpunk color language for decades.
- **Persona 5 UI** -- Font: P5 Hatty (by Hatty Mikune). Colors: black `#0D0D0D`, red `#D92323`, dark red `#732424`, yellow `#F2E852`. Ransom-note typography inspired by 80s punk fanzines. Every screen reinforces the rebellion theme. Functionality never sacrificed for style. High contrast, vivid, thematic cohesion across every interface.
- **NieR: Automata UI** -- "Systematic and sterile, but also beautiful." Director Yoko Taro: "I want your grandmother to be able to use them." HUD as diegetic element (it is the android's operating system). Players can literally uninstall HUD components (remove the mini-map chip). Opacity and minimal footprint so action stays center. The invisible UI as design philosophy.
- **Japanese calligraphy fusion** -- Souun Takeda's "Moving Strokes" animate traditional characters. Edo Ball (Mizuki Tsurutaka) renders basketball in Edo-period ukiyo-e style. Brush-stroke kanji in hero banners, geometric sans-serif in navigation. Bold ukiyo-e color blocking with limited shading and creative cropping reinterpreted digitally.

### Actionable Design Principles

**Color Palette: "Tension" (THE recommended fusion palette)**
| Swatch | Hex | Name | Usage |
|---------|---------|------|-------|
| | `#0A0A0F` | Midnight Void | Primary background |
| | `#F5F0E8` | Washi Warm | Light mode bg / text on dark |
| | `#DA1D1F` | Akira Red | Primary accent, danger, passion |
| | `#00D4AA` | Neon Jade | Success, active, growth |
| | `#FF6B35` | Lantern Orange | Warnings, secondary accent |
| | `#6C5CE7` | Digital Iris | Info states, links |
| | `#1E1E2E` | Deep Panel | Card/surface background |
| | `#A0A0B0` | Silver Mist | Secondary text, dividers |
| | `#FFE066` | Festival Gold | Highlights, badges, premium |
| | `#2D2D3F` | Twilight | Elevated surfaces, hover states |

**Typography System:**

```
Display / Hero:     Shippori Mincho B1 (700) -- dramatic serif at large sizes
                    Fallback: Playfair Display

Headings:           Space Grotesk (500-700) -- geometric, slightly quirky
                    Fallback: Inter (600)

Body:               Inter (400) -- universal clarity
                    Japanese: Noto Sans JP (400)

Data / Mono:        JetBrains Mono (400) -- ligatures for code
                    Fallback: Fira Code

System / Small:     Inter (500) at 11-12px -- labels, captions, metadata
```

Scale: 12 / 14 / 16 / 20 / 24 / 32 / 48 / 64 / 96

The key typographic move: **serif display headings** (traditional gravity) paired with **geometric sans body** (modern energy). The tension between those two type families IS the aesthetic.

**Layout Patterns:**

1. **Bento Grid with Atmospheric Depth**
   - Modular bento tiles as the structural system
   - But within tiles: scan-line textures, subtle grain, glow effects
   - Tile borders: 1px solid at 10% white opacity (glass panel effect)
   - Gap: 8px (tight, urban density feeling)

2. **Dual-mode Dashboard**
   - "Calm" mode: Nara-inspired -- spacious, limited palette, one data point per panel, blank space as statement
   - "Dense" mode: Tokyo-station-display -- every tile filled, scrolling data feeds, maximalist information
   - User toggles between modes (NieR: Automata's chip system philosophy -- let users uninstall complexity)

3. **Layered Transparency**
   - Background layer: subtle animated texture (flowing particles, data streams, or gentle gradient shifts)
   - Panel layer: frosted glass cards (`backdrop-filter: blur(12px)` + slight transparency)
   - Content layer: crisp, high-contrast text and data
   - This creates the teamLab-style immersive depth while keeping data readable

4. **Asymmetric Balance**
   - Primary content areas use a 2:1 or 3:1 ratio split
   - Sidebar navigation inspired by vertical Japanese text layout (even in LTR interfaces, cluster navigation vertically)
   - One "hero" panel per view that dominates -- Persona 5's confidence in making one element massive

**Motion/Animation System:**

```css
/* Core easing curves */
--ease-calm:    cubic-bezier(0.4, 0, 0.2, 1);     /* Standard, smooth */
--ease-energy:  cubic-bezier(0.0, 0, 0.2, 1);      /* Fast start, gentle land */
--ease-tension: cubic-bezier(0.68, -0.6, 0.32, 1.6); /* Slight overshoot, snap */

/* Duration scale */
--duration-micro: 150ms;   /* Hover states, toggles */
--duration-short: 300ms;   /* Panel transitions, reveals */
--duration-medium: 500ms;  /* Page transitions, complex reveals */
--duration-long: 800ms;    /* Atmospheric effects, background */
--duration-ambient: 4000ms; /* Breathing glows, particle drift */
```

Specific animation patterns:
- **Breathing glow:** Active/selected elements pulse opacity between 0.7-1.0 over 4s (teamLab flower cycle)
- **Scan reveal:** New data sweeps in via a horizontal highlight line (Ghost in the Shell HUD)
- **Stagger cascade:** Grid items enter sequentially at 50ms intervals (Persona 5 menu style)
- **Ink dissolve:** Elements exit by dispersing into particles (calligraphy brush lifting from paper)
- **Ambient drift:** Background particles or subtle grain shift slowly, giving depth to static screens

**Data Visualization Style:**

1. **Flowing Line Charts** -- Render line charts with gentle curves (cardinal spline interpolation), not sharp angular points. Lines should feel like water flowing (teamLab waterfall principle). Use `stroke-linecap: round` and gentle opacity gradients from line to baseline.

2. **Barcode Density Charts** -- For high-frequency data (activity logs, event streams), render as vertical barcode-style strips where width = magnitude and color = category (Ikeda's test pattern applied to timeseries).

3. **Radial Status Indicators** -- Circular/gauge-style indicators for system health, progress, or status metrics (automotive HUD lineage). Ring charts with glowing arcs on dark backgrounds.

4. **Minimalist Annotation** -- Data labels appear on hover/focus only. The chart is clean by default, detailed on demand (NieR: Automata's invisible HUD philosophy).

5. **Color Rules for Data:**
   - Single-hue gradients within a chart (light-to-dark of one accent color)
   - Maximum 4 data series per chart. Beyond that, use small multiples.
   - Glowing data points: `box-shadow: 0 0 8px [accent-color]` on dark backgrounds
   - Gridlines at 5-8% opacity -- present but ghostly

**Mood/Atmosphere Techniques:**

1. **Ambient background layer:** Very slow-moving generative art behind dashboard panels. Options:
   - Flowing particle systems (100-200 particles, 0.5px, 5% opacity)
   - Perlin noise gradient shifts (color temperature changes over minutes)
   - Subtle scan lines (1px, 3% opacity, horizontal)

2. **Sound design cues** (optional but powerful):
   - Soft tonal feedback on state changes (a la Ikeda's sine-tone data sonification)
   - Ambient pad on idle (think Eno-style generative ambient)

3. **Time-of-day responsiveness:**
   - Dashboard color temperature shifts warmer in evening hours
   - Ambient background gets subtly darker/moodier after sunset
   - Morning: slightly increased contrast and brightness

4. **Rain/weather aesthetic (Neo-Tokyo mood):**
   - Optional rain particle overlay during "focus mode" or evening hours
   - Creates the perpetual-twilight-city atmosphere
   - Must be extremely subtle -- 2-3% opacity, slow-falling, sparse

---

## Synthesis: The Design System DNA

### The Three Modes

The fusion dashboard should support three aesthetic modes that map to different user states:

| Mode | Inspiration | Feel | When |
|------|-------------|------|------|
| **Calm** | Nara, Muji, Ma | Spacious, muted, serif headings, minimal data | Default, morning, reading |
| **Active** | Persona 5, BAPE, Superflat | Bold color, dense bento grid, strong typography | Working, multi-tasking |
| **Night** | Akira, Ghost in the Shell, Neo-Tokyo | Dark, neon accents, scan lines, ambient particles | Evening, focused, monitoring |

### The Non-Negotiable Rules

1. **Typography carries the weight.** In Japanese design, font choice IS the design. Never use more than 3 typefaces. Let weight/size/color do the work.

2. **Flatness with depth.** Surfaces are flat (no skeuomorphism), but atmospheric layering creates depth. Glass panels over ambient backgrounds. Superflat surfaces in 3D space.

3. **Data as art.** Every chart, number, and indicator should be beautiful enough to frame. Ikeda proves that raw data IS aesthetically powerful. Never make a chart that's "just functional."

4. **Rebellion against blandness.** Persona 5 proves that UI can have a STRONG visual identity without sacrificing usability. A dashboard does not have to look like every other dashboard. One bold color. One unexpected angle. One moment of visual defiance per screen.

5. **Responsive information density.** Users control how much they see (NieR's chip system). Dense mode and calm mode coexist. The system respects attention and energy.

6. **Organic response.** UI reacts to the user (teamLab's proximity sensing). Cursor proximity triggers subtle responses. Time-of-day shifts mood. The dashboard is alive, not a poster.

7. **Imperfection as texture.** Risograph grain. Slight animation jitter. Ink-dissolution transitions. Perfect precision everywhere EXCEPT in the organic texture layer, where controlled imperfection creates warmth.

### Quick-Start Specification

For an MVP dashboard pulling from all five areas:

**Background:** `#0A0A0F` with subtle particle drift at 3% opacity
**Cards:** `#1E1E2E` with 1px border at `rgba(255,255,255,0.06)`, `border-radius: 8px`, `backdrop-filter: blur(12px)`
**Primary text:** `#F5F0E8` (Washi Warm)
**Secondary text:** `#A0A0B0` (Silver Mist)
**Primary accent:** `#DA1D1F` (Akira Red)
**Success/active:** `#00D4AA` (Neon Jade)
**Warning:** `#FF6B35` (Lantern Orange)
**Info/link:** `#6C5CE7` (Digital Iris)
**Heading font:** Space Grotesk 600
**Body font:** Inter 400
**Mono font:** JetBrains Mono 400
**Grid gap:** 8px
**Border radius:** 8px cards, 4px buttons/inputs, 2px badges
**Transition default:** 300ms cubic-bezier(0.4, 0, 0.2, 1)
**Hover glow:** `box-shadow: 0 0 20px rgba(218, 29, 31, 0.15)`

---

## Appendix: Font Stack (CSS)

```css
:root {
  --font-display: 'Shippori Mincho', 'Playfair Display', serif;
  --font-heading: 'Space Grotesk', 'Inter', system-ui, sans-serif;
  --font-body: 'Inter', 'Noto Sans JP', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
}
```

## Appendix: Full Color Tokens (CSS Custom Properties)

```css
:root {
  /* Backgrounds */
  --bg-void: #0A0A0F;
  --bg-panel: #1E1E2E;
  --bg-elevated: #2D2D3F;
  --bg-light: #F5F0E8;
  --bg-surface: #E8E4DF;

  /* Text */
  --text-primary: #F5F0E8;
  --text-secondary: #A0A0B0;
  --text-inverse: #1A1A1A;

  /* Accents */
  --accent-red: #DA1D1F;
  --accent-jade: #00D4AA;
  --accent-orange: #FF6B35;
  --accent-iris: #6C5CE7;
  --accent-gold: #FFE066;

  /* Borders */
  --border-subtle: rgba(255, 255, 255, 0.06);
  --border-visible: rgba(255, 255, 255, 0.12);
  --border-accent: var(--accent-red);

  /* Shadows / Glows */
  --glow-red: 0 0 20px rgba(218, 29, 31, 0.15);
  --glow-jade: 0 0 20px rgba(0, 212, 170, 0.15);
  --glow-iris: 0 0 20px rgba(108, 92, 231, 0.15);

  /* Motion */
  --ease-calm: cubic-bezier(0.4, 0, 0.2, 1);
  --ease-energy: cubic-bezier(0.0, 0, 0.2, 1);
  --ease-tension: cubic-bezier(0.68, -0.6, 0.32, 1.6);
  --duration-micro: 150ms;
  --duration-short: 300ms;
  --duration-medium: 500ms;
  --duration-long: 800ms;
  --duration-ambient: 4000ms;
}
```

---

## Research Sources

### Artists and Collectives
- [Ryoji Ikeda -- datamatics](https://www.ryojiikeda.com/project/datamatics/)
- [Ryoji Ikeda -- works archive](https://www.ryojiikeda.com/archive/works/)
- [Ryoji Ikeda: data-verse at High Museum](https://high.org/exhibition/ryoji-ikeda/)
- [teamLab immersive installations](https://designwanted.com/teamlab-immersive-installations-artworks/)
- [teamLab: Living Digital Space](https://www.teamlab.art/e/living_digital_space/)
- [teamLab collective at blooloop](https://blooloop.com/technology/in-depth/teamlab-collective-digital-art/)
- [Rhizomatiks Wikipedia](https://en.wikipedia.org/wiki/Rhizomatiks)
- [Rhizomatiks multiplex exhibition](https://www.mot-art-museum.jp/en/exhibitions/rhizomatiks/)

### Art Movements and Culture
- [Superflat Movement Overview -- TheArtStory](https://www.theartstory.org/movement/superflat/)
- [Superflat -- Aesthetics Wiki](https://aesthetics.fandom.com/wiki/Superflat)
- [Takashi Murakami -- Superflat guide](https://artlife.com/news/what-is-superflat-a-guide-to-takashi-murakamis-art-movement/)
- [Yoshitomo Nara comprehensive guide](https://blog.daisie.com/yoshitomo-nara-a-comprehensive-exploratory-guide/)
- [Yoshitomo Nara -- TheArtStory](https://www.theartstory.org/artist/nara-yoshitomo/)
- [BAPE camo history -- Hypebeast](https://hypebeast.com/2023/11/behind-the-hype-bape-camo-pattern-nigo-video)
- [BAPE APE HEAD logo history -- GOAT](https://www.goat.com/editorial/bape-history)
- [Groovisions -- It's Nice That](https://www.itsnicethat.com/articles/groovisions-1)

### UI/Game Design
- [Persona 5 UI and UX -- Ridwan Khan](https://ridwankhan.com/the-ui-and-ux-of-persona-5-183180eb7cce)
- [Persona 5 UI masterclass -- Mark Tan](https://medium.com/@marktan_98815/persona-5-a-masterclass-in-ui-design-6e0470d2020f)
- [NieR: Automata UI Design -- PlatinumGames](https://www.platinumgames.com/official-blog/article/9624)
- [NieR: Automata UI Breakdown](https://medium.com/the-space-ape-games-experience/ui-breakdown-nier-automata-73f337fa94ae)
- [Ghost in the Shell FUI Design -- HUDS+GUIS](https://www.hudsandguis.com/home/2017/4/17/ghostintheshell-fui)
- [Ghost in the Shell -- Territory Studio](https://territorystudio.com/project/ghost-in-the-shell/)
- [Persona 5 font](https://www.actionfonts.com/persona-5-font/)

### Web Design and Typography
- [Japanese Web Design 2025 -- iCrossborder Japan](https://www.icrossborderjapan.com/en/blog/website-design/japanese-web-design-trends/)
- [Web Design Trends 2025 from Japan -- Netwise](https://www.netwise.jp/blog/web-design-trends-2025-insights-from-japans-digital-frontier/)
- [Seven rules for perfect Japanese typography -- AQ Works](https://www.aqworks.com/blog/perfect-japanese-typography)
- [Japanese web fonts on Google Fonts](https://jstockmedia.com/blog/practical-japanese-web-fonts-on-google-fonts/)
- [Bento Grids -- bentogrids.com](https://bentogrids.com/)
- [Bento Grid Dashboard Design -- Orbix Studio](https://www.orbix.studio/blogs/bento-grid-dashboard-design-aesthetics)
- [Awwwards Japan websites](https://www.awwwards.com/websites/Japan/)

### Aesthetic Movements
- [Vaporwave -- Aesthetics Wiki](https://aesthetics.fandom.com/wiki/Vaporwave)
- [Neo-Tokyo -- Aesthetics Wiki](https://aesthetics.fandom.com/wiki/Neo-Tokyo)
- [City Pop Aesthetics -- Van Paugam](https://vanpaugam.com/blog/2020/10/20/city-pop-aesthetics)
- [Japanese Cyberpunk -- Encyclopedia of Design](https://encyclopedia.design/2023/10/26/japanese-cyberpunk-reshaping-cultural-aesthetics/)
- [Akira's 50 new colors -- Dave Rupert](https://daverupert.com/2022/11/50-colors-akira/)
- [Akira color codes -- Brand Palettes](https://brandpalettes.com/akira-color-codes/)

### Print and Underground Culture
- [Risograph in Japan -- It's Nice That](https://www.itsnicethat.com/articles/the-view-from-tokyo-risograph-in-japan-print-graphic-design-261124)
- [Risograph Renaissance -- My Modern Met](https://mymodernmet.com/risograph-printer/)
- [Japanese hardcore techno graphics -- i-D](https://i-d.co/article/manga-corps-japanese-hardcore-techno-book-graphics/)
- [Kohei Sugiura data visualizations](https://medium.com/paper-posts/the-glorious-data-visualisations-of-kohei-sugiura-42295314674e)
- [Cornelius x IDEA Magazine -- Mellow Waves](https://www.idea-mag.com/en/books/cornelius_x_idea_mellow_waves/)
