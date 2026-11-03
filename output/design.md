# Campus Customs Desk: design notes

The dashboard (`frontend/`, React + Vite + TypeScript) is designed as a **back-office desk** rather than an admin panel. The person using it is the shop owner: they don't want to read logs, they want to see their staff work, sign what needs signing, and know how much money is left. So every part of the screen borrows from a physical object a small-shop owner already understands: paper tickets on a spike, a team on the shop floor, a cash register, a chequebook and an outbox.

Start it with `npm run dev` in `frontend/` (opens http://localhost:5173). It talks to the FastAPI backend at http://localhost:8000 (`VITE_API_URL` in `frontend/.env`), and the backend allows the Vite origin for CORS.

## Layout

Three columns, read left to right like a working day: **what came in → who's working on it → what needs me.**

| Area | What it is | Why |
|---|---|---|
| **Masthead** (navy band, gold rule) | Brand mark; a tear-off **desk calendar** showing the shop's date (2026-08-31, from `desk.date_today`, not the computer clock); a brass **nameplate** where you type your name; the **cash register**; **⟲ Fresh start** (reset). | The things that are always true about the shop sit at the top, like a counter: what day it is, who's signing, how much is in the till. |
| **Left: the ticket spike** | Each ticket is a paper slip with a perforated top edge, a slight tilt, the ticket number in mono, the requester, the exact ask (`1 × CC-TEE-WHITE · size S`) and the original note in quotes. The selected slip slides out with a navy edge and gets the **Start the team** button. | Tickets *are* paper in a shop. Tilted slips feel like a real spike rather than a table, and only the selected slip carries a button, so it's always clear what you're about to run. |
| **Center: the floor** | The Boss's desk at the head, four specialist desks below, joined by curved "wires". Below the floor is **the wire**, a live transcript of the run. After a run, the **shift report** appears: the Boss's call on a yellow sticky memo, then one card per agent. | This is the show. You watch the Boss hand work out and each specialist pick it up, so the multi-agent idea is something you *see*, not something you read about. |
| **Right: what needs me** | The **signature tray** (approvals as cheques) and the **outbox** (drafts as envelopes). | Everything that needs a human sits in one column, on the side where your hand is. |

Below 1240px the right column moves under the other two; below 760px everything stacks into one column (checked at 375px with no sideways scrolling).

## How the agents read differently

Each agent has **its own colour, its own badge and its own voice (a typeface)**. You can tell who is talking without reading the name, and the transcript doesn't turn into a grey wall of text.

| Agent | Colour | Badge | Voice | Why |
|---|---|---|---|---|
| Boss | Yale navy | **B** in serif | Fraunces serif, medium weight | The decision-maker sounds like a memo: calm and authoritative. |
| Inventory | Teal | **In** | IBM Plex Mono | Stock counts, SKUs and sizes are data, so they read like a stock sheet. |
| Accounting | Ledger green | **$** | Tabular figures | Numbers line up like a ledger column. |
| Facilities | Terracotta / brick | **Fa** | Sturdy medium sans | Buildings and leases: solid and plain. |
| Customer Service | Warm rose | **CS** | Italic | A friendly, human hand, because these are the people who write to customers. |

On the **floor**, each desk shows its state in plain words: *At desk*, *Thinking*, *Using tools*, *Waiting on a teammate*, *Done*, or *Not on this ticket*. A tool counter shows how many tools it used, and "asked ×2" appears if it was handed work more than once.
- **While a run is live,** the desk that's currently working lifts slightly and glows in its colour, with animated typing dots and a speech bubble showing what it's doing right now. For example `check_stock(CC-TEE-WHITE, S)`, or "Asking Accounting…". The wire from the Boss to that desk turns into moving dashes.
- **Once the run is done,** agents the Boss never called fade to 45% opacity. That makes the planning question from Problem 6 ("who did the Boss call?") answerable at a glance: on ticket 101, Facilities is visibly benched.

On **the wire** (the transcript), each line has a coloured left rule, the agent's name in its colour, and the agent's voice. Nested hand-offs are indented by delegation depth, so Boss → Inventory → Accounting reads as a tree.
- **Hand-offs** read as quoted briefs: **→ Accounting** "Ticket 101: request approval to pay invoice 501…".
- **Tool calls** are small mono receipt chips.
- **Results** are dashed chips with the key fact pulled out: "get_lease $2,400.00 due 2026-09-02", "blocked by open invoice".
- **Refusals** turn red, so a guardrail firing (an unapproved `pay`, a blocked vendor) jumps out.

## Resolved tickets

When the run finishes, a **red rubber stamp thumps onto the slip**. It reads RESOLVED (it scales in from 2.4× with a little overshoot), with the Boss's detailed status in small caps underneath: *Needs your signature*, *In progress*, *Closed*. A toast confirms "Ticket 102: the team has made its call."
- **Why resolved = "the agents have made their call":** that's the moment the desk's job flips from watching to deciding. The small print keeps it honest, because a ticket can be resolved by the team and still need you.
- **The sign flag:** a gold **✍ sign #1** flag sits on any ticket with a payment waiting, and disappears the moment you sign.
- **While agents work,** a red pin pulses on the slip and "● LIVE" blinks above the floor.

The **shift report** is the after-action summary. The Boss's decision sits on a pinned yellow sticky memo with its next steps. Below it, each agent that worked the ticket gets a card with:
- who asked it
- a one-paragraph summary in its own voice
- tool-tally chips (`quote_discount ×3`)
- what it left for you: ✍ requests filed, ✉ drafts saved, ⚠ blockers

## Cash and approvals

**The register.** Checking is shown as a dark cash-register display with glowing green digits (mono, tabular), because money is the one number the owner always watches.
- **What's committed:** a thin amber-to-red meter shows how much of the balance is already requested and waiting on a signature, with "$3,240 awaiting signature · $160 if all signed" underneath. The owner sees *before* signing that rent plus the invoice leaves only $160.
- **When a payment goes through:** the digits **roll down** to the new balance over about a second, and a little paper receipt reading **−$2,400.00** tears off below the register and drifts away. Tested on a scratch DB: $3,400.00 → $1,000.00.
- **Cash never goes up.** No revenue is modelled, so a green LED reminds you this till only drains.

**The signature tray.** Each payment or purchase order the agents prepared is drawn as a **cheque**. It has a guilloche background, "Pay to the order of Elm City Properties", the amount in a box *and* spelled out ("Two thousand four hundred and 00/100 dollars"), a numbered top-right (No. 0002), and a memo line saying which agent prepared it, for which ticket, and why.
- **Signing:** your name from the nameplate appears on the signature line in a handwritten script. **Sign & pay** is the only control in the app that moves money, and it stays disabled until you've entered a name.
- **Voiding:** **Void** rejects the request instead.
- **Too big to pay:** if a cheque is larger than the balance, it gets a red border and a warning *before* you click, because `pay` would refuse it.
- **Afterwards:** decided requests drop into a short list with PAID / VOID stamps and who signed.

Why cheques: the human-approval rule is the most important control in the system. Turning it into a physical act (reading the payee, seeing the amount in words, signing your own name) makes it feel deliberate rather than like clicking OK on a dialog.

**The outbox.** Drafts are envelopes marked "Draft #3" with a dashed rose badge. Click one to read the letter. The header says *drafts · never sent*, because nothing in this system emails anyone.

## Details that make it feel like a place

- **Warm paper on a wood-grain desk** (subtle repeating stripes) instead of white-on-grey SaaS. A **dark mode** ("the desk after hours") follows the system setting.
- **Fraunces** for headings and the Boss, **IBM Plex Sans** for body text, **IBM Plex Mono** for anything that's data.
- **Physical metaphors throughout,** all drawn in CSS and SVG with no images: slips with perforations, a rubber stamp, a sticky memo with tape, a brass nameplate, a tear-off calendar, cheques and envelopes.
- **Motion with a purpose:** the stamp thump on resolve, the till rolling down on payment, transcript lines sliding in, typing dots on the working desk. All of it switches off under `prefers-reduced-motion`.
- **Forgiving:** your signing name is remembered between visits. A clear banner explains how to start the backend if it isn't running, and another warns if the server has no API key. A run in progress survives a page refresh, because the desk asks `/health` which ticket is running and picks the transcript back up.
- **Honest:** only one run at a time (the shared till), Reset asks for confirmation, and the Boss's real status always sits under the RESOLVED stamp.

## How it talks to the backend

| Desk feature | Route |
|---|---|
| Ticket slips, stamps, sign flags | `GET /tickets` (every 8 s while idle; after every action) |
| Start the team | `POST /tickets/{id}/run`, then `GET /events?run_id=…&after=<last id>` every second until `running` is false |
| Floor desks, speech bubbles, the wire | `GET /events` (what each agent said, tools called, results, refusals) |
| Shift report | `GET /tickets/{id}/summary` |
| Register | `GET /cash` |
| Cheques, Sign & pay, Void | `GET /approvals?status=all`, `POST /approvals/{id}/approve`, `POST /approvals/{id}/reject` |
| Outbox | `GET /drafts` |
| Calendar, banners, resuming a live run | `GET /health` |
| Fresh start | `POST /reset` |
