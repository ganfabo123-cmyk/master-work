/*
 * test_variables.cpp — Unit tests for the variable registry.
 */

#include "test_framework.hpp"
#include "../include/variables.hpp"

static VarRegistry make_reg()
{
    VarRegistry r;
    var_registry_init(&r);
    return r;
}

TEST("var_registry_init zeroes count")
{
    VarRegistry r;
    var_registry_init(&r);
    EXPECT_EQ(var_count(&r), 0U);
}

TEST("var_registry_init rejects null")
{
    EXPECT_EQ(var_registry_init(nullptr), -1);
}

TEST("var_alloc returns valid id")
{
    VarRegistry r = make_reg();
    VarId id = var_alloc(&r, "X");
    EXPECT_NE(id, VAR_ID_INVALID);
}

TEST("var_alloc increments count")
{
    VarRegistry r = make_reg();
    var_alloc(&r, "X");
    var_alloc(&r, "Y");
    EXPECT_EQ(var_count(&r), 2U);
}

TEST("var_alloc rejects null name")
{
    VarRegistry r = make_reg();
    EXPECT_EQ(var_alloc(&r, nullptr), VAR_ID_INVALID);
}

TEST("var_alloc each call produces unique id")
{
    VarRegistry r = make_reg();
    VarId a = var_alloc(&r, "X");
    VarId b = var_alloc(&r, "X"); /* same name is allowed — fresh var */
    EXPECT_NE(a, b);
}

TEST("fresh variable walks as TERM_UNBOUND")
{
    VarRegistry r  = make_reg();
    VarId       id = var_alloc(&r, "X");
    WalkResult  wr = var_walk(&r, id);
    EXPECT_EQ(wr.tag, TERM_UNBOUND);
    EXPECT_EQ(wr.root_id, id);
}

TEST("var_bind_term stores TERM_TERMREF binding")
{
    VarRegistry r  = make_reg();
    VarId       id = var_alloc(&r, "X");
    EXPECT_EQ(var_bind_term(&r, id, 42U), 0);
    WalkResult wr = var_walk(&r, id);
    EXPECT_EQ(wr.tag, TERM_TERMREF);
    EXPECT_EQ(wr.value.term_ref, 42U);
}

TEST("var_bind_term rejects already-bound variable")
{
    VarRegistry r  = make_reg();
    VarId       id = var_alloc(&r, "X");
    var_bind_term(&r, id, 1U);
    EXPECT_EQ(var_bind_term(&r, id, 2U), -1);
}

TEST("var_bind_term rejects zero TermRef (TERM_REF_INVALID)")
{
    VarRegistry r  = make_reg();
    VarId       id = var_alloc(&r, "X");
    EXPECT_EQ(var_bind_term(&r, id, TERM_REF_INVALID), -1);
}

TEST("var_bind_var creates TERM_VAR chain")
{
    VarRegistry r = make_reg();
    VarId x = var_alloc(&r, "X");
    VarId y = var_alloc(&r, "Y");
    EXPECT_EQ(var_bind_var(&r, x, y), 0);
    WalkResult wr = var_walk(&r, x);
    EXPECT_EQ(wr.tag, TERM_UNBOUND); /* Y is also unbound, chain ends there */
    EXPECT_EQ(wr.root_id, y);
}

TEST("var_bind_var to self is a no-op")
{
    VarRegistry r  = make_reg();
    VarId       id = var_alloc(&r, "X");
    EXPECT_EQ(var_bind_var(&r, id, id), 0);
    EXPECT_EQ(var_walk(&r, id).tag, TERM_UNBOUND);
}

TEST("var_bind_atom stores TERM_ATOM binding")
{
    VarRegistry r      = make_reg();
    VarId       id     = var_alloc(&r, "X");
    const AtomId atom  = 7U;
    EXPECT_EQ(var_bind_atom(&r, id, atom), 0);
    WalkResult wr = var_walk(&r, id);
    EXPECT_EQ(wr.tag, TERM_ATOM);
    EXPECT_EQ(wr.value.atom_id, atom);
}

TEST("var_walk follows var→var chain to termref")
{
    VarRegistry r = make_reg();
    VarId x = var_alloc(&r, "X");
    VarId y = var_alloc(&r, "Y");
    var_bind_var(&r, x, y);
    var_bind_term(&r, y, 99U);
    WalkResult wr = var_walk(&r, x);
    EXPECT_EQ(wr.tag, TERM_TERMREF);
    EXPECT_EQ(wr.value.term_ref, 99U);
}

TEST("var_reset clears all bindings")
{
    VarRegistry r  = make_reg();
    VarId       id = var_alloc(&r, "X");
    var_bind_term(&r, id, 5U);
    var_reset(&r);
    EXPECT_EQ(var_count(&r), 0U);
}

TEST("var_walk on invalid id returns TERM_UNBOUND with invalid root")
{
    VarRegistry r  = make_reg();
    WalkResult  wr = var_walk(&r, VAR_ID_INVALID);
    EXPECT_EQ(wr.tag, TERM_UNBOUND);
    EXPECT_EQ(wr.root_id, VAR_ID_INVALID);
}

TEST("var_count returns 0 for null")
{
    EXPECT_EQ(var_count(nullptr), 0U);
}

int main() { return epilog_test::run_all(); }
