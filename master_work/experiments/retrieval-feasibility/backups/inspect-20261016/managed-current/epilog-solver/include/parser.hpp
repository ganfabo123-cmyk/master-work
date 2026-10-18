/*
 * parser.hpp — Clause and query parser for Epilog.
 * JPL rules: no recursion, bounded loops, no post-init malloc.
 */

#pragma once

#include <cstdint>
#include "lexer.hpp"
#include "terms.hpp"
#include "atoms.hpp"
#include "variables.hpp"

constexpr uint32_t PARSER_MAX_BODY_GOALS = 256U;
constexpr uint32_t PARSER_MAX_CLAUSES    = 512U;

struct ParsedClause {
    TermRef  head       = TERM_REF_INVALID;
    TermRef  body[PARSER_MAX_BODY_GOALS] = {};
    uint32_t body_len   = 0U;
};

struct ParsedQuery {
    TermRef  goals[PARSER_MAX_BODY_GOALS] = {};
    uint32_t goal_count = 0U;
};

enum ParseResult : uint8_t {
    PARSE_OK = 0,
    PARSE_EOF,
    PARSE_ERR_SYNTAX,
    PARSE_ERR_OVERFLOW,
    PARSE_ERR_ARGS
};

struct Parser {
    const TokenList *tokens    = nullptr;
    uint32_t         pos       = 0U;
    TermArena       *arena     = nullptr;
    AtomTable       *atoms     = nullptr;
    VarRegistry     *vars      = nullptr;
    char             error_msg[128] = {};
};

int         parser_init(Parser *p, const TokenList *tokens, TermArena *arena,
                        AtomTable *atoms, VarRegistry *vars);
ParseResult parser_next_clause(Parser *p, ParsedClause *out);
ParseResult parser_query(Parser *p, ParsedQuery *out);
