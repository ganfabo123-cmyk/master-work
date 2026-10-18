/*
 * test_atoms.cpp — Unit tests for the atom interning table.
 */

#include "test_framework.hpp"
#include "../include/atoms.hpp"

/* ---- Helpers ------------------------------------------------------------- */

/* AtomTable is ~1 MB — too large for the default Windows stack.
 * Use a single static instance re-initialised per test. */
static AtomTable &fresh_table()
{
    static AtomTable t;
    atom_table_init(&t);
    return t;
}
#define make_table() fresh_table()

/* ---- Tests --------------------------------------------------------------- */

TEST("atom_table_init zeroes count")
{
    AtomTable &t = fresh_table();
    EXPECT_EQ(atom_count(&t), 0U);
}

TEST("atom_table_init rejects null")
{
    EXPECT_EQ(atom_table_init(nullptr), -1);
}

TEST("intern returns valid id for simple atom")
{
    AtomTable t = make_table();
    AtomId id = atom_intern(&t, "alice");
    EXPECT_NE(id, ATOM_ID_INVALID);
}

TEST("intern same spelling twice returns same id")
{
    AtomTable t = make_table();
    AtomId a = atom_intern(&t, "alice");
    AtomId b = atom_intern(&t, "alice");
    EXPECT_EQ(a, b);
}

TEST("intern different spellings return different ids")
{
    AtomTable t = make_table();
    AtomId a = atom_intern(&t, "alice");
    AtomId b = atom_intern(&t, "bob");
    EXPECT_NE(a, b);
}

TEST("intern increments count")
{
    AtomTable t = make_table();
    atom_intern(&t, "alice");
    atom_intern(&t, "bob");
    atom_intern(&t, "alice"); /* duplicate — should not increment */
    EXPECT_EQ(atom_count(&t), 2U);
}

TEST("intern rejects null spelling")
{
    AtomTable t = make_table();
    EXPECT_EQ(atom_intern(&t, nullptr), ATOM_ID_INVALID);
}

TEST("intern rejects null table")
{
    EXPECT_EQ(atom_intern(nullptr, "alice"), ATOM_ID_INVALID);
}

TEST("intern rejects spelling exceeding ATOM_MAX_LEN")
{
    AtomTable t = make_table();
    char big[ATOM_MAX_LEN + 2U];
    memset(big, 'x', sizeof(big) - 1U);
    big[sizeof(big) - 1U] = '\0';
    EXPECT_EQ(atom_intern(&t, big), ATOM_ID_INVALID);
}

TEST("lookup finds interned atom")
{
    AtomTable t = make_table();
    AtomId interned = atom_intern(&t, "carol");
    AtomId found    = atom_lookup(&t, "carol");
    EXPECT_EQ(interned, found);
}

TEST("lookup returns invalid for absent atom")
{
    AtomTable t = make_table();
    EXPECT_EQ(atom_lookup(&t, "nobody"), ATOM_ID_INVALID);
}

TEST("lookup does not insert")
{
    AtomTable t = make_table();
    atom_lookup(&t, "ghost");
    EXPECT_EQ(atom_count(&t), 0U);
}

TEST("spelling round-trips through intern")
{
    AtomTable   t  = make_table();
    AtomId      id = atom_intern(&t, "hello");
    const char *sp = atom_spelling(&t, id);
    REQUIRE(sp != nullptr);
    EXPECT_EQ(strcmp(sp, "hello"), 0);
}

TEST("spelling returns null for ATOM_ID_INVALID")
{
    AtomTable t = make_table();
    EXPECT_NULL(atom_spelling(&t, ATOM_ID_INVALID));
}

TEST("spelling returns null for out-of-range id")
{
    AtomTable t = make_table();
    EXPECT_NULL(atom_spelling(&t, 9999U));
}

TEST("intern many atoms — stress collision handling")
{
    AtomTable t = make_table();
    char buf[16];
    for (uint32_t i = 0U; i < 100U; ++i) {
        snprintf(buf, sizeof(buf), "atom_%u", i);
        AtomId id = atom_intern(&t, buf);
        EXPECT_NE(id, ATOM_ID_INVALID);
    }
    EXPECT_EQ(atom_count(&t), 100U);

    /* verify all spellings still round-trip */
    for (uint32_t i = 0U; i < 100U; ++i) {
        snprintf(buf, sizeof(buf), "atom_%u", i);
        AtomId id = atom_lookup(&t, buf);
        EXPECT_NE(id, ATOM_ID_INVALID);
        const char *sp = atom_spelling(&t, id);
        REQUIRE(sp != nullptr);
        EXPECT_EQ(strcmp(sp, buf), 0);
    }
}

TEST("intern empty string is a valid atom")
{
    AtomTable t = make_table();
    AtomId id = atom_intern(&t, "");
    EXPECT_NE(id, ATOM_ID_INVALID);
    const char *sp = atom_spelling(&t, id);
    REQUIRE(sp != nullptr);
    EXPECT_EQ(strcmp(sp, ""), 0);
}

int main() { return epilog_test::run_all(); }
