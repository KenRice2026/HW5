# Campus Customs Multi-Agent Operations (Homework 5)

An agentic team that runs the Campus Customs shop. Open tickets (customer orders, rent, unpaid bills, discount requests) land on a board. Five AI agents work them through an MCP server over the shop database. A person watches on a React dashboard and **signs every payment**.

| Piece | Built with | Where |
|---|---|---|
| MCP server: 26 tools over the shop database | FastMCP | `mcp_server/` |
| Agent team (Boss, Inventory, Accounting, Facilities, Customer Service) plus the API | PydanticAI on Claude, FastAPI | `backend/` |
| Dashboard ("the desk") | React + Vite + TypeScript | `frontend/` |

## Project layout

```
hw5/
├── AI_prompts.md            every prompt used, by problem
├── requirements.txt         Python dependencies (pinned)
├── .env.example             environment variables (copy to .env; only ANTHROPIC_API_KEY is required)
├── .gitignore
├── .mcp.json                registers the campus-customs MCP server with Claude Code
├── README.md
├── data/
│   ├── campus_customs.db        original: read-only, the reset source
│   └── campus_customs_new.db    working copy the agents read and write
├── mcp_server/
│   ├── server.py            FastMCP server (26 tools)
│   └── README.md            tool list and the rules the tools enforce
├── backend/
│   ├── main.py              FastAPI routes for the dashboard
│   ├── models.py            Pydantic data types (AgentReport, BossDecision, AuditRecord, ...)
│   ├── prompts/             one detailed prompt per agent
│   │   ├── boss.md · inventory.md · accounting.md · facilities.md · customer_service.md
│   ├── agents/              the five agents + delegate() (full connectivity)
│   ├── config.py            model, effort, token limits, which MCP tools each agent may use
│   ├── mcp_tools.py         the shared MCP connection, filtered per role
│   ├── team.py              agent loop: run_ticket / run_board / reset
│   ├── approvals.py         human approve/reject (never available to agents)
│   ├── audit.py             appends every agent step to output/audit_trail.json
│   └── run.py               command line
├── frontend/                the React desk (see frontend/README.md)
└── output/
    ├── harness.md           tables, MCP tools, agents, routes, dashboard, safety rules, full-run results
    ├── mcp_smoke.json       evidence that each MCP tool works from Claude Code
    ├── desk_tickets.html    Expected vs Actual per ticket, Cash tab, Reflection tab
    ├── design.md            dashboard design choices
    ├── resolved_tickets.json  per ticket: final status, outcome, agent contributions, human approvals
    ├── resolved_board.html  screenshots of the React board for each resolved ticket
    ├── audit_trail.json     append-only log of every agent step, signature and payment
    ├── github_url.txt       link to this repository
    ├── runs/                per-run traces
    └── board_screens/       the screenshots used in resolved_board.html
```

## Setup

Requires Python 3.12, Node 20+, and an Anthropic API key.

```bash
git clone https://github.com/KenRice2026/HW5.git
cd HW5
python -m venv .venv
```

Activate the virtual environment, then install:

| OS | Activate |
|---|---|
| Windows PowerShell | `.venv\Scripts\Activate.ps1` |
| Windows cmd | `.venv\Scripts\activate.bat` |
| macOS / Linux | `source .venv/bin/activate` |

```bash
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

Set your API key. Copy `.env.example` to `.env` and fill it in, or set it in your shell:

```bash
export ANTHROPIC_API_KEY=your-key            # PowerShell: $env:ANTHROPIC_API_KEY = "your-key"
```

`.env` files are git-ignored and never committed. `frontend/.env` is optional: without it the desk calls `http://localhost:8000` (see `frontend/.env.example`).

## The two databases

| File | Role |
|---|---|
| `data/campus_customs.db` | **Original.** Never written. The clean starting point. |
| `data/campus_customs_new.db` | **Working copy.** Everything the agents and the MCP server read and write. As committed, it holds the end of our Problem 9 run (checking $152.00, 3 payments). |

**For a clean run, copy the original over the working copy.** Either use the app:

```bash
python -m backend.run --reset        # or, with the backend running: curl -X POST http://localhost:8000/reset
```

or copy the file by hand:

```bash
cp data/campus_customs.db data/campus_customs_new.db          # PowerShell: Copy-Item data\campus_customs.db data\campus_customs_new.db
```

All three give the same result. The original is only ever read, so you can reset as often as you like.

## Run it

Use three terminals, all starting from the project root with the virtual environment active.

**1. MCP server (optional on its own).** The FastAPI backend starts its own copy of the MCP server over stdio, so you don't need to run this to use the app. To start it standalone, for example to inspect the tools or connect another MCP client:

```bash
python mcp_server/server.py
```

Claude Code picks it up from `.mcp.json` as `campus-customs`. That file uses absolute paths from the author's machine; change `command` to your `.venv` Python and `args` to your `mcp_server/server.py` path.

**2. FastAPI backend:**

```bash
cd backend
uvicorn main:app --reload --port 8000
```

The API is at http://localhost:8000, with interactive docs at http://localhost:8000/docs.

**3. React board:**

```bash
cd frontend
npm run dev
```

The desk opens at http://localhost:5173. In Windows PowerShell, if script execution is disabled, use `npm.cmd run dev`.

## A full three-ticket run

**Always reset the database before a full run** over tickets 101, 102 and 103, so every ticket starts open with $3,400.00 in checking.

**On the board:**
1. Press **⟲ Fresh start**. This resets the DB; the register should read $3,400.00 and all three slips should be open.
2. Type your name on the brass **Signing as** nameplate.
3. For each ticket (101, 102, 103): select its slip, press **▶ Start the team**, and watch the agents on the floor and in the wire.
4. Sign the cheques that appear in the **Signature tray**. Signing is what pays and lowers cash.
5. Press **↻ Run the team again** on tickets that are waiting on you, until each slip is stamped RESOLVED.

**From the command line:**

```bash
python -m backend.run --board                              # resets first, then works 101, 102, 103
python -m backend.run --pending                            # see what needs a signature
python -m backend.run --approve 1 --approver "Your Name"   # sign request #1 (it pays)
python -m backend.run --board --no-reset                   # continue after signing
python -m backend.run --ticket 101                         # or work one ticket
```

Agents never pay on their own. Every payment waits for a person's signature.

## How a ticket flows

1. The **Boss** reads the ticket and delegates. Any agent can delegate to any other, up to a depth of 3.
2. Specialists work through their own MCP tools only. For example, only Accounting can file payments, and only Customer Service can draft messages.
3. Anything that costs money becomes an **approval request**. A person signs it on the dashboard; only then does `pay` run. `pay` refuses unapproved requests, changed amounts, and anything that would make the balance negative.
4. Messages are **drafts** that are never sent.
5. Every step is appended to `output/audit_trail.json`.

**Full run (Problem 9):** starting balance $3,400.00. Three signed payments: rent $2,400.00, invoice 501 $840.00, and a purchase order for one tee at $8.00. Ending balance **$152.00**, matching `cash_accounts`. See the Cash tab in `output/desk_tickets.html`.
