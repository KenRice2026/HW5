"""Campus Customs MCP server.

Every agent on the Campus Customs team (Boss, Inventory, Accounting, Facilities,
Customer Service) reaches the shop's data through these tools. The server only
talks to data/campus_customs_new.db (or CC_DB_PATH, used for tests);
data/campus_customs.db is the untouched original kept for resets.

Rules the tools enforce, so no agent can talk its way around them:
- "Today" is desk.date_today, never the computer's clock.
- Nothing is invented: every amount, date and quantity comes from a table row. If a
  row is not found the tool says so.
- Money only moves through pay(), and pay() refuses unless a human approved the
  request first and the checking balance covers it (no negative balances).
- A vendor with an open unpaid invoice cannot get a new purchase order.
- Messages are drafts saved on the board. No tool sends email or contacts a vendor.

On first use the server adds three working tables to the database
(approval_requests, purchase_orders, drafts). The original tables are unchanged in
shape; a reset (copying the original file back) removes the working tables.

Two tools are for people, not agents: decide_approval_request (a human approves or
rejects a request) and reset_working_database. The backend never gives them to any
agent; the dashboard/CLI call them on a person's behalf.
"""

import calendar
import os
import shutil
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from fastmcp import FastMCP

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = Path(os.environ.get("CC_DB_PATH", DATA_DIR / "campus_customs_new.db"))
ORIGINAL_DB_PATH = DATA_DIR / "campus_customs.db"  # read-only: the reset source

AGENT_NAMES = {"boss", "inventory", "accounting", "facilities", "customer_service"}

TICKET_STATUSES = ("open", "in_progress", "awaiting_approval", "waiting_on_vendor", "resolved", "declined")
DRAFT_AUDIENCES = ("customer", "vendor", "landlord")
PAYMENT_KINDS = ("invoice", "rent")

mcp = FastMCP("campus-customs")

