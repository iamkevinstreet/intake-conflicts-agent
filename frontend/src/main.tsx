// ########################################################################
// #                        frontend/src/main.tsx                         #
// ########################################################################
/**
 * Author:            Kevin Street
 * Created on:        2026-10-29
 * Last modified on:  2026-10-29
 *
 * Starts the web app: the fonts, the styles and the trace logger, then
 * the app in strict mode.
 */

// ########################################################################
// #                               Imports                                #
// ########################################################################
// Third-party
import '@fontsource-variable/public-sans';
import '@fontsource-variable/source-serif-4';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

// Local
import './log';
import './styles/tokens.css';
import './styles/base.css';
import './styles/intake.css';
import './styles/review.css';
import { App } from './App';

// ########################################################################
// #                              App start                               #
// ########################################################################
// log.debug('Finds the element the app renders into')
const root = document.getElementById('root');

// log.debug('Stops with a clear error when the page has no root element')
if (root === null) {
  // log.debug('Throws, since nothing can render without it')
  throw new Error('index.html needs an element with id root');
}

// log.debug('Renders the app in strict mode')
createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
