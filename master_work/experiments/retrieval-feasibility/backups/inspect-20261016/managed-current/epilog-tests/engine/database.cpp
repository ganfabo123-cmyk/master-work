/*
 * database.cpp — Clause database implementation.
 * JPL rules: no recursion, bounded loops, no post-init malloc.
 */

#include "../include/database.hpp"
#include <cstring>
#include <cassert>

static PredEntry *find_pred(Database *db, AtomId functor, uint8_t arity)
{
    assert(db != nullptr);
    for (uint32_t i = 0U; i < db->pred_count; ++i) {
        if (db->preds[i].functor == functor && db->preds[i].arity == arity) {
            return &db->preds[i];
        }
    }
    return nullptr;
}

static PredEntry *find_or_create_pred(Database *db, AtomId functor, uint8_t arity)
{
    PredEntry *e = find_pred(db, functor, arity);
    if (e != nullptr) { return e; }
    if (db->pred_count >= DB_MAX_PREDICATES) { return nullptr; }

    e = &db->preds[db->pred_count];
    memset(e, 0, sizeof(PredEntry));
    e->functor = functor;
    e->arity   = arity;
    e->first   = db->clause_count;
    e->count   = 0U;
    db->pred_count++;
    return e;
}

int db_init(Database *db)
{
    if (db == nullptr) { return -1; }
    memset(db, 0, sizeof(Database));
    return 0;
}

int db_assert_last(Database *db, const ParsedClause *clause, TermArena *arena)
{
    if (db == nullptr || clause == nullptr) { return -1; }
    if (db->clause_count >= DB_MAX_CLAUSES) { return -1; }

    const Term *head_term = term_get(arena, clause->head);
    if (head_term == nullptr) { return -1; }

    AtomId  functor;
    uint8_t arity;

    switch (head_term->kind) {
        case TERM_KIND_ATOM:
            functor = head_term->data.atom_id;
            arity   = 0U;
            break;
        case TERM_KIND_COMPOUND:
            functor = head_term->data.compound.functor;
            arity   = head_term->data.compound.arity;
            break;
        default:
            return -1;
    }

    PredEntry *pred = find_or_create_pred(db, functor, arity);
    if (pred == nullptr) { return -1; }

    const uint32_t insert_pos = pred->first + pred->count;

    for (uint32_t shift = db->clause_count; shift > insert_pos; --shift) {
        db->clauses[shift]    = db->clauses[shift - 1U];
        db->clauses[shift].id = static_cast<ClauseId>(shift + 1U);
    }

    for (uint32_t pi = 0U; pi < db->pred_count; ++pi) {
        if (&db->preds[pi] != pred && db->preds[pi].first >= insert_pos) {
            db->preds[pi].first++;
        }
    }

    StoredClause *sc = &db->clauses[insert_pos];
    memset(sc, 0, sizeof(StoredClause));
    sc->head     = clause->head;
    sc->body_len = clause->body_len;
    sc->id       = static_cast<ClauseId>(insert_pos + 1U);

    assert(clause->body_len <= DB_MAX_BODY_GOALS);
    for (uint32_t bi = 0U; bi < clause->body_len; ++bi) {
        sc->body[bi] = clause->body[bi];
    }

    pred->count++;
    db->clause_count++;
    return 0;
}

int db_retract_first(Database *db, AtomId functor, uint8_t arity)
{
    if (db == nullptr || functor == ATOM_ID_INVALID) { return -1; }

    PredEntry *pred = find_pred(db, functor, arity);
    if (pred == nullptr || pred->count == 0U) { return -1; }

    const uint32_t remove_pos = pred->first;

    for (uint32_t shift = remove_pos; shift + 1U < db->clause_count; ++shift) {
        db->clauses[shift]    = db->clauses[shift + 1U];
        db->clauses[shift].id = static_cast<ClauseId>(shift + 1U);
    }
    db->clause_count--;
    pred->count--;

    for (uint32_t pi = 0U; pi < db->pred_count; ++pi) {
        if (&db->preds[pi] != pred && db->preds[pi].first > remove_pos) {
            db->preds[pi].first--;
        }
    }
    return 0;
}

const PredEntry *db_get_pred(const Database *db, AtomId functor, uint8_t arity)
{
    if (db == nullptr || functor == ATOM_ID_INVALID) { return nullptr; }
    for (uint32_t i = 0U; i < db->pred_count; ++i) {
        if (db->preds[i].functor == functor && db->preds[i].arity == arity) {
            return &db->preds[i];
        }
    }
    return nullptr;
}

const StoredClause *db_get_clause(const Database *db, uint32_t idx)
{
    if (db == nullptr || idx >= db->clause_count) { return nullptr; }
    return &db->clauses[idx];
}