_WORKING_TABLES = """
CREATE TABLE IF NOT EXISTS approval_requests (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,              -- invoice_payment | rent_payment | purchase_order
    ref_id INTEGER NOT NULL,         -- invoices.id | leases.id | purchase_orders.id
    ticket_id INTEGER,
    payee TEXT NOT NULL,
    amount REAL NOT NULL,
    reason TEXT NOT NULL,
    requested_by TEXT NOT NULL,      -- agent name
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | approved | rejected | paid
    requested_on TEXT NOT NULL,      -- shop date
    decided_by TEXT,                 -- human approver's name
    decided_on TEXT,
    decision_note TEXT,
    payment_id INTEGER
);
CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY,
    vendor_id INTEGER NOT NULL,
    sku TEXT NOT NULL,
    size TEXT NOT NULL,
    qty INTEGER NOT NULL,
    unit_cost REAL NOT NULL,
    total REAL NOT NULL,
    ticket_id INTEGER,
    status TEXT NOT NULL DEFAULT 'pending_approval',  -- pending_approval | rejected | ordered
    expected_arrival TEXT,           -- shop date the vendor's lead time lands on
    created_by TEXT NOT NULL,
    created_on TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER,
    audience TEXT NOT NULL,          -- customer | vendor | landlord
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_on TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'   -- drafts are never sent by the system
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(_WORKING_TABLES)
    return conn


def _rows(conn, sql, args=()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, args).fetchall()]


def _row(conn, sql, args=()) -> dict | None:
    r = conn.execute(sql, args).fetchone()
    return dict(r) if r else None


def _today(conn) -> str:
    return conn.execute("SELECT date_today FROM desk").fetchone()[0]


def _days_between(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def _add_month(day: str) -> str:
    d = date.fromisoformat(day)
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1])).isoformat()


def _invoice_view(inv: dict, today: str) -> dict:
    days = _days_between(inv["due_date"], today)
    return {**inv, "days_overdue": max(days, 0), "is_overdue": inv["status"] == "open" and days > 0}


def _vendor_status(conn, vendor_id: int) -> dict | None:
    vendor = _row(conn, "SELECT id, name, specialty, lead_days FROM vendors WHERE id = ?", (vendor_id,))
    if vendor is None:
        return None
    today = _today(conn)
    open_invoices = [_invoice_view(i, today) for i in _rows(
        conn, "SELECT * FROM invoices WHERE vendor_id = ? AND status = 'open' ORDER BY due_date", (vendor_id,))]
    return {
        **vendor,
        "open_invoices": open_invoices,
        "open_invoice_total": round(sum(i["amount"] for i in open_invoices), 2),
        "can_ship_new_product": not open_invoices,
        "earliest_arrival_if_ordered_today": (date.fromisoformat(today) + timedelta(days=vendor["lead_days"])).isoformat(),
    }


def _cash(conn) -> dict:
    acct = _row(conn, "SELECT name, balance, date FROM cash_accounts WHERE name = 'checking'")
    pending = _row(conn, "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS n FROM approval_requests "
                         "WHERE status IN ('pending', 'approved')")
    return {
        **acct,
        "awaiting_approval_or_payment": round(pending["total"], 2),
        "requests_outstanding": pending["n"],
        "balance_if_all_outstanding_paid": round(acct["balance"] - pending["total"], 2),
    }


# --------------------------------------------------------------------------- board

@mcp.tool
def get_shop_date() -> dict:
    """Return the shop's "today" (desk.date_today). Use this date - never the real clock -
    to decide what is overdue or coming due."""
    with _connect() as conn:
        return {"date_today": _today(conn)}


@mcp.tool
def list_tickets(status: str | None = None) -> dict:
    """List tickets on the board, optionally filtered by status
    (open, in_progress, awaiting_approval, waiting_on_vendor, resolved, declined)."""
    with _connect() as conn:
        if status:
            rows = _rows(conn, "SELECT * FROM tickets WHERE status = ? ORDER BY id", (status,))
        else:
            rows = _rows(conn, "SELECT * FROM tickets ORDER BY id")
    return {"count": len(rows), "tickets": rows}


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Return one ticket plus every row it links to: the inventory row for its sku/size,
    the pricing row for its sku, its invoice (with days overdue) or lease, and any
    approval requests, purchase orders and drafts already made for it."""
    with _connect() as conn:
        t = _row(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if t is None:
            return {"found": False, "ticket_id": ticket_id, "message": "No ticket with this id."}
        today = _today(conn)
        linked = {}
        if t["sku"]:
            linked["inventory"] = _row(conn, "SELECT * FROM inventory WHERE sku = ? AND size = ?", (t["sku"], t["size"]))
            linked["pricing"] = _row(conn, "SELECT * FROM pricing WHERE sku = ?", (t["sku"],))
        if t["invoice_id"]:
            inv = _row(conn, "SELECT * FROM invoices WHERE id = ?", (t["invoice_id"],))
            linked["invoice"] = _invoice_view(inv, today) if inv else None
        if t["lease_id"]:
            linked["lease"] = _row(conn, "SELECT * FROM leases WHERE id = ?", (t["lease_id"],))
        linked["approval_requests"] = _rows(conn, "SELECT * FROM approval_requests WHERE ticket_id = ?", (ticket_id,))
        linked["purchase_orders"] = _rows(conn, "SELECT * FROM purchase_orders WHERE ticket_id = ?", (ticket_id,))
        linked["drafts"] = _rows(conn, "SELECT * FROM drafts WHERE ticket_id = ?", (ticket_id,))
    return {"found": True, "date_today": today, "ticket": t, "linked": linked}


@mcp.tool
def update_ticket(ticket_id: int, agent: str, note: str, status: str | None = None) -> dict:
    """Add a dated note to a ticket and optionally change its status
    (open, in_progress, awaiting_approval, waiting_on_vendor, resolved, declined).
    The original ticket text is kept; notes are appended below it."""
    if status is not None and status not in TICKET_STATUSES:
        return {"ok": False, "message": f"Unknown status '{status}'. Use one of {list(TICKET_STATUSES)}."}
    with _connect() as conn:
        t = _row(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if t is None:
            return {"ok": False, "message": "No ticket with this id."}
        line = f"[{_today(conn)} {agent}] {note.strip()}"
        notes = f"{t['notes']}\n{line}" if t["notes"] else line
        conn.execute("UPDATE tickets SET notes = ?, status = ? WHERE id = ?",
                     (notes, status or t["status"], ticket_id))
        return {"ok": True, "ticket": _row(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))}


# --------------------------------------------------------------------------- inventory

@mcp.tool
def check_stock(sku: str, size: str) -> dict:
    """Look up how many units of a SKU in a given size are on hand (inventory table).

    Use this before promising a customer order (e.g. ticket 101: CC-TEE-WHITE size S)
    or a bulk order (ticket 103: CC-HOOD-NAVY size M).
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (sku, size),
        ).fetchone()
    if row is None:
        return {"found": False, "sku": sku, "size": size,
                "message": "No inventory row for this sku and size."}
    return {"found": True, **dict(row)}


@mcp.tool
def list_inventory(sku: str | None = None) -> dict:
    """List inventory rows (every size), optionally for one SKU. Rows with qty 0 are flagged."""
    with _connect() as conn:
        if sku:
            rows = _rows(conn, "SELECT * FROM inventory WHERE sku = ? ORDER BY size", (sku,))
        else:
            rows = _rows(conn, "SELECT * FROM inventory ORDER BY sku, size")
    for r in rows:
        r["out_of_stock"] = r["qty"] == 0
    return {"count": len(rows), "inventory": rows}


@mcp.tool
def reserve_stock(sku: str, size: str, qty: int, ticket_id: int, agent: str) -> dict:
    """Take units off the shelf for a ticket (lowers inventory.qty). Refuses if there are
    fewer than qty on hand - it never lets stock go negative."""
    if qty <= 0:
        return {"ok": False, "message": "qty must be positive."}
    with _connect() as conn:
        row = _row(conn, "SELECT * FROM inventory WHERE sku = ? AND size = ?", (sku, size))
        if row is None:
            return {"ok": False, "message": "No inventory row for this sku and size."}
        if row["qty"] < qty:
            return {"ok": False, "on_hand": row["qty"], "requested": qty,
                    "message": f"Only {row['qty']} on hand; cannot reserve {qty}."}
        conn.execute("UPDATE inventory SET qty = qty - ? WHERE sku = ? AND size = ?", (qty, sku, size))
        conn.execute("UPDATE tickets SET notes = COALESCE(notes || char(10), '') || ? WHERE id = ?",
                     (f"[{_today(conn)} {agent}] Reserved {qty} x {sku} {size} from {row['location']}.", ticket_id))
        return {"ok": True, "reserved": qty, "qty_left": row["qty"] - qty, "sku": sku, "size": size}


@mcp.tool
def list_vendors() -> dict:
    """List every vendor with specialty, lead time, open unpaid invoices and whether they
    can ship new product right now (a vendor with any open invoice cannot)."""
    with _connect() as conn:
        ids = [r["id"] for r in _rows(conn, "SELECT id FROM vendors ORDER BY id")]
        return {"vendors": [_vendor_status(conn, i) for i in ids]}


@mcp.tool
def get_vendor_status(vendor_id: int) -> dict:
    """One vendor's lead time, open invoices (with days overdue) and whether they will ship
    new product. Also gives the earliest arrival date if an order were placed today."""
    with _connect() as conn:
        v = _vendor_status(conn, vendor_id)
    if v is None:
        return {"found": False, "vendor_id": vendor_id, "message": "No vendor with this id."}
    return {"found": True, **v}


# --------------------------------------------------------------------------- accounting

@mcp.tool
def get_pricing(sku: str) -> dict:
    """Look up a SKU's unit cost and list price, plus the margin at list price (pricing table).

    Use this before answering a discount request (e.g. ticket 103: bulk discount
    on CC-HOOD-NAVY) so any discount stays above cost.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?",
            (sku,),
        ).fetchone()
    if row is None:
        return {"found": False, "sku": sku, "message": "No pricing row for this sku."}
    result = {"found": True, **dict(row)}
    result["margin_per_unit"] = round(row["list_price"] - row["unit_cost"], 2)
    result["margin_pct"] = round(100 * (row["list_price"] - row["unit_cost"]) / row["list_price"], 1)
    return result


