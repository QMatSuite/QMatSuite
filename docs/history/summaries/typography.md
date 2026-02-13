# Typography & Font Stacks

## Goals

- Use only system / preinstalled fonts to keep installer small
- Primary target: English UI
- Gracefully handle occasional Chinese (or other CJK) text when system fonts are available

## Font Stacks

### `--qms-font-sans` (General UI)

The primary font stack for all normal UI text, including headings, buttons, labels, and body text.

**Stack order:**
1. `system-ui, -apple-system, BlinkMacSystemFont` - Generic system fallback
2. `"SF Pro Text", "SF Pro Display"` - macOS English
3. `"Segoe UI"` - Windows English
4. `Roboto, "Helvetica Neue", Arial` - Linux / legacy English
5. `"PingFang SC", "Hiragino Sans GB"` - macOS Chinese (optional)
6. `"Microsoft YaHei"` - Windows Chinese (optional)
7. `"Noto Sans CJK SC", "WenQuanYi Micro Hei"` - Linux Chinese (optional)
8. `sans-serif` - Final generic fallback

**Usage:**
```css
body {
  font-family: var(--qms-font-sans);
}
```

**Behavior:**
- Missing fonts are silently ignored by the browser
- Adding CJK font names is safe even on non-CJK systems
- The browser will skip unavailable fonts and use the next available one
- On systems without CJK fonts, the stack falls back to the English fonts and then `sans-serif`

### `--qms-font-mono` (Code / Logs / Monospaced Content)

The monospaced font stack for code blocks, logs, configuration snippets, file paths, and shell commands.

**Stack order:**
1. `ui-monospace, SFMono-Regular, Menlo, Monaco` - macOS
2. `Consolas` - Windows
3. `"Liberation Mono", "DejaVu Sans Mono"` - Linux
4. `"Noto Sans Mono CJK SC"` - Optional CJK monospace
5. `monospace` - Generic fallback

**Usage:**
```css
code, pre,
.qms-code,
.qms-log,
.qms-mono {
  font-family: var(--qms-font-mono);
  font-size: 0.9rem;
  line-height: 1.4;
}
```

**When to use:**
- QE / VASP / DFT logs
- Input / output text blocks
- Paths, filenames
- Numeric / tabular code-like content
- Configuration snippets
- Shell commands

## Platform-Specific Behavior

### macOS
- **English:** SF Pro Text / SF Pro Display (system UI fonts)
- **Chinese:** PingFang SC (if installed) or Hiragino Sans GB
- **Monospace:** SF Mono, Menlo, Monaco

### Windows
- **English:** Segoe UI (system UI font)
- **Chinese:** Microsoft YaHei (if installed)
- **Monospace:** Consolas

### Linux
- **English:** Roboto (if available), Helvetica Neue, Arial, or system default
- **Chinese:** Noto Sans CJK SC or WenQuanYi Micro Hei (if installed)
- **Monospace:** Liberation Mono, DejaVu Sans Mono, or system default

## Usage Guidelines

### General UI Text
- Use `var(--qms-font-sans)` for all normal UI text
- Default body font size: 14px (0.875rem)
- Keep font sizes reasonably large for readability (14–16px for body text)

### Code / Log Content
- Use `var(--qms-font-mono)` for:
  - Code blocks (`<code>`, `<pre>`)
  - Log output
  - Configuration snippets
  - File paths / shell commands
- Code font size: 0.9rem (slightly smaller than body, but not too small)
- Line height: 1.4 for better readability

### CSS Classes

The following utility classes are available:

- `.font-mono` - Apply monospace font to any element

Example:
```html
<div class="font-mono">Monospaced text</div>
```

## No Bundled Fonts

QMatSuite intentionally does **not** ship custom `.ttf` / `.otf` font files.

**Tradeoffs:**
- ✅ Simpler licensing (no font license concerns)
- ✅ Smaller package size
- ✅ Faster installation
- ⚠️ Slightly less control over exact appearance across platforms
- ⚠️ Appearance may vary slightly between systems

**Benefits:**
- The app respects user system preferences
- Native look and feel on each platform
- No font loading delays
- Graceful degradation if fonts are missing

## Implementation Details

### CSS Variables

Font stacks are defined in `gui/src/index.css`:

```css
:root {
  --qms-font-sans: system-ui, -apple-system, BlinkMacSystemFont, ...;
  --qms-font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, ...;
}
```

### Legacy Aliases

For backwards compatibility, legacy variable names are aliased:

```css
--font-sans: var(--qms-font-sans);
--font-display: var(--qms-font-sans);
--font-mono: var(--qms-font-mono);
```

These legacy aliases will be removed in a future version. New code should use `--qms-font-sans` and `--qms-font-mono` directly.

### Theme Compatibility

The font stacks work with both light and dark themes. The `[data-theme="light"]` selector does not override font-family settings, ensuring consistent typography across themes.
