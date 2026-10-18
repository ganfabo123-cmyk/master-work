/*
 * atoms.cpp — Atom table implementation.
 * JPL rules: no recursion, bounded loops, no post-init malloc.
 */

#include "../include/atoms.hpp"

#include <cassert>
#include <cstring>
#include <cstdint>

static uint32_t fnv1a_32(const char *s)
{
    uint32_t hash = 2166136261U;
    uint32_t i;
    assert(s != nullptr);
    for (i = 0U; i < ATOM_MAX_LEN + 1U && s[i] != '\0'; ++i) {
        hash ^= static_cast<uint32_t>(static_cast<unsigned char>(s[i]));
        hash *= 16777619U;
    }
    return hash;
}

static uint32_t probe_slot(const AtomTable *t, const char *spelling,
                            uint32_t hash, int *found)
{
    uint32_t idx  = hash % ATOM_TABLE_CAPACITY;
    uint32_t step = 0U;

    assert(t != nullptr && spelling != nullptr && found != nullptr);
    *found = 0;

    for (step = 0U; step < ATOM_TABLE_CAPACITY; ++step) {
        const Atom *slot = &t->slots[idx];
        if (slot->id == ATOM_ID_INVALID) { return idx; }
        if (slot->hash == hash &&
            strncmp(slot->spelling, spelling, ATOM_MAX_LEN) == 0) {
            *found = 1;
            return idx;
        }
        idx = (idx + 1U) % ATOM_TABLE_CAPACITY;
    }
    return ATOM_TABLE_CAPACITY;
}

int atom_table_init(AtomTable *t)
{
    if (t == nullptr) { return -1; }
    memset(t, 0, sizeof(AtomTable));
    return 0;
}

AtomId atom_intern(AtomTable *t, const char *spelling)
{
    if (t == nullptr || spelling == nullptr) { return ATOM_ID_INVALID; }

    const size_t len = strnlen(spelling, ATOM_MAX_LEN + 1U);
    if (len > ATOM_MAX_LEN) { return ATOM_ID_INVALID; }

    const uint32_t hash = fnv1a_32(spelling);
    int found;
    const uint32_t idx = probe_slot(t, spelling, hash, &found);

    if (idx == ATOM_TABLE_CAPACITY) { return ATOM_ID_INVALID; }
    if (found) { return t->slots[idx].id; }

    assert(t->count < ATOM_TABLE_CAPACITY);
    Atom *slot = &t->slots[idx];
    memcpy(slot->spelling, spelling, len);
    slot->spelling[len] = '\0';
    slot->hash = hash;
    slot->id   = static_cast<AtomId>(t->count + ATOM_ID_MIN);
    t->count++;
    return slot->id;
}

AtomId atom_lookup(const AtomTable *t, const char *spelling)
{
    if (t == nullptr || spelling == nullptr) { return ATOM_ID_INVALID; }

    const size_t len = strnlen(spelling, ATOM_MAX_LEN + 1U);
    if (len > ATOM_MAX_LEN) { return ATOM_ID_INVALID; }

    const uint32_t hash = fnv1a_32(spelling);
    int found;
    const uint32_t idx = probe_slot(t, spelling, hash, &found);

    if (!found || idx == ATOM_TABLE_CAPACITY) { return ATOM_ID_INVALID; }
    return t->slots[idx].id;
}

const char *atom_spelling(const AtomTable *t, AtomId id)
{
    if (t == nullptr || id == ATOM_ID_INVALID) { return nullptr; }
    for (uint32_t i = 0U; i < ATOM_TABLE_CAPACITY; ++i) {
        if (t->slots[i].id == id) { return t->slots[i].spelling; }
    }
    return nullptr;
}

uint32_t atom_count(const AtomTable *t)
{
    if (t == nullptr) { return 0U; }
    return t->count;
}
