// ########################################################################
// #                     frontend/src/lib/required.ts                     #
// ########################################################################
/**
 * Author:            Kevin Street
 * Created on:        2026-10-29
 * Last modified on:  2026-10-29
 *
 * Takes a function's arguments the way the code standard asks. Every
 * parameter has a default, null where there is no natural one, so a
 * function that cannot work without a value takes it with required(): it
 * returns the value when the caller gave it, and throws a TypeError
 * naming the argument when the caller left it out. TypeScript then sees
 * the value without null.
 */

// ########################################################################
// #                          Required arguments                          #
// ########################################################################
// log.debug('Defines the step that takes an argument the caller must give')
/**
 * Returns an argument's value, or stops when the caller left it out.
 *
 * @param argument - Exactly one argument, by name: required({ runs }).
 * @returns The argument's value, which is never null or undefined.
 * @throws {TypeError} When the value is null or undefined, or when the
 *   call does not pass exactly one argument.
 */
export function required<T>(argument: Readonly<Record<string, T | null | undefined>> = {}): T {
  // log.debug('Reads the names of the arguments passed')
  const names = Object.keys(argument);
  // log.debug('Takes the one name, if exactly one was passed')
  const name = names.length === 1 ? names[0] : undefined;
  // log.debug('Stops unless exactly one argument was passed, by name')
  if (name === undefined) {
    // log.debug('Throws the error for a call with no argument or several')
    throw new TypeError('required() takes exactly one argument, by name');
  }
  // log.debug('Reads the argument value')
  const value = argument[name];
  // log.debug('Stops when the caller left the argument out')
  if (value === null || value === undefined) {
    // log.debug('Throws the same error a missing argument raises in Python')
    throw new TypeError(`missing required argument: '${name}'`);
  }
  // log.debug('Returns the value, which is never null or undefined')
  return value;
}
