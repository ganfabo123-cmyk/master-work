/*
 * builtins.cpp — Built-in predicate implementations.
 * JPL rules: no recursion (term_write uses explicit stack), bounded loops.
 */

#include "../include/builtins.hpp"
#include "../include/parser.hpp"
#include <cstring>
#include <cstdio>
#include <cassert>

/* ---- term_write ----------------------------------------------------------- */

constexpr uint32_t PRINT_STACK_CAP = 512U;

struct PrintFrame { TermRef ref; int after_comma; };

int term_write(TermRef ref, const TermArena *arena,
               const VarRegistry *vars, const AtomTable *atoms)
{
    if (arena == nullptr || vars == nullptr || atoms == nullptr) { return -1; }

    PrintFrame stack[PRINT_STACK_CAP];
    uint32_t   top = 0U;
    stack[top++] = { ref, 0 };

    for (uint32_t steps = 0U; steps < PRINT_STACK_CAP && top > 0U; ++steps) {
        const PrintFrame frame = stack[--top];
        const TermRef    dr    = deref(frame.ref, arena, vars);
        const Term      *t     = term_get(arena, dr);

        if (t == nullptr) { printf("_"); continue; }

        switch (t->kind) {
            case TERM_KIND_ATOM: {
                const char *sp = atom_spelling(atoms, t->data.atom_id);
                printf("%s", sp ? sp : "_");
                break;
            }
            case TERM_KIND_INT:
                printf("%d", static_cast<int>(t->data.int_val));
                break;
            case TERM_KIND_VAR: {
                const WalkResult wr = var_walk(vars, t->data.var.var_id);
                if (wr.tag == TERM_UNBOUND) {
                    const char *vn = t->data.var.name;
                    printf("%s", (vn && vn[0]) ? vn : "_");
                } else if (wr.tag == TERM_ATOM) {
                    const char *sp = atom_spelling(atoms, wr.value.atom_id);
                    printf("%s", sp ? sp : "_");
                } else if (wr.tag == TERM_TERMREF && top < PRINT_STACK_CAP) {
                    stack[top++] = { wr.value.term_ref, 0 };
                } else {
                    printf("_");
                }
                break;
            }
            case TERM_KIND_COMPOUND: {
                const uint8_t arity = t->data.compound.arity;
                const char *fn = atom_spelling(atoms, t->data.compound.functor);
                printf("%s(", fn ? fn : "?");
                if (top + static_cast<uint32_t>(arity) >= PRINT_STACK_CAP) {
                    printf("...)");
                    break;
                }
                for (uint8_t i = 0U; i < arity; ++i) {
                    if (i > 0U) { printf(","); }
                    term_write(term_arg(arena, dr, i), arena, vars, atoms);
                }
                printf(")");
                break;
            }
        }
    }
    return 0;
}

/* ---- Built-in implementations --------------------------------------------- */

static BuiltinResult bi_true(TermRef, SolverEnv *) { return BUILTIN_SUCCEED; }
static BuiltinResult bi_fail(TermRef, SolverEnv *) { return BUILTIN_FAIL;    }
static BuiltinResult bi_cut (TermRef, SolverEnv *) { return BUILTIN_CUT;     }

static BuiltinResult bi_unify(TermRef goal, SolverEnv *env)
{
    const TermRef a = term_arg(env->arena, goal, 0U);
    const TermRef b = term_arg(env->arena, goal, 1U);
    if (a == TERM_REF_INVALID || b == TERM_REF_INVALID) { return BUILTIN_FAIL; }

    const uint32_t mark = trail_mark(&env->trail);
    if (unify(a, b, env->arena, env->vars, &env->trail)) { return BUILTIN_SUCCEED; }
    trail_undo(&env->trail, env->vars, mark);
    return BUILTIN_FAIL;
}

static BuiltinResult bi_not_unify(TermRef goal, SolverEnv *env)
{
    const TermRef a = term_arg(env->arena, goal, 0U);
    const TermRef b = term_arg(env->arena, goal, 1U);
    if (a == TERM_REF_INVALID || b == TERM_REF_INVALID) { return BUILTIN_FAIL; }

    const uint32_t mark = trail_mark(&env->trail);
    const int ok = unify(a, b, env->arena, env->vars, &env->trail);
    trail_undo(&env->trail, env->vars, mark);
    return ok ? BUILTIN_FAIL : BUILTIN_SUCCEED;
}

static BuiltinResult bi_write(TermRef goal, SolverEnv *env)
{
    const TermRef arg = term_arg(env->arena, goal, 0U);
    if (arg == TERM_REF_INVALID) { return BUILTIN_FAIL; }
    term_write(arg, env->arena, env->vars, env->atoms);
    return BUILTIN_SUCCEED;
}

static BuiltinResult bi_nl(TermRef, SolverEnv *) { printf("\n"); return BUILTIN_SUCCEED; }

/* copy_for_assert — deep-copy a term from the per-query arena into the clause
 * arena so stored clauses never reference query-scoped memory (which is
 * re-initialised on the next query). Variables are re-registered in the clause
 * registry and matched by name, so repeated occurrences of one variable stay
 * shared inside the asserted clause. */
