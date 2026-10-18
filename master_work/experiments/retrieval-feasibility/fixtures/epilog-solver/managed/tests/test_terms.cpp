/*
 * test_terms.cpp — Unit tests for the term arena.
 */

#include "test_framework.hpp"
#include "../include/terms.hpp"

/* Large structs live in static storage — too big for Windows default stack. */
static TermArena &fresh_arena()
{
    static TermArena a;
    term_arena_init(&a);
    return a;
}
static VarRegistry &fresh_reg()
{
    static VarRegistry r;
    var_registry_init(&r);
    return r;
}
static AtomTable &fresh_atoms()
{
    static AtomTable t;
    atom_table_init(&t);
    return t;
}
#define make_arena() fresh_arena()
#define make_reg()   fresh_reg()

TEST("term_arena_init zeroes count")
{
    TermArena a;
    term_arena_init(&a);
    EXPECT_EQ(a.count, 0U);
}

TEST("term_arena_init rejects null")
{
    EXPECT_EQ(term_arena_init(nullptr), -1);
}

TEST("make_atom returns valid ref")
{
    TermArena a = make_arena();
    AtomTable &t = fresh_atoms();
    AtomId id = atom_intern(&t, "alice");
    TermRef ref = term_make_atom(&a, id);
    EXPECT_NE(ref, TERM_REF_INVALID);
}

TEST("make_atom stores TERM_KIND_ATOM")
{
    TermArena a = make_arena();
    AtomTable &t = fresh_atoms();
    AtomId  id  = atom_intern(&t, "foo");
    TermRef ref = term_make_atom(&a, id);
    EXPECT_EQ(term_kind(&a, ref), TERM_KIND_ATOM);
}

TEST("make_atom rejects ATOM_ID_INVALID")
{
    TermArena a = make_arena();
    EXPECT_EQ(term_make_atom(&a, ATOM_ID_INVALID), TERM_REF_INVALID);
}

TEST("make_int stores TERM_KIND_INT and correct value")
{
    TermArena   a   = make_arena();
    TermRef     ref = term_make_int(&a, -42);
    REQUIRE(ref != TERM_REF_INVALID);
    const Term *t   = term_get(&a, ref);
    REQUIRE(t != nullptr);
    EXPECT_EQ(t->kind,         TERM_KIND_INT);
    EXPECT_EQ(t->data.int_val, -42);
}

TEST("make_var stores TERM_KIND_VAR and name")
{
    TermArena   a = make_arena();
    VarRegistry r = make_reg();
    VarId       v = var_alloc(&r, "MyVar");
    TermRef   ref = term_make_var(&a, v, "MyVar");
    REQUIRE(ref != TERM_REF_INVALID);
    const Term *t = term_get(&a, ref);
    REQUIRE(t != nullptr);
    EXPECT_EQ(t->kind, TERM_KIND_VAR);
    EXPECT_EQ(strcmp(t->data.var.name, "MyVar"), 0);
}

TEST("make_var stores underscore for null name")
{
    TermArena   a = make_arena();
    VarRegistry r = make_reg();
    VarId       v = var_alloc(&r, "_");
    TermRef   ref = term_make_var(&a, v, nullptr);
    REQUIRE(ref != TERM_REF_INVALID);
    const Term *t = term_get(&a, ref);
    REQUIRE(t != nullptr);
    EXPECT_EQ(t->data.var.name[0], '_');
}

TEST("make_compound stores arity and functor")
{
    TermArena a = make_arena();
    AtomTable &t = fresh_atoms();
    AtomId f    = atom_intern(&t, "parent");
    AtomId alice = atom_intern(&t, "alice");
    AtomId bob   = atom_intern(&t, "bob");
    TermRef args[2] = { term_make_atom(&a, alice), term_make_atom(&a, bob) };
    TermRef ref = term_make_compound(&a, f, 2U, args);
    REQUIRE(ref != TERM_REF_INVALID);
    const Term *term = term_get(&a, ref);
    REQUIRE(term != nullptr);
    EXPECT_EQ(term->kind, TERM_KIND_COMPOUND);
    EXPECT_EQ(term->data.compound.arity, 2U);
    EXPECT_EQ(term->data.compound.functor, f);
}

TEST("term_arg retrieves correct argument refs")
{
    TermArena a = make_arena();
    AtomTable &t = fresh_atoms();
    AtomId f     = atom_intern(&t, "f");
    AtomId alice = atom_intern(&t, "alice");
    AtomId bob   = atom_intern(&t, "bob");
    TermRef r0 = term_make_atom(&a, alice);
    TermRef r1 = term_make_atom(&a, bob);
    TermRef args[2] = { r0, r1 };
    TermRef comp = term_make_compound(&a, f, 2U, args);
    EXPECT_EQ(term_arg(&a, comp, 0U), r0);
    EXPECT_EQ(term_arg(&a, comp, 1U), r1);
}

TEST("term_arg returns TERM_REF_INVALID for out-of-range index")
{
    TermArena a = make_arena();
    AtomTable &t = fresh_atoms();
    AtomId f     = atom_intern(&t, "f");
    AtomId alice = atom_intern(&t, "alice");
    TermRef args[1] = { term_make_atom(&a, alice) };
    TermRef comp = term_make_compound(&a, f, 1U, args);
    EXPECT_EQ(term_arg(&a, comp, 1U), TERM_REF_INVALID);
}

TEST("term_get returns null for TERM_REF_INVALID")
{
    TermArena a = make_arena();
    EXPECT_NULL(term_get(&a, TERM_REF_INVALID));
}

TEST("term_get returns null for out-of-range ref")
{
    TermArena a = make_arena();
    EXPECT_NULL(term_get(&a, 9999U));
}

TEST("make_compound rejects null args when arity > 0")
{
    TermArena a = make_arena();
    AtomTable &t = fresh_atoms();
    AtomId f = atom_intern(&t, "f");
    EXPECT_EQ(term_make_compound(&a, f, 1U, nullptr), TERM_REF_INVALID);
}

TEST("multiple terms accumulate in arena with sequential refs")
{
    TermArena a = make_arena();
    AtomTable &t = fresh_atoms();
    AtomId a1 = atom_intern(&t, "a");
    AtomId a2 = atom_intern(&t, "b");
    TermRef r1 = term_make_atom(&a, a1);
    TermRef r2 = term_make_atom(&a, a2);
    EXPECT_EQ(r2, r1 + 1U); /* refs are 1-based sequential */
    EXPECT_EQ(a.count, 2U);
}

int main() { return epilog_test::run_all(); }
