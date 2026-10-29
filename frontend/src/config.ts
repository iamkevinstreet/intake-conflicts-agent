// ########################################################################
// #                        frontend/src/config.ts                        #
// ########################################################################
/**
 * Author:            Kevin Street
 * Created on:        2026-10-29
 * Last modified on:  2026-10-29
 *
 * Holds the web app's settings, frozen: the keys of config/config.toml
 * the browser needs, which the build reads from the file, and the API's
 * address. It is the only module that reads what the build passes in or
 * its environment, and nothing from config/.env ever reaches it.
 */

// ########################################################################
// #                           Local constants                            #
// ########################################################################
// log.debug('Takes the keys of config/config.toml the build passed in')
const BUILT = __CONFIG__;
// log.debug('Builds the settings; the API address defaults to this origin, through the proxy')
export const CONFIG = Object.freeze({
  api: Object.freeze({ ...BUILT.api, base: import.meta.env.VITE_API_BASE ?? BUILT.api.prefix }),
  agent: Object.freeze({ ...BUILT.agent }),
  match: Object.freeze({ ...BUILT.match }),
  units: Object.freeze({ ...BUILT.units }),
});
