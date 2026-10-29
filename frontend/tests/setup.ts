// ########################################################################
// #                       frontend/tests/setup.ts                        #
// ########################################################################
// #  Author:            Kevin Street                                     #
// #  Created on:        2026-10-29                                       #
// #  Last modified on:  2026-10-29                                       #
// #  Purpose:           Test setup: DOM matchers, the trace logger, and  #
// #                     a clean page after every test.                   #
// ########################################################################
/** Test setup: DOM matchers, the global logger, and a clean page per test. */

import '@testing-library/jest-dom/vitest';
import '../src/log';

import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

// log.debug('Removes rendered pages and restores stubbed functions after each test')
afterEach(() => {
  // log.debug('Unmounts whatever the test rendered')
  cleanup();
  // log.debug('Restores any function a test replaced')
  vi.restoreAllMocks();
});
