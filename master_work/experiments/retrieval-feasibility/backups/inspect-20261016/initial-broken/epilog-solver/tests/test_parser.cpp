/*
 * test_parser.cpp — Unit tests for the clause and query parser.
 */

#include "test_framework.hpp"
#include "../include/parser.hpp"

/* ---- Helpers ------------------------------------------------------------- */

/* Large members (AtomTable ~1MB, TermArena ~4MB) live in static storage. */
struct ParseCtx {
    static AtomTable   s_atoms;
    static TermArena   s_arena;
    static VarRegistry s_vars;
    static TokenList   s_tokens;
    AtomTable   &atoms;
    TermArena   &arena;
    VarRegistry &vars;
    TokenList   &tokens;
    Parser      parser = {};

    ParseCtx()
        : atoms(s_atoms), arena(s_arena), vars(s_vars), tokens(s_tokens)
    {
        atom_table_init(&atoms);
        term_arena_init(&arena);
        var_registry_init(&vars);
    }

    bool lex_and_init(const char *src)
    {
        if (lex(src, &tokens) < 0) { return false; }
        return parser_init(&parser, &tokens, &arena, &atoms, &vars) == 0;
    }

    ParseResult next_clause(ParsedClause &out)
    {
        return parser_next_clause(&parser, &out);
    }

    ParseResult query(ParsedQuery &out)
    {
        return parser_query(&parser, &out);
    }

    TermKind kind(TermRef ref) { return term_kind(&arena, ref); }

    AtomId functor(TermRef ref)
    {
        const Term *t = term_get(&arena, ref);
        if (!t) return ATOM_ID_INVALID;
        if (t->kind == TERM_KIND_ATOM)     return t->data.atom_id;
        if (t->kind == TERM_KIND_COMPOUND) return t->data.compound.functor;
        return ATOM_ID_INVALID;
    }

    const char *spelling(AtomId id) { return atom_spelling(&atoms, id); }
};

AtomTable   ParseCtx::s_atoms  = {};
TermArena   ParseCtx::s_arena  = {};
VarRegistry ParseCtx::s_vars   = {};
TokenList   ParseCtx::s_tokens = {};

/* ---- Clause parsing ------------------------------------------------------ */

TEST("parse simple fact: foo.")
{
    ParseCtx ctx;
    REQUIRE(ctx.lex_and_init("foo."));
    ParsedClause c;
    EXPECT_EQ(ctx.next_clause(c), PARSE_OK);
    EXPECT_EQ(ctx.kind(c.head), TERM_KIND_ATOM);
    EXPECT_EQ(c.body_len, 0U);
}

TEST("parse compound fact: parent(alice, bob).")
{
    ParseCtx ctx;
    REQUIRE(ctx.lex_and_init("parent(alice, bob)."));
    ParsedClause c;
    REQUIRE(ctx.next_clause(c) == PARSE_OK);
    EXPECT_EQ(ctx.kind(c.head), TERM_KIND_COMPOUND);
    const char *sp = ctx.spelling(ctx.functor(c.head));
    REQUIRE(sp != nullptr);
    EXPECT_EQ(strcmp(sp, "parent"), 0);
    EXPECT_EQ(c.body_len, 0U);
}

TEST("parse rule: child(X,Y) :- parent(Y,X).")
{
    ParseCtx ctx;
    REQUIRE(ctx.lex_and_init("child(X,Y) :- parent(Y,X)."));
    ParsedClause c;
    REQUIRE(ctx.next_clause(c) == PARSE_OK);
    EXPECT_EQ(ctx.kind(c.head), TERM_KIND_COMPOUND);
    EXPECT_EQ(c.body_len, 1U);
}

TEST("parse rule with two body goals")
{
    ParseCtx ctx;
    REQUIRE(ctx.lex_and_init("gp(X,Y) :- parent(X,Z), parent(Z,Y)."));
    ParsedClause c;
    REQUIRE(ctx.next_clause(c) == PARSE_OK);
    EXPECT_EQ(c.body_len, 2U);
}

