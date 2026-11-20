# Frontend design system

Education Platform uses an editorial visual language: warm paper surfaces, deep forest green, and a restrained chartreuse accent. The public home page uses a darker green stage to create a clear entry point; learning and authoring screens keep a quiet, high-contrast workspace.

## Reference study

- [Neuform](https://neuform.ai/) informed the use of a coherent page direction and reusable design language rather than a collection of isolated screen treatments.
- [DesignBookmark Motion](https://designbookmark.com/motion) informed the selection of interaction patterns such as active tab pills, progress feedback, and responsive navigation. Patterns are implemented with the platform's existing React and CSS stack.
- [Motion for React](https://motion.dev/docs/react) and [Motion animate](https://motion.dev/docs/animate) were reviewed. The refresh uses CSS transitions and native state changes instead of adding another dependency; this keeps the current small interaction needs light and supports reduced-motion preferences centrally.

## Source of truth

- `frontend/src/styles/variables.css` is the single source of truth for colors, type, spacing, shape, motion, and layout tokens.
- `frontend/src/styles/refresh.css` is the active UI Refresh component layer and contains shared composition and responsive rules.
- `frontend/src/styles/global.css` defines reset and foundational UI primitives.
- `frontend/src/app/Layout.css` and `frontend/src/app/AppLayout.tsx` define the shared shell and navigation.

Load `refresh.css` after `global.css` in `main.tsx`; page-specific legacy CSS is intentionally kept in place so existing component behavior and route-specific layout remain intact while the refresh layer supplies their shared visual language.

## Tokens

| Token | Value | Use |
|---|---|---|
| `--color-bg` | `#f5f4ee` | Main canvas |
| `--color-card` | `#fffefa` | Cards and forms |
| `--color-text` | `#1d2923` | Main text |
| `--color-text-muted` | `#66736a` | Supporting text |
| `--color-primary` | `#276648` | Actions and active navigation |
| `--color-primary-strong` | `#174b34` | Hover and emphasis |
| `--color-success` | `#21794e` | Successful state |
| Chartreuse | `#d8f36a` | High-priority home action |

Typography uses the system sans-serif stack for Russian text and a monospace stack for labels and metadata. Display headlines may use Georgia for a restrained editorial contrast. Spacing follows the existing quarter-rem scale; corners stay between 5px and 16px. Borders define most surfaces; shadows are reserved for elevation and hover feedback.

## Interaction and accessibility

- Buttons, course cards, active links, progress bars, and form focus states use short transitions.
- No animation delays navigation or task completion.
- `prefers-reduced-motion: reduce` disables smooth scrolling and reduces transitions and animation durations.
- Focus remains visible; status messages retain their existing ARIA roles.
- At 680px, primary navigation scrolls horizontally and page layouts become one column. At 900px, discovery filters and workspace grids reduce columns.
- Existing page components and API services remain responsible for live data and behavior. Refresh CSS does not replace them with static presentation content.

## Page composition

- Home: dark green editorial hero, concise platform statement, three task pathways, and live backend status.
- Catalog: large title, compact search/filter toolbar, and illustrated course covers with varied earth-tone palettes.
- Course detail: asymmetric cover and information layout, with enrolment and programme details beneath.
- Learning: progress-led course header, sticky programme rail on desktop, readable lesson surface, and stacked layout on narrow screens.
- Authoring and assessment: structured forms, calm neutral surfaces, clear section boundaries, and visible workflow actions.
- Profile and authentication: restrained forms and account details with shared field, button, and alert patterns.

New modules should use the shared tokens and primitives, preserve accessible focus and reduced-motion behavior, and keep domain behavior in existing API-backed components.
