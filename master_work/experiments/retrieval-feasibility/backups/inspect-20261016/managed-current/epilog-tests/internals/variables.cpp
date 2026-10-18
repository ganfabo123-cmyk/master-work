/*
 * variables.cpp — Logic variable registry implementation.
 * JPL rules: no recursion, bounded loops, no post-init malloc.
 */

#include "../include/variables.hpp"

#include <cassert>
#include <cstring>

static VarEntry *entry_at(VarRegistry *r, VarId id)
{
    assert(r != nullptr);
    if (id == VAR_ID_INVALID || id < VAR_ID_MIN) { return nullptr; }
    const uint32_t idx = id - VAR_ID_MIN;
    if (idx >= VAR_REGISTRY_CAPACITY || idx >= r->count) { return nullptr; }
    return &r->entries[idx];
}

static const VarEntry *entry_at_c(const VarRegistry *r, VarId id)
{
    assert(r != nullptr);
    if (id == VAR_ID_INVALID || id < VAR_ID_MIN) { return nullptr; }
    const uint32_t idx = id - VAR_ID_MIN;
    if (idx >= VAR_REGISTRY_CAPACITY || idx >= r->count) { return nullptr; }
    return &r->entries[idx];
}

int var_registry_init(VarRegistry *r)
{
    if (r == nullptr) { return -1; }
    memset(r, 0, sizeof(VarRegistry));
    return 0;
}

VarId var_alloc(VarRegistry *r, const char *name)
{
    if (r == nullptr || name == nullptr) { return VAR_ID_INVALID; }
    if (r->count >= VAR_REGISTRY_CAPACITY) { return VAR_ID_INVALID; }

    const size_t len = strnlen(name, VAR_NAME_MAX_LEN + 1U);
    if (len > VAR_NAME_MAX_LEN) { return VAR_ID_INVALID; }

    const VarId new_id = static_cast<VarId>(r->count + VAR_ID_MIN);
    VarEntry *slot = &r->entries[r->count];
    memset(slot, 0, sizeof(VarEntry));
    memcpy(slot->name, name, len);
    slot->name[len] = '\0';
    slot->tag = TERM_UNBOUND;
    slot->id  = new_id;
    r->count++;
    return new_id;
}

int var_bind_atom(VarRegistry *r, VarId id, AtomId atom_id)
{
    if (r == nullptr || atom_id == ATOM_ID_INVALID) { return -1; }
    VarEntry *e = entry_at(r, id);
    if (e == nullptr || e->tag != TERM_UNBOUND) { return -1; }
    e->tag          = TERM_ATOM;
    e->value.atom_id = atom_id;
    return 0;
}

int var_bind_var(VarRegistry *r, VarId id, VarId other_id)
{
    if (r == nullptr) { return -1; }
    if (id == other_id) { return 0; }
    VarEntry *e = entry_at(r, id);
    if (e == nullptr) { return -1; }
    if (entry_at(r, other_id) == nullptr) { return -1; }
    if (e->tag != TERM_UNBOUND) { return -1; }
    e->tag          = TERM_VAR;
    e->value.var_id = other_id;
    return 0;
}

int var_bind_term(VarRegistry *r, VarId id, TermRef ref)
{
    if (r == nullptr || ref == 0U) { return -1; }
    VarEntry *e = entry_at(r, id);
    if (e == nullptr || e->tag != TERM_UNBOUND) { return -1; }
    e->tag            = TERM_TERMREF;
    e->value.term_ref = ref;
    return 0;
}

WalkResult var_walk(const VarRegistry *r, VarId id)
{
    WalkResult result;
    result.tag          = TERM_UNBOUND;
    result.value.var_id = VAR_ID_INVALID;
    result.root_id      = VAR_ID_INVALID;

    if (r == nullptr || id == VAR_ID_INVALID) { return result; }

    VarId current = id;
    for (uint32_t steps = 0U; steps < VAR_REGISTRY_CAPACITY; ++steps) {
        const VarEntry *e = entry_at_c(r, current);
        if (e == nullptr) { return result; }
        if (e->tag != TERM_VAR) {
            result.tag      = e->tag;
            result.value    = e->value;
            result.root_id  = current;
            return result;
        }
        current = e->value.var_id;
    }
    assert(false);
    return result;
}

int var_reset(VarRegistry *r)
{
    if (r == nullptr) { return -1; }
    memset(r, 0, sizeof(VarRegistry));
    return 0;
}

uint32_t var_count(const VarRegistry *r)
{
    if (r == nullptr) { return 0U; }
    return r->count;
}