TEST("parse multiple clauses in sequence")
{
    ParseCtx ctx;
    REQUIRE(ctx.lex_and_init("a. b. c."));
    ParsedClause c;
    EXPECT_EQ(ctx.next_clause(c), PARSE_OK);
    EXPECT_EQ(ctx.next_clause(c), PARSE_OK);
    EXPECT_EQ(ctx.next_clause(c), PARSE_OK);
    EXPECT_EQ(ctx.next_clause(c), PARSE_EOF);
}

TEST("parse empty source produces PARSE_EOF immediately")
{
    ParseCtx ctx;
    REQUIRE(ctx.lex_and_init(""));
    ParsedClause c;
    EXPECT_EQ(ctx.next_clause(c), PARSE_EOF);
}

TEST("parse integer term in fact: size(42).")
{
    ParseCtx ctx;
    REQUIRE(ctx.lex_and_init("size(42)."));
    ParsedClause c;
    REQUIRE(ctx.next_clause(c) == PARSE_OK);
    EXPECT_EQ(ctx.kind(c.head), TERM_KIND_COMPOUND);
    /* arg 0 should be an integer */
    TermRef arg = term_arg(&ctx.arena, c.head, 0U);
    EXPECT_EQ(ctx.kind(arg), TERM_KIND_INT);
    EXPECT_EQ(term_get(&ctx.arena, arg)->data.int_val, 42);
}

/* ---- Query parsing ------------------------------------------------------- */

TEST("parse query: ?- foo.")
{
    ParseCtx ctx;
    REQUIRE(ctx.lex_and_init("?- foo."));
    ParsedQuery q;
    REQUIRE(ctx.query(q) == PARSE_OK);
    EXPECT_EQ(q.goal_count, 1U);
    EXPECT_EQ(ctx.kind(q.goals[0]), TERM_KIND_ATOM);
}

TEST("parse query with two goals: ?- a, b.")
{
    ParseCtx ctx;
    REQUIRE(ctx.lex_and_init("?- a, b."));
    ParsedQuery q;
    REQUIRE(ctx.query(q) == PARSE_OK);
    EXPECT_EQ(q.goal_count, 2U);
}

TEST("parse infix = in query: ?- X = foo.")
{
    ParseCtx ctx;
    REQUIRE(ctx.lex_and_init("?- X = foo."));
    ParsedQuery q;
    REQUIRE(ctx.query(q) == PARSE_OK);
    EXPECT_EQ(q.goal_count, 1U);
    /* the goal should be a compound =/2 */
    EXPECT_EQ(ctx.kind(q.goals[0]), TERM_KIND_COMPOUND);
    const char *sp = ctx.spelling(ctx.functor(q.goals[0]));
    REQUIRE(sp != nullptr);
    EXPECT_EQ(strcmp(sp, "="), 0);
}

TEST("parser_init rejects null arguments")
{
    ParseCtx ctx;
    REQUIRE(ctx.lex_and_init("foo."));
    EXPECT_EQ(parser_init(nullptr, &ctx.tokens, &ctx.arena, &ctx.atoms, &ctx.vars), -1);
    EXPECT_EQ(parser_init(&ctx.parser, nullptr, &ctx.arena, &ctx.atoms, &ctx.vars), -1);
}

/* ---- Variable identity within a clause ----------------------------------- */

TEST("same variable name in head and body shares a VarId")
{
    ParseCtx ctx;
    REQUIRE(ctx.lex_and_init("f(X) :- g(X)."));
    ParsedClause c;
    REQUIRE(ctx.next_clause(c) == PARSE_OK);

    /* X in head (arg 0) and X in body g(X) (arg 0) should have same var_id */
    TermRef head_arg = term_arg(&ctx.arena, c.head, 0U);
    TermRef body_g   = c.body[0];
    TermRef body_arg = term_arg(&ctx.arena, body_g, 0U);

    REQUIRE(head_arg != TERM_REF_INVALID);
    REQUIRE(body_arg != TERM_REF_INVALID);

    const Term *th = term_get(&ctx.arena, head_arg);
    const Term *tb = term_get(&ctx.arena, body_arg);
    REQUIRE(th != nullptr && tb != nullptr);
    EXPECT_EQ(th->data.var.var_id, tb->data.var.var_id);
}

int main() { return epilog_test::run_all(); }
