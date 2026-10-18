/*
 * parser.cpp — Clause and query parser.
 * JPL rules: no recursion, bounded loops, no post-init malloc.
 */

#include "../include/parser.hpp"
#include <cstring>
#include <cassert>
#include <cstdio>

static const Token *peek(const Parser *p)
{
    assert(p != nullptr && p->tokens != nullptr);
    if (p->pos >= p->tokens->count) {
        return &p->tokens->items[p->tokens->count - 1U];
    }
    return &p->tokens->items[p->pos];
}

static const Token *advance(Parser *p)
{
    const Token *t = peek(p);
    if (t->kind != TOK_EOF) { p->pos++; }
    return t;
}

static const Token *expect(Parser *p, TokenKind kind)
{
    const Token *t = peek(p);
    if (t->kind != kind) {
        snprintf(p->error_msg, sizeof(p->error_msg),
                 "line %u: expected %s, got %s '%s'",
                 t->line, tok_kind_name(kind), tok_kind_name(t->kind), t->text);
        return nullptr;
    }
    return advance(p);
}

/* parse_term — parse one term; returns TERM_REF_INVALID on error. */
static TermRef parse_term(Parser *p)
{
    const Token *t   = peek(p);
    TermRef      ref = TERM_REF_INVALID;

    /* integer */
    if (t->kind == TOK_INT) {
        advance(p);
        ref = term_make_int(p->arena, t->int_val);
    }
    /* variable */
    else if (t->kind == TOK_VAR) {
        advance(p);
        VarId vid = VAR_ID_INVALID;
        for (uint32_t k = 0U; k < p->vars->count; ++k) {
            if (strncmp(p->vars->entries[k].name, t->text, VAR_NAME_MAX_LEN) == 0) {
                vid = p->vars->entries[k].id;
                break;
            }
        }
        if (vid == VAR_ID_INVALID) { vid = var_alloc(p->vars, t->text); }
        if (vid == VAR_ID_INVALID) {
            snprintf(p->error_msg, sizeof(p->error_msg),
                     "line %u: variable registry full", t->line);
            return TERM_REF_INVALID;
        }
        ref = term_make_var(p->arena, vid, t->text);
    }
    /* cut */
    else if (t->kind == TOK_CUT) {
        advance(p);
        AtomId aid = atom_intern(p->atoms, "!");
        if (aid == ATOM_ID_INVALID) { return TERM_REF_INVALID; }
        ref = term_make_atom(p->arena, aid);
    }
    /* atom or compound */
    else if (t->kind == TOK_ATOM || t->kind == TOK_OP) {
        const char *name = t->text;
        advance(p);
        AtomId aid = atom_intern(p->atoms, name);
        if (aid == ATOM_ID_INVALID) {
            snprintf(p->error_msg, sizeof(p->error_msg),
                     "line %u: atom table full", t->line);
            return TERM_REF_INVALID;
        }

        if (peek(p)->kind == TOK_LPAREN) {
            TermRef args[TERM_MAX_ARITY];
            uint8_t arity = 0U;
            advance(p);
            if (peek(p)->kind != TOK_RPAREN) {
                for (uint32_t a = 0U; a < static_cast<uint32_t>(TERM_MAX_ARITY); ++a) {
                    TermRef arg = parse_term(p);
                    if (arg == TERM_REF_INVALID) { return TERM_REF_INVALID; }
                    args[arity++] = arg;
                    if (peek(p)->kind != TOK_COMMA) { break; }
                    advance(p);
                }
            }
            if (expect(p, TOK_RPAREN) == nullptr) { return TERM_REF_INVALID; }
            ref = term_make_compound(p->arena, aid, arity, args);
        } else {
            ref = term_make_atom(p->arena, aid);
        }
    }
    else {
        snprintf(p->error_msg, sizeof(p->error_msg),
                 "line %u: unexpected token %s '%s'",
                 t->line, tok_kind_name(t->kind), t->text);
        return TERM_REF_INVALID;
    }

    if (ref == TERM_REF_INVALID) { return TERM_REF_INVALID; }

    /* infix = or \= following any primary term */
    {
        const Token *op = peek(p);
        if (op->kind == TOK_OP &&
            (strncmp(op->text, "=",  2) == 0 ||
             strncmp(op->text, "\\=", 3) == 0)) {
            char   op_name[TOKEN_TEXT_MAX + 1U];
            memcpy(op_name, op->text, TOKEN_TEXT_MAX);
            op_name[TOKEN_TEXT_MAX] = '\0';
            advance(p);

            const TermRef rhs = parse_term(p);
            if (rhs == TERM_REF_INVALID) { return TERM_REF_INVALID; }

            const AtomId op_aid = atom_intern(p->atoms, op_name);
            if (op_aid == ATOM_ID_INVALID) { return TERM_REF_INVALID; }

            const TermRef pair[2] = { ref, rhs };
            ref = term_make_compound(p->arena, op_aid, 2U, pair);
        }
    }
    return ref;
}

