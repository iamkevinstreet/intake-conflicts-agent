// ########################################################################
// #                frontend/src/components/EmailForm.tsx                 #
// ########################################################################
/**
 * Author:            Kevin Street
 * Created on:        2026-10-29
 * Last modified on:  2026-10-29
 *
 * Shows the intake form: paste an email or try a made-up example,
 * within the length limits.
 */

// ########################################################################
// #                               Imports                                #
// ########################################################################
// Third-party
import { useState } from 'react';

// Local
import { CONFIG } from '../config';
import { required } from '../lib/required';
import type { Example } from '../types';

// ########################################################################
// #                           Global constants                           #
// ########################################################################
// log.debug('Takes the shortest email the API accepts, from the config')
const MIN_EMAIL_CHARS = CONFIG.agent.min_email_chars;
// log.debug('Takes the longest email the API accepts, from the config')
const MAX_EMAIL_CHARS = CONFIG.agent.max_email_chars;

// ########################################################################
// #                             Intake form                              #
// ########################################################################
interface Props {
  examples?: Example[];
  busy?: boolean;
  onSubmit?: ((email: string) => void) | null;
}

// log.debug('Defines the form')
/**
 * Shows the email box, the made-up examples and the button that runs
 * the intake.
 *
 * @param props - The form's props.
 * @param props.examples - The made-up emails to offer; none hides them.
 * @param props.busy - Whether an intake is running.
 * @param props.onSubmit - Runs the intake on the email. Required.
 * @returns The form.
 */
export function EmailForm({
  examples = [],
  busy = false,
  onSubmit = null,
}: Props = {}): React.JSX.Element {
  // log.debug('Takes the submit handler, which the caller must give')
  onSubmit = required({ onSubmit });
  // log.debug('Keeps the email being written')
  const [email, setEmail] = useState('');
  // log.debug('Measures it without surrounding space')
  const length = email.trim().length;
  // log.debug('Allows a run only within the limits and when not already running')
  const ready = !busy && length >= MIN_EMAIL_CHARS && length <= MAX_EMAIL_CHARS;

  // log.debug('Defines the submit handler')
  /**
   * Runs the intake when the email is within the limits.
   *
   * @param event - The form's submit event. Required.
   */
  const submit = (event: React.SubmitEvent<HTMLFormElement> | null = null): void => {
    // log.debug('Takes the event, which the caller must give')
    event = required({ event });
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
      {examples.length > 0 && <ExampleList examples={examples} busy={busy} onPick={setEmail} />}
      <button type="submit" className="ia-button" disabled={!ready}>
        {busy ? 'The agent is working...' : 'Run the intake'}
      </button>
    </form>
  );
}

interface ExampleProps {
  examples?: Example[];
  busy?: boolean;
  onPick?: ((email: string) => void) | null;
}

// log.debug('Defines the list of made-up examples')
/**
 * Shows the made-up examples, each a button that puts its email in the
 * box.
 *
 * @param props - The list's props.
 * @param props.examples - The made-up emails to offer.
 * @param props.busy - Whether an intake is running, which turns the
 *   buttons off.
 * @param props.onPick - Puts an example's email in the box. Required.
 * @returns The list.
 */
function ExampleList({
  examples = [],
  busy = false,
  onPick = null,
}: ExampleProps = {}): React.JSX.Element {
  // log.debug('Takes the pick handler, which the caller must give')
  onPick = required({ onPick });
  // log.debug('Returns a button for each example')
  return (
    <div className="ia-form__examples">
      <p className="ia-form__examples-title">Or try a made-up example:</p>
      <ul>
        {examples.map((example) => (
          <li key={example.id}>
            <button
              type="button"
              className="ia-chip"
              onClick={() => onPick(example.email)}
              disabled={busy}
            >
              {example.title}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
