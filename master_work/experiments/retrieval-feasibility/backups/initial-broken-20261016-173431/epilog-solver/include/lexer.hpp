/*
 * lexer.hpp — Tokenizer for the Epilog source language.
 * JPL rules: no recursion, bounded array, no post-init malloc.
 */

#pragma once

#include <cstdint>
#include <cstddef>

constexpr uint32_t TOKEN_LIST_CAPACITY = 2048U;
constexpr uint32_t TOKEN_TEXT_MAX      = 63U;

enum TokenKind : uint8_t {
    TOK_ATOM = 0,
    TOK_VAR,
    TOK_INT,
    TOK_LPAREN,
    TOK_RPAREN,
    TOK_COMMA,
    TOK_DOT,
    TOK_NECK,
    TOK_QUERY,
    TOK_PIPE,
    TOK_SEMI,
    TOK_CUT,
    TOK_OP,
    TOK_EOF,
    TOK_ERROR
};

struct Token {
    TokenKind kind    = TOK_EOF;
    char      text[TOKEN_TEXT_MAX + 1U] = {};
    int32_t   int_val = 0;
    uint32_t  line    = 1U;
};

struct TokenList {
    Token    items[TOKEN_LIST_CAPACITY];
    uint32_t count = 0U;
};

/* lex — tokenise *src into *out. Returns 0 on success, -1 on error. */
int lex(const char *src, TokenList *out);

/* tok_kind_name — human-readable name (for error messages). */
const char *tok_kind_name(TokenKind k);
