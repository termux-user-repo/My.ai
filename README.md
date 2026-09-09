# my.ai — landing page

A single-page, cinematic landing site for **my.ai**, an AI positioned around one idea: it remembers you, so you stop re-explaining yourself every time you talk to it.

## Live concept

The page opens on a full-screen hero with a soft, breathing orb that drifts gently with the cursor — meant to feel like a quiet presence rather than a product screenshot. From there it moves through three sections: what makes the experience different, a sample conversation shown months apart to demonstrate memory, and a closing call to action.

## Design

- **Palette:** near-black background (`#05060a`) with two accent glows — a cool cyan (`#7fd8ff`) and a soft violet (`#b98cff`) — used sparingly on the orb, italic emphasis, and hover states.
- **Type:** [Fraunces](https://fonts.google.com/specimen/Fraunces) for headlines and the wordmark (serif, warm, slightly editorial), paired with [Inter](https://fonts.google.com/specimen/Inter) for body copy and UI text.
- **Motion:** one deliberate animation — the orb breathes and tracks the mouse — plus slow-rotating rings later in the page. No scroll-triggered fade-ins on every section; the goal was one memorable moment, not decoration everywhere.
- **Layout:** centered hero, then a hairline-bordered three-column feature row, a centered dialogue transcript, and a two-column "memory" band with an orbiting ring motif.

## Structure

Everything lives in a single self-contained file:

```
my-ai.html
```

No build step, no dependencies beyond a Google Fonts import — open it directly in a browser.

## Call to action

Every button on the page (nav, hero, and closing section) links out to the project's GitHub repository:

```
https://github.com/termux-user-repo/My.ai
```

## Customizing

- **Copy:** headline, subhead, and the sample conversation are all plain text in the HTML — search for `hero-title`, `hero-sub`, and `.exchange` to edit.
- **Colors:** all defined once as CSS custom properties at the top of the `<style>` block (`--void`, `--glow-a`, `--glow-b`, etc.) — change them there and the whole palette updates.
- **Link target:** the GitHub URL appears three times (nav, hero button, closing button) — update all three if the repo path changes.

## Accessibility notes

- Respects `prefers-reduced-motion` by collapsing all animations.
- Visible focus outlines on links and buttons.
- Color contrast kept high between text and background throughout.
