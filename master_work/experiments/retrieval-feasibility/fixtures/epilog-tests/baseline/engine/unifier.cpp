/*
 * unifier.cpp — Robinson unification, iterative implementation.
 * JPL rules: no recursion, bounded work stack, no post-init malloc.
 */

#include "../include/unifier.hpp"
#include <cstring>
#include <cassert>

/* ---- Trail ---------------------------------------------------------------- */

int trail_init(Trail *t)
{
    if (t == nullptr) { return -1; }
    memset(t, 0, sizeof(Trail));
    return 0;
}

uint32_t trail_mark(const Trail *t)
{
    assert(t != nullptr);
    return t->top;
}

void trail_undo(Trail *t, VarRegistry *vars, uint32_t mark)
{
    assert(t != nullptr && vars != nullptr);
    while (t->top > mark) {
        const VarId vid = t->bound[t->top - 1U];
        if (vid != VAR_ID_INVALID) {
            const uint32_t idx = vid - VAR_ID_MIN;
            if (idx < vars->count) {
                VarEntry *e         = &vars->entries[idx];
                e->tag              = TERM_UNBOUND;
                e->value.var_id     = VAR_ID_INVALID;
            }
        }
        t->top--;
    }
}

/* ---- deref ---------------------------------------------------------------- */

TermRef deref(TermRef ref, const TermArena *arena, const VarRegistry *vars)
{
    if (ref == TERM_REF_INVALID) { return TERM_REF_INVALID; }

    for (uint32_t steps = 0U; steps < VAR_REGISTRY_CAPACITY; ++steps) {
        const Term *t = term_get(arena, ref);
        if (t == nullptr) { return TERM_REF_INVALID; }
        if (t->kind != TERM_KIND_VAR) { return ref; }

        const WalkResult wr = var_walk(vars, t->data.var.var_id);
        if (wr.tag == TERM_UNBOUND)  { return ref; }
        if (wr.tag == TERM_TERMREF)  { ref = wr.value.term_ref; continue; }
        if (wr.tag == TERM_VAR) {
            for (uint32_t ni = 0U; ni < arena->count; ++ni) {
                const Term *cand = &arena->nodes[ni];
                if (cand->kind == TERM_KIND_VAR &&
                    cand->data.var.var_id == wr.root_id) {
                    ref = cand->ref;
                    break;
                }
            }
        }
    }
    return ref;
}

/* ---- bind_var ------------------------------------------------------------- */

static int bind_var(VarId vid, TermRef target_ref, const TermArena *arena,
                    VarRegistry *vars, Trail *trail)
{
    assert(vars != nullptr && trail != nullptr && arena != nullptr);
    if (trail->top >= TRAIL_CAPACITY) { return -1; }

    const Term *target = term_get(arena, target_ref);
    if (target == nullptr) { return -1; }

    if (target->kind == TERM_KIND_VAR) {
        if (var_bind_var(vars, vid, target->data.var.var_id) < 0) { return -1; }
    } else {
        if (var_bind_term(vars, vid, target_ref) < 0) { return -1; }
    }

    trail->bound[trail->top] = vid;
    trail->top++;
    return 0;
}

/* ---- unify ---------------------------------------------------------------- */

struct UnifyPair { TermRef a; TermRef b; };

int unify(TermRef a, TermRef b,
          const TermArena *arena, VarRegistry *vars, Trail *trail)
{
    UnifyPair stack[UNIFY_STACK_CAPACITY];
    uint32_t  top = 0U;

    if (arena == nullptr || vars == nullptr || trail == nullptr) { return 0; }

    stack[top++] = { a, b };

    for (uint32_t steps = 0U; steps < UNIFY_STACK_CAPACITY && top > 0U; ++steps) {
        const TermRef ra = deref(stack[--top].a, arena, vars);
        const TermRef rb = deref(stack[top].b,   arena, vars);

        if (ra == rb) { continue; }

        const Term *ta = term_get(arena, ra);
        const Term *tb = term_get(arena, rb);
        if (ta == nullptr || tb == nullptr) { return 0; }

        if (ta->kind == TERM_KIND_VAR) {
            if (bind_var(ta->data.var.var_id, rb, arena, vars, trail) < 0) { return 0; }
            continue;
        }
        if (tb->kind == TERM_KIND_VAR) {
            if (bind_var(tb->data.var.var_id, ra, arena, vars, trail) < 0) { return 0; }
            continue;
        }

        if (ta->kind == TERM_KIND_ATOM && tb->kind == TERM_KIND_ATOM) {
            if (ta->data.atom_id != tb->data.atom_id) { return 0; }
            continue;
        }
        if (ta->kind == TERM_KIND_INT && tb->kind == TERM_KIND_INT) {
            if (ta->data.int_val != tb->data.int_val) { return 0; }
            continue;
        }
        if (ta->kind == TERM_KIND_COMPOUND && tb->kind == TERM_KIND_COMPOUND) {
            const uint8_t arity = ta->data.compound.arity;
            if (ta->data.compound.functor != tb->data.compound.functor) { return 0; }
            if (arity != tb->data.compound.arity) { return 0; }
            if (top + static_cast<uint32_t>(arity) >= UNIFY_STACK_CAPACITY) { return 0; }
            for (uint8_t i = 0U; i < arity; ++i) {
                stack[top++] = { term_arg(arena, ra, i), term_arg(arena, rb, i) };
            }
            continue;
        }
        return 0;
    }

    return (top == 0U) ? 1 : 0;
}