@mcp.tool
def quote_discount(sku: str, qty: int, discount_pct: float) -> dict:
    """Price an order of qty units at discount_pct off list (pricing table) and show the
    margin that is left. Flags any price at or below unit cost. Quoting changes nothing."""
    with _connect() as conn:
        p = _row(conn, "SELECT * FROM pricing WHERE sku = ?", (sku,))
    if p is None:
        return {"found": False, "sku": sku, "message": "No pricing row for this sku."}
    unit_price = round(p["list_price"] * (1 - discount_pct / 100), 2)
    margin = round(unit_price - p["unit_cost"], 2)
    return {
        "found": True, "sku": sku, "qty": qty, "discount_pct": discount_pct,
        "list_price": p["list_price"], "unit_cost": p["unit_cost"],
        "unit_price": unit_price, "order_total": round(unit_price * qty, 2),
        "margin_per_unit": margin, "order_margin": round(margin * qty, 2),
        "margin_pct": round(100 * margin / unit_price, 1) if unit_price else None,
        "below_or_at_cost": unit_price <= p["unit_cost"],
        "max_discount_pct_before_cost": round(100 * (1 - p["unit_cost"] / p["list_price"]), 1),
    }


@mcp.tool
def get_cash_balance() -> dict:
    """Checking balance (cash_accounts), plus money already requested but not yet paid and
    what the balance would be if every outstanding request were paid. No revenue is modeled:
    cash only goes down."""
    with _connect() as conn:
        return _cash(conn)


