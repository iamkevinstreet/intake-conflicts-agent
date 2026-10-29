// ########################################################################
// #                      frontend/src/globals.d.ts                       #
// ########################################################################
/**
 * Author:            Kevin Street
 * Created on:        2026-10-29
 * Last modified on:  2026-10-29
 *
 * Declares the globals every module may use: the trace logger, the keys
 * of config/config.toml the build passes to the browser, and the one
 * build variable the app reads.
 */

// ########################################################################
// #                         Global declarations                          #
// ########################################################################
declare const log: { debug(message: string): void };

/** The keys of config/config.toml the browser needs, as vite.config.ts reads them. */
interface BrowserConfig {
  readonly api: {
    readonly prefix: string;
    readonly request_id_header: string;
    readonly min_reason_chars: number;
    readonly max_note_chars: number;
  };
  readonly agent: {
    readonly min_email_chars: number;
    readonly max_email_chars: number;
  };
  readonly match: {
    readonly possible: number;
    readonly likely: number;
  };
  readonly units: {
    readonly ms_per_second: number;
  };
}

declare const __CONFIG__: BrowserConfig;

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
}
