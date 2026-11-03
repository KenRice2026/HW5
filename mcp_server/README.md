# Campus Customs MCP Server

This is the MCP server for the Campus Customs multi-agent team. Every agent (Boss, Inventory, Accounting, Facilities and Customer Service) reads and works the shop's data through these tools instead of touching the database directly. It is built with [FastMCP](https://gofastmcp.com) and runs over stdio.

## Database

- **Uses:** `data/campus_customs_new.db`, the working copy the agents operate on. The `CC_DB_PATH` environment variable can point it at a scratch copy for tests.
- **Never touches:** `data/campus_customs.db`, the untouched original kept for comparison and resets.
- On first use the server adds three working tables to the working copy: `approval_requests`, `purchase_orders` and `drafts`. A reset (`python -m backend.run --reset`) copies the original back, which removes them.

The tools return only what is stored in the database. If a row doesn't exist, the tool says "not found" instead of inventing data.

## Rules the tools enforce

- "Today" is `desk.date_today`, never the computer's clock.
- Money moves only through `pay`, and `pay` refuses unless a **human** approved the request, the amount still matches the database, and checking can cover it. Balances can't go negative.
- `create_purchase_order` refuses any vendor with an open unpaid invoice. Expected arrival is the shop date plus the vendor's `lead_days`.
- `draft_message` only saves drafts. No tool sends email or contacts a vendor.
- After a payment: a row goes in `payments` (with the approver's name), the checking balance drops, and the paid item updates (invoice → `paid`, lease `next_due` + 1 month, purchase order → `ordered`).

## Human-only tools

`decide_approval_request` and `reset_working_database` are for people. The backend never puts them in any agent's toolset (`HUMAN_ONLY_TOOLS` in `backend/config.py`, checked at startup), so no agent can approve its own request or wipe the board. `decide_approval_request` also refuses agent names as the approver. The dashboard / CLI (`backend/approvals.py`) calls it with a person's name, then calls `pay`.

The backend has no other path to the data: every read and write, including approvals and resets, goes through this server.

## Tools (26)

| Area | Tool | Reads / writes |
|---|---|---|
| Board | `get_shop_date()` | desk |
| | `list_tickets(status)` | tickets |
| | `get_ticket(ticket_id)` | tickets + linked inventory, pricing, invoice, lease, requests, POs, drafts |
| | `update_ticket(ticket_id, agent, note, status)` | writes tickets (notes appended, status) |
| Inventory | `check_stock(sku, size)` | inventory |
| | `list_inventory(sku)` | inventory |
| | `reserve_stock(sku, size, qty, ticket_id, agent)` | writes inventory (never below 0) |
| | `list_vendors()` | vendors + open invoices |
| | `get_vendor_status(vendor_id)` | vendors + invoices (can it ship? earliest arrival) |
| Accounting | `get_pricing(sku)` | pricing |
| | `quote_discount(sku, qty, discount_pct)` | pricing (read-only maths) |
| | `get_cash_balance()` | cash_accounts + outstanding requests |
| | `list_invoices(status, vendor_id)` | invoices (days overdue) |
| | `get_invoice(invoice_id)` | invoices + vendor |
| | `request_payment_approval(kind, ref_id, ticket_id, requested_by, reason)` | writes approval_requests (amount from DB) |
| | `create_purchase_order(vendor_id, sku, size, qty, ticket_id, created_by)` | writes purchase_orders + approval_requests |
| | `list_purchase_orders(status)` | purchase_orders |
| | `list_approval_requests(status)` | approval_requests |
| | `list_payments()` | payments (with approver) |
| | `pay(request_id)` | writes payments, cash_accounts, invoices / leases / purchase_orders |
| Human only | `decide_approval_request(request_id, approve, approver, note)` | writes approval_requests, purchase_orders (on reject), tickets (note) |
| | `reset_working_database()` | copies `campus_customs.db` over the working copy |
| Facilities | `get_lease(lease_id)` | leases (days until due) |
| | `list_leases()` | leases |
| Customer Service | `draft_message(ticket_id, audience, recipient, subject, body, created_by)` | writes drafts (never sent) |
| | `list_drafts(ticket_id)` | drafts |

## Running

From the Homework 5 folder:

```bash
pip install -r requirements.txt
python mcp_server/server.py
```

Claude Code picks it up from `.mcp.json` as `campus-customs`.
