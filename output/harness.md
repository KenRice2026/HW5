# Campus Customs Harness

The harness for Campus Customs Multi-Agent Operations: an MCP server over the shop database, a PydanticAI team of five agents behind a FastAPI backend, and a React desk where a human watches the agents and signs payments.

**Contents:**
- **[Tables](#tables)**: 9 shop tables, plus 3 working tables
- **[MCP tools](#agents-and-mcp-tools)**: 26 tools, with the tables each one uses
- **[Five agents](#agent-team-problem-5)**: Boss, Inventory, Accounting, Facilities, Customer Service
- **[Audit trail](#audit-trail)**
- **[Safety rules](#safety)**
- **[API routes](#backend-routes-problem-7)**
- **[Dashboard](#agent-dashboard-problem-8)**
- **[Full run: resolving the three tickets](#full-run-resolving-the-three-tickets-problem-9)**

**Quick start** (from the Homework 5 folder, with `ANTHROPIC_API_KEY` set):

| Step | Command |
|---|---|
| Install | `pip install -r requirements.txt` and `cd frontend && npm install` |
| Backend | `cd backend && uvicorn main:app --reload --port 8000` |
| Dashboard | `cd frontend && npm run dev` (in Windows PowerShell, `npm.cmd run dev`). Opens http://localhost:5173 |
| CLI | `python -m backend.run --reset` · `--ticket 101` · `--board` · `--pending` · `--approve 1 --approver "Name"` |
| Claude Code | `.mcp.json` registers the `campus-customs` MCP server |

| Output file | What it is |
|---|---|
| `output/harness.md` | This file |
| `output/mcp_smoke.json` | Problem 4 MCP tool evidence |
| `output/desk_tickets.html` | Expected vs Actual per ticket, plus the Cash tab |
| `output/design.md` | Dashboard design |
| `output/resolved_tickets.json` | Per-ticket outcome, agent contributions, human approvals |
| `output/resolved_board.html` | Screenshots of the React board for each resolved ticket |
| `output/audit_trail.json` | Append-only audit of every agent step |
| `output/runs/` | Per-run traces |

## Database

- **Original (read-only, reset source):** `data/campus_customs.db` — never modified.
- **Working copy (agents read/write):** `data/campus_customs_new.db` — reset by copying the original over it before a full ticket run.
- "Today" for the shop is `desk.date_today` = **2026-08-31**.

## Tables

### desk
Fields: `date_today`, `notes`

Why it matters: the shop's clock — every agent uses `date_today` to decide what is overdue or coming due.

### tickets
Fields: `id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at`

Why it matters: the work board — the Boss reads each open ticket and routes it; its foreign keys point agents to the inventory, lease or invoice involved.

### inventory
Fields: `sku`, `name`, `size`, `qty`, `location` (key: `sku` + `size`)

Why it matters: Inventory checks stock by sku and size here to spot shortfalls before an order is promised.

### pricing
Fields: `sku`, `unit_cost`, `list_price`

Why it matters: Accounting uses cost vs. list price to check margins on discount requests and to price restock purchase orders.

### vendors
Fields: `id`, `name`, `specialty`, `lead_days`

Why it matters: Inventory picks the restock vendor by specialty, and `lead_days` sets when restocked product can arrive.

### invoices
Fields: `id`, `vendor_id`, `amount`, `due_date`, `status`, `description`

Why it matters: unpaid bills — an overdue open invoice blocks that vendor from shipping, and paying it needs human approval.

### leases
Fields: `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes`

Why it matters: Facilities tracks rent amount and due date here so rent is paid on time.

### cash_accounts
Fields: `name`, `balance`, `date`

Why it matters: the only cash the shop has (no revenue is modeled) — the pay tool must refuse any payment that would make the balance negative.

### payments
Fields: `id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by`

Why it matters: the audit trail — every approved payment is written here with who approved it (empty at start).

### Working tables (added by the MCP server, working copy only)

The MCP server creates these in `campus_customs_new.db` the first time it is used. A reset copies the original back, which removes them; the original database never has them.

| Table | Fields | Why it matters |
|---|---|---|
| `approval_requests` | `id`, `kind` (invoice_payment / rent_payment / purchase_order), `ref_id`, `ticket_id`, `payee`, `amount`, `reason`, `requested_by`, `status` (pending / approved / rejected / paid), `requested_on`, `decided_by`, `decided_on`, `decision_note`, `payment_id` | The queue between agents and a human. Agents file requests, a person decides, and `pay` only accepts `approved` ones. |
| `purchase_orders` | `id`, `vendor_id`, `sku`, `size`, `qty`, `unit_cost`, `total`, `ticket_id`, `status` (pending_approval / rejected / ordered), `expected_arrival`, `created_by`, `created_on` | Restocks priced at `pricing.unit_cost`, with arrival = shop date + `vendors.lead_days`. |
| `drafts` | `id`, `ticket_id`, `audience`, `recipient`, `subject`, `body`, `created_by`, `created_on`, `status` (always `draft`) | Messages that stay on the board. Nothing is ever sent. |

## Starting state (2026-08-31)

| Item | Value |
|---|---|
| Cash (checking) | $3,400.00 |
| Invoice 501 — Bulldog Print Co | $840.00, due 2026-08-28, **open → 3 days overdue** |
| Lease 1 — Chapel Street shop | $2,400.00 rent, due 2026-09-02 (2 days) |
| Payments | none |

## Open tickets and how they link

### Ticket 101 — customer_order (Tauhid Zaman)
1 × `CC-TEE-WHITE` size S. Links to **inventory** (`sku` + `size`) and **invoices** (`invoice_id` 501).
- Inventory: size S qty = **0** → shortfall of 1.
- Invoice 501 (Bulldog Print Co, vendor 1) is the rush reprint for this exact tee/size — still open and overdue.
- Vendor 1 (apparel reprint, 5 lead days) won't ship until invoice 501 is paid.
- Agents involved: Inventory → Accounting (pay 501, human approval) → Customer Service (draft ETA message).

### Ticket 102 — rent_notice (Elm City Properties)
Rent due in 2 days. Links to **leases** (`lease_id` 1).
- $2,400 due 2026-09-02; payment needs human approval and must not overdraw cash.
- Agents involved: Facilities → Accounting (prepare payment, human approval).

### Ticket 103 — price_override (Yale AI Club)
20 × `CC-HOOD-NAVY` size M, bulk discount request. Links to **inventory** and **pricing** via `sku`.
- Inventory: size M qty = **8** → shortfall of 12.
- Pricing: unit cost $22, list $58 (62% margin at list) — room for a discount; the Boss makes the final call.
- Restock would come from Bulldog Print Co (apparel), also blocked by invoice 501.
- Agents involved: Inventory, Accounting (margin check), Boss (decision), Customer Service (draft reply).

## Cash pressure

Paying invoice 501 ($840) and rent ($2,400) uses $3,240 of $3,400, leaving **$160**. A 12-hoodie restock at cost ($264) would not fit, so the agents must prioritize and the pay tool must refuse overdrafts.

## MCP tools (Problem 3)

Server: `mcp_server/server.py` (FastMCP, `campus-customs`), working only on `data/campus_customs_new.db`. Every agent uses these tools.

### `check_stock(sku, size)`
- **Reads:** `inventory`
- **Unlocks:** ticket **101**
- **Why:** Ticket 101 asks for 1 × `CC-TEE-WHITE` in size S, and `check_stock("CC-TEE-WHITE", "S")` returns qty 0. That proves the order can't ship from the shelf and starts the restock path through Bulldog Print Co and invoice 501. (The same tool also shows only 8 M hoodies on hand for ticket 103.)

### `get_lease(lease_id)`
- **Reads:** `leases`
- **Unlocks:** ticket **102**
- **Why:** Ticket 102 is only an email saying "rent due in 2 days," and its `lease_id` 1 is the only link to the facts. `get_lease(1)` returns the $2,400 rent, the Elm City Properties landlord and the 2026-09-02 due date that Facilities needs before Accounting can prepare a payment.

### `get_pricing(sku)`
- **Reads:** `pricing`
- **Unlocks:** ticket **103**
- **Why:** Ticket 103 asks for a bulk discount on 20 `CC-HOOD-NAVY` hoodies. `get_pricing("CC-HOOD-NAVY")` returns the $22 cost against the $58 list price ($36 or 62% margin per unit), so Accounting and the Boss can choose a discount that stays above cost.

## MCP connection and tool tests (Problem 4)

**Connection:** the server is registered with the vibe coder (Claude Code) in the project file `.mcp.json` as `campus-customs` (stdio). It runs `mcp_server/server.py` with the Homework 5 `.venv` Python, where FastMCP 4.1.5 is installed (`requirements.txt`).

**Test method:** a FastMCP client loaded `.mcp.json`, started the server over stdio, listed the tools, and called each one. Both databases had the same MD5 hash before and after the tests (`46effb90…`), so the tools changed nothing.

Tools listed: `check_stock`, `get_lease`, `get_pricing`.

| Call | Result | Matches the DB? |
|---|---|---|
| `check_stock("CC-TEE-WHITE", "S")` (ticket 101) | qty **0**, Classic Bulldog Tee, Aisle B | Yes |
| `check_stock("CC-HOOD-NAVY", "M")` (ticket 103) | qty **8**, Basic Hoodie Big Yale, Aisle A | Yes |
| `get_lease(1)` (ticket 102) | Chapel Street shop, Elm City Properties, **$2,400**, due **2026-09-02** | Yes |
| `get_pricing("CC-HOOD-NAVY")` (ticket 103) | cost **$22**, list **$58**, margin $36 (62.1%) | Yes |
| `check_stock("CC-SOCKS", "M")` (not in the DB) | `found: false`, "No inventory row for this sku and size." | Yes, no data invented |

**Native test in the vibe coder:** with the session opened in the Homework 5 folder, Claude Code loaded `campus-customs` from `.mcp.json` and exposed the tools as `mcp__campus-customs__check_stock`, `mcp__campus-customs__get_lease` and `mcp__campus-customs__get_pricing`. Claude Code called each one directly:

| Native call | Returned |
|---|---|
| `check_stock(sku="CC-TEE-WHITE", size="S")` | qty 0, Aisle B (ticket 101: out of stock) |
| `check_stock(sku="CC-HOOD-NAVY", size="M")` | qty 8, Aisle A (ticket 103: 12 short of 20) |
| `get_lease(lease_id=1)` | Chapel Street shop, Elm City Properties, $2,400, due 2026-09-02 (ticket 102) |
| `get_pricing(sku="CC-HOOD-NAVY")` | cost $22, list $58, margin $36 / 62.1% (ticket 103) |

## Agent team (Problem 5)

Built with PydanticAI 2.64 on `anthropic:claude-opus-5-5` (set `CC_MODEL` to change). Effort is `high` for the Boss and Accounting and `medium` for the others.

### Layout

| Path | What it is |
|---|---|
| `backend/prompts/{boss,inventory,accounting,facilities,customer_service}.md` | One detailed prompt per agent: role, owned tables, tools, step-by-step procedure, shop rules, output. |
| `backend/models.py` | Data types: `AgentName`, `TicketStatus`, `AgentReport` (specialists), `BossDecision` (Boss), `TeamDeps` (run context), `TraceEvent`, `TicketRun`, `BoardRun`, `ApprovalDecision`. |
| `backend/agents/base.py` | `make_agent()` and the `delegate(to, task)` tool every agent has. |
| `backend/agents/{boss,inventory,accounting,facilities,customer_service}.py` | The five agents, one file each. |
| `backend/agents/__init__.py` | Registers all five in `TEAM`, which is what gives full connectivity. |
| `backend/mcp_tools.py` | The single stdio connection to the MCP server, a filtered view of it per role, and per-call tracing. |
| `backend/audit.py` | Appends every agent-loop step to `output/audit_trail.json`. |
| `backend/config.py` | Model, effort, depth and token limits, `ROLE_TOOLS` (which MCP tools each agent sees), `HUMAN_ONLY_TOOLS`. |
| `backend/team.py` | The agent loop: `run_ticket()`, `run_board()`, `reset_database()` (through MCP). |
| `backend/approvals.py` | Human approve/reject through MCP `decide_approval_request`, then `pay`. Not available to agents. |
| `backend/run.py` | CLI: `--reset`, `--ticket N`, `--board`, `--pending`, `--approve/--reject ID --approver NAME`. |

### Roles and their MCP tools

Every agent also has `get_shop_date`, `get_ticket`, `list_tickets` and `delegate`.

| Agent | Job | Its MCP tools |
|---|---|---|
| Boss | Reads each ticket, decides who works it, makes the final call (`BossDecision`). | `list_approval_requests`, `list_purchase_orders`, `list_drafts`, `get_cash_balance`, `list_payments` |
| Inventory | Stock by SKU + size, shortfalls, restock vendor and lead time, reserving stock. | `check_stock`, `list_inventory`, `reserve_stock`, `list_vendors`, `get_vendor_status`, `list_purchase_orders` |
| Accounting | Cash, invoices, margins and discounts; prepares payments and POs for human approval. | `get_cash_balance`, `list_invoices`, `get_invoice`, `get_pricing`, `quote_discount`, `list_vendors`, `get_vendor_status`, `get_lease`, `request_payment_approval`, `create_purchase_order`, `list_purchase_orders`, `list_approval_requests`, `list_payments`, `pay` |
| Facilities | Leases, rent amount and due date, landlord notices. | `get_lease`, `list_leases`, `get_cash_balance`, `list_approval_requests` |
| Customer Service | Drafts messages to customers, the landlord and vendors (never sent). | `check_stock`, `get_pricing`, `quote_discount`, `get_vendor_status`, `draft_message`, `list_drafts` |

### Full connectivity and the agent loop

- Every agent has `delegate(to, task)` and can call any other agent. The call runs the other agent as a nested run that shares the ticket's usage budget (80 model requests) and trace, and returns its structured report as JSON.
- Guards: an agent can't delegate to itself, and chains stop at depth 3 (for example Boss → Inventory → Accounting → Facilities). Refusals are recorded in the trace.
- `run_ticket(id)`: the Boss works the ticket and returns a `BossDecision`. The loop writes the final status and decision note to the ticket and saves the trace in `output/runs/ticket_<id>_<run>.json`.
- `run_board()`: **resets the working DB from the original first** (shop rule), then works every ticket that isn't resolved or declined, one at a time, so each ticket sees the cash left by the ones before it. Use `--no-reset` to continue after approvals.
- Human approval: agents can only file requests. A person approves on the dashboard or CLI (`approvals.decide`, which rejects agent names as approvers). Approval immediately calls `pay`, which re-checks the amount and cash.

### MCP tools added in Problem 5

The server grew from 3 to 26 tools (the full list with tables is in "Agents and MCP tools" below). The ones each ticket needs:
- **101:** `get_ticket` links the order to invoice 501. `get_vendor_status(1)` shows Bulldog Print Co is blocked by that open invoice (`can_ship_new_product: false`). `request_payment_approval("invoice", 501)` queues the $840 payment. After approval, `create_purchase_order` for 1 × CC-TEE-WHITE S arrives in 5 lead days. `draft_message` holds the customer update.
- **102:** `get_lease(1)` adds `days_until_due` (2). `request_payment_approval("rent", 1)` queues the $2,400 rent. After payment, `pay` moves `next_due` to 2026-10-02.
- **103:** `quote_discount("CC-HOOD-NAVY", 20, pct)` prices discount levels (10% = $52.20/unit, $1,044 total, highest discount before cost 62.1%). `create_purchase_order` prices the 12-unit shortfall ($264). `get_cash_balance` shows whether it fits once other requests are counted.

### Offline tests (no API calls, scratch DB copy)

- **MCP money flow, 22 checks passed:**
  - Invoice and rent payment requests take their amounts from the DB, and a duplicate request is refused.
  - `pay` refuses before human approval, refuses an agent name as the approver, and refuses to pay twice.
  - Approved payments update payments, cash, invoice and lease (3,400 → 2,560 → 2,552 → 152).
  - A PO is refused while the vendor has an open invoice and allowed after it is paid.
  - The 12-hoodie PO ($264) is refused at $152 (no negative balance).
  - Over-reserving stock is refused, and drafts are saved but not sent.
- **Agent wiring, 13 checks passed** (PydanticAI `FunctionModel` stand-ins drove the real `delegate` and MCP tools):
  - The chain Boss → Inventory → Accounting → Facilities ran.
  - Each agent saw exactly its `ROLE_TOOLS`; only Accounting has `pay` and only Customer Service has `draft_message`.
  - Depth-4 delegation and an unapproved `pay` were refused and recorded in the trace.
  - The loop wrote the Boss's status and note to the ticket.
- Both real database files kept the same MD5 hash throughout.

### Live test: ticket 102 on claude-opus-5-5

Ran after a reset, with `python -m backend.run --ticket 102`. It took 81 seconds, with no errors. The trace is in `output/runs/ticket_102_c81111f6.json`.

- **Boss** read the ticket, shop date and cash, then delegated in order to Facilities → Accounting → Customer Service.
- **Facilities:**
  - `get_lease(1)`: $2,400, due 2026-09-02, 2 days from the shop date, which matches the landlord's email.
  - It also checked cash and existing requests (none).
- **Accounting:**
  - It checked the lease, cash ($3,400) and the queue, then filed `request_payment_approval("rent", 1)`.
  - That created request #1 for $2,400, pending, with "$1,000 left after payment" stated in its reason.
- **Customer Service:** checked for existing drafts (none), then saved draft #1 to the landlord. The draft says the payment is in approval and doesn't promise a date. It was not sent.
- **BossDecision:** `awaiting_approval`, `waiting_on_human: true`, request [1], draft [1]. Its reasoning cites the lease, the shop date and the cash numbers.
- **Database after the run:** ticket 102 is `awaiting_approval` with the Boss's note. `payments` is empty and checking is still $3,400. No money moved without a human.
- **Prompt fix after review:** in its next steps the Boss said "Accounting runs pay(1)" after approval. Approval actually runs `pay` automatically, so `boss.md` now says so.

## Agents and MCP tools

All shop facts come from the `campus-customs` MCP server over `data/campus_customs_new.db`. The backend has no second data layer: approvals and resets also go through MCP tools.

### Agents

| Agent | File | Prompt | Output |
|---|---|---|---|
| Boss | `backend/agents/boss.py` | `backend/prompts/boss.md` | `BossDecision` |
| Inventory | `backend/agents/inventory.py` | `backend/prompts/inventory.md` | `AgentReport` |
| Accounting | `backend/agents/accounting.py` | `backend/prompts/accounting.md` | `AgentReport` |
| Facilities | `backend/agents/facilities.py` | `backend/prompts/facilities.md` | `AgentReport` |
| Customer Service | `backend/agents/customer_service.py` | `backend/prompts/customer_service.md` | `AgentReport` |

Every agent also has `delegate(to, task)`, a backend tool (not MCP) that runs another agent. It reads no tables.

### MCP tools (26)

R = reads, W = writes. "Used by" lists who can call the tool: agents through their filtered toolset; the run loop and humans through the backend.

| Tool | Tables | Used by | Added |
|---|---|---|---|
| `get_shop_date` | desk (R) | all agents | P5 |
| `list_tickets` | tickets (R) | all agents, run loop | P5 |
| `get_ticket` | tickets, inventory, pricing, invoices, leases, approval_requests, purchase_orders, drafts (R) | all agents | P5 |
| `update_ticket` | tickets (W) | run loop only (writes the Boss's final status + note) | P5 |
| `check_stock` | inventory (R) | Inventory, Customer Service | P3 |
| `list_inventory` | inventory (R) | Inventory | P5 |
| `reserve_stock` | inventory (W), tickets (W note) | Inventory | P5 |
| `list_vendors` | vendors, invoices (R) | Inventory, Accounting | P5 |
| `get_vendor_status` | vendors, invoices, desk (R) | Inventory, Accounting, Customer Service | P5 |
| `get_pricing` | pricing (R) | Accounting, Customer Service | P3 |
| `quote_discount` | pricing (R) | Accounting, Customer Service | P5 |
| `get_cash_balance` | cash_accounts, approval_requests (R) | Boss, Accounting, Facilities | P5 |
| `list_invoices` | invoices, desk (R) | Accounting | P5 |
| `get_invoice` | invoices, vendors, desk (R) | Accounting | P5 |
| `request_payment_approval` | invoices / leases, vendors (R); approval_requests (W) | Accounting | P5 |
| `create_purchase_order` | vendors, invoices, pricing, inventory (R); purchase_orders, approval_requests (W) | Accounting | P5 |
| `list_purchase_orders` | purchase_orders, vendors (R) | Boss, Inventory, Accounting | P5 |
| `list_approval_requests` | approval_requests (R) | Boss, Accounting, Facilities, CLI | P5 |
| `list_payments` | payments (R) | Boss, Accounting | P5 (this round) |
| `pay` | approval_requests, invoices, leases, purchase_orders, cash_accounts (R/W); payments (W) | Accounting (approved requests only), human approval flow | P5 |
| `decide_approval_request` | approval_requests, purchase_orders, tickets (W) | **humans only** (dashboard/CLI) | P5 (this round) |
| `reset_working_database` | whole working DB (W, copied from the original) | **humans / run loop only** | P5 (this round) |
| `get_lease` | leases, desk (R) | Accounting, Facilities | P3 |
| `list_leases` | leases, desk (R) | Facilities | P5 |
| `draft_message` | drafts (W) | Customer Service | P5 |
| `list_drafts` | drafts (R) | Boss, Customer Service | P5 |

`config.py` asserts at startup that no agent's toolset contains a human-only tool, and the wiring test confirms what each agent actually sees.

## Audit trail

`output/audit_trail.json` is one JSON list of entries, and **runs only ever append to it.** Each append reads the list, adds the entry and atomically replaces the file. If the file can't be read, it is left untouched and entries go to `audit_trail.unreadable.jsonl` instead.

**One entry per agent-loop step.** `backend/agents/base.py: run_agent()` walks the PydanticAI graph with `agent.iter()`. Every run, top-level or delegated, goes through it.

| `step_type` | When | What it records |
|---|---|---|
| `prompt` | An agent is handed a task | The task text, model, prompt-file hash (`prompt_version`) |
| `model_response` | The model replies | Text, thinking (if any), each tool call with arguments, this step's tokens (input/output/cache) |
| `model_request` | Results go back to the model | Each tool result (truncated at 4,000 chars), whether it was a refusal, framework retry prompts |
| `final_output` | The agent finishes | Its validated `AgentReport` / `BossDecision` |
| `error` | The run fails (usage limit, API, validation) | The error |
| `ticket_update` | The loop writes the decision | The `update_ticket` args and result |
| `reset` | The working DB is reset | The `reset_working_database` result |
| `human_decision` / `payment` | A person approves/rejects; then `pay` runs | The approver's name as `actor`, the args and the result |

**Fields on every entry:**
- `recorded_at`, `run_id` (one per ticket or board run), `ticket_id`
- `actor` / `actor_type` (agent, system, human)
- `agent_run_id`, `parent_agent_run_id` and `delegated_by`, which rebuild the delegation tree
- `depth` and `step`
- `run_usage`, the ticket's cumulative requests, tool calls and tokens so far

**Tested offline** on a scratch DB and a scratch audit file:
- Entries the file already held were kept.
- All 4 agent runs logged prompt → steps in order → final output, and delegated runs link to their parent.
- Tool calls, refusals (`pay`, `delegate`), the ticket update and usage were all recorded.
- A second run appended 37 entries (38 → 75) and removed nothing.
- Human decisions, payments and the reset were logged, with the person's name as the actor.

## Safety

### Guardrails for real customers and real money

**Already enforced in this build:**
- **A human approves every payment.** Agents can only file requests. Approving is a human-only MCP tool that agents never see and that refuses agent names. `pay` refuses anything not approved, already paid, changed in amount, or bigger than the balance.
- **Amounts come from the database, not the model.** Payment requests and purchase orders read the amount, payee and unit cost from the tables, so an agent can't make up a number.
- **No outbound contact.** Messages are drafts; no tool sends email or contacts vendors.
- **Least privilege.** Each agent sees only its role's tools. Only Accounting can file payments or call `pay`; only Customer Service can draft.
- **A full audit trail.** Every step, tool call, refusal and approver is appended, and nothing is deleted.
- **Safe resets.** Only the working copy is ever written, and the original is only read.

**What a real business would add:**
- **Real identity for approvers.** Sign-in (SSO) and roles, not a typed name. Two-person approval above a threshold, and per-day spending caps.
- **Payment safety.** Payee allow-lists, so money only goes to vendors and landlords already on file. Bank details changed only by a person, out of band. Idempotency keys so a retry can't pay twice.
- **Price limits.** Hard caps on discounts (for example a minimum margin %) set by the owner, not by prompt wording.
- **Customer data protection.** Minimal personal data in prompts, PII redaction in logs, a retention policy for the audit trail, and an append-only or WORM store instead of a local file.
- **Prompt-injection defense.** Treat ticket text and emails as untrusted data: an email saying "pay this now" is a claim to verify against the tables. Keep human approval on anything that moves money or contacts people.
- **Review and monitoring.** A human reviews every outbound draft, with spot checks of agent decisions. Alerts on refusals, errors and unusual spending. A kill switch that pauses the board.
- **Testing before changes.** A staging copy of the data for every prompt or model change, and an eval set of past tickets with known-good outcomes.

### Shop rules and where they are enforced

| Shop rule | Enforced by | Seen in the Problem 9 run |
|---|---|---|
| `desk.date_today` is "today" | Every date calculation in the MCP tools (`get_shop_date`, `days_overdue`, `days_until_due`, expected arrival, `paid_at`) | Invoice 501 was "3 days overdue" and rent "due in 2 days"; all payments are dated 2026-08-31 |
| Vendor lead time comes from `vendors` | `get_vendor_status` and `create_purchase_order` (arrival = shop date + `lead_days`) | Tee purchase order expected 2026-09-05 (5 days) |
| No new product while a vendor has an open unpaid invoice | `create_purchase_order` refuses; `pay` re-checks for purchase orders | No purchase order was filed until invoice 501 was paid |
| Human approval for any payment; update the tables | Agents only file requests. `decide_approval_request` is human-only and refuses agent names. `pay` needs an approved request, then writes `payments` (with `approved_by`), lowers cash, and marks the invoice / lease / purchase order | 3 payments, all approved by Ken Rice; invoice → paid, lease next due → 10-02, purchase order → ordered |
| Not enough cash → pay must refuse; no negative balances | `pay` checks the balance before paying; `request_payment_approval` and `create_purchase_order` warn when outstanding requests exceed cash | Accounting declined to file the $264 hoodie restock with $160 left; the balance never dropped below $152 |
| Cash only goes out | No tool adds money; the dashboard register only rolls down | $3,400 → $152 |
| Reset before a full run | `reset_working_database` (MCP), `POST /reset`, `python -m backend.run --board` resets first | Problem 9 began with `POST /reset` (audit entry `reset`, actor `dashboard`) |
| Don't email customers or call vendors | No sending tool exists; `draft_message` only saves; the dashboard outbox says "never sent" | 5 drafts saved, 0 sent |

### Lessons from the full run

- **Who really signed.** On Ken Rice's instruction in chat, Claude clicked approve with the approver name "Ken Rice". Each approval note says so, and in its ticket 102 memo the Boss flagged that note and asked Ken to confirm it. A real business would require the approver to sign in themselves (SSO) rather than let anyone type a name.
- **Stale drafts.** When cash and vendor state changed between runs, Inventory noticed that draft 3 still said the vendor was blocked. Drafts should be re-checked before sending, and a draft could be marked stale automatically when the facts it quotes change.
- **Audit writes must not break runs.** A OneDrive file lock crashed one early run while it wrote the audit file. Writes now retry and hold entries in memory instead of raising.

### Limits that keep token use in check

| Limit | Value | Where |
|---|---|---|
| Model requests per ticket (all agents together) | 60 | `TICKET_LIMITS` in `backend/config.py` |
| Tool calls per ticket | 120 | `TICKET_LIMITS` |
| Total tokens per ticket | 600,000 | `TICKET_LIMITS`; going over stops the run and logs an `error` entry, and nothing is paid because payment still needs a human |
| Output tokens per model response | 8,000 | `MAX_OUTPUT_TOKENS` |
| Delegation depth | 3 | `MAX_DELEGATION_DEPTH`; deeper hand-offs and self-delegation are refused |
| Effort | `high` for Boss and Accounting, `medium` for the other three | `EFFORT` |
| Prompt caching | Instructions and tool definitions cached | `anthropic_cache_instructions` / `anthropic_cache_tool_definitions` |
| Small tools | Each role sees 7–17 MCP tools instead of all 26, so every request carries a shorter tool list | `ROLE_TOOLS` |
| Bounded results | Lookups return single rows or filtered lists; the trace and audit truncate long results | MCP tools, `audit.py` |
| Board runs | One ticket at a time, each with its own budget | `run_board()` |

## Backend routes (Problem 7)

`backend/main.py` (FastAPI). Start it from `backend/` with `uvicorn main:app --reload --port 8000`, then open http://localhost:8000 (interactive docs at `/docs`). Shop data comes through the MCP server; agent events come from `output/audit_trail.json`.

- `GET  http://localhost:8000/tickets`: the three tickets. Each has its `status` and a `state`: `open`, then `running` while agents work, then `resolved` once the Boss has made its call. It also gives `closed` and `pending_approval_ids`.
- `GET  http://localhost:8000/tickets/{ticket_id}/summary`: what each agent did on that ticket across every run since the last reset. Includes the Boss's latest decision, per-agent reports, tool counts, requests and drafts, and `first_event_id` for loading the full transcript.
- `POST http://localhost:8000/tickets/{ticket_id}/run`: starts the agent team (Boss first) on that ticket in the background and returns a `run_id` (202). Returns 409 if a run is already going, 404 for an unknown ticket.
- `GET  http://localhost:8000/runs/{run_id}`: whether that run is `running`, `done` or `error`, with the Boss's decision when done.
- `GET  http://localhost:8000/events?after={last_id}&ticket_id=&run_id=&agent=&limit=`: recent agent events (who acted, what they said, the tools they called and the results, refusals), so the board can refresh by asking only for new events.
- `GET  http://localhost:8000/approvals?status=pending`: payment and purchase-order requests the agents prepared (`pending` by default, or `all`).
- `POST http://localhost:8000/approvals/{request_id}/approve` with `{"approver": "<person>", "note": ""}`: a human approves. **This is the only route that changes cash**: it records the approval, then `pay` runs (refused if checking can't cover it, and refused for agent names).
- `POST http://localhost:8000/approvals/{request_id}/reject` with `{"approver": "<person>"}`: a human rejects; no money moves.
- `GET  http://localhost:8000/cash`: the checking balance from `cash_accounts`, plus the amount requested but not yet paid.
- `GET  http://localhost:8000/drafts?ticket_id=`: messages the agents drafted (never sent).
- `POST http://localhost:8000/reset`: resets `campus_customs_new.db` to the original values for a fresh run (409 while a run is going).
- `GET  http://localhost:8000/health`: server up, model, whether a run is in progress, whether the API key is set.
- `GET  http://localhost:8000/`: list of routes.

**Tests:**
- **Offline route test, 25 checks passed.** It used FastAPI's TestClient on a scratch DB and a scratch audit file, with scripted models standing in for Claude:
  - reset, tickets and cash
  - run → 202, with live events while it runs; a second run or a reset during it → 409; the result appears at `/runs/{id}`
  - `/events` lists what each agent said and the tools it used; `after` returns only new events
  - an agent name as approver → 403, a missing approver → 422
  - approving pays (3,400 → 2,560); approving twice → 409; rejecting moves no money
  - human decisions appear in the events, and reset restores 3,400
- **Live check.** The server was started from `backend/` with the command above.
  - The read routes returned the real board state: 101 and 102 `awaiting_approval`, 103 `in_progress`; cash $3,400 with $3,240 requested; requests #1 and #2; 3 drafts.
  - CORS allows `http://localhost:5173` and gives an outside origin no CORS header.
  - `--reload` restarted cleanly after `main.py` changed.

## Agent dashboard (Problem 8)

`frontend/` (React + Vite + TypeScript). Start it with `npm run dev`, which opens http://localhost:5173. It calls the backend at http://localhost:8000 (`frontend/.env`), and the backend's CORS explicitly allows `http://localhost:5173` (plus any other localhost port). Design rationale is in `output/design.md`.

**What it does:**
- **Lists all 3 tickets** as paper slips.
- **Starts the team:** pick a slip and press *Start the team*.
- **Shows the agents live:** five agent desks with live state and speech bubbles, plus a live transcript (the wire), updated every second from `/events`.
- **Marks the ticket resolved** with a RESOLVED stamp when the run finishes, showing the Boss's detailed status underneath.
- **Summarizes each agent's work** in a shift report (`/tickets/{id}/summary`).
- **Lets a person approve:** payments and purchase orders appear as cheques; *Sign & pay* approves, *Void* rejects.
- **Shows the checking balance** in a cash register that rolls down after an approved payment.

**Backend additions for the dashboard:**
- `GET /tickets/{id}/summary`: per-agent summary for the latest run since the last reset.
- `/tickets` now reports `state`: `open`, then `running` while the agents work, then `resolved` once the Boss has made its call. It also reports `closed`, `pending_approval_ids` and `running_ticket`.
- `/health` adds `shop_date` and `running_ticket`.

**Tests:**
- **Type-check, lint and build:** `tsc -b`, `eslint .` and `vite build` all pass.
- **Live check on the real board** (read-only): all 3 slips show RESOLVED, with sign flags on 101 and 102. The floor shows the agents ticket 101 used and greys out Facilities. Its 28-line transcript and shift report load, and the two cheques ($840, $2,400) appear.
  - This check found and fixed one bug: the board run shares one `run_id` across tickets, so the dashboard now also filters events by ticket.
- **End-to-end test on a scratch DB:** a second backend ran on :8001 and a second desk on :5174, so the real working DB was not touched.
  1. Typed a signer name and picked ticket 102, then *Start the team*.
  2. Watched Facilities → Accounting → Customer Service live; the slip then got its RESOLVED stamp, the shift report appeared and a $2,400 cheque arrived.
  3. *Sign & pay* moved the register from $3,400.00 to $1,000.00 with a −$2,400.00 receipt. The cheque was listed as PAID by the signer, and the sign flag cleared.
- **Phone width (375px):** single column, no sideways scrolling.
- **Real working DB afterwards:** $3,400, with requests #1 and #2 still pending.

## Full run: resolving the three tickets (Problem 9)

1. **Reset:** `POST /reset` through the backend. **Starting checking balance: $3,400.00.** All three tickets open, no payments, invoice 501 open, rent due 2026-09-02.
2. **First pass**, each ticket run through `POST /tickets/{id}/run`:
   - **101** → `awaiting_approval`: request #1 to pay invoice 501, $840.
   - **102** → `awaiting_approval`: request #2 for rent, $2,400.
   - **103** → `in_progress`: 10% offer, 8 hoodies reserved, draft 3.
3. **Human (Ken Rice):** approved #2 (rent first), then #1, through `POST /approvals/{id}/approve`. Cash went $3,400 → $1,000 → $160.
4. **Second pass:**
   - **102** → **`resolved`**: the rent payment is confirmed; draft 4 to the landlord.
   - **101** → `awaiting_approval`: purchase order #1 for 1 tee at $8, filed as request #3.
   - **103** → **`resolved`**: the $264 restock can't be afforded with $160 left, so the request is answered with the offer already made.
5. **Human (Ken Rice):** approved #3. Cash went $160 → **$152.00**; purchase order #1 is `ordered`, arriving 2026-09-05.
6. **Third pass:** **101** → `waiting_on_vendor`. Draft 5 gives Tauhid the 2026-09-05 date. The board shows it RESOLVED, but the shop date (2026-08-31) never reaches the delivery date, so the status stays `waiting_on_vendor`.

| | 101 | 102 | 103 | Total |
|---|---|---|---|---|
| Agent runs | 3 | 2 | 2 | 7 |
| First call by the Boss | Inventory | Facilities | Inventory (+ Accounting at the same time) | |
| Agents used | Boss, Inventory, Accounting, Customer Service | Boss, Facilities, Accounting, Customer Service | Boss, Inventory, Accounting, Customer Service | Facilities only on 102 |
| Cash change | −$848.00 | −$2,400.00 | $0.00 | −$3,248.00 |
| Final status | `waiting_on_vendor` | `resolved` | `resolved` | 3/3 resolved on the board |

**Ending checking balance: $152.00**, which equals `cash_accounts.balance` in the working DB and $3,400.00 − $2,400.00 − $840.00 − $8.00. Itemized in the Cash tab of `output/desk_tickets.html`; per ticket in `output/resolved_tickets.json`; board screenshots in `output/resolved_board.html`. `output/audit_trail.json` now holds 369 entries: earlier runs plus this full run, appended and never removed.

**Dashboard changes made during this problem:**
- **Whole-ticket summaries:** the shift report and transcript now cover every run of a ticket since the reset, plus human signatures, not just its latest run.
- **Current warnings only:** warnings now come only from a ticket's latest run.
- **Accurate labels:** "noted" vs "filed/saved" now reflects which agent actually filed a request or saved a draft.

## Notes on the data

- No table maps SKUs to vendors; agents infer the vendor from `vendors.specialty` (apparel → Bulldog Print Co, mugs → Elm City Gifts).
- `CC-MUG-CREST` (qty 0) and `CC-TEE-WHITE` S (qty 0) are out of stock even outside the tickets.