@mcp.tool
def list_invoices(status: str | None = None, vendor_id: int | None = None) -> dict:
    """List vendor invoices (optionally by status 'open'/'paid' and/or vendor), with days
    overdue measured from desk.date_today."""
    sql, args = "SELECT * FROM invoices WHERE 1=1", []
    if status:
        sql += " AND status = ?"; args.append(status)
    if vendor_id is not None:
        sql += " AND vendor_id = ?"; args.append(vendor_id)
    with _connect() as conn:
        today = _today(conn)
        rows = [_invoice_view(i, today) for i in _rows(conn, sql + " ORDER BY due_date", args)]
    return {"date_today": today, "count": len(rows), "invoices": rows}


@mcp.tool
def get_invoice(invoice_id: int) -> dict:
    """One invoice with its vendor and days overdue (from desk.date_today)."""
    with _connect() as conn:
        inv = _row(conn, "SELECT * FROM invoices WHERE id = ?", (invoice_id,))
        if inv is None:
            return {"found": False, "invoice_id": invoice_id, "message": "No invoice with this id."}
        vendor = _row(conn, "SELECT * FROM vendors WHERE id = ?", (inv["vendor_id"],))
        return {"found": True, **_invoice_view(inv, _today(conn)), "vendor": vendor}


@mcp.tool
def request_payment_approval(kind: str, ref_id: int, ticket_id: int, requested_by: str, reason: str) -> dict:
    """Ask a human to approve a payment. kind is 'invoice' (ref_id = invoices.id) or
    'rent' (ref_id = leases.id). The amount and payee are read from the database, not
    supplied by the agent. This moves no money - it puts the request on the board as
    'pending' until a person approves or rejects it on the dashboard."""
    if kind not in PAYMENT_KINDS:
        return {"ok": False, "message": f"kind must be one of {list(PAYMENT_KINDS)}. "
                                        "Purchase orders use create_purchase_order."}
    with _connect() as conn:
        if kind == "invoice":
            inv = _row(conn, "SELECT i.*, v.name AS vendor FROM invoices i JOIN vendors v ON v.id = i.vendor_id "
                             "WHERE i.id = ?", (ref_id,))
            if inv is None:
                return {"ok": False, "message": "No invoice with this id."}
            if inv["status"] != "open":
                return {"ok": False, "message": f"Invoice {ref_id} is '{inv['status']}', not open."}
            req_kind, payee, amount = "invoice_payment", inv["vendor"], inv["amount"]
        else:
            lease = _row(conn, "SELECT * FROM leases WHERE id = ?", (ref_id,))
            if lease is None:
                return {"ok": False, "message": "No lease with this id."}
            req_kind, payee, amount = "rent_payment", lease["landlord"], lease["monthly_rent"]
        dup = _row(conn, "SELECT * FROM approval_requests WHERE kind = ? AND ref_id = ? "
                         "AND status IN ('pending', 'approved')", (req_kind, ref_id))
        if dup:
            return {"ok": False, "existing_request": dup,
                    "message": f"Request {dup['id']} for this already exists ({dup['status']})."}
        cur = conn.execute(
            "INSERT INTO approval_requests (kind, ref_id, ticket_id, payee, amount, reason, requested_by, requested_on) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (req_kind, ref_id, ticket_id, payee, amount, reason, requested_by, _today(conn)))
        req = _row(conn, "SELECT * FROM approval_requests WHERE id = ?", (cur.lastrowid,))
        cash = _cash(conn)
    return {"ok": True, "request": req, "cash": cash,
            "warning": None if cash["balance_if_all_outstanding_paid"] >= 0 else
            "Outstanding requests now exceed the checking balance; not all of them can be paid."}


@mcp.tool
def create_purchase_order(vendor_id: int, sku: str, size: str, qty: int, ticket_id: int, created_by: str) -> dict:
    """Prepare a restock purchase order at unit_cost from the pricing table and send it for
    human approval (it costs cash). Refuses if the vendor has any open unpaid invoice -
    vendors don't ship while they are owed money. Expected arrival = shop date + vendor
    lead_days. Nothing is sent to the vendor."""
    if qty <= 0:
        return {"ok": False, "message": "qty must be positive."}
    with _connect() as conn:
        vendor = _vendor_status(conn, vendor_id)
        if vendor is None:
            return {"ok": False, "message": "No vendor with this id."}
        if not vendor["can_ship_new_product"]:
            return {"ok": False, "blocked_by_invoices": vendor["open_invoices"],
                    "message": f"{vendor['name']} has open unpaid invoices and will not ship new product. "
                               "Pay those first (with human approval)."}
        price = _row(conn, "SELECT * FROM pricing WHERE sku = ?", (sku,))
        if price is None:
            return {"ok": False, "message": "No pricing row for this sku, so the cost is unknown."}
        if _row(conn, "SELECT 1 AS x FROM inventory WHERE sku = ? AND size = ?", (sku, size)) is None:
            return {"ok": False, "message": "No inventory row for this sku and size."}
        today, total = _today(conn), round(price["unit_cost"] * qty, 2)
        po = conn.execute(
            "INSERT INTO purchase_orders (vendor_id, sku, size, qty, unit_cost, total, ticket_id, expected_arrival, "
            "created_by, created_on) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (vendor_id, sku, size, qty, price["unit_cost"], total, ticket_id,
             vendor["earliest_arrival_if_ordered_today"], created_by, today)).lastrowid
        req = conn.execute(
            "INSERT INTO approval_requests (kind, ref_id, ticket_id, payee, amount, reason, requested_by, requested_on) "
            "VALUES ('purchase_order', ?, ?, ?, ?, ?, ?, ?)",
            (po, ticket_id, vendor["name"], total, f"Restock {qty} x {sku} {size} for ticket {ticket_id}",
             created_by, today)).lastrowid
        cash = _cash(conn)
        return {"ok": True,
                "purchase_order": _row(conn, "SELECT * FROM purchase_orders WHERE id = ?", (po,)),
                "request": _row(conn, "SELECT * FROM approval_requests WHERE id = ?", (req,)),
                "cash": cash,
                "warning": None if cash["balance_if_all_outstanding_paid"] >= 0 else
                "Outstanding requests now exceed the checking balance; not all of them can be paid."}


