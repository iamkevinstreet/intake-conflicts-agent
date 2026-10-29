// ########################################################################
// #                          frontend/node.d.ts                          #
// ########################################################################
/**
 * Author:            Kevin Street
 * Created on:        2026-10-29
 * Last modified on:  2026-10-29
 *
 * Declares the one Node function vite.config.ts uses to read
 * config/config.toml, so the rest of the frontend is still checked
 * against the browser's globals alone.
 */

// ########################################################################
// #                          Node declarations                           #
// ########################################################################
declare module 'node:fs' {
  /**
   * Reads a whole file as text, as Node's readFileSync does.
   *
   * @param path - The file's address.
   * @param encoding - The text's encoding.
   * @returns The file's text.
   */
  export function readFileSync(path: URL, encoding: 'utf8'): string;
}
