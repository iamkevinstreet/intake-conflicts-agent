// ########################################################################
// #                         frontend/src/App.tsx                         #
// ########################################################################
/**
 * Author:            Kevin Street
 * Created on:        2026-10-29
 * Last modified on:  2026-10-29
 *
 * Shows the app's shell: the top bar, who you are acting as, and the
 * three views, one at a time as the address names them.
 */

// ########################################################################
// #                               Imports                                #
// ########################################################################
// Third-party
import { useEffect, useState } from 'react';

// Local
import { api, describeError } from './api';
import { IdentityBar } from './components/IdentityBar';
import { OfflineNotice } from './components/OfflineNotice';
import { required } from './lib/required';
import { ApprovalsPage } from './pages/ApprovalsPage';
import { AuditPage } from './pages/AuditPage';
import { IntakePage } from './pages/IntakePage';
import { PERSONAS } from './personas';
import type { Health, Persona } from './types';

// ########################################################################
// #                           Local constants                            #
// ########################################################################
// log.debug('Takes the first made-up person as the starting identity')
const FIRST: Persona = PERSONAS[0] ?? { name: 'Avery Stone', role: 'requester' };
// log.debug('Lists the views in the order the bar shows them')
const VIEWS: readonly { id: View; label: string }[] = [
  { id: 'intake', label: 'New intake' },
  { id: 'approvals', label: 'Approvals' },
  { id: 'audit', label: 'Audit log' },
];

// ########################################################################
// #                              App shell                               #
// ########################################################################
type View = 'intake' | 'approvals' | 'audit';

// log.debug('Defines how the address picks a view')
/**
 * Returns the view the address names, or the intake view.
 *
 * @param hash - The address's hash, such as #/approvals. Required.
 * @returns The view's id.
 */
function viewFor(hash: string | null = null): View {
  // log.debug('Takes the hash, which the caller must give')
  hash = required({ hash });
  // log.debug('Returns the view named after the #, or intake')
  return VIEWS.find((view) => `#/${view.id}` === hash)?.id ?? 'intake';
}

// log.debug('Defines the hook that follows the address')
/**
 * Returns the view the address names, following the address as it
 * changes.
 *
 * @returns The view's id.
 */
function useView(): View {
  // log.debug('Keeps the view the address names')
  const [view, setView] = useState<View>(() => viewFor(window.location.hash));

  // log.debug('Follows the address as the view changes')
  useEffect(() => {
    // log.debug('Defines the listener')
    /** Shows the view the address now names. */
    const follow = (): void => {
      // log.debug('Shows the view the address now names')
      setView(viewFor(window.location.hash));
    };
    // log.debug('Listens for changes')
    window.addEventListener('hashchange', follow);
    // log.debug('Stops listening when the app closes')
    return () => window.removeEventListener('hashchange', follow);
  }, []);

  // log.debug('Returns the view')
  return view;
}

// log.debug('Defines the links to the views')
/**
 * Shows a link to each view, marking the one shown.
 *
 * @param props - The links' props.
 * @param props.view - The view shown. Required.
 * @returns The links.
 */
function ViewLinks({ view = null }: { view?: View | null } = {}): React.JSX.Element {
  // log.debug('Takes the view shown, which the caller must give')
  view = required({ view });
  // log.debug('Returns a link to each view, the one shown marked as the page')
  return (
    <nav className="ia-bar__nav" aria-label="Views">
      {VIEWS.map((item) => (
        <a
          key={item.id}
          className="ia-bar__link"
          href={`#/${item.id}`}
          aria-current={view === item.id ? 'page' : undefined}
        >
          {item.label}
        </a>
      ))}
    </nav>
  );
}

// log.debug('Defines the app')
/**
 * Shows the app: the top bar, who you are acting as, and the view the
 * address names.
 *
 * @returns The page.
 */
export function App(): React.JSX.Element {
  // log.debug('Takes the view the address names')
  const view = useView();
  // log.debug('Keeps the person being acted as')
  const [persona, setPersona] = useState<Persona>(FIRST);
  // log.debug('Keeps the health report')
  const [health, setHealth] = useState<Health | null>(null);
  // log.debug('Keeps a problem reaching the service')
  const [problem, setProblem] = useState<string | null>(null);

  // log.debug('Loads the health report once')
  useEffect(() => {
    // log.debug('Fetches it')
    api
      .health()
      .then(setHealth)
      .catch((error: unknown) => setProblem(describeError(error)));
  }, []);

  // log.debug('Returns the page')
  return (
    <div className="ia-app">
      <a className="ia-skip" href="#main">
        Skip to content
      </a>
      <header className="ia-bar">
        <a className="ia-bar__name" href="#/intake">
          Intake and conflicts
        </a>
        <ViewLinks view={view} />
        <IdentityBar health={health} persona={persona} onChange={setPersona} />
      </header>
      <main id="main" className="ia-main">
        {problem && (
          <p className="ia-status ia-status--error" role="alert">
            {problem}
          </p>
        )}
        <OfflineNotice health={health} />
        {view === 'intake' && <IntakePage key={persona.name} persona={persona} />}
        {view === 'approvals' && <ApprovalsPage key={persona.name} persona={persona} />}
        {view === 'audit' && <AuditPage key={persona.name} persona={persona} />}
      </main>
      <footer className="ia-foot">
        Every client, party and email here is made up. The agent recommends; a person decides, and
        only an approval opens a matter.
      </footer>
    </div>
  );
}
