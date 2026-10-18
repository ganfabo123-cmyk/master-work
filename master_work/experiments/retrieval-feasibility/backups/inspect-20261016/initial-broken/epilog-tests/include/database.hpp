/*
 * database.hpp — Clause database for the Epilog inference engine.
 * JPL rules: no recursion, bounded capacities, no post-init malloc.
 */

#pragma once

#include <cstdint>
#include "atoms.hpp"
#include "terms.hpp"
#include "parser.hpp"

constexpr uint32_t DB_MAX_PREDICATES = 512U;
constexpr uint32_t DB_MAX_CLAUSES    = 4096U;
constexpr uint32_t DB_MAX_BODY_GOALS = PARSER_MAX_BODY_GOALS;

using ClauseId = uint32_t;
constexpr ClauseId CLAUSE_ID_INVALID = 0U;

struct StoredClause {
    TermRef  head    = TERM_REF_INVALID;
    TermRef  body[DB_MAX_BODY_GOALS] = {};
    uint32_t body_len = 0U;
    ClauseId id       = CLAUSE_ID_INVALID;
};

struct PredEntry {
    AtomId   functor = ATOM_ID_INVALID;
    uint8_t  arity   = 0U;
    uint32_t first   = 0U;
    uint32_t count   = 0U;
};

struct Database {
    StoredClause clauses[DB_MAX_CLAUSES];
    uint32_t     clause_count = 0U;
    PredEntry    preds[DB_MAX_PREDICATES];
    uint32_t     pred_count   = 0U;
};

int                 db_init(Database *db);
int                 db_assert_last(Database *db, const ParsedClause *clause,
                                   TermArena *arena);
int                 db_retract_first(Database *db, AtomId functor, uint8_t arity);
const PredEntry    *db_get_pred(const Database *db, AtomId functor, uint8_t arity);
const StoredClause *db_get_clause(const Database *db, uint32_t idx);
