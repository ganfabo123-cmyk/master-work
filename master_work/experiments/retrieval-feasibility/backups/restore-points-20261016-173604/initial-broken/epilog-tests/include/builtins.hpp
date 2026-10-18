/*
 * builtins.hpp — Built-in predicate dispatch for Epilog 0.1.
 * JPL rules: no recursion, bounded dispatch table, no post-init malloc.
 */

#pragma once

#include <cstdint>
#include "terms.hpp"
#include "atoms.hpp"
#include "variables.hpp"
#include "unifier.hpp"
#include "database.hpp"
#include "solver.hpp"

enum BuiltinResult : uint8_t {
    BUILTIN_SUCCEED = 0,
    BUILTIN_FAIL    = 1,
    BUILTIN_CUT     = 2,
    BUILTIN_ERROR   = 3
};

using BuiltinFn = BuiltinResult (*)(TermRef goal, SolverEnv *env);

/* builtin_lookup — return fn for functor/arity, or nullptr. */
BuiltinFn builtin_lookup(AtomId functor, uint8_t arity, const AtomTable *atoms);

/* term_write — print term to stdout in Prolog notation. Returns 0 or -1. */
int term_write(TermRef ref, const TermArena *arena,
               const VarRegistry *vars, const AtomTable *atoms);
