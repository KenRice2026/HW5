# Campus Customs Desk (frontend)

React + Vite + TypeScript dashboard for the Campus Customs agent team.

```bash
npm install
npm run dev
```

`npm run dev` serves the desk at http://localhost:5173 and opens it in your browser. Start the backend first, from `backend/`:

```bash
uvicorn main:app --reload --port 8000
```

The backend URL is set in `.env` (`VITE_API_URL=http://localhost:8000`), and the backend allows the `http://localhost:5173` origin for CORS.

| File | What it is |
|---|---|
| `src/App.tsx` | State, polling while agents run, approve/void, reset |
| `src/api.ts` | Typed client for the backend routes |
| `src/agents.ts` | Each agent's colour, badge and voice; money and amount-in-words helpers |
| `src/feed.ts` | Turns `/events` into transcript lines and desk states |
| `src/components/` | `TicketSpike`, `Floor`, `Wire`, `ShiftReport`, `Register`, `SignatureTray`, `Outbox` |

Design notes are in `../output/design.md`.