@mcp.tool
def list_purchase_orders(status: str | None = None) -> dict:
    """List purchase orders (pending_approval, rejected, ordered) with vendor names."""
    sql = "SELECT p.*, v.name AS vendor FROM purchase_orders p JOIN vendors v ON v.id = p.vendor_id"
    with _connect() as conn:
        rows = _rows(conn, sql + (" WHERE p.status = ?" if status else "") + " ORDER BY p.id",
                     (status,) if status else ())
    return {"count": len(rows), "purchase_orders": rows}


@mcp.tool
def list_approval_requests(status: str | None = None) -> dict:
    """List payment and purchase-order approval requests (pending, approved, rejected, paid)."""
    with _connect() as conn:
        rows = _rows(conn, "SELECT * FROM approval_requests" + (" WHERE status = ?" if status else "") +
                     " ORDER BY id", (status,) if status else ())
    return {"count": len(rows), "requests": rows}


@mcp.tool
def list_payments() -> dict:
    """Every payment made (payments table): kind, what it paid, amount, date, and the
    human who approved it."""
    with _connect() as conn:
        rows = _rows(conn, "SELECT * FROM payments ORDER BY id")
    return {"count": len(rows), "total_paid": round(sum(r["amount"] for r in rows), 2), "payments": rows}


@mcp.tool
def decide_approval_request(request_id: int, approve: bool, approver: str, note: str = "") -> dict:
    """HUMAN ONLY - never given to agents. Record a person's approval or rejection of a
    pending request (approval_requests). approver must be the person's name; agent names
    are refused. Approving does not pay - call pay(request_id) next. Rejecting a
    purchase order marks it rejected. A dated note is added to the ticket."""
    approver = approver.strip()
    if not approver or approver.lower() in AGENT_NAMES:
        return {"ok": False, "message": "Refused: approvals must come from a person, not an agent."}
    with _connect() as conn:
        req = _row(conn, "SELECT * FROM approval_requests WHERE id = ?", (request_id,))
        if req is None:
            return {"ok": False, "message": "No approval request with this id."}
        if req["status"] != "pending":
            return {"ok": False, "message": f"Request {request_id} is already '{req['status']}'."}
        today, status = _today(conn), ("approved" if approve else "rejected")
        conn.execute("UPDATE approval_requests SET status = ?, decided_by = ?, decided_on = ?, decision_note = ? "
                     "WHERE id = ?", (status, approver, today, note, request_id))
        if not approve and req["kind"] == "purchase_order":
            conn.execute("UPDATE purchase_orders SET status = 'rejected' WHERE id = ?", (req["ref_id"],))
        if req["ticket_id"]:
            conn.execute("UPDATE tickets SET notes = COALESCE(notes || char(10), '') || ? WHERE id = ?",
                         (f"[{today} {approver}] {status.capitalize()} request {request_id} ({req['kind']}, "
                          f"${req['amount']:,.2f} to {req['payee']}). {note}".strip(), req["ticket_id"]))
        return {"ok": True, "request": _row(conn, "SELECT * FROM approval_requests WHERE id = ?", (request_id,))}


