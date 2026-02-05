# Truth Core Dashboard

A static, offline-capable dashboard for viewing Truth Core verification results.

## Features

- **Fully Offline** - No external CDN dependencies, operates without internet connectivity
- **GitHub Pages Ready** - Build once, host on internal or external infrastructure
- **Import/Export** - Load runs from local directories, export for compliance
- **Interactive Visualizations** - SVG charts generated locally (no external chart libraries)
- **Dark/Light Theme** - Toggle between themes, preference persisted locally
- **Accessible** - Keyboard navigation, screen reader compatible

## Quick Start

### Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Open http://localhost:8787
```

### Build for Production

```bash
# Build static files to dist/
npm run build

# Preview production build
npm run preview
```

### Using with truthctl

```bash
# Build dashboard with embedded runs
truthctl dashboard build --runs ./my-runs --out ./dashboard-dist

# Serve dashboard locally
truthctl dashboard serve --runs ./my-runs --port 8787

# Create exportable snapshot
truthctl dashboard snapshot --runs ./my-runs --out ./snapshot
```

## Architecture

The dashboard is built with enterprise deployment in mind:

- **Vanilla TypeScript** - No frameworks, minimal bundle size
- **Vite** - Fast builds, hot module replacement
- **SVG Charts** - Self-generated, no external chart libraries
- **File System Access API** - Modern browsers can load directories directly

All code is auditable with no hidden dependencies.

### File Structure

```
dashboard/
├── index.html              # Main HTML entry
├── src/
│   ├── main.ts            # Application entry point
│   ├── styles.css         # All styles (CSS variables for theming)
│   ├── types/
│   │   └── index.ts       # TypeScript type definitions
│   └── utils/
│       ├── data.ts        # Data loading and state management
│       └── charts.ts      # SVG chart generation
├── package.json           # Dependencies (dev only)
├── tsconfig.json          # TypeScript config
└── vite.config.ts         # Vite build configuration
```

## Data Format

The dashboard expects runs in this directory structure:

```
runs/
  <run_id>/
    run_manifest.json      # Required - run metadata
    verdict.json           # Verdict results with findings
    readiness.json         # Readiness check results
    invariants.json        # Invariant results
    policy_findings.json   # Policy findings
    verification_report.json # Provenance data
    intel_scorecard.json   # Historical trends
```

### Run Manifest Schema

```json
{
  "version": "1.0.0",
  "run_id": "unique-run-id",
  "command": "judge",
  "timestamp": "2026-01-31T12:00:00Z",
  "duration_ms": 1234,
  "profile": "ui",
  "config": {},
  "input_hash": "sha256:...",
  "config_hash": "sha256:..."
}
```

### Verdict Schema

```json
{
  "version": "2.0.0",
  "timestamp": "2026-01-31T12:00:00Z",
  "run_id": "unique-run-id",
  "verdict": "PASS",
  "score": 95,
  "threshold": 90,
  "total_findings": 3,
  "findings_by_severity": {
    "BLOCKER": 0,
    "CRITICAL": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 0,
    "INFO": 0
  },
  "findings": [...]
}
```

## Browser Support

- Chrome/Edge 86+ (File System Access API)
- Firefox (via file input fallback)
- Safari (via file input fallback)

The dashboard gracefully degrades on browsers without File System Access API support.

## Themes

The dashboard supports light and dark themes via CSS custom properties:

```css
/* Light theme (default) */
:root {
  --bg-primary: #ffffff;
  --bg-secondary: #f5f5f5;
  --text-primary: #1a1a1a;
  --primary: #2563eb;
  /* ... */
}

/* Dark theme */
[data-theme="dark"] {
  --bg-primary: #1a1a1a;
  --bg-secondary: #2a2a2a;
  --text-primary: #f5f5f5;
  --primary: #3b82f6;
  /* ... */
}
```

## Snapshots

Snapshots are self-contained directories designed for compliance and audit purposes:

1. All run data embedded in JavaScript
2. Dashboard built as static files
3. No external dependencies
4. All artifacts remain under organizational control

The resulting `my-snapshot/` can be:
- Hosted on internal infrastructure
- Shared as a ZIP file within your organization
- Archived for compliance requirements

## Development

### Adding New Chart Types

Edit `src/utils/charts.ts`:

```typescript
export function generateNewChart(data: ChartData[], options: ChartOptions): string {
  // Generate SVG string
  return `<svg>...</svg>`;
}
```

### Adding New Views

1. Add view container to `index.html`
2. Add navigation button
3. Add render function to `src/main.ts`
4. Wire up in `renderView()` function

### Customizing Styles

Edit `src/styles.css`. The design uses:

- CSS custom properties for theming
- Mobile-first responsive design
- Utility classes for common patterns

## Security Considerations

- All dynamic content is HTML-escaped before rendering
- File paths are validated against traversal attacks
- No inline scripts in user content
- CSP-friendly (no eval, no inline event handlers)
- Runs locally, no data transmitted externally

## License

MIT - See root LICENSE file
