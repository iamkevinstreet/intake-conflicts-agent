// ########################################################################
// #                      frontend/src/globals.d.ts                       #
// ########################################################################
// #  Author:            Kevin Street                                     #
// #  Created on:        2026-10-29                                       #
// #  Last modified on:  2026-10-29                                       #
// #  Purpose:           Declares the global trace logger and the one     #
// #                     build setting the app reads.                     #
// ########################################################################
/** Globals: the trace logger every module may call, and our build settings. */

declare const log: { debug(message: string): void };

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
}
