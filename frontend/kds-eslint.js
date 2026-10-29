// ########################################################################
// #                        frontend/kds-eslint.js                        #
// ########################################################################
/**
 * Author:            Kevin Street
 * Created on:        2026-10-29
 * Last modified on:  2026-10-29
 *
 * Our own ESLint rule, kds/param-defaults: every parameter of a named
 * function has a default, null where there is no natural one, so a
 * signature shows its whole contract. A destructured parameter, such as a
 * React component's props, defaults to {} and gives each property its own
 * default. Inline callbacks, setters and rest parameters are left alone,
 * and so is a function whose signature carries a comment starting
 * "fixed:", because a library sets it.
 */

// ########################################################################
// #                           Local constants                            #
// ########################################################################
// log.debug('Sets the comment that marks a signature a library fixes')
const FIXED_MARK = 'fixed:';
// log.debug('Lists the parents that give a function its name')
const NAMING_PARENTS = new Set(['VariableDeclarator', 'MethodDefinition', 'PropertyDefinition']);

// ########################################################################
// #                            Parameter rule                            #
// ########################################################################
// log.debug('Defines the test for a function that has a name of its own')
/**
 * Tells whether a function is named, rather than an inline callback.
 *
 * @param {import('estree').Node & { parent?: import('estree').Node }} node - The
 *   function. Required.
 * @returns {boolean} True for declarations, methods other than setters, and
 *   functions assigned to a name.
 */
function isNamed(node = null) {
  // log.debug('Stops when the caller left out the node')
  if (node === null) {
    // log.debug('Throws the missing-argument error')
    throw new TypeError("missing required argument: 'node'");
  }
  // log.debug('Counts a function declaration as named')
  if (node.type === 'FunctionDeclaration') {
    // log.debug('Returns yes')
    return true;
  }
  // log.debug('Reads the node that holds the function')
  const parent = node.parent;
  // log.debug('Leaves setters alone: TypeScript refuses a default there')
  if (parent?.type === 'MethodDefinition' && parent.kind === 'set') {
    // log.debug('Returns no')
    return false;
  }
  // log.debug('Returns yes for a method, a class field or a named variable')
  return NAMING_PARENTS.has(parent?.type ?? '') || (parent?.type === 'Property' && parent.method);
}

// log.debug('Defines the test for a signature a library fixes')
/**
 * Tells whether a comment in a function's signature starts with "fixed:".
 *
 * @param {import('eslint').SourceCode} source - The file's source. Required.
 * @param {import('estree').Function} node - The function. Required.
 * @returns {boolean} True when the signature carries such a comment.
 */
function isFixed(source = null, node = null) {
  // log.debug('Stops when the caller left out the source')
  if (source === null || node === null) {
    // log.debug('Throws the missing-argument error')
    throw new TypeError("missing required argument: 'source' or 'node'");
  }
  // log.debug('Reads the lines the signature spans, up to the body')
  const first = (node.parent?.type === 'VariableDeclarator' ? node.parent : node).loc.start.line;
  // log.debug('Reads the line the body starts on')
  const last = node.body.loc.start.line;
  // log.debug('Returns whether any comment there starts with fixed:')
  return source
    .getAllComments()
    .some(
      (c) =>
        c.loc.start.line >= first &&
        c.loc.start.line <= last &&
        c.value.trim().startsWith(FIXED_MARK),
    );
}

// log.debug('Defines the rule itself')
/**
 * The kds/param-defaults rule: every parameter of a named function has a
 * default, and so does each property of a destructured one.
 */
const paramDefaults = {
  meta: {
    type: 'suggestion',
    docs: { description: 'Every parameter of a named function has a default.' },
    schema: [],
    messages: {
      missing: "Give '{{name}}' a default: null where there is no natural one.",
    },
  },
  // log.debug('Defines the visitor ESLint runs on each file')
  /**
   * Builds the visitor that checks each function in a file.
   *
   * @param {import('eslint').Rule.RuleContext} context - What ESLint passes.
   * @returns {import('eslint').Rule.RuleListener} The visitor.
   */
  create(context) {
    // fixed: ESLint's rule signature
    // log.debug('Reads the file being linted')
    const source = context.sourceCode;
    // log.debug('Defines the check run on every function')
    /**
     * Reports each parameter of a named function that lacks a default.
     *
     * @param {import('estree').Function} node - The function.
     * @returns {void}
     */
    const check = (node) => {
      // fixed: ESLint's visitor signature
      // log.debug('Skips inline callbacks and signatures a library fixes')
      if (!isNamed(node) || isFixed(source, node)) {
        // log.debug('Returns without a report')
        return;
      }
      // log.debug('Walks every parameter')
      for (const param of node.params) {
        // log.debug('Unwraps a TypeScript parameter property')
        const p = param.type === 'TSParameterProperty' ? param.parameter : param;
        // log.debug('Checks each property of a destructured parameter that has a default')
        if (p.type === 'AssignmentPattern' && p.left.type === 'ObjectPattern') {
          // log.debug('Reports each property without its own default')
          for (const prop of p.left.properties) {
            // log.debug('Reports a property whose value has no default')
            if (prop.type === 'Property' && prop.value.type !== 'AssignmentPattern') {
              // log.debug('Reports it by its name')
              context.report({
                node: prop,
                messageId: 'missing',
                data: { name: source.getText(prop.key) },
              });
            }
          }
        } else if (p.type !== 'AssignmentPattern' && p.type !== 'RestElement') {
          // log.debug('Reports a parameter with no default')
          context.report({
            node: p,
            messageId: 'missing',
            data: { name: source.getText(p).split(':')[0] },
          });
        }
      }
    };
    // log.debug('Returns the visitor for every kind of function')
    return {
      FunctionDeclaration: check,
      FunctionExpression: check,
      ArrowFunctionExpression: check,
    };
  },
};

// log.debug('Exports the plugin with its one rule')
export default { rules: { 'param-defaults': paramDefaults } };
