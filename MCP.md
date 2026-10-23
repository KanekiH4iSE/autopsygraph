# AutopsyGraph as an MCP server

Any MCP client — Claude Code, Codex, OpenCode, Antigravity, Cursor, VS Code, Claude Desktop — can ask the forensic graph
*why an agent run failed*, *how often it recurs* and, **with the user's explicit approval**, apply the fix.

Transport: **stdio**. Command (Windows paths of this machine — adjust for yours):

```
C:\Users\User\projects\autopsygraph\.venv\Scripts\python.exe C:\Users\User\projects\autopsygraph\mcp_server.py
```

The server reads Neo4j credentials from the project `.env`.

## Tools

| Tool | What it does | Writes? |
|---|---|---|
| `list_failed_runs` | Failed runs with task, request, why they failed, stored diagnosis | no |
| `get_run(run_id)` | Request, answer, step timeline (tools, args, errors, evidence incl. stale), claims vs ground truth | no |
| `diagnose_run(run_id)` | Root-cause step, pattern, confidence, evidence trail, should-have, fix, symptoms, fleet context | stores `:Diagnosis` (idempotent) |
| `fleet_report` | Ignored errors ("8 runs, ignored in 7"), failures by pattern, failing tools, accuracy | no |
| `apply_fix(run_id, pattern, approve)` | **Only with `approve=true` after the user agrees.** Re-runs the agent with the guardrail, stores `<run>_fix` (`REPLAY_OF`), re-checks it | adds a replay run |
| `query_graph(cypher, limit)` | Read-only Cypher (writes are rejected) | no |

Try: *"Use autopsygraph: which tool failure is ignored most often, and why did run_017 fail? Propose the fix."*

## Client setup

**Claude Code** (registered on this machine ✔ connected)
```bash
claude mcp add autopsygraph --scope user -- "C:\Users\User\projects\autopsygraph\.venv\Scripts\python.exe" "C:\Users\User\projects\autopsygraph\mcp_server.py"
```

**Codex CLI** (registered on this machine) — `~/.codex/config.toml`
```toml
[mcp_servers.autopsygraph]
command = 'C:\Users\User\projects\autopsygraph\.venv\Scripts\python.exe'
args = ['C:\Users\User\projects\autopsygraph\mcp_server.py']
startup_timeout_sec = 60
```

**OpenCode** (registered on this machine ✔ connected) — `~/.config/opencode/opencode.json`
```json
{ "mcp": { "autopsygraph": { "type": "local", "enabled": true,
  "command": ["C:\\Users\\User\\projects\\autopsygraph\\.venv\\Scripts\\python.exe",
              "C:\\Users\\User\\projects\\autopsygraph\\mcp_server.py"] } } }
```

**Antigravity** — Agent panel → `…` → *MCP Servers* → *Manage MCP Servers* → *View raw config*, add:
```json
{ "mcpServers": { "autopsygraph": {
  "command": "C:\\Users\\User\\projects\\autopsygraph\\.venv\\Scripts\\python.exe",
  "args": ["C:\\Users\\User\\projects\\autopsygraph\\mcp_server.py"] } } }
```

**Cursor** (`~/.cursor/mcp.json`) and **Claude Desktop** (`%APPDATA%\Claude\claude_desktop_config.json`) use the same
`mcpServers` block as Antigravity.

**VS Code** (`.vscode/mcp.json`)
```json
{ "servers": { "autopsygraph": { "type": "stdio",
  "command": "C:\\Users\\User\\projects\\autopsygraph\\.venv\\Scripts\\python.exe",
  "args": ["C:\\Users\\User\\projects\\autopsygraph\\mcp_server.py"] } } }
```

## Safety

- Read tools are annotated read-only; `query_graph` runs in a read transaction, so the database rejects writes.
- `apply_fix` refuses to act without `approve=true` and returns `approval_required` with the guardrail to show the user.
  MCP clients additionally ask the user before every tool call.
- Replays never modify the original run and are excluded from run lists and fleet statistics.