@mcp.tool
def reset_working_database() -> dict:
    """HUMAN ONLY - never given to agents. Copy the untouched original
    (data/campus_customs.db) over the working database, undoing all agent work. Run this
    before a full run that resolves tickets. The original file is only read."""
    if DB_PATH.resolve() == ORIGINAL_DB_PATH.resolve():
        return {"ok": False, "message": "Refused: the working database path points at the original."}
    shutil.copyfile(ORIGINAL_DB_PATH, DB_PATH)
    with _connect() as conn:
        return {"ok": True, "working_db": DB_PATH.name, "date_today": _today(conn), "cash": _cash(conn),
                "open_tickets": conn.execute("SELECT COUNT(*) FROM tickets WHERE status = 'open'").fetchone()[0]}


@mcp.tool
def pay(request_id: int) -> dict:
    """Pay an approval request that a HUMAN has already approved. Refuses if the request is
    pending, rejected or already paid, if the amount no longer matches the database, or if
    checking does not have enough cash (no negative balances). On success it records the
    payment, lowers the checking balance, and updates the paid item: the invoice is marked
    paid, the lease's next_due moves forward one month, or the purchase order is ordered."""
    with _connect() as conn:
        req = _row(conn, "SELECT * FROM approval_requests WHERE id = ?", (request_id,))
        if req is None:
            return {"ok": False, "message": "No approval request with this id."}
        if req["status"] != "approved" or not req["decided_by"]:
            return {"ok": False, "status": req["status"],
                    "message": f"Refused: request {request_id} is '{req['status']}'. "
                               "Only requests a human has approved can be paid."}
        today = _today(conn)
        if req["kind"] == "invoice_payment":
            inv = _row(conn, "SELECT * FROM invoices WHERE id = ?", (req["ref_id"],))
            if inv is None or inv["status"] != "open":
                return {"ok": False, "message": "Refused: the invoice is missing or no longer open."}
            amount, pay_kind = inv["amount"], "invoice"
        elif req["kind"] == "rent_payment":
            lease = _row(conn, "SELECT * FROM leases WHERE id = ?", (req["ref_id"],))
            if lease is None:
                return {"ok": False, "message": "Refused: the lease is missing."}
            amount, pay_kind = lease["monthly_rent"], "rent"
        else:
            po = _row(conn, "SELECT * FROM purchase_orders WHERE id = ?", (req["ref_id"],))
            if po is None or po["status"] != "pending_approval":
                return {"ok": False, "message": "Refused: the purchase order is missing or not awaiting payment."}
            if not _vendor_status(conn, po["vendor_id"])["can_ship_new_product"]:
                return {"ok": False, "message": "Refused: this vendor now has an open unpaid invoice."}
            amount, pay_kind = po["total"], "purchase_order"
        if round(amount, 2) != round(req["amount"], 2):
            return {"ok": False, "message": f"Refused: approved amount {req['amount']} no longer matches {amount}."}
        balance = conn.execute("SELECT balance FROM cash_accounts WHERE name = 'checking'").fetchone()[0]
        if balance < amount:
            return {"ok": False, "balance": balance, "amount": amount,
                    "message": f"Refused: checking has ${balance:,.2f}, not enough for ${amount:,.2f}. "
                               "Balances may not go negative."}
        pid = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, 'checking', ?, ?)",
            (pay_kind, req["ref_id"], amount, today, req["decided_by"])).lastrowid
        conn.execute("UPDATE cash_accounts SET balance = balance - ?, date = ? WHERE name = 'checking'", (amount, today))
        if pay_kind == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (req["ref_id"],))
        elif pay_kind == "rent":
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (_add_month(lease["next_due"]), req["ref_id"]))
        else:
            vendor = _vendor_status(conn, po["vendor_id"])
            conn.execute("UPDATE purchase_orders SET status = 'ordered', expected_arrival = ? WHERE id = ?",
                         (vendor["earliest_arrival_if_ordered_today"], req["ref_id"]))
        conn.execute("UPDATE approval_requests SET status = 'paid', payment_id = ? WHERE id = ?", (pid, request_id))
        return {"ok": True,
                "payment": _row(conn, "SELECT * FROM payments WHERE id = ?", (pid,)),
                "cash": _cash(conn)}


