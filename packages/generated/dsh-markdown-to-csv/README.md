English | [中文](README.zh.md)

# @deepseek-ai/dsh-markdown-to-csv

Convert a markdown table into a downloadable CSV file.

The plugin registers one tool, `markdown_to_csv`. The calling agent does the
normalization: the user pastes raw markdown (which may be malformed — broken
pipe alignment, missing header delimiter rows, inconsistent column counts,
surrounding prose), the agent repairs it into a clean markdown table as part
of its normal reply, and then calls the tool with that table. The tool parses
the table locally (no extra model work), serializes RFC 4180 CSV (CRLF
records, quoted fields, a UTF-8 BOM so Excel opens non-ASCII text correctly),
and serves it over a token-gated route on the web server.

The tool returns the download URL; the agent presents it as a clickable link.
The link works only in the dsh web GUI, because the browser-side markdown
renderer blocks non-http(s) destinations.

## Usage

Load the plugin in `dsh web`:

```sh
pnpm dsh web --patch ./packages/generated/dsh-markdown-to-csv/cordis.yml
```

Open `http://127.0.0.1:3080`, paste a markdown table, and ask for the CSV.
The agent calls `markdown_to_csv` with the normalized table and replies with
a download link.

### Configuration

```yaml
plugins:
  markdown-to-csv:
    downloadTtlSeconds: 3600   # how long a download link stays valid
    maxPendingDownloads: 128   # cap before oldest-first eviction
```

All fields are optional; these are the defaults.

### Tool: markdown_to_csv

Inputs:

- `markdown` (required): the normalized markdown table — a header row with
  pipe-separated cells, an optional delimiter row, then the data rows.
- `filename` (optional, default `table.csv`): the served filename, sanitized
  to a safe basename with a `.csv` extension.

Outputs (`filename`, `downloadUrl`, `rowCount`, `columnCount`). The tool
fails loudly when the text contains no pipe-bearing table, or when a data row
has more cells than the header; short rows are padded with empty cells.

## Model Experience

### Plugin interaction

#### What the model sees

The `markdown_to_csv` tool schema (required `markdown`, optional `filename`)
and, per call, a rendered result summarizing the row and column counts plus
the plain download URL. The URL is delivered as text; the agent's reply turns
it into a markdown link.

The plugin performs no model work of its own: it parses the markdown locally,
so the tool result is the only text the model sees from the conversion.

#### Token effect

No extra provider calls. The tool result adds only the short rendered line
(`N rows × M columns ... URL`) to the agent's request context.

#### KV Cache effect

None: the plugin never issues a provider request, so the request prefix is
unaffected.

## Download route

Each conversion stores one BOM-prefixed CSV body in memory under a
`crypto.randomUUID()` token. The route prefix is
`/api/md-table-csv/<token>` on the composed `ctx.webServer`; responses carry
`Content-Type: text/csv; charset=utf-8`, `Content-Disposition: attachment`
with an ASCII fallback and an RFC 5987 UTF-8 filename, `Content-Length`, and
`Cache-Control: no-store`. Unknown or expired tokens answer 404. Expired
entries are removed on access, and the store evicts the oldest entries beyond
`maxPendingDownloads`. Nothing is written to disk.

## Known Limitations and Deferred Work

- The download link requires the web server composed in the same process; a
  headless composition without `@deepseek-ai/dsh-host-webserver` fails each
  call loudly rather than falling back to writing files.
- The tool parses only the first contiguous run of pipe-bearing lines; the
  calling agent must pass a single table. Rows longer than the header fail
  loudly so the agent can re-align and retry.
- Cell content cannot span physical lines (markdown tables cannot either):
  the calling agent must join or escape embedded newlines before invoking the
  tool.
- The served CSV lives only in process memory: the link dies with the
  process and after `downloadTtlSeconds`, and it is not durable across
  restarts.
- The download route is not a general file server: it serves exactly the
  CSVs this plugin created.