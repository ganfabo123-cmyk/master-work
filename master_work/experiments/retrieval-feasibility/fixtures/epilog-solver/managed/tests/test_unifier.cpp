/*
 * test_unifier.cpp — Unit tests for Robinson unification and trail.
 */

#include "test_framework.hpp"
#include "../include/unifier.hpp"

/* ---- Helpers ------------------------------------------------------------- */

struct UnifyCtx {
    static AtomTable   s_atoms;
    static TermArena   s_arena;
    static VarRegistry s_vars;
    AtomTable   &atoms;
    TermArena   &arena;
    VarRegistry &vars;
    Trail        trail = {};

    UnifyCtx()
        : atoms(s_atoms), arena(s_arena), vars(s_vars)
    {
        atom_table_init(&atoms);  /* clears atom table — fresh each test */
        term_arena_init(&arena);  /* clears term arena */
        var_registry_init(&vars);
        trail_init(&trail);
    }

    AtomId intern(const char *s) { return atom_intern(&atoms, s); }

    TermRef atom(const char *s)
    {
        return term_make_atom(&arena, atom_intern(&atoms, s));
    }

    TermRef integer(int32_t v) { return term_make_int(&arena, v); }

    TermRef var(const char *name)
    {
        VarId id = var_alloc(&vars, name);
        return term_make_var(&arena, id, name);
    }

    TermRef compound(const char *f, std::initializer_list<TermRef> args)
    {
        AtomId  fid = atom_intern(&atoms, f);
        TermRef buf[TERM_MAX_ARITY];
        uint8_t n   = 0U;
        for (TermRef r : args) { buf[n++] = r; }
        return term_make_compound(&arena, fid, n, buf);
    }

    bool unify(TermRef a, TermRef b)
    {
        return ::unify(a, b, &arena, &vars, &trail) == 1;
    }

    TermRef deref(TermRef r) { return ::deref(r, &arena, &vars); }

    uint32_t mark() { return trail_mark(&trail); }

    void undo(uint32_t m) { trail_undo(&trail, &vars, m); }
};

AtomTable   UnifyCtx::s_atoms = {};
TermArena   UnifyCtx::s_arena = {};
VarRegistry UnifyCtx::s_vars  = {};

/* ---- Atom unification ---------------------------------------------------- */

TEST("atom unifies with itself")
{
    UnifyCtx ctx;
    TermRef a = ctx.atom("alice");
    TermRef b = ctx.atom("alice");
    EXPECT(ctx.unify(a, b));
}

TEST("different atoms fail to unify")
{
    UnifyCtx ctx;
    EXPECT(!ctx.unify(ctx.atom("alice"), ctx.atom("bob")));
}

/* ---- Integer unification ------------------------------------------------- */

TEST("equal integers unify")
{
    UnifyCtx ctx;
    EXPECT(ctx.unify(ctx.integer(42), ctx.integer(42)));
}

TEST("different integers fail to unify")
{
    UnifyCtx ctx;
    EXPECT(!ctx.unify(ctx.integer(1), ctx.integer(2)));
}

/* ---- Variable unification ------------------------------------------------ */

TEST("unbound variable unifies with atom — variable gets bound")
{
    UnifyCtx ctx;
    TermRef x    = ctx.var("X");
    TermRef alice = ctx.atom("alice");
    REQUIRE(ctx.unify(x, alice));
    TermRef dr = ctx.deref(x);
    EXPECT_EQ(dr, alice);
}

TEST("unbound variable unifies with integer")
{
    UnifyCtx ctx;
    TermRef x = ctx.var("X");
    TermRef n = ctx.integer(7);
    REQUIRE(ctx.unify(x, n));
    EXPECT_EQ(ctx.deref(x), n);
}

TEST("two unbound variables unify — one binds to the other")
{
    UnifyCtx ctx;
    TermRef x = ctx.var("X");
    TermRef y = ctx.var("Y");
    REQUIRE(ctx.unify(x, y));
    /* bind Y to an atom then deref X should reach alice */
    TermRef alice = ctx.atom("alice");
    REQUIRE(ctx.unify(y, alice));
    EXPECT_EQ(ctx.deref(x), alice);
}

