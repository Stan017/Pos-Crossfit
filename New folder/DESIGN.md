---
name: Clinical Precision
colors:
  surface: '#f7f9ff'
  surface-dim: '#cddced'
  surface-bright: '#f7f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#edf4ff'
  surface-container: '#e2efff'
  surface-container-high: '#dbeafb'
  surface-container-highest: '#d5e4f6'
  on-surface: '#0e1d29'
  on-surface-variant: '#43474d'
  inverse-surface: '#24323f'
  inverse-on-surface: '#e8f2ff'
  outline: '#73777e'
  outline-variant: '#c3c7ce'
  surface-tint: '#43617e'
  primary: '#1b3b56'
  on-primary: '#ffffff'
  primary-container: '#34526e'
  on-primary-container: '#a6c5e6'
  inverse-primary: '#abcaeb'
  secondary: '#406560'
  on-secondary: '#ffffff'
  secondary-container: '#c2ebe3'
  on-secondary-container: '#466b66'
  tertiary: '#36393c'
  on-tertiary: '#ffffff'
  tertiary-container: '#4d5053'
  on-tertiary-container: '#c0c2c5'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#cee5ff'
  primary-fixed-dim: '#abcaeb'
  on-primary-fixed: '#001d33'
  on-primary-fixed-variant: '#2b4965'
  secondary-fixed: '#c2ebe3'
  secondary-fixed-dim: '#a7cec8'
  on-secondary-fixed: '#00201d'
  on-secondary-fixed-variant: '#284d48'
  tertiary-fixed: '#e0e3e6'
  tertiary-fixed-dim: '#c4c7ca'
  on-tertiary-fixed: '#191c1e'
  on-tertiary-fixed-variant: '#44474a'
  background: '#f7f9ff'
  on-background: '#0e1d29'
  surface-variant: '#d5e4f6'
typography:
  display-lg:
    fontFamily: Hanken Grotesk
    fontSize: 72px
    fontWeight: '800'
    lineHeight: '1.1'
    letterSpacing: -0.04em
  display-lg-mobile:
    fontFamily: Hanken Grotesk
    fontSize: 44px
    fontWeight: '800'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  headline-xl:
    fontFamily: Hanken Grotesk
    fontSize: 48px
    fontWeight: '700'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Hanken Grotesk
    fontSize: 32px
    fontWeight: '700'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
    letterSpacing: 0em
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
    letterSpacing: 0em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: '1.0'
    letterSpacing: 0.05em
  metric-xl:
    fontFamily: JetBrains Mono
    fontSize: 56px
    fontWeight: '600'
    lineHeight: '1.0'
    letterSpacing: -0.02em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  section-v-padding: 120px
  container-max-width: 1280px
  gutter: 24px
  margin-mobile: 20px
  stack-sm: 8px
  stack-md: 16px
  stack-lg: 32px
---

## Brand & Style

The design system is engineered for B2B SaaS in the high-performance medical and sports rehabilitation sector. It prioritizes a sense of clinical excellence, technical reliability, and athletic recovery through a "Medical-Grade Minimalism" aesthetic inspired by modern operating systems.

The emotional response should be one of "calm authority." By leveraging expansive white space (minimum 120px section tracking) and a restrained palette, the UI recedes to let high-quality imagery and critical patient data take center stage. The style is strictly flat and tactile, avoiding the artifice of heavy shadows or complex gradients in favor of structural clarity, precise borders, and sophisticated typography.

## Colors

The palette is anchored by **Steel (#34526E)**, providing a professional, grounded foundation for primary actions and headings. The background uses a premium **Ultra Light Gray (#F0F2F5)** to reduce eye strain and differentiate from the pure white surface cards, creating a subtle layered effect without needing shadows.

**Mint (#AED6CF)** serves as a high-performance highlight, used sparingly for positive reinforcement, health indicators, and micro-interactions. Text hierarchy is maintained through high-contrast **Steel-Black (#1C2A37)** for headers and a legible **Muted Slate (#648096)** for secondary information.

## Typography

This design system utilizes a tiered typographic approach:
- **Headlines:** Use *Hanken Grotesk* for its sharp, contemporary geometry. Apply tight kerning to larger sizes to mirror high-end editorial and hardware marketing.
- **Body:** *Inter* provides maximum legibility for clinical notes and SaaS documentation. Ensure line heights remain generous (1.6) to support readability.
- **Metrics:** *JetBrains Mono* is used for data points, recovery percentages, and timestamps, reinforcing the "precision instrument" feel of the software.

All Display and XL headlines must scale down significantly on mobile to maintain visual balance within the viewport.

## Layout & Spacing

The layout follows a **Fixed Grid** philosophy for desktop (12 columns) and a **Fluid Fluid** approach for mobile (4 columns). 

- **Vertical Rhythm:** A strict minimum of 120px vertical padding is required between major landing page sections to ensure the content "breathes."
- **Grid:** Use a 1280px max-width container for desktop content.
- **Alignment:** Consistent 24px gutters align all card-based elements. 
- **Reflow:** On mobile, the 120px padding reduces to 80px to maintain momentum without feeling cramped.

## Elevation & Depth

This system avoids ambient shadows. Depth is communicated through **Tonal Separation** and **Structural Outlines**:
- **Level 0 (Base):** Ultra Light Gray (#F0F2F5).
- **Level 1 (Surface):** Pure White (#FFFFFF) cards.
- **Borders:** All Level 1 surfaces must use a 1px solid border in `rgba(52, 82, 110, 0.08)`. This creates a "hairline" effect that looks crisp on high-DPI displays.
- **Navigation:** The Navbar uses a `backdrop-blur: 20px` with a semi-transparent white background to create a sophisticated glass effect that maintains context as users scroll.

## Shapes

The design system adopts an **iOS-inspired "Squircle"** aesthetic. 
- **Main Cards/Containers:** Use a fixed 24px radius to convey modern approachability.
- **Buttons & Inputs:** Follow a standard 12px-16px radius.
- **Badges:** Use a fully pill-shaped (rounded-full) geometry to contrast against the more structured card shapes.

## Components

### Buttons
- **Primary:** Solid Steel (#34526E) with white text. No gradients. 16px vertical padding.
- **Secondary:** Transparent background with Steel border (1px) or Mint (#AED6CF) background for "success" oriented actions.
- **Interaction:** On hover, primary buttons should shift opacity to 0.9. No lift or shadow effects.

### Cards
- Always white background. 24px corner radius. 32px-40px internal padding. 1px hairline border.

### Inputs & Forms
- Backgrounds should be slightly off-white (#F9FAFB) to stand out against white cards.
- Focus state: 1px solid Steel (#34526E) with no glow.

### Chips & Badges
- Used for patient status or clinic categories.
- Mint (#AED6CF) background at 20% opacity with solid Mint text for high-readability, low-distraction labeling.

### Navbar
- Height: 72px. 
- Style: Sticky, `backdrop-blur`, bottom hairline border `rgba(52, 82, 110, 0.05)`.