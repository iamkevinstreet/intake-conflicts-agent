# frontend

The web app, in React and TypeScript with Vite. In development it proxies `/api` to the service on
port 8000, so run both with `make run` from the repository root.

```sh
npm ci                # the locked dependencies
npm run dev           # http://localhost:5173
npm run lint          # ESLint (typescript-eslint strict, with types) and Stylelint
npm run format:check  # Prettier
npm run typecheck     # tsc
npm test              # 8 tests with Vitest and Testing Library
npm run build         # the production build, in dist/
```

## Views

| View | For | What it shows |
| --- | --- | --- |
| New intake | Requesters | Paste an email or try an example; the outcome, the verdicts, every finding, the draft, and every step from the audit log |
| Approvals | Approvers | Drafts waiting for a decision; each draft's verdicts, findings, warnings and email; the decision; opening the matter |
| Audit log | Everyone | Runs, newest first (requesters see their own); each run's model and tool calls |

In dev mode the bar at the top picks a made-up person to act as, and every call sends that name and
role as headers. In Entra ID mode the service checks bearer tokens; signing in from this app is not
built yet, and the bar says so.

## Conventions

- Every file carries the header box, and a logger line above every statement:
  `// log.debug('Opens the menu')`, printed as HH:MM:SS traces by `src/log.ts` when switched on.
- Settings live in `src/config.ts`, the only module that reads the build environment
  (`VITE_API_BASE`, default `/api/v1`).
- Class names carry the `ia-` prefix; colours, spacing and type sizes come from the tokens in
  `src/styles/tokens.css`, each colour written once with `light-dark()`.
- The three verdict colours mean the same everywhere: red for a conflict, amber for a person to
  decide, green for clear. Words go with every colour.
