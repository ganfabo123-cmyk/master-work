/*
 * test_solver.cpp — Integration tests for the SLD resolution engine.
 *
 * Covers the Phase 0.1 acceptance criteria and key solver behaviours:
 * backtracking, multiple solutions, cut, built-ins.
 */

#include "test_framework.hpp"
#include "../include/solver.hpp"
#include "../include/builtins.hpp"
#include "../include/parser.hpp"
#include "../include/lexer.hpp"

/* ---- Test harness -------------------------------------------------------- */

struct SolverCtx {
    AtomTable   atoms;
    Database    db;
    TermArena   clause_arena;
    VarRegistry clause_vars;
    TermArena   query_arena;
    VarRegistry query_vars;

    SolverCtx()
    {
        atom_table_init(&atoms);
        db_init(&db);
        term_arena_init(&clause_arena);
        var_registry_init(&clause_vars);
        term_arena_init(&query_arena);
        var_registry_init(&query_vars);
    }

    /* Assert clauses from a source string. Returns number asserted or -1. */
    int load(const char *src)
    {
        static TokenList toks;
        memset(&toks, 0, sizeof(toks));
        if (lex(src, &toks) < 0) { return -1; }
        var_registry_init(&clause_vars);
        Parser p;
        if (parser_init(&p, &toks, &clause_arena, &atoms, &clause_vars) < 0) {
            return -1;
        }
        int n = 0;
        ParsedClause c;
        for (;;) {
            memset(&c, 0, sizeof(c));
            ParseResult r = parser_next_clause(&p, &c);
            if (r == PARSE_EOF) { break; }
            if (r != PARSE_OK)  { return -1; }
            if (db_assert_last(&db, &c, &clause_arena) < 0) { return -1; }
            n++;
        }
        return n;
    }

    /* Run a single query and return the solution count (0 = false). */
    uint32_t query(const char *src)
    {
        static TokenList toks;
        memset(&toks, 0, sizeof(toks));
        term_arena_init(&query_arena);
        var_registry_init(&query_vars);
        if (lex(src, &toks) < 0) { return 0; }
        Parser p;
        if (parser_init(&p, &toks, &query_arena, &atoms, &query_vars) < 0) {
            return 0;
        }
        ParsedQuery pq;
        if (parser_query(&p, &pq) != PARSE_OK) { return 0; }

        SolverEnv env;
        solver_env_init(&env, &query_arena, &clause_arena,
                        &query_vars, &clause_vars, &atoms, &db);

        return solve(&env, pq.goals, pq.goal_count,
                     [](SolverEnv *, const TermRef *, uint32_t, void *) {
                         return SOLVE_NEXT;
                     }, nullptr);
    }

    /* Run query; for first solution, invoke cb on the env to inspect bindings. */
    bool query_one(const char *src, std::function<void(SolverEnv &)> cb)
    {
        static TokenList toks;
        memset(&toks, 0, sizeof(toks));
        term_arena_init(&query_arena);
        var_registry_init(&query_vars);
        if (lex(src, &toks) < 0) { return false; }
        Parser p;
        if (parser_init(&p, &toks, &query_arena, &atoms, &query_vars) < 0) {
            return false;
        }
        ParsedQuery pq;
        if (parser_query(&p, &pq) != PARSE_OK) { return false; }

        SolverEnv env;
        solver_env_init(&env, &query_arena, &clause_arena,
                        &query_vars, &clause_vars, &atoms, &db);

        bool fired = false;
        auto wrapper_cb = [&](SolverEnv *e, const TermRef *, uint32_t, void *) {
            if (!fired) { fired = true; cb(*e); }
            return SOLVE_STOP;
        };

        solve(&env, pq.goals, pq.goal_count,
              [](SolverEnv *e, const TermRef *g, uint32_t gc, void *ud) {
                  return (*static_cast<decltype(wrapper_cb)*>(ud))(e, g, gc, nullptr);
              }, &wrapper_cb);
        return fired;
    }
};

/* ---- Phase 0.1 acceptance criteria --------------------------------------- */

TEST("0.1 acceptance: grandparent(alice, carol) succeeds")
{
    SolverCtx ctx;
    REQUIRE(ctx.load(
        "parent(alice, bob). "
        "parent(bob, carol). "
        "grandparent(X, Y) :- parent(X, Z), parent(Z, Y)."
    ) == 3);
    EXPECT_EQ(ctx.query("?- grandparent(alice, carol)."), 1U);
}

TEST("0.1 acceptance: grandparent(alice, alice) fails")
{
    SolverCtx ctx;
    REQUIRE(ctx.load(
        "parent(alice, bob). "
        "parent(bob, carol). "
        "grandparent(X, Y) :- parent(X, Z), parent(Z, Y)."
    ) > 0);
    EXPECT_EQ(ctx.query("?- grandparent(alice, alice)."), 0U);
}

/* ---- Fact queries -------------------------------------------------------- */

