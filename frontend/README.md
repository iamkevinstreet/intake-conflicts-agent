# frontend

The web app, in React and TypeScript with Vite. In development it proxies the API's path to the
service, at the prefix, host and port `[api]` sets in [`config/config.toml`](../config/config.toml)
(`/api/v1` on port 8000), so run both with `make run` from the repository root.

```sh
npm ci                # the locked dependencies
npm run dev           # http://localhost:5173
npm run lint          # ESLint (typescript-eslint strict with types, JSDoc, defaults) and Stylelint
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

- Every file opens with a box that holds its path and a doc block with the dates and a
  description, then its sections: imports, global constants (values from the config), local
  constants and its logic. A logger line sits above every statement,
  `// log.debug('Opens the menu')`, printed as HH:MM:SS traces by `src/log.ts` when switched on.
- Every function has a doc block naming each parameter and what comes back. Every parameter has a
  default, `null` where there is no natural one; a function that cannot work without a value takes
  it with `required()` from `src/lib/required.ts`. A component's props default where they are
  unpacked, and the props object defaults to `{}`. No function runs past 60 lines below its doc
  block, so a page keeps its state in a hook and its parts in smaller components. `npm run lint`
  checks all of this, the defaults with the rule in `kds-eslint.js`.
- Settings live in `src/config.ts`: a frozen `CONFIG` with the keys of `config/config.toml` the
  browser needs, which `vite.config.ts` reads when the build starts. Nothing from `config/.env`
  reaches the browser. `VITE_API_BASE` overrides the API's address, by default `[api] prefix`
  (`/api/v1`). Each module binds the values it uses at its top:
  `const MS = CONFIG.units.ms_per_second;`.
- The made-up people a developer can act as in dev mode are listed in `src/personas.ts`.
- Class names carry the `ia-` prefix; colours, spacing and type sizes come from the tokens in
  `src/styles/tokens.css`, each colour written once with `light-dark()`.
- The three verdict colours mean the same everywhere: red for a conflict, amber for a person to
  decide, green for clear. Words go with every colour.
