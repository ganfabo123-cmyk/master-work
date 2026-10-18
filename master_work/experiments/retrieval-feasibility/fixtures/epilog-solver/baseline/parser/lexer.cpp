/*
 * lexer.cpp — Tokenizer implementation.
 * JPL rules: no recursion, bounded loop, no post-init malloc.
 */

#include "../include/lexer.hpp"
#include <cstring>
#include <cassert>
#include <cstdint>

static bool is_alpha(char c)  { return (c>='a'&&c<='z')||(c>='A'&&c<='Z'); }
static bool is_digit(char c)  { return c>='0' && c<='9'; }
static bool is_lower(char c)  { return c>='a' && c<='z'; }
static bool is_upper(char c)  { return c>='A' && c<='Z'; }
static bool is_alnum(char c)  { return is_alpha(c) || is_digit(c) || c=='_'; }
static bool is_space(char c)  { return c==' '||c=='\t'||c=='\r'||c=='\n'; }

static bool is_op_char(char c)
{
    return c=='='||c=='\\'||c=='+'||c=='-'||c=='*'||c=='/'||
           c=='<'||c=='>'||c=='@'||c=='#'||c=='^'||c=='~';
}

static int append_token(TokenList *out, TokenKind kind,
                        const char *text, int32_t int_val, uint32_t line)
{
    assert(out != nullptr);
    if (out->count >= TOKEN_LIST_CAPACITY) { return -1; }

    Token *t   = &out->items[out->count];
    t->kind    = kind;
    t->int_val = int_val;
    t->line    = line;

    if (text != nullptr) {
        const size_t len = strnlen(text, TOKEN_TEXT_MAX);
        memcpy(t->text, text, len);
        t->text[len] = '\0';
    } else {
        t->text[0] = '\0';
    }
    out->count++;
    return 0;
}

int lex(const char *src, TokenList *out)
{
    if (src == nullptr || out == nullptr) { return -1; }

    memset(out, 0, sizeof(TokenList));
    const uint32_t len  = static_cast<uint32_t>(strnlen(src, 1U << 20));
    uint32_t       line = 1U;
    uint32_t       i    = 0U;
    char           buf[TOKEN_TEXT_MAX + 1U];

    while (i < len) {
        const char c = src[i];

        if (is_space(c)) { if (c == '\n') { line++; } i++; continue; }

        /* line comment */
        if (c == '%') { while (i < len && src[i] != '\n') { i++; } continue; }

        /* block comment */
        if (c == '/' && i + 1U < len && src[i + 1U] == '*') {
            uint32_t depth = 1U;
            i += 2U;
            while (i + 1U < len && depth > 0U) {
                if (src[i] == '\n')                     { line++; }
                if (src[i]=='*' && src[i+1U]=='/') { depth--; i+=2U; continue; }
                if (src[i]=='/' && src[i+1U]=='*') { depth++; i+=2U; continue; }
                i++;
            }
            continue;
        }

        /* atom: lowercase-initial */
        if (is_lower(c)) {
            uint32_t bp = 0U;
            while (i < len && is_alnum(src[i]) && bp < TOKEN_TEXT_MAX) { buf[bp++] = src[i++]; }
            buf[bp] = '\0';
            if (append_token(out, TOK_ATOM, buf, 0, line) < 0) { return -1; }
            continue;
        }

        /* variable: uppercase or underscore */
        if (is_upper(c) || c == '_') {
            uint32_t bp = 0U;
            while (i < len && is_alnum(src[i]) && bp < TOKEN_TEXT_MAX) { buf[bp++] = src[i++]; }
            buf[bp] = '\0';
            if (append_token(out, TOK_VAR, buf, 0, line) < 0) { return -1; }
            continue;
        }

        /* integer */
        if (is_digit(c)) {
            int32_t  val = 0;
            uint32_t bp  = 0U;
            while (i < len && is_digit(src[i]) && bp < TOKEN_TEXT_MAX) {
                val = val * 10 + static_cast<int32_t>(src[i] - '0');
                buf[bp++] = src[i++];
            }
            buf[bp] = '\0';
            if (append_token(out, TOK_INT, buf, val, line) < 0) { return -1; }
            continue;
        }

        /* single-quoted atom */
        if (c == '\'') {
            uint32_t bp = 0U;
            i++;
            while (i < len && src[i] != '\'' && bp < TOKEN_TEXT_MAX) {
                if (src[i] == '\n') { line++; }
                buf[bp++] = src[i++];
            }
            if (i < len) { i++; }
            buf[bp] = '\0';
            if (append_token(out, TOK_ATOM, buf, 0, line) < 0) { return -1; }
            continue;
        }

        /* two-character tokens */
        if (c == ':' && i+1U < len && src[i+1U] == '-') { append_token(out, TOK_NECK,  ":-", 0, line); i+=2U; continue; }
        if (c == '?' && i+1U < len && src[i+1U] == '-') { append_token(out, TOK_QUERY, "?-", 0, line); i+=2U; continue; }
        if (c == '\\' && i+1U < len && src[i+1U] == '=') { append_token(out, TOK_OP, "\\=", 0, line); i+=2U; continue; }

        /* operator sequences */
        if (is_op_char(c)) {
            uint32_t bp = 0U;
            while (i < len && is_op_char(src[i]) && bp < TOKEN_TEXT_MAX) { buf[bp++] = src[i++]; }
            buf[bp] = '\0';
            if (append_token(out, TOK_OP, buf, 0, line) < 0) { return -1; }
            continue;
        }

        /* single-character punctuation */
        switch (c) {
            case '(': append_token(out, TOK_LPAREN, "(", 0, line); break;
            case ')': append_token(out, TOK_RPAREN, ")", 0, line); break;
            case ',': append_token(out, TOK_COMMA,  ",", 0, line); break;
            case '.':
                /* '.' always terminates a clause in this dialect. No operator
                 * spelling contains '.', so it is never part of an operator
                 * sequence; lexing it as TOK_OP whenever the next character is
                 * non-space broke clauses like "a.b. c." after concatenation. */
                append_token(out, TOK_DOT, ".", 0, line);
                break;
            case '|': append_token(out, TOK_PIPE, "|", 0, line); break;
            case ';': append_token(out, TOK_SEMI, ";", 0, line); break;
            case '!': append_token(out, TOK_CUT,  "!", 0, line); break;
            default: {
                char err[2] = { c, '\0' };
                append_token(out, TOK_ERROR, err, 0, line);
                return -1;
            }
        }
        i++;
    }

    append_token(out, TOK_EOF, "", 0, line);
    return 0;
}

const char *tok_kind_name(TokenKind k)
{
    switch (k) {
        case TOK_ATOM:   return "atom";
        case TOK_VAR:    return "variable";
        case TOK_INT:    return "integer";
        case TOK_LPAREN: return "'('";
        case TOK_RPAREN: return "')'";
        case TOK_COMMA:  return "','";
        case TOK_DOT:    return "'.'";
        case TOK_NECK:   return "':-'";
        case TOK_QUERY:  return "'?-'";
        case TOK_PIPE:   return "'|'";
        case TOK_SEMI:   return "';'";
        case TOK_CUT:    return "'!'";
        case TOK_OP:     return "operator";
        case TOK_EOF:    return "EOF";
        case TOK_ERROR:  return "error";
        default:         return "unknown";
    }
}
