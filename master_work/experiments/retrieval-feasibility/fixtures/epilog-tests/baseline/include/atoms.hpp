/*
 * atoms.hpp — Atom table for the Epilog inference engine.
 *
 * An atom is an immutable, interned string. Every unique spelling maps to
 * exactly one AtomId. Comparisons are therefore O(1) integer comparisons.
 *
 * JPL rules: no post-init malloc, bounded loops, no recursion, pointer depth ≤ 1.
 */

#pragma once

#include <cstddef>
#include <cstdint>

constexpr uint32_t ATOM_TABLE_CAPACITY = 4096U;
constexpr uint32_t ATOM_MAX_LEN        = 255U;

using AtomId = uint32_t;
constexpr AtomId ATOM_ID_INVALID = 0U;
constexpr AtomId ATOM_ID_MIN     = 1U;

struct Atom {
    char     spelling[ATOM_MAX_LEN + 1U];
    uint32_t hash;
    AtomId   id;
};

struct AtomTable {
    Atom     slots[ATOM_TABLE_CAPACITY];
    uint32_t count = 0U;
};

/* atom_table_init — zero-initialise *t. Returns 0 or -1. */
int atom_table_init(AtomTable *t);

/* atom_intern — intern spelling; returns existing or new AtomId.
 * Returns ATOM_ID_INVALID on overflow or NULL input. */
AtomId atom_intern(AtomTable *t, const char *spelling);

/* atom_lookup — find without inserting. Returns ATOM_ID_INVALID if absent. */
AtomId atom_lookup(const AtomTable *t, const char *spelling);

/* atom_spelling — pointer to NUL-terminated spelling of id; NULL if invalid.
 * Valid for the lifetime of *t; do NOT free. */
const char *atom_spelling(const AtomTable *t, AtomId id);

/* atom_count — number of interned atoms. */
uint32_t atom_count(const AtomTable *t);
