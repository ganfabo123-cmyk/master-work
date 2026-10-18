/*
 * solver.cpp — Backtracking SLD resolution engine.
 * JPL rules: no C recursion, bounded stacks, no post-init malloc.
 */

#include "../include/solver.hpp"
#include "../include/builtins.hpp"
#include "../include/log.hpp"
#include <cstring>
#include <cassert>

/* ---- Internal frame types ------------------------------------------------- */

struct GoalStack {
    TermRef  goals[GOAL_STACK_CAPACITY];
    uint32_t top = 0U;
};

struct ChoicePoint {
    uint32_t clause_idx;
    uint32_t clause_end;
    TermRef  goal;
    uint32_t trail_mark;
    uint32_t goal_top;
};

struct ChoiceStack {
    ChoicePoint items[CHOICE_STACK_CAPACITY];
    uint32_t    top = 0U;
};

/* ---- Variable rename map -------------------------------------------------- */

constexpr uint32_t RENAME_MAP_CAP = VAR_REGISTRY_CAPACITY;

struct RenameMap {
    VarId    old_id[RENAME_MAP_CAP];
    VarId    new_id[RENAME_MAP_CAP];
    uint32_t count = 0U;
};

static VarId rename_lookup(const RenameMap *rm, VarId old)
{
    for (uint32_t i = 0U; i < rm->count; ++i) {
        if (rm->old_id[i] == old) { return rm->new_id[i]; }
    }
    return VAR_ID_INVALID;
}

/* rename_term — deep-copy a clause term into env->arena with fresh VarIds. */
static TermRef rename_term(TermRef ref, const TermArena *arena,
                            SolverEnv *env, RenameMap *rm,
                            const AtomTable *)
{
    for (uint32_t step = 0U; step < TERM_ARENA_CAPACITY; ++step) {
        const Term *t = term_get(arena, ref);
        if (t == nullptr) { return TERM_REF_INVALID; }

        switch (t->kind) {
            case TERM_KIND_ATOM:
                return term_make_atom(env->arena, t->data.atom_id);
            case TERM_KIND_INT:
                return term_make_int(env->arena, t->data.int_val);
            case TERM_KIND_VAR: {
                const VarId old   = t->data.var.var_id;
                VarId       fresh = rename_lookup(rm, old);
                if (fresh == VAR_ID_INVALID) {
                    const char *vname = t->data.var.name;
                    fresh = var_alloc(env->vars, vname[0] ? vname : "_");
                    if (fresh == VAR_ID_INVALID) { return TERM_REF_INVALID; }
                    if (rm->count < RENAME_MAP_CAP) {
                        rm->old_id[rm->count] = old;
                        rm->new_id[rm->count] = fresh;
                        rm->count++;
                    }
                }
                return term_make_var(env->arena, fresh, t->data.var.name);
            }
            case TERM_KIND_COMPOUND: {
                TermRef        new_args[TERM_MAX_ARITY];
                const uint8_t  arity = t->data.compound.arity;
                for (uint8_t i = 0U; i < arity; ++i) {
                    new_args[i] = rename_term(term_arg(arena, ref, i),
                                              arena, env, rm, nullptr);
                    if (new_args[i] == TERM_REF_INVALID) { return TERM_REF_INVALID; }
                }
                return term_make_compound(env->arena, t->data.compound.functor,
                                          arity, new_args);
            }
            default:
                return TERM_REF_INVALID;
        }
        break;
    }
    return TERM_REF_INVALID;
}

/* ---- GoalStack helpers ---------------------------------------------------- */

static int gs_push(GoalStack *gs, TermRef g)
{
    if (gs->top >= GOAL_STACK_CAPACITY) { return -1; }
    gs->goals[gs->top++] = g;
    return 0;
}

static TermRef gs_pop(GoalStack *gs)
{
    if (gs->top == 0U) { return TERM_REF_INVALID; }
    return gs->goals[--gs->top];
}

/* ---- Public API ----------------------------------------------------------- */

int solver_env_init(SolverEnv *env,
                    TermArena *arena, TermArena *clause_arena,
                    VarRegistry *vars, VarRegistry *clause_vars,
                    AtomTable *atoms, Database *db)
{
    if (!env || !arena || !clause_arena || !vars || !clause_vars || !atoms || !db) {
        return -1;
    }
    memset(env, 0, sizeof(SolverEnv));
    env->arena        = arena;
    env->clause_arena = clause_arena;
    env->vars         = vars;
    env->clause_vars  = clause_vars;
    env->atoms        = atoms;
    env->db           = db;
    trail_init(&env->trail);
    return 0;
}