# --------------------------------------------------------------------------- facilities

@mcp.tool
def get_lease(lease_id: int) -> dict:
    """Look up a shop lease: space, landlord, monthly rent and next due date (leases table).

    Use this for rent tickets (e.g. ticket 102 links to lease_id 1). days_until_due is
    measured from desk.date_today.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
            (lease_id,),
        ).fetchone()
        today = _today(conn)
    if row is None:
        return {"found": False, "lease_id": lease_id, "message": "No lease with this id."}
    return {"found": True, **dict(row), "days_until_due": _days_between(today, row["next_due"])}


@mcp.tool
def list_leases() -> dict:
    """List every lease with rent and days until the next due date (from desk.date_today)."""
    with _connect() as conn:
        today = _today(conn)
        rows = _rows(conn, "SELECT * FROM leases ORDER BY next_due")
    for r in rows:
        r["days_until_due"] = _days_between(today, r["next_due"])
    return {"date_today": today, "leases": rows}


# --------------------------------------------------------------------------- customer service

@mcp.tool
def draft_message(ticket_id: int, audience: str, recipient: str, subject: str, body: str, created_by: str) -> dict:
    """Save a message as a DRAFT on the board for a human to review. audience is 'customer',
    'vendor' or 'landlord'. Nothing is emailed or sent to anyone."""
    if audience not in DRAFT_AUDIENCES:
        return {"ok": False, "message": f"audience must be one of {list(DRAFT_AUDIENCES)}."}
    with _connect() as conn:
        did = conn.execute(
            "INSERT INTO drafts (ticket_id, audience, recipient, subject, body, created_by, created_on) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ticket_id, audience, recipient, subject, body, created_by, _today(conn))).lastrowid
        return {"ok": True, "sent": False, "draft": _row(conn, "SELECT * FROM drafts WHERE id = ?", (did,))}


@mcp.tool
def list_drafts(ticket_id: int | None = None) -> dict:
    """List drafted messages, optionally for one ticket. Drafts are never sent by the system."""
    with _connect() as conn:
        rows = _rows(conn, "SELECT * FROM drafts" + (" WHERE ticket_id = ?" if ticket_id else "") + " ORDER BY id",
                     (ticket_id,) if ticket_id else ())
    return {"count": len(rows), "drafts": rows}


if __name__ == "__main__":
    mcp.run(show_banner=False)
