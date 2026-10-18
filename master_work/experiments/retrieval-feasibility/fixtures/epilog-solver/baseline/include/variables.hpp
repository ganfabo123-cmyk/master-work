/*
 * variables.hpp — Logic variable registry for the Epilog inference engine.
 *
 * Variables are identified by VarId scoped to a VarRegistry that lives for
 * one query. Bindings are stored as TERM_ATOM, TERM_VAR, or TERM_TERMREF
 * tags so the unifier can follow chains without C-stack recursion.
 *
 * JPL rules: no post-init malloc, bounded loops, no recursion, pointer depth ≤ 1.
 */

#pragma once

#include <cstddef>
#include <cstdint>
#include "atoms.hpp"

constexpr uint32_t VAR_REGISTRY_CAPACITY = 1024U;
constexpr uint32_t VAR_NAME_MAX_LEN      = 63U;

using VarId   = uint32_t;
using TermRef = uint32_t;   /* opaque index into a TermArena */

constexpr VarId   VAR_ID_INVALID  = 0U;
constexpr VarId   VAR_ID_MIN      = 1U;
constexpr TermRef TERM_REF_INVALID = 0U;

enum TermTag : uint8_t {
    TERM_UNBOUND  = 0,
    TERM_ATOM     = 1,
    TERM_VAR      = 2,
    TERM_TERMREF  = 3
};

union BindingValue {
    AtomId  atom_id;
    VarId   var_id;
    TermRef term_ref;
};

struct VarEntry {
    char         name[VAR_NAME_MAX_LEN + 1U];
    TermTag      tag   = TERM_UNBOUND;
    BindingValue value = {};
    VarId        id    = VAR_ID_INVALID;
};

struct VarRegistry {
    VarEntry entries[VAR_REGISTRY_CAPACITY];
    uint32_t count = 0U;
};

struct WalkResult {
    TermTag      tag      = TERM_UNBOUND;
    BindingValue value    = {};
    VarId        root_id  = VAR_ID_INVALID;
};

int      var_registry_init(VarRegistry *r);
VarId    var_alloc(VarRegistry *r, const char *name);
int      var_bind_atom(VarRegistry *r, VarId id, AtomId atom_id);
int      var_bind_var(VarRegistry *r, VarId id, VarId other_id);
int      var_bind_term(VarRegistry *r, VarId id, TermRef ref);
WalkResult var_walk(const VarRegistry *r, VarId id);
int      var_reset(VarRegistry *r);
uint32_t var_count(const VarRegistry *r);
