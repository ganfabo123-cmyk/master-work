/*
 * terms.cpp — Term arena implementation.
 * JPL rules: no recursion, bounded loops, no post-init malloc.
 */

#include "../include/terms.hpp"
#include <cassert>
#include <cstring>

int term_arena_init(TermArena *a)
{
    if (a == nullptr) { return -1; }
    memset(a, 0, sizeof(TermArena));
    return 0;
}

TermRef term_make_atom(TermArena *a, AtomId id)
{
    if (a == nullptr || id == ATOM_ID_INVALID) { return TERM_REF_INVALID; }
    if (a->count >= TERM_ARENA_CAPACITY) { return TERM_REF_INVALID; }

    const TermRef ref = static_cast<TermRef>(a->count + 1U);
    Term *t = &a->nodes[a->count];
    memset(t, 0, sizeof(Term));
    t->kind         = TERM_KIND_ATOM;
    t->data.atom_id = id;
    t->ref          = ref;
    a->count++;
    return ref;
}

TermRef term_make_var(TermArena *a, VarId id, const char *name)
{
    if (a == nullptr || id == VAR_ID_INVALID) { return TERM_REF_INVALID; }
    if (a->count >= TERM_ARENA_CAPACITY) { return TERM_REF_INVALID; }

    const TermRef ref = static_cast<TermRef>(a->count + 1U);
    Term *t = &a->nodes[a->count];
    memset(t, 0, sizeof(Term));
    t->kind            = TERM_KIND_VAR;
    t->data.var.var_id = id;
    if (name != nullptr) {
        const size_t nlen = strnlen(name, VAR_NAME_MAX_LEN);
        memcpy(t->data.var.name, name, nlen);
        t->data.var.name[nlen] = '\0';
    } else {
        t->data.var.name[0] = '_';
        t->data.var.name[1] = '\0';
    }
    t->ref = ref;
    a->count++;
    return ref;
}

TermRef term_make_int(TermArena *a, int32_t val)
{
    if (a == nullptr) { return TERM_REF_INVALID; }
    if (a->count >= TERM_ARENA_CAPACITY) { return TERM_REF_INVALID; }

    const TermRef ref = static_cast<TermRef>(a->count + 1U);
    Term *t = &a->nodes[a->count];
    memset(t, 0, sizeof(Term));
    t->kind         = TERM_KIND_INT;
    t->data.int_val = val;
    t->ref          = ref;
    a->count++;
    return ref;
}

TermRef term_make_compound(TermArena *a, AtomId functor, uint8_t arity,
                            const TermRef *args)
{
    if (a == nullptr || functor == ATOM_ID_INVALID) { return TERM_REF_INVALID; }
    if (arity > TERM_MAX_ARITY) { return TERM_REF_INVALID; }
    if (arity > 0U && args == nullptr) { return TERM_REF_INVALID; }
    if (a->count >= TERM_ARENA_CAPACITY) { return TERM_REF_INVALID; }
    if (a->args.count + static_cast<uint32_t>(arity) > ARG_POOL_CAPACITY) {
        return TERM_REF_INVALID;
    }

    const TermRef ref = static_cast<TermRef>(a->count + 1U);
    Term *t = &a->nodes[a->count];
    memset(t, 0, sizeof(Term));
    t->kind                    = TERM_KIND_COMPOUND;
    t->data.compound.functor   = functor;
    t->data.compound.arity     = arity;
    t->data.compound.arg_start = a->args.count;
    t->ref                     = ref;

    for (uint8_t i = 0U; i < arity; ++i) {
        assert(a->args.count < ARG_POOL_CAPACITY);
        a->args.slots[a->args.count] = args[i];
        a->args.count++;
    }

    a->count++;
    return ref;
}

const Term *term_get(const TermArena *a, TermRef ref)
{
    if (a == nullptr || ref == TERM_REF_INVALID) { return nullptr; }
    const uint32_t idx = ref - 1U;
    if (idx >= a->count) { return nullptr; }
    return &a->nodes[idx];
}

TermRef term_arg(const TermArena *a, TermRef ref, uint8_t n)
{
    const Term *t = term_get(a, ref);
    if (t == nullptr || t->kind != TERM_KIND_COMPOUND) { return TERM_REF_INVALID; }
    if (n >= t->data.compound.arity) { return TERM_REF_INVALID; }
    const uint32_t pool_idx = t->data.compound.arg_start + static_cast<uint32_t>(n);
    assert(pool_idx < ARG_POOL_CAPACITY);
    return a->args.slots[pool_idx];
}

TermKind term_kind(const TermArena *a, TermRef ref)
{
    const Term *t = term_get(a, ref);
    if (t == nullptr) { return static_cast<TermKind>(0); }
    return t->kind;
}