TEST("ground fact query succeeds")
{
    SolverCtx ctx;
    ctx.load("likes(alice, pizza).");
    EXPECT_EQ(ctx.query("?- likes(alice, pizza)."), 1U);
}

TEST("ground fact query fails for unknown fact")
{
    SolverCtx ctx;
    ctx.load("likes(alice, pizza).");
    EXPECT_EQ(ctx.query("?- likes(bob, pizza)."), 0U);
}

TEST("variable query returns all matching solutions")
{
    SolverCtx ctx;
    ctx.load("color(red). color(green). color(blue).");
    EXPECT_EQ(ctx.query("?- color(X)."), 3U);
}

/* ---- Rule chaining ------------------------------------------------------- */

TEST("single-body rule resolves correctly")
{
    SolverCtx ctx;
    ctx.load("parent(alice, bob). child(X, Y) :- parent(Y, X).");
    EXPECT_EQ(ctx.query("?- child(bob, alice)."), 1U);
}

TEST("two-body rule resolves via conjunction")
{
    SolverCtx ctx;
    ctx.load(
        "parent(alice, bob). parent(bob, carol)."
        "gp(X,Y) :- parent(X,Z), parent(Z,Y)."
    );
    EXPECT_EQ(ctx.query("?- gp(alice, carol)."), 1U);
    EXPECT_EQ(ctx.query("?- gp(alice, bob)."),   0U);
}

TEST("recursive rule — ancestor")
{
    SolverCtx ctx;
    ctx.load(
        "parent(alice, bob). parent(bob, carol). parent(carol, dave)."
        "ancestor(X,Y) :- parent(X,Y)."
        "ancestor(X,Y) :- parent(X,Z), ancestor(Z,Y)."
    );
    EXPECT_EQ(ctx.query("?- ancestor(alice, dave)."), 1U);
    EXPECT_EQ(ctx.query("?- ancestor(dave, alice)."), 0U);
}

/* ---- Backtracking -------------------------------------------------------- */

TEST("multiple clauses — correct solution count")
{
    SolverCtx ctx;
    ctx.load("fruit(apple). fruit(banana). fruit(cherry).");
    EXPECT_EQ(ctx.query("?- fruit(X)."), 3U);
}

TEST("backtracking finds second solution after first fails")
{
    SolverCtx ctx;
    ctx.load(
        "path(a, b). path(b, c). path(a, c)."
        "reachable(X, Y) :- path(X, Y)."
    );
    EXPECT_EQ(ctx.query("?- reachable(a, c)."), 1U);
}

/* ---- Built-in predicates ------------------------------------------------- */

TEST("true/0 always succeeds")
{
    SolverCtx ctx;
    EXPECT_EQ(ctx.query("?- true."), 1U);
}

TEST("fail/0 always fails")
{
    SolverCtx ctx;
    EXPECT_EQ(ctx.query("?- fail."), 0U);
}

TEST("=/2 unifies two atoms")
{
    SolverCtx ctx;
    EXPECT_EQ(ctx.query("?- foo = foo."), 1U);
}

TEST("=/2 fails for different atoms")
{
    SolverCtx ctx;
    EXPECT_EQ(ctx.query("?- foo = bar."), 0U);
}

TEST("=/2 binds variable")
{
    SolverCtx ctx;
    EXPECT_EQ(ctx.query("?- X = alice."), 1U);
}

TEST("\\=/2 succeeds for non-unifiable terms")
{
    SolverCtx ctx;
    EXPECT_EQ(ctx.query("?- foo \\= bar."), 1U);
}

TEST("\\=/2 fails for unifiable terms")
{
    SolverCtx ctx;
    EXPECT_EQ(ctx.query("?- foo \\= foo."), 0U);
}

TEST("cut stops backtracking over choice points")
{
    SolverCtx ctx;
    ctx.load("first(X) :- member(X), !. member(a). member(b). member(c).");
    /* without cut we'd get 3 solutions; with cut just 1 */
    EXPECT_EQ(ctx.query("?- first(X)."), 1U);
}

/* ---- assert / retract ---------------------------------------------------- */

TEST("assert adds fact queryable immediately")
{
    SolverCtx ctx;
    ctx.query("?- assert(dynamic(ok)).");
    EXPECT_EQ(ctx.query("?- dynamic(ok)."), 1U);
}

TEST("retract removes first matching clause")
{
    SolverCtx ctx;
    ctx.load("item(a). item(b). item(c).");
    ctx.query("?- retract(item(a)).");
    EXPECT_EQ(ctx.query("?- item(a)."), 0U);
    EXPECT_EQ(ctx.query("?- item(b)."), 1U);
}

/* ---- Conjunctive query --------------------------------------------------- */

TEST("conjunction: both goals must succeed")
{
    SolverCtx ctx;
    ctx.load("a. b.");
    EXPECT_EQ(ctx.query("?- a, b."), 1U);
}

TEST("conjunction fails if second goal fails")
{
    SolverCtx ctx;
    ctx.load("a.");
    EXPECT_EQ(ctx.query("?- a, b."), 0U);
}

int main() { return epilog_test::run_all(); }
