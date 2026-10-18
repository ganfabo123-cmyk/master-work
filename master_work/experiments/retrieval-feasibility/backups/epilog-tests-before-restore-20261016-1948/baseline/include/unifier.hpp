/*
 * unifier.hpp — Robinson unification for the Epilog inference engine.
 * JPL rules: no recursion, bounded work stack, no post-init malloc.
 */

#pragma once

#include <cstdint>
#include "terms.hpp"
#include "variables.hpp"

constexpr uint32_t TRAIL_CAPACITY       = 4096U;
constexpr uint32_t UNIFY_STACK_CAPACITY = 512U;

struct Trail {
    VarId    bound[TRAIL_CAPACITY] = {};
    uint32_t top = 0U;
};

int      trail_init(Trail *t);
uint32_t trail_mark(const Trail *t);
void     trail_undo(Trail *t, VarRegistry *vars, uint32_t mark);

/* unify — iterative Robinson unification. Returns 1 on success, 0 on failure. */
int     unify(TermRef a, TermRef b,
              const TermArena *arena, VarRegistry *vars, Trail *trail);

/* deref — follow variable binding chain to the canonical root TermRef. */
TermRef deref(TermRef ref, const TermArena *arena, const VarRegistry *vars);
