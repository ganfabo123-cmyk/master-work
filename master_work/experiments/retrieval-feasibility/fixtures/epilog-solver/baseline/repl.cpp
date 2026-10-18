/*
 * repl.cpp — Read-Eval-Print Loop.
 * JPL rules: no recursion, bounded buffers, no post-init malloc.
 */

#include "include/repl.hpp"
#include "include/lexer.hpp"
#include "include/parser.hpp"
#include "include/solver.hpp"
#include "include/builtins.hpp"

#include <cstdio>
#include <cstring>
#include <cassert>

/* ---- SolutionContext ------------------------------------------------------ */

struct SolutionContext {
    const TermArena   *arena         = nullptr;
    const VarRegistry *vars          = nullptr;
    const AtomTable   *atoms         = nullptr;
    VarId    query_vars[VAR_REGISTRY_CAPACITY]                          = {};
    char     query_var_names[VAR_REGISTRY_CAPACITY][VAR_NAME_MAX_LEN+1U] = {};
    uint32_t query_var_count = 0U;
};

static SolveSignal print_solution(SolverEnv *env,
                                  const TermRef *, uint32_t,
                                  void *userdata)
{
    auto *ctx = static_cast<SolutionContext *>(userdata);
    int any_binding = 0;

    for (uint32_t i = 0U; i < ctx->query_var_count; ++i) {
        const VarId  vid  = ctx->query_vars[i];
        const char  *name = ctx->query_var_names[i];
        if (name[0] == '_' && name[1] == '\0') { continue; }

        for (uint32_t ni = 0U; ni < env->arena->count; ++ni) {
            const Term *t = &env->arena->nodes[ni];
            if (t->kind == TERM_KIND_VAR && t->data.var.var_id == vid) {
                printf("%s = ", name);
                term_write(t->ref, env->arena, env->vars, env->atoms);
                printf("\n");
                any_binding = 1;
                break;
            }
        }
    }

    if (!any_binding) { printf("true"); }
    printf(" ; ");
    fflush(stdout);

    char ch = static_cast<char>(getchar());
    if (ch == ';') {
        while (ch != '\n' && ch != static_cast<char>(EOF)) { ch = static_cast<char>(getchar()); }
        return SOLVE_NEXT;
    }
    if (ch != '\n') {
        while (ch != '\n' && ch != static_cast<char>(EOF)) { ch = static_cast<char>(getchar()); }
    }
    return SOLVE_STOP;
}

/* ---- run_query ------------------------------------------------------------ */

static void run_query(ReplState *s, const char *src)
{
    static TokenList      tokens;
    static SolutionContext ctx;

    memset(&tokens, 0, sizeof(tokens));
    memset(&ctx,    0, sizeof(ctx));

    if (lex(src, &tokens) < 0) { fprintf(stderr, "lex error\n"); return; }

    term_arena_init(&s->query_arena);
    var_registry_init(&s->query_vars);

    Parser parser;
    if (parser_init(&parser, &tokens, &s->query_arena,
                    &s->atoms, &s->query_vars) < 0) { return; }

    ParsedQuery pq;
    if (parser_query(&parser, &pq) != PARSE_OK) {
        fprintf(stderr, "parse error: %s\n", parser.error_msg);
        return;
    }

    ctx.arena           = &s->query_arena;
    ctx.vars            = &s->query_vars;
    ctx.atoms           = &s->atoms;
    ctx.query_var_count = s->query_vars.count;
    for (uint32_t i = 0U; i < s->query_vars.count && i < VAR_REGISTRY_CAPACITY; ++i) {
        ctx.query_vars[i] = s->query_vars.entries[i].id;
        memcpy(ctx.query_var_names[i], s->query_vars.entries[i].name,
               VAR_NAME_MAX_LEN + 1U);
    }

    SolverEnv env;
    if (solver_env_init(&env, &s->query_arena, &s->clause_arena,
                        &s->query_vars, &s->clause_vars,
                        &s->atoms, &s->db) < 0) { return; }

    const uint32_t solutions = solve(&env, pq.goals, pq.goal_count,
                                     print_solution, &ctx);
    if (solutions == 0U) { printf("false.\n"); } else { printf("\n"); }
}

/* ---- load_clauses --------------------------------------------------------- */