TEST("variable already bound to atom — unifies with same atom")
{
    UnifyCtx ctx;
    TermRef x     = ctx.var("X");
    TermRef alice = ctx.atom("alice");
    ctx.unify(x, alice);
    EXPECT(ctx.unify(x, alice));
}

TEST("variable already bound — fails with different atom")
{
    UnifyCtx ctx;
    TermRef x = ctx.var("X");
    ctx.unify(x, ctx.atom("alice"));
    EXPECT(!ctx.unify(x, ctx.atom("bob")));
}

/* ---- Compound unification ------------------------------------------------ */

TEST("compound with same functor and arity unifies")
{
    UnifyCtx ctx;
    TermRef a = ctx.compound("f", { ctx.atom("a") });
    TermRef b = ctx.compound("f", { ctx.atom("a") });
    EXPECT(ctx.unify(a, b));
}

TEST("compound with different functor fails")
{
    UnifyCtx ctx;
    TermRef a = ctx.compound("f", { ctx.atom("a") });
    TermRef b = ctx.compound("g", { ctx.atom("a") });
    EXPECT(!ctx.unify(a, b));
}

TEST("compound with different arity fails")
{
    UnifyCtx ctx;
    TermRef a = ctx.compound("f", { ctx.atom("a") });
    TermRef b = ctx.compound("f", { ctx.atom("a"), ctx.atom("b") });
    EXPECT(!ctx.unify(a, b));
}

TEST("compound arg variables get bound")
{
    UnifyCtx ctx;
    TermRef x   = ctx.var("X");
    TermRef lhs = ctx.compound("f", { x });
    TermRef rhs = ctx.compound("f", { ctx.atom("val") });
    REQUIRE(ctx.unify(lhs, rhs));
    EXPECT_EQ(ctx.deref(x), term_arg(&ctx.arena, rhs, 0U));
}

TEST("nested compound unification")
{
    UnifyCtx ctx;
    TermRef x    = ctx.var("X");
    TermRef inner = ctx.compound("g", { x });
    TermRef lhs  = ctx.compound("f", { inner });
    TermRef rhs  = ctx.compound("f", { ctx.compound("g", { ctx.atom("z") }) });
    REQUIRE(ctx.unify(lhs, rhs));
    EXPECT_EQ(ctx.deref(x), term_arg(&ctx.arena, term_arg(&ctx.arena, rhs, 0U), 0U));
}

/* ---- Trail / backtracking ------------------------------------------------ */

TEST("trail_mark and trail_undo restore unbound state")
{
    UnifyCtx ctx;
    TermRef  alice = ctx.atom("alice"); /* capture ref before any undo */
    TermRef  x     = ctx.var("X");
    uint32_t mark  = ctx.mark();
    ctx.unify(x, alice);
    EXPECT_EQ(ctx.deref(x), alice);    /* still bound before undo */
    ctx.undo(mark);
    /* after undo, X should be unbound again */
    const Term *t = term_get(&ctx.arena, x);
    REQUIRE(t != nullptr);
    WalkResult wr = var_walk(&ctx.vars, t->data.var.var_id);
    EXPECT_EQ(wr.tag, TERM_UNBOUND);
}

TEST("trail undo does not affect bindings made before the mark")
{
    UnifyCtx ctx;
    TermRef before_ref = ctx.atom("before"); /* capture before binding */
    TermRef x = ctx.var("X");
    TermRef y = ctx.var("Y");
    ctx.unify(x, before_ref);
    uint32_t mark = ctx.mark();
    ctx.unify(y, ctx.atom("after"));
    ctx.undo(mark);
    /* X still bound — deref(x) should equal the before_ref atom */
    EXPECT_EQ(ctx.deref(x), before_ref);
    /* Y unbound */
    const Term *ty = term_get(&ctx.arena, y);
    REQUIRE(ty != nullptr);
    EXPECT_EQ(var_walk(&ctx.vars, ty->data.var.var_id).tag, TERM_UNBOUND);
}

/* ---- Type mismatch ------------------------------------------------------- */

TEST("atom vs compound fails")
{
    UnifyCtx ctx;
    EXPECT(!ctx.unify(ctx.atom("f"), ctx.compound("f", { ctx.atom("a") })));
}

TEST("atom vs integer fails")
{
    UnifyCtx ctx;
    EXPECT(!ctx.unify(ctx.atom("a"), ctx.integer(1)));
}

int main() { return epilog_test::run_all(); }
