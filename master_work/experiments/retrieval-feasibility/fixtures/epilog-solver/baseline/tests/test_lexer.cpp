/*
 * test_lexer.cpp — Unit tests for the tokenizer.
 */

#include "test_framework.hpp"
#include "../include/lexer.hpp"

static TokenList lex_str(const char *src)
{
    TokenList out;
    lex(src, &out);
    return out;
}

/* Shorthand: kind of the n-th token. */
static TokenKind kind(const TokenList &tl, uint32_t n)
{
    return tl.items[n].kind;
}

static const char *text(const TokenList &tl, uint32_t n)
{
    return tl.items[n].text;
}

/* ---- Basic token kinds --------------------------------------------------- */

TEST("lex empty string produces only EOF")
{
    TokenList tl = lex_str("");
    EXPECT_EQ(tl.count, 1U);
    EXPECT_EQ(kind(tl, 0), TOK_EOF);
}

TEST("lex atom: lowercase identifier")
{
    TokenList tl = lex_str("alice");
    REQUIRE(tl.count >= 2U);
    EXPECT_EQ(kind(tl, 0), TOK_ATOM);
    EXPECT_EQ(strcmp(text(tl, 0), "alice"), 0);
}

TEST("lex variable: uppercase initial")
{
    TokenList tl = lex_str("X");
    REQUIRE(tl.count >= 2U);
    EXPECT_EQ(kind(tl, 0), TOK_VAR);
    EXPECT_EQ(strcmp(text(tl, 0), "X"), 0);
}

TEST("lex variable: underscore initial")
{
    TokenList tl = lex_str("_Anon");
    REQUIRE(tl.count >= 2U);
    EXPECT_EQ(kind(tl, 0), TOK_VAR);
}

TEST("lex integer")
{
    TokenList tl = lex_str("42");
    REQUIRE(tl.count >= 2U);
    EXPECT_EQ(kind(tl, 0), TOK_INT);
    EXPECT_EQ(tl.items[0].int_val, 42);
}

TEST("lex single-quoted atom preserves content")
{
    TokenList tl = lex_str("'hello world'");
    REQUIRE(tl.count >= 2U);
    EXPECT_EQ(kind(tl, 0), TOK_ATOM);
    EXPECT_EQ(strcmp(text(tl, 0), "hello world"), 0);
}

TEST("lex neck operator :-")
{
    TokenList tl = lex_str(":-");
    EXPECT_EQ(kind(tl, 0), TOK_NECK);
}

TEST("lex query operator ?-")
{
    TokenList tl = lex_str("?-");
    EXPECT_EQ(kind(tl, 0), TOK_QUERY);
}

TEST("lex dot terminator")
{
    TokenList tl = lex_str("foo. ");
    /* foo, dot, EOF */
    REQUIRE(tl.count >= 3U);
    EXPECT_EQ(kind(tl, 0), TOK_ATOM);
    EXPECT_EQ(kind(tl, 1), TOK_DOT);
}

TEST("lex cut !")
{
    TokenList tl = lex_str("!");
    EXPECT_EQ(kind(tl, 0), TOK_CUT);
}

TEST("lex semicolon ;")
{
    TokenList tl = lex_str(";");
    EXPECT_EQ(kind(tl, 0), TOK_SEMI);
}

TEST("lex pipe |")
{
    TokenList tl = lex_str("|");
    EXPECT_EQ(kind(tl, 0), TOK_PIPE);
}

TEST("lex equals operator =")
{
    TokenList tl = lex_str("=");
    EXPECT_EQ(kind(tl, 0), TOK_OP);
    EXPECT_EQ(strcmp(text(tl, 0), "="), 0);
}

TEST("lex not-equals \\=")
{
    TokenList tl = lex_str("\\=");
    EXPECT_EQ(kind(tl, 0), TOK_OP);
    EXPECT_EQ(strcmp(text(tl, 0), "\\="), 0);
}

/* ---- Compound token sequences -------------------------------------------- */

TEST("lex parent(alice, bob).")
{
    TokenList tl = lex_str("parent(alice, bob).");
    /*  0:ATOM 1:LPAREN 2:ATOM 3:COMMA 4:ATOM 5:RPAREN 6:DOT 7:EOF */
    REQUIRE(tl.count >= 7U);
    EXPECT_EQ(kind(tl, 0), TOK_ATOM);
    EXPECT_EQ(kind(tl, 1), TOK_LPAREN);
    EXPECT_EQ(kind(tl, 2), TOK_ATOM);
    EXPECT_EQ(kind(tl, 3), TOK_COMMA);
    EXPECT_EQ(kind(tl, 4), TOK_ATOM);
    EXPECT_EQ(kind(tl, 5), TOK_RPAREN);
    EXPECT_EQ(kind(tl, 6), TOK_DOT);
}

TEST("lex ?- grandparent(X, Y).")
{
    TokenList tl = lex_str("?- grandparent(X, Y).");
    EXPECT_EQ(kind(tl, 0), TOK_QUERY);
    EXPECT_EQ(kind(tl, 1), TOK_ATOM);
    EXPECT_EQ(kind(tl, 2), TOK_LPAREN);
    EXPECT_EQ(kind(tl, 3), TOK_VAR);
}

/* ---- Whitespace and comments --------------------------------------------- */

TEST("lex skips whitespace between tokens")
{
    TokenList tl = lex_str("  foo   bar  ");
    EXPECT_EQ(kind(tl, 0), TOK_ATOM);
    EXPECT_EQ(kind(tl, 1), TOK_ATOM);
}

TEST("lex skips % line comments")
{
    TokenList tl = lex_str("alice. % this is a comment\nbob.");
    EXPECT_EQ(kind(tl, 0), TOK_ATOM);
    EXPECT_EQ(strcmp(text(tl, 0), "alice"), 0);
    EXPECT_EQ(kind(tl, 2), TOK_ATOM);
    EXPECT_EQ(strcmp(text(tl, 2), "bob"), 0);
}

TEST("lex skips /* block comments */")
{
    TokenList tl = lex_str("a /* skip this */ b.");
    EXPECT_EQ(kind(tl, 0), TOK_ATOM);
    EXPECT_EQ(strcmp(text(tl, 0), "a"), 0);
    EXPECT_EQ(kind(tl, 1), TOK_ATOM);
    EXPECT_EQ(strcmp(text(tl, 1), "b"), 0);
}

/* ---- Line tracking ------------------------------------------------------- */

TEST("lex tracks line numbers across newlines")
{
    TokenList tl = lex_str("a.\nb.");
    EXPECT_EQ(tl.items[0].line, 1U);
    EXPECT_EQ(tl.items[2].line, 2U);
}

/* ---- Null / error guard -------------------------------------------------- */

TEST("lex returns -1 for null src")
{
    TokenList tl;
    EXPECT_EQ(lex(nullptr, &tl), -1);
}

TEST("lex returns -1 for null out")
{
    EXPECT_EQ(lex("foo.", nullptr), -1);
}

int main() { return epilog_test::run_all(); }