static int load_clauses(ReplState *s, const char *src, const char *label)
{
    static TokenList tokens;
    memset(&tokens, 0, sizeof(tokens));

    if (lex(src, &tokens) < 0) {
        fprintf(stderr, "%s: lex error\n", label);
        return -1;
    }

    var_registry_init(&s->clause_vars);

    Parser parser;
    if (parser_init(&parser, &tokens, &s->clause_arena,
                    &s->atoms, &s->clause_vars) < 0) { return -1; }

    int loaded = 0;
    for (;;) {
        ParsedClause clause;
        memset(&clause, 0, sizeof(ParsedClause));
        const ParseResult pr = parser_next_clause(&parser, &clause);
        if (pr == PARSE_EOF) { break; }
        if (pr != PARSE_OK) {
            fprintf(stderr, "%s: parse error: %s\n", label, parser.error_msg);
            return -1;
        }
        if (db_assert_last(&s->db, &clause, &s->clause_arena) < 0) {
            fprintf(stderr, "%s: database full\n", label);
            return -1;
        }
        loaded++;
    }
    return loaded;
}

/* ---- Public API ----------------------------------------------------------- */

int repl_init(ReplState *s)
{
    if (s == nullptr) { return -1; }
    if (atom_table_init(&s->atoms)          < 0) { return -1; }
    if (db_init(&s->db)                     < 0) { return -1; }
    if (term_arena_init(&s->clause_arena)   < 0) { return -1; }
    if (var_registry_init(&s->clause_vars)  < 0) { return -1; }
    if (term_arena_init(&s->query_arena)    < 0) { return -1; }
    if (var_registry_init(&s->query_vars)   < 0) { return -1; }
    return 0;
}

int repl_load_file(ReplState *s, const char *path)
{
    if (s == nullptr || path == nullptr) { return -1; }

    FILE *f = nullptr;
#if defined(_MSC_VER) || defined(__clang_version__)
    if (fopen_s(&f, path, "r") != 0 || f == nullptr) {
#else
    f = fopen(path, "r");
    if (f == nullptr) {
#endif
        fprintf(stderr, "cannot open '%s'\n", path);
        return -1;
    }

    char   buf[1U << 16];
    size_t n = fread(buf, 1U, sizeof(buf) - 1U, f);
    fclose(f);
    buf[n] = '\0';

    const int result = load_clauses(s, buf, path);
    if (result >= 0) {
        printf("%% Loaded %d clause(s) from '%s'\n", result, path);
    }
    return (result >= 0) ? 0 : -1;
}

void repl_run(ReplState *s)
{
    assert(s != nullptr);
    printf("Epilog 0.1  (type 'halt.' to exit, '?- goal.' to query)\n");

    char     line[REPL_LINE_MAX];
    char     src[REPL_LINE_MAX * 8U];
    uint32_t src_len = 0U;

    for (;;) {
        printf(src_len == 0U ? "?- " : "|  ");
        fflush(stdout);

        if (fgets(line, static_cast<int>(REPL_LINE_MAX), stdin) == nullptr) {
            printf("\n");
            break;
        }

        const size_t len = strnlen(line, REPL_LINE_MAX);
        if (src_len + len >= sizeof(src) - 1U) {
            fprintf(stderr, "input too long\n");
            src_len = 0U;
            continue;
        }
        memcpy(src + src_len, line, len);
        src_len += static_cast<uint32_t>(len);
        src[src_len] = '\0';

        /* check for '.' terminator */
        bool complete = false;
        for (uint32_t i = 0U; i < src_len; ++i) {
            if (src[i] == '.' &&
                (i+1U >= src_len || src[i+1U]==' '  || src[i+1U]=='\n' ||
                 src[i+1U]=='\r' || src[i+1U]=='\t' || src[i+1U]=='\0')) {
                complete = true;
                break;
            }
        }
        if (!complete) { continue; }

        if (strncmp(src, "halt.", 5) == 0) { break; }

        if (src_len >= 2U && src[0] == '?' && src[1] == '-') {
            run_query(s, src);
            src_len = 0U;
            continue;
        }

        if (strncmp(src, "consult(", 8) == 0 ||
            strncmp(src, ":- consult(", 11) == 0) {
            const char *open  = strchr(src, '(');
            const char *close = strchr(src, ')');
            if (open != nullptr && close != nullptr && close > open + 1U) {
                char   path[256];
                size_t plen = static_cast<size_t>(close - open - 1U);
                if (plen >= sizeof(path)) { plen = sizeof(path) - 1U; }
                memcpy(path, open + 1U, plen);
                if (path[0] == '\'') {
                    memmove(path, path + 1U, plen - 1U);
                    plen--;
                    if (plen > 0U && path[plen-1U] == '\'') { plen--; }
                }
                path[plen] = '\0';
                repl_load_file(s, path);
            }
            src_len = 0U;
            continue;
        }

        load_clauses(s, src, "<stdin>");
        src_len = 0U;
    }
}
