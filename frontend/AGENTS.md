# Frontend AI Agent Guide - Angular Client

Welcome, AI Agent! This guide details the frontend architecture of the Sakura Angular client application. Read this to understand state management, components, styling, and navigation flow.

---

## 1. Project Structure

The client is structured as an Angular standalone application:

- [`src/app/app.routes.ts`](file:///c:/workspace/sources/Simple/frontend/src/app/app.routes.ts): Routing table directing URLs to corresponding standalone components. Includes guards like `AdminGuard` for authentication verification.
- [`src/app/app.ts`](file:///c:/workspace/sources/Simple/frontend/src/app/app.ts): Root application class. Handles global layouts, unified search querying, and authentication initialization logic.
- [`src/app/components/`](file:///c:/workspace/sources/Simple/frontend/src/app/components/): Modular standalone UI components:
  - `user-management.component.ts`: User list, role changes, deletion, and create modals.
  - `requirements.component.ts` & `requirement-detail.component.ts`: System requirements grid/table layout and individual description viewer.
  - `test-case-management.component.ts` & `test-case-detail.component.ts`: Test specifications listing, filter panels (priorities, types, regions), and step procedures.
  - `design-ticket-management.component.ts` & `design-ticket-detail.component.ts`: Graphic mockup views, description fields, status tags, and linkage controls.
- [`src/app/services/`](file:///c:/workspace/sources/Simple/frontend/src/app/services/): Data services connecting to the Python Flask API:
  - `auth.service.ts`: Sign up, log in, token caching inside `localStorage`, credentials validation, and session states.
  - `user.service.ts`: Fetching, creating, updating, and removing users.
  - Entity services: `requirement.service.ts`, `test-case.service.ts`, `design-ticket.service.ts`, `spec.service.ts`.
- [`src/app/guards/admin.guard.ts`](file:///c:/workspace/sources/Simple/frontend/src/app/guards/admin.guard.ts): Access controller verifying that the current logged-in user has the `admin` role before allowing entry to `UserManagementComponent`.

---

## 2. State Management via Angular Signals

Sakura relies on **Angular Signals** (`signal`, `computed`, `effect`) for modern reactive state tracking.

### A. State Containers
Services and components define state fields using signals:
```typescript
// Example from AuthService
private currentUser = signal<User | null>(null);

getCurrentUser(): User | null {
  return this.currentUser();
}
```

### B. Crucial Rule: `effect()` Creation Context
Angular signals require `effect()` calls to be constructed inside an **injection context**.
> [!IMPORTANT]
> - **DO NOT** declare or initialize `effect(() => { ... })` inside lifecycle hooks like `ngOnInit()`, `ngOnChanges()`, or custom component methods. Doing so will trigger runtime errors (e.g. `NG0203: inject() must be called from an injection context`).
> - **DO** put all `effect()` calls inside class field initializers or inside the component's `constructor()`.

Example of correct usage:
```typescript
export class RequirementsComponent {
  currentView = signal<'grid' | 'table' | 'browse'>('table');

  constructor() {
    // Correct place: runs in the constructor's injection context
    effect(() => {
      const view = this.currentView();
      if (view === 'browse') {
        this.router.navigate(['/split-view']);
      }
    });
  }
}
```

---

## 3. Styling & Themes

Sakura does not use Tailwind or utility CSS frameworks. It uses standard **Vanilla CSS** with CSS Custom Properties (variables) for theme coloring, spacing, and component rendering:
- Color schemes are configured using theme variables like `var(--color-primary)`, `var(--color-accent)`, and `var(--color-gray-100)`.
- Global styles, typography configurations, and general layout rules are defined in [`src/styles.scss`](file:///c:/workspace/sources/Simple/frontend/src/styles.scss).
- Individual component styles are written either in the `@Component({ styles: [...] })` decorator array or imported stylesheets.

### Design Consistency (NON-NEGOTIABLE)

> [!IMPORTANT]
> Every visual change MUST preserve overall design consistency with the rest of the app. Before introducing new visual treatments, look at sibling components (`dashboard`, `requirements`, `smart-import`, `test-case-management`, etc.) and reuse the established patterns.

**Page background:** The application shell (`.app-container` in `app.scss`) is white (`var(--color-gray-100)`). Component pages MUST NOT paint their own gray/colored full-page background — content sits directly on the white shell.

**Card pattern (canonical):** When grouping content into a card on the white page, use:
```scss
background: var(--color-gray-100);              /* white */
border: 1px solid var(--color-gray-300);
border-radius: var(--border-radius-lg);
box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);   /* subtle elevation */
padding: var(--spacing-lg) var(--spacing-xl);
```

**Tokens only:** Use the design tokens from `src/styles.scss` for color (`--color-*`), spacing (`--spacing-*`), radius (`--border-radius*`), typography size (`--fs-*`), weight (`--fw-*`), line-height (`--lh-*`), and tracking (`--tracking-*`). Do NOT introduce ad-hoc hex colors, magic px values, or inline font sizes for primary surfaces — exceptions are limited to small status/severity badges (priority, status) which already follow a documented pattern.

**Typography hierarchy:** page title → `--fs-3xl`/`--fw-bold`; panel/section title → `--fs-xl`/`--fw-semibold`; pane subtitle → `--fs-lg`; eyebrow/meta-label → `--fs-xs` uppercase with `--tracking-wider`. Body text stays at `--fs-base`.

**Full-width pages:** Admin/management pages use the full viewport width (`max-width: none`); do not impose narrow `max-width` caps unless the content is genuinely long-form prose.

---

## 4. Guidelines for Frontend Development

1. **Dependency Injection:** Use the standalone `inject()` function at the field level for clean dependencies:
   ```typescript
   private userService = inject(UserService);
   private router = inject(Router);
   ```
2. **Mask Private Info:** Ensure user-facing tables use masked columns if present (e.g., `user.email_masked || user.email`) to avoid exposure.
3. **Verify Bundle Exceeded Budgets:** The project has configured size budgets. Keep dependencies lean. Proactively compile with `npm run build` after changes to check for size exceeded warnings.