static ParseResult parse_term_list(Parser *p, TermRef *out, uint32_t cap,
                                   uint32_t *count)
{
    assert(p != nullptr && out != nullptr && count != nullptr);
    *count = 0U;

    for (uint32_t n = 0U; n < cap; ++n) {
        const TermRef ref = parse_term(p);
        if (ref == TERM_REF_INVALID) { return PARSE_ERR_SYNTAX; }
        out[n] = ref;
        (*count)++;
        if (peek(p)->kind != TOK_COMMA) { break; }
        advance(p);
    }

    if (*count == cap && peek(p)->kind == TOK_COMMA) { return PARSE_ERR_OVERFLOW; }
    return PARSE_OK;
}

int parser_init(Parser *p, const TokenList *tokens, TermArena *arena,
                AtomTable *atoms, VarRegistry *vars)
{
    if (p==nullptr || tokens==nullptr || arena==nullptr ||
        atoms==nullptr || vars==nullptr) { return -1; }
    memset(p, 0, sizeof(Parser));
    p->tokens = tokens;
    p->arena  = arena;
    p->atoms  = atoms;
    p->vars   = vars;
    p->pos    = 0U;
    return 0;
}

ParseResult parser_next_clause(Parser *p, ParsedClause *out)
{
    if (p == nullptr || out == nullptr) { return PARSE_ERR_ARGS; }
    memset(out, 0, sizeof(ParsedClause));
    var_reset(p->vars);

    if (peek(p)->kind == TOK_EOF) { return PARSE_EOF; }

    const TermRef head = parse_term(p);
    if (head == TERM_REF_INVALID) { return PARSE_ERR_SYNTAX; }
    out->head = head;

    if (peek(p)->kind == TOK_NECK) {
        advance(p);
        const ParseResult r = parse_term_list(p, out->body, PARSER_MAX_BODY_GOALS,
                                              &out->body_len);
        if (r != PARSE_OK) { return r; }
    }

    if (expect(p, TOK_DOT) == nullptr) { return PARSE_ERR_SYNTAX; }
    return PARSE_OK;
}

ParseResult parser_query(Parser *p, ParsedQuery *out)
{
    if (p == nullptr || out == nullptr) { return PARSE_ERR_ARGS; }
    memset(out, 0, sizeof(ParsedQuery));
    var_reset(p->vars);

    if (expect(p, TOK_QUERY) == nullptr) { return PARSE_ERR_SYNTAX; }

    const ParseResult r = parse_term_list(p, out->goals, PARSER_MAX_BODY_GOALS,
                                          &out->goal_count);
    if (r != PARSE_OK) { return r; }

    if (expect(p, TOK_DOT) == nullptr) { return PARSE_ERR_SYNTAX; }
    return PARSE_OK;
}
