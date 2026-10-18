/*
 * terms.hpp — Term representation for the Epilog inference engine.
 *
 * A Term is: Atom | Var | Compound | Int.
 * All terms live in a TermArena (fixed-size, no post-init malloc).
 * TermRef is a 1-based index; 0 == TERM_REF_INVALID.
 *
 * JPL rules: no post-init malloc, bounded loops, no recursion, pointer depth ≤ 1.
 */

#pragma once

#include <cstdint>
#include <cstddef>
#include "atoms.hpp"
#include "variables.hpp"

constexpr uint32_t TERM_ARENA_CAPACITY = 8192U;
constexpr uint32_t ARG_POOL_CAPACITY   = 32768U;
constexpr uint8_t  TERM_MAX_ARITY      = 255U;

enum TermKind : uint8_t {
    TERM_KIND_ATOM     = 1,
    TERM_KIND_VAR      = 2,
    TERM_KIND_COMPOUND = 3,
    TERM_KIND_INT      = 4
};

struct Term {
    TermKind kind = TERM_KIND_ATOM;
    union {
        AtomId  atom_id;
        int32_t int_val;
        struct { VarId var_id; char name[VAR_NAME_MAX_LEN + 1U]; } var;
        struct { AtomId functor; uint8_t arity; uint32_t arg_start; } compound;
    } data = {};
    TermRef ref = TERM_REF_INVALID;
};

struct ArgPool {
    TermRef  slots[ARG_POOL_CAPACITY];
    uint32_t count = 0U;
};

struct TermArena {
    Term     nodes[TERM_ARENA_CAPACITY];
    uint32_t count = 0U;
    ArgPool  args;
};

int      term_arena_init(TermArena *a);
TermRef  term_make_atom(TermArena *a, AtomId id);
TermRef  term_make_var(TermArena *a, VarId id, const char *name);
TermRef  term_make_int(TermArena *a, int32_t val);
TermRef  term_make_compound(TermArena *a, AtomId functor, uint8_t arity,
                             const TermRef *args);
const Term *term_get(const TermArena *a, TermRef ref);
TermRef  term_arg(const TermArena *a, TermRef ref, uint8_t n);
TermKind term_kind(const TermArena *a, TermRef ref);
