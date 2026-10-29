// ########################################################################
// #                       frontend/tests/setup.ts                        #
// ########################################################################
/**
 * Author:            Kevin Street
 * Created on:        2026-10-29
 * Last modified on:  2026-10-29
 *
 * Sets up every test: the DOM matchers, the trace logger, and a clean
 * page after each one.
 */

// ########################################################################
// #                               Imports                                #
// ########################################################################
// Third-party
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

// Local
import '../src/log';

// ########################################################################
// #                              Test setup                              #
// ########################################################################
// log.debug('Removes rendered pages and restores stubbed functions after each test')
afterEach(() => {
  // log.debug('Unmounts whatever the test rendered')
  cleanup();
  // log.debug('Restores any function a test replaced')
  vi.restoreAllMocks();
});
