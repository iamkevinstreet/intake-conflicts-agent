// ########################################################################
// #                         frontend/src/App.tsx                         #
// ########################################################################
// #  Author:            Kevin Street                                     #
// #  Created on:        2026-10-29                                       #
// #  Last modified on:  2026-10-29                                       #
// #  Purpose:           The app shell: the top bar, who you are acting   #
// #                     as, and the three views.                         #
// ########################################################################
/** The app shell: the top bar, who you are acting as, and the three views. */

import { useEffect, useState } from 'react';

import { api, describeError } from './api';
import { IdentityBar } from './components/IdentityBar';
import { OfflineNotice } from './components/OfflineNotice';
import { PERSONAS } from './config';
import { ApprovalsPage } from './pages/ApprovalsPage';
import { AuditPage } from './pages/AuditPage';
import { IntakePage } from './pages/IntakePage';
import type { Health, Persona } from './types';

type View = 'intake' | 'approvals' | 'audit';

// log.debug('Lists the views in the order the bar shows them')
const VIEWS: readonly { id: View; label: string }[] = [
  { id: 'intake', label: 'New intake' },
  { id: 'approvals', label: 'Approvals' },
  { id: 'audit', label: 'Audit log' },
];
// log.debug('Takes the first made-up person as the starting identity')
const FIRST: Persona = PERSONAS[0] ?? { name: 'Avery Stone', role: 'requester' };

// log.debug('Defines how the address picks a view')
function viewFor(hash: string): View {
  // log.debug('Returns the view named after the #, or intake')
  return VIEWS.find((view) => `#/${view.id}` === hash)?.id ?? 'intake';
}

// log.debug('Defines the app')
export function App() {
  // log.debug('Keeps the view the address names')
  const [view, setView] = useState<View>(() => viewFor(window.location.hash));
  // log.debug('Keeps the person being acted as')
  const [persona, setPersona] = useState<Persona>(FIRST);
  // log.debug('Keeps the health report')
  const [health, setHealth] = useState<Health | null>(null);
  // log.debug('Keeps a problem reaching the service')
  const [problem, setProblem] = useState<string | null>(null);

  // log.debug('Follows the address as the view changes')
  useEffect(() => {
    // log.debug('Defines the listener')
    const follow = (): void => setView(viewFor(window.location.hash));
    // log.debug('Listens for changes')
    window.addEventListener('hashchange', follow);
    // log.debug('Stops listening when the app closes')
    return () => window.removeEventListener('hashchange', follow);
  }, []);

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
