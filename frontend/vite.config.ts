// ########################################################################
// #                       frontend/vite.config.ts                        #
// ########################################################################
/**
 * Author:            Kevin Street
 * Created on:        2026-10-29
 * Last modified on:  2026-10-29
 *
 * Sets the build, dev-server and test settings: React, the API proxy,
 * and jsdom for tests. It reads config/config.toml when the build
 * starts and passes the browser only the keys it needs, as __CONFIG__;
 * nothing from config/.env is read. The dev server proxies the API's
 * path to the address the backend listens on.
 */

// ########################################################################
// #                               Imports                                #
// ########################################################################
// Standard library
import { readFileSync } from 'node:fs';

// Third-party
import react from '@vitejs/plugin-react';
import { parse } from 'smol-toml';
import { defineConfig } from 'vitest/config';

// Local
import { required } from './src/lib/required.ts';

// ########################################################################
// #                           Local constants                            #
// ########################################################################
// log.debug('Sets the file every setting and shared value comes from')
const CONFIG_FILE = new URL('../config/config.toml', import.meta.url);
// log.debug('Reads the file once, when the build starts')
const SETTINGS = parse(readFileSync(CONFIG_FILE, 'utf8'));
// log.debug('Sets the port the dev server listens on, which [api] allowed_origins names')
const DEV_PORT = 5173;

// ########################################################################
// #                            Build settings                            #
// ########################################################################
// log.debug('Defines how one value is found in the config file')
/**
 * Returns a value of config/config.toml, whatever its type.
 *
 * @param table - The table the value is in, such as api. Required.
 * @param key - The value's key in the table. Required.
 * @returns The value, or undefined when the file has none there.
 */
function lookup(table: string | null = null, key: string | null = null): unknown {
  // log.debug('Takes the table, which the caller must give')
  table = required({ table });
  // log.debug('Takes the key, which the caller must give')
  key = required({ key });
  // log.debug('Reads the table')
  const section: unknown = SETTINGS[table];
  // log.debug('Returns the value when the table is one, else nothing')
  return typeof section === 'object' && section !== null
    ? (section as Record<string, unknown>)[key]
    : undefined;
}

// log.debug('Defines how a text value is read from the config file')
/**
 * Returns a text value of config/config.toml.
 *
 * @param table - The table the value is in, such as api. Required.
 * @param key - The value's key in the table. Required.
 * @returns The value.
 * @throws {TypeError} When the file has no text value there.
 */
function text(table: string | null = null, key: string | null = null): string {
  // log.debug('Takes the table, which the caller must give')
  table = required({ table });
  // log.debug('Takes the key, which the caller must give')
  key = required({ key });
  // log.debug('Finds the value')
  const found = lookup(table, key);
  // log.debug('Stops the build when it is not text')
  if (typeof found !== 'string') {
    // log.debug('Throws, naming the setting')
    throw new TypeError(`config/config.toml needs [${table}] ${key} as text`);
  }
  // log.debug('Returns it')
  return found;
}

// log.debug('Defines how a whole number is read from the config file')
/**
 * Returns a whole number of config/config.toml.
 *
 * @param table - The table the value is in, such as api. Required.
 * @param key - The value's key in the table. Required.
 * @returns The value.
 * @throws {TypeError} When the file has no whole number there.
 */
function whole(table: string | null = null, key: string | null = null): number {
  // log.debug('Takes the table, which the caller must give')
  table = required({ table });
  // log.debug('Takes the key, which the caller must give')
  key = required({ key });
  // log.debug('Finds the value')
  const found = lookup(table, key);
  // log.debug('Stops the build when it is not a whole number')
  if (typeof found !== 'number' || !Number.isInteger(found)) {
    // log.debug('Throws, naming the setting')
    throw new TypeError(`config/config.toml needs [${table}] ${key} as a whole number`);
  }
  // log.debug('Returns it')
  return found;
}

// log.debug('Reads the keys of the config file the browser needs, and nothing else')
const browserConfig: BrowserConfig = {
  api: {
    prefix: text('api', 'prefix'),
    request_id_header: text('api', 'request_id_header'),
    min_reason_chars: whole('api', 'min_reason_chars'),
    max_note_chars: whole('api', 'max_note_chars'),
  },
  agent: {
    min_email_chars: whole('agent', 'min_email_chars'),
    max_email_chars: whole('agent', 'max_email_chars'),
  },
  match: { possible: whole('match', 'possible'), likely: whole('match', 'likely') },
  units: { ms_per_second: whole('units', 'ms_per_second') },
};

// log.debug('Exports the build, dev-server and test settings')
export default defineConfig({
  plugins: [react()],
  define: { __CONFIG__: JSON.stringify(browserConfig) },
  server: {
    port: DEV_PORT,
    strictPort: true,
    proxy: {
      [browserConfig.api.prefix]: {
        target: `http://${text('api', 'host')}:${String(whole('api', 'port'))}`,
        changeOrigin: false,
      },
    },
  },
  build: { outDir: 'dist', emptyOutDir: true, sourcemap: false },
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.test.{ts,tsx}'],
  },
});