static TermRef copy_for_assert(TermRef ref, SolverEnv *env)
{
    for (uint32_t step = 0U; step < TERM_ARENA_CAPACITY; ++step) {
        const TermRef dr = deref(ref, env->arena, env->vars);
        const Term *t = term_get(env->arena, dr);
        if (t == nullptr) { return TERM_REF_INVALID; }

        switch (t->kind) {
            case TERM_KIND_ATOM:
                return term_make_atom(env->clause_arena, t->data.atom_id);
            case TERM_KIND_INT:
                return term_make_int(env->clause_arena, t->data.int_val);
            case TERM_KIND_VAR: {
                const char *vname = t->data.var.name;
                VarId vid = VAR_ID_INVALID;
                for (uint32_t k = 0U; k < env->clause_vars->count; ++k) {
                    if (strncmp(env->clause_vars->entries[k].name, vname,
                                VAR_NAME_MAX_LEN) == 0) {
                        vid = env->clause_vars->entries[k].id;
                        break;
                    }
                }
                if (vid == VAR_ID_INVALID) {
                    vid = var_alloc(env->clause_vars, vname[0] ? vname : "_");
                }
                if (vid == VAR_ID_INVALID) { return TERM_REF_INVALID; }
                return term_make_var(env->clause_arena, vid, vname);
            }
            case TERM_KIND_COMPOUND: {
                TermRef       new_args[TERM_MAX_ARITY];
                const uint8_t arity = t->data.compound.arity;
                for (uint8_t i = 0U; i < arity; ++i) {
                    new_args[i] = copy_for_assert(term_arg(env->arena, dr, i), env);
                    if (new_args[i] == TERM_REF_INVALID) { return TERM_REF_INVALID; }
                }
                return term_make_compound(env->clause_arena,
                                          t->data.compound.functor,
                                          arity, new_args);
            }
            default:
                return TERM_REF_INVALID;
        }
        break;
    }
    return TERM_REF_INVALID;
}

static BuiltinResult bi_assert(TermRef goal, SolverEnv *env)
{
    const TermRef arg = term_arg(env->arena, goal, 0U);
    if (arg == TERM_REF_INVALID) { return BUILTIN_FAIL; }

    ParsedClause pc;
    memset(&pc, 0, sizeof(ParsedClause));

    const TermRef darg = deref(arg, env->arena, env->vars);
    const Term   *t    = term_get(env->arena, darg);
    if (t == nullptr) { return BUILTIN_FAIL; }

    /* check for ':-'(Head, Body) form — restructured to avoid goto */
    bool is_rule = false;
    if (t->kind == TERM_KIND_COMPOUND && t->data.compound.arity == 2U) {
        const char *fn = atom_spelling(env->atoms, t->data.compound.functor);
        if (fn != nullptr && strncmp(fn, ":-", 3) == 0) {
            pc.head    = copy_for_assert(term_arg(env->arena, darg, 0U), env);
            pc.body[0] = copy_for_assert(term_arg(env->arena, darg, 1U), env);
            if (pc.head == TERM_REF_INVALID || pc.body[0] == TERM_REF_INVALID) {
                return BUILTIN_FAIL;
            }
            pc.body_len = 1U;
            is_rule     = true;
        }
    }
    if (!is_rule) {
        pc.head = copy_for_assert(arg, env);
        if (pc.head == TERM_REF_INVALID) { return BUILTIN_FAIL; }
        pc.body_len = 0U;
    }

    /* Stored clauses must live in the clause arena: the solver's rename pass
     * reads them from there, and the query arena is wiped between queries. */
    if (db_assert_last(env->db, &pc, env->clause_arena) < 0) { return BUILTIN_FAIL; }
    return BUILTIN_SUCCEED;
}

static BuiltinResult bi_retract(TermRef goal, SolverEnv *env)
{
    const TermRef arg = term_arg(env->arena, goal, 0U);
    if (arg == TERM_REF_INVALID) { return BUILTIN_FAIL; }

    const Term *t = term_get(env->arena, deref(arg, env->arena, env->vars));
    if (t == nullptr) { return BUILTIN_FAIL; }

    AtomId  functor;
    uint8_t arity;
    if (t->kind == TERM_KIND_ATOM) {
        functor = t->data.atom_id; arity = 0U;
    } else if (t->kind == TERM_KIND_COMPOUND) {
        functor = t->data.compound.functor; arity = t->data.compound.arity;
    } else {
        return BUILTIN_FAIL;
    }

    if (db_retract_first(env->db, functor, arity) < 0) { return BUILTIN_FAIL; }
    return BUILTIN_SUCCEED;
}

/* ---- Dispatch table ------------------------------------------------------- */

struct BuiltinEntry { const char *name; uint8_t arity; BuiltinFn fn; };

static const BuiltinEntry BUILTIN_TABLE[] = {
    { "true",    0U, bi_true       },
    { "fail",    0U, bi_fail       },
    { "false",   0U, bi_fail       },
    { "!",       0U, bi_cut        },
    { "=",       2U, bi_unify      },
    { "\\=",     2U, bi_not_unify  },
    { "write",   1U, bi_write      },
    { "nl",      0U, bi_nl         },
    { "assert",  1U, bi_assert     },
    { "assertz", 1U, bi_assert     },
    { "retract", 1U, bi_retract    }
};

constexpr uint32_t BUILTIN_TABLE_SIZE =
    static_cast<uint32_t>(sizeof(BUILTIN_TABLE) / sizeof(BUILTIN_TABLE[0]));

BuiltinFn builtin_lookup(AtomId functor, uint8_t arity, const AtomTable *atoms)
{
    if (functor == ATOM_ID_INVALID || atoms == nullptr) { return nullptr; }
    const char *name = atom_spelling(atoms, functor);
    if (name == nullptr) { return nullptr; }
    for (uint32_t i = 0U; i < BUILTIN_TABLE_SIZE; ++i) {
        if (BUILTIN_TABLE[i].arity == arity &&
            strncmp(BUILTIN_TABLE[i].name, name, ATOM_MAX_LEN) == 0) {
            return BUILTIN_TABLE[i].fn;
        }
    }
    return nullptr;
}