uint32_t solve(SolverEnv *env, const TermRef *goals, uint32_t goal_count,
               SolutionCallback cb, void *userdata)
{
    if (!env || !goals || goal_count == 0U || !cb) { return 0U; }

    GoalStack   gs;
    ChoiceStack cs;
    memset(&gs, 0, sizeof(GoalStack));
    memset(&cs, 0, sizeof(ChoiceStack));

    uint32_t solutions = 0U;

    for (uint32_t gi = goal_count; gi > 0U; --gi) {
        if (gs_push(&gs, goals[gi - 1U]) < 0) { return 0U; }
    }

    /* label targets — using C++ style with a flag to avoid cross-init goto */
    bool do_backtrack = false;

    for (uint32_t iter = 0U; iter < 10000000U; ++iter) {

        if (do_backtrack) {
            do_backtrack = false;
            goto backtrack;
        }

        /* SUCCESS */
        if (gs.top == 0U) {
            solutions++;
            if (cb(env, goals, goal_count, userdata) == SOLVE_STOP) {
                return solutions;
            }
            if (cs.top == 0U) { return solutions; }
            goto backtrack;
        }

        /* pop and process next goal */
        {
            const TermRef  goal    = gs_pop(&gs);
            const TermRef  dgoal   = deref(goal, env->arena, env->vars);
            const Term    *gt      = term_get(env->arena, dgoal);
            AtomId         functor = ATOM_ID_INVALID;
            uint8_t        arity   = 0U;

            if (gt == nullptr)                  { goto backtrack; }
            if (gt->kind == TERM_KIND_ATOM)     { functor = gt->data.atom_id; arity = 0U; }
            else if (gt->kind == TERM_KIND_COMPOUND) {
                functor = gt->data.compound.functor;
                arity   = gt->data.compound.arity;
            } else { goto backtrack; }

            /* built-in? */
            {
                BuiltinFn bf = builtin_lookup(functor, arity, env->atoms);
                if (bf != nullptr) {
                    switch (bf(dgoal, env)) {
                        case BUILTIN_SUCCEED: continue;
                        case BUILTIN_FAIL:    goto backtrack;
                        case BUILTIN_CUT:     cs.top = 0U; continue;
                        case BUILTIN_ERROR:   return solutions;
                    }
                }
            }

            /* user-defined clause lookup */
            {
                const PredEntry *pred = db_get_pred(env->db, functor, arity);
                VLOG_SUBSYS("SOLVE", "goal functor=%u arity=%u pred=%s count=%u",
                            functor, arity,
                            pred ? atom_spelling(env->atoms, functor) : "?NONE",
                            pred ? pred->count : 0U);
                if (pred == nullptr || pred->count == 0U) {
                    VLOG_SUBSYS("SOLVE", "%s", "no clauses -> backtrack");
                    goto backtrack;
                }

                if (pred->count > 1U && cs.top < CHOICE_STACK_CAPACITY) {
                    ChoicePoint *cp  = &cs.items[cs.top++];
                    cp->clause_idx   = pred->first + 1U;
                    cp->clause_end   = pred->first + pred->count;
                    cp->goal         = goal;
                    cp->trail_mark   = trail_mark(&env->trail);
                    cp->goal_top     = gs.top;
                }

                {
                    const StoredClause *sc = db_get_clause(env->db, pred->first);
                    if (sc == nullptr) { goto backtrack; }

                    RenameMap rm;
                    memset(&rm, 0, sizeof(RenameMap));
                    const uint32_t mark = trail_mark(&env->trail);

                    const TermRef fresh_head = rename_term(
                        sc->head, env->clause_arena, env, &rm, env->atoms);
                    if (fresh_head == TERM_REF_INVALID) { goto backtrack; }

                    VLOG_SUBSYS("SOLVE", "trying clause head ref=%u", sc->head);
                    if (!unify(dgoal, fresh_head, env->arena, env->vars, &env->trail)) {
                        VLOG_SUBSYS("SOLVE", "%s", "unify failed -> backtrack");
                        trail_undo(&env->trail, env->vars, mark);
                        goto backtrack;
                    }
                    VLOG_SUBSYS("SOLVE", "unified ok, body_len=%u", sc->body_len);

                    for (uint32_t bi = sc->body_len; bi > 0U; --bi) {
                        const TermRef fresh_body = rename_term(
                            sc->body[bi - 1U], env->clause_arena, env, &rm, env->atoms);
                        if (fresh_body == TERM_REF_INVALID ||
                            gs_push(&gs, fresh_body) < 0) {
                            trail_undo(&env->trail, env->vars, mark);
                            goto backtrack;
                        }
                    }
                }
            }
            continue;
        }

        backtrack:
        {
            if (cs.top == 0U) { return solutions; }

            ChoicePoint *cp = &cs.items[cs.top - 1U];
            trail_undo(&env->trail, env->vars, cp->trail_mark);
            gs.top = cp->goal_top;

            if (cp->clause_idx >= cp->clause_end) { cs.top--; goto backtrack; }

            {
                const StoredClause *sc = db_get_clause(env->db, cp->clause_idx);
                const TermRef dgoal = deref(cp->goal, env->arena, env->vars);

                cp->clause_idx++;
                if (cp->clause_idx >= cp->clause_end) { cs.top--; }

                if (sc == nullptr) { goto backtrack; }

                RenameMap rm;
                memset(&rm, 0, sizeof(RenameMap));
                const uint32_t mark = trail_mark(&env->trail);

                const TermRef fresh_head = rename_term(
                    sc->head, env->clause_arena, env, &rm, env->atoms);
                if (fresh_head == TERM_REF_INVALID) { goto backtrack; }

                if (!unify(dgoal, fresh_head, env->arena, env->vars, &env->trail)) {
                    trail_undo(&env->trail, env->vars, mark);
                    goto backtrack;
                }

                for (uint32_t bi = sc->body_len; bi > 0U; --bi) {
                    const TermRef fresh_body = rename_term(
                        sc->body[bi - 1U], env->clause_arena, env, &rm, env->atoms);
                    if (fresh_body == TERM_REF_INVALID ||
                        gs_push(&gs, fresh_body) < 0) {
                        trail_undo(&env->trail, env->vars, mark);
                        goto backtrack;
                    }
                }
            }
            continue;
        }
    }
    return solutions;
}
