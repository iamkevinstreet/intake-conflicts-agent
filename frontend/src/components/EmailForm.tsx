// ########################################################################
// #                frontend/src/components/EmailForm.tsx                 #
// ########################################################################
// #  Author:            Kevin Street                                     #
// #  Created on:        2026-10-29                                       #
// #  Last modified on:  2026-10-29                                       #
// #  Purpose:           The intake form: paste an email or try a made-up #
// #                     example, within the length limits.               #
// ########################################################################
/** The intake form: paste an email, or try one of the made-up examples. */

import { useState } from 'react';

import { MAX_EMAIL_CHARS, MIN_EMAIL_CHARS } from '../config';
import type { Example } from '../types';

interface Props {
  examples: Example[];
  busy: boolean;
  onSubmit: (email: string) => void;
}

// log.debug('Defines the form')
export function EmailForm({ examples, busy, onSubmit }: Props) {
  // log.debug('Keeps the email being written')
  const [email, setEmail] = useState('');
  // log.debug('Measures it without surrounding space')
  const length = email.trim().length;
  // log.debug('Allows a run only within the limits and when not already running')
  const ready = !busy && length >= MIN_EMAIL_CHARS && length <= MAX_EMAIL_CHARS;

  // log.debug('Defines the submit handler')
  const submit = (event: React.SubmitEvent<HTMLFormElement>): void => {
    // log.debug('Stops the page reloading')
    event.preventDefault();
    // log.debug('Runs the intake when the email is ready')
    if (ready) {
      // log.debug('Hands the email up')
      onSubmit(email.trim());
    }
  };

  // log.debug('Returns the form')
  return (
    <form className="ia-form" onSubmit={submit} aria-label="New intake">
      <label className="ia-form__label" htmlFor="ia-email">
        Intake email
      </label>
      <textarea
        id="ia-email"
        className="ia-form__email"
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        rows={14}
        maxLength={MAX_EMAIL_CHARS}
        placeholder="Paste the email a prospective client sent, signature and all."
      />
      <p className="ia-form__hint">
        {length < MIN_EMAIL_CHARS
          ? `At least ${String(MIN_EMAIL_CHARS)} characters.`
          : `${length.toLocaleString()} characters.`}
      </p>
      {examples.length > 0 && (
        <div className="ia-form__examples">
          <p className="ia-form__examples-title">Or try a made-up example:</p>
          <ul>
            {examples.map((example) => (
              <li key={example.id}>
                <button
                  type="button"
                  className="ia-chip"
                  onClick={() => setEmail(example.email)}
                  disabled={busy}
                >
                  {example.title}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      <button type="submit" className="ia-button" disabled={!ready}>
        {busy ? 'The agent is working...' : 'Run the intake'}
      </button>
    </form>
  );
}
