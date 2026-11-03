# AI Prompts

## <span style="color:blue"><b>Problem 1: Vibe Coder Prompts</b></span>

### 2026-11-02 17:03

AI for managers homework 5

### 2026-11-02 17:04

Confirm you can find the Homework 5 folder in my AI for managers folder at the following filepath: C:\Users\kenri\OneDrive\Documents\Yale\Canvas Course Info\MGT 409 - AI for Managers-

### 2026-11-02 17:06

Similar to other problems, Please create an AI_prompts.md file in the Homework 5 folder that logs all of my prompts.  Please also create a new header for each problem with the title.

### 2026-11-02 17:10

Scenario: Campus Customs Multi-Agent Operations is the agentic team that runs the shop.  Open tickets land on a board - customer orders, rent, unpaid bills, discount requests, whatever the shop has to handle.  You will build three pieces that talk to each other: an MCP server, a FastAPI backend with a multi-agent team, and a React dashboard so a human can watch the agents at work and approve requests. 

The agent team should have full connectivity - any agent may delegate tasks to any other agent for help.  In this assignment you will build these agents: 

* Boss-reads each ticket, decides who should work on it, and makes final calls

### 2026-11-02 17:16

* Inventory- checks stock by sku and size, spots shortfalls, and figures out which vendor can restock
* Accounting: watches cash and invoices, checks margins, and prepares payments or purchases orders for human approval
* Facilities- handles the shop space side (leases, rent, etc.)
* Customer Service- drafts messages for customers


Data:
There are two campus_customs.db files in the Homework 5 folder under data, please only edit/modify the campus_customs_new.db file, I want to keep the campus_customs.db file original for later comparison purposes- I need the campus_customs.db file untouched so we can reset when we want to start resolving tickets.

Rules of this shop:

* The filed desk.date_today is "today" for the shop.  Use this date to determine what's overdue.
* Vendor lead time comes from the vendors table
* A vendor won't ship new product while they still have open unpaid invoice
* Human approval required for any payments.  Points will be deducted if this is not done.  If payment is made, make sure to update relevant table.
* If not enough cash, pay tool must refuse - no negative balances.
* Cash only goes out in this homework- we didn't model revenue, so no money comes in
* Before full run to resolve tickets, make sure to reset database to original values
* Do NOT email customers or call real vendors.  Drafts stay on the board.

### 2026-11-02 17:19

Problem 1: Vibe Coder Prompts
Create AI_prompts.md in the Homework 5 folder

## <span style="color:blue"><b>Problem 2: Study the Campus Customs database</b></span>

### 2026-11-02 17:21

Problem 2: Study the Campus Customs database.
Open data/campus_customs.db and look through every table and its fields.  A copy of this file has already been created, so no need to create another duplicate of this file.   
Study the three open tickets so you see how they link to other tables. 
Start output/harness.md.  For each table, list fields and one short line on why that table matters for the agents.  This harness file will keep growing in later problems.

## <span style="color:blue"><b>Problem 3: Build the MCP server</b></span>

### 2026-11-02 17:23

Problem 3: Build the MCP server

### 2026-11-02 17:26

Write and MCP server in mcp_server/ using FastMCP.  It will talk to data/campus_customs_new.db.  You do NOT need to connect or run it in this problem.  Every agent in this homework uses the tools in this MCP server.  You

### 2026-11-02 17:28

Write and MCP server in mcp_server/ using FastMCP.  It will talk to data/campus_customs_new.db.  You do NOT need to connect or run it in this problem.  Every agent in this homework uses the tools in this MCP server.  You will add more tools to it later; for now write three tools you know will be needed for tickets in the database.  Keep names clear.  Never invent any data, only use information in the database. 

In output/harness.md, list each of your three MCP tools.  For every tool include: which table it reads, which ticket it helps unlock (101, 102, or 103), and one sentence on why that tool is the right one for that ticket.  Vague lines like "reads inventory" score low- tie the tool to the ticket.  

Also add a short mcp_server/README.md file that explains that the MCP server is for, which database file it uses, and the three tools it has.

## <span style="color:blue"><b>Problem 4: Add the MCP server to vibe coder and test each tool</b></span>

### 2026-11-02 17:31

Problem 4: add the MCP ser er to vibe coder and test each tool

### 2026-11-02 17:36

Yes, test natively

### 2026-11-02 17:36

Add the MCP server to this project to Claude Code can call the tools.  Save the connection JSON text in .mcp.json at the project root (or however Claude Code saves local MCP server lists.

### 2026-11-02 17:38

WIth vibe coder connected, test each of the three MCP tools.  Save evidence in output/mcp_smoke.json.  For every tool, include: 

* prompt asked of the vibe coder;
* Tool name;
* Tool output (must match values in data/campus_customs_new.db)

## <span style="color:blue"><b>Problem 5: Build the agent team and grow the MCP tools</b></span>

### 2026-11-02 17:39

Problem 5: Build the agent team and grow the MCP tools

### 2026-11-02 17:43

Build agentic team for Campus Customs using PydanticAI: Boss, Inventory, Accounting, Facilities, and Customer Service.  Include prompts, models and agent loops so they can delegate work to each other with full connectivity.  
Put agent prompts in backend/prompts/ - one file per agent.  Put data types in backend/models.py, and the agent files under backend/ (your layout can vary as long as the five roles are clear).  
Write each prompt in your own words with shop rules that agent needs.  More detailed prompts that cover all aspects of an agent's work and scope score higher than short generic prompt.

### 2026-11-02 18:03

please pass the API key from my windows user variable

### 2026-11-02 18:07

Reset the DB

### 2026-11-02 18:10

Add any tools agent needs to MCP server so they can work on open tickets.  Shop facts come from MCP server over data/campus_customs_new.db - do not invent second shop-tools layer that bypasses MCP.  

Wire agents so they append to output/audit_trail.json as they run: for each agent-loop step, record enough to audit later.  Append to this file- do not wipe it each run.  

In output/harness.md, list each agent and each MCP tool (including ones you add in this problem) along with which table the tool uses.  Also add a short safety section: the guardrails a real business would want when agents touch real customers and real money, plus limits that keep token use in check.  

Update mcp_server/README.md so tool list matches what you have now.

### 2026-11-02 19:17

Yes, run ticket 101

## <span style="color:blue"><b>Problem 6: Plan the three tickets</b></span>

### 2026-11-02 19:20

Before you wire the backend, write down what you expect the team to do on each open ticket.  Build output/desk_tickets.html - a page you can double-click with one tab per ticket (101, 102, 103).  Also add empty cash and reflection tabs for later problems (leave them blank or with a short "coming later" note for now).  
On each ticket tab, fill an Expected section only (leave room for an Actual section you will fill after you run the agents).  
For each ticket's Expected section, write in your own words: 

* Who the Boss should call first, and why
* All the agent delegations you expect- not "Boss calls everyone"
* Which MCP Tools you expect that run to use

Plans that send every specialist on every ticket score low.  You will compare this plan to what actually happens when the agents resolve 3 tickets.

### 2026-11-02 19:31

Yes, my prior prompt was for Problem 6: Plan the three tickets.  Please move my prior prompt to under Problem 6.

### 2026-11-02 19:32

Yes please run the board now and fill in the Actual sections.

## <span style="color:blue"><b>Problem 7: Backend routes</b></span>

### 2026-11-02 19:33

New problem: Problem 7: backend routes

### 2026-11-02 19:34

Your react frontend dahsboard (the next problem) needs a backend it can call.  In backend/main.py, use FastAPI and add routes that do the following: 

* Return the three tickets and whether each is open or resolved;
* Take a ticket id and run your agent team on that ticket:

### 2026-11-02 19:36

<task-notification>
<task-id>bee449vqk</task-id>
<tool-use-id>toolu_01DAM8uHMnBZxxbKoDydnL71</tool-use-id>
<output-file>C:\Users\kenri\AppData\Local\Temp\claude\C--Users-kenri-OneDrive-Documents-Yale-Canvas-Course-Info-MGT-409---AI-for-Managers--Homework-5\7ae323bb-d634-4fab-981d-7326d6b0ef7d\tasks\bee449vqk.output</output-file>
<status>completed</status>
<summary>Background command "Run the full board live against Claude" completed (exit code 0)</summary>
</task-notification>

### 2026-11-02 19:41

<pasted_content id="b03b">
Your react frontend dahsboard (the next problem) needs a backend it can call.  In backend/main.py, use FastAPI and add routes that do the following:

* Return the three tickets and whether each is open or resolved;
* Take a ticket id and run your agent team on that ticket:
</pasted_content id="b03b">

* Return recent agent events- what each agent said and which tools they used- so the board can refresh;
* Approve a payment or purchase after a human clicks approve (agents only prepaer the pay; this route is what actually changes cash);
* Return current checking balance from cash_accounts;
* Reset the database to the original values when you want to try a fresh run


From the backend/ folder, start server with: uvicorn main:app --reload --port 8000
This turns on your backend at http://localhost:8000 so the frontend dashboard can call those routes.  In output/harness.md, list each route in one line (what URL/what it does).

## <span style="color:blue"><b>Problem 8: Agent Dashboard</b></span>

### 2026-11-02 19:50

New problem 8: Agent Dashboard

### 2026-11-02 19:52

Build the frontend dashboard in frontend/ with React+Vite+TypeScript.  THe page should call the routes you built in Problem 7.  At minimum the board should: 

* List all 3 tickets;
* Let me pick one ticket and start the agent team on it;
* Show each agent and what they are saying/doing while the ticket runs;
* Mark a ticket resolved when the run finishes;
* Show a short summary of what each agent did on that ticket
* Let a human approve a pay or purchase when asked

### 2026-11-02 19:55

<pasted_content id="b03b">
Build the frontend dashboard in frontend/ with React+Vite+TypeScript.  THe page should call the routes you built in Problem 7.  At minimum the board should:

* List all 3 tickets;
* Let me pick one ticket and start the agent team on it;
* Show each agent and what they are saying/doing while the ticket runs;
* Mark a ticket resolved when the run finishes;
* Show a short summary of what each agent did on that ticket
* Let a human approve a pay or purchase when asked
</pasted_content id="b03b">

* Show the checking balance (it should drop after an approved pay)

Make the dashboard look good. Be creative with layout and feel- this is a real desk people would want to sit at, so put thought into how it looks. 
Tell the front end to talk to your backend at http://localhost:8000.  On the backend, allow the Vite page origin (usually http://localhost:5173) so the browser is allowed to call those routes.  Start the board wtih: npm run dev.  This opens the React desk in your browser so you can pick tickets and watch agents.  
Write output/design.md wtih what you chose for the daskboard look (layout, how agents read differently, how resolved tickets and cash show up) and why- including teh creative choices that make it feel special and something humans would actually enjoy using.

## <span style="color:blue"><b>Problem 9: Resolve the tickets</b></span>

### 2026-11-02 20:19

New Problem 9: Resolve the tickets

### 2026-11-02 20:28

Before testing the agents on a full run over the three tickets, reset the working database data/campus_customs_new.db again so you start clean.  Note the starting checking balance.  Then run all three tickets on the board (101, 102, 103) until each is resolved.  
Open output/desk_tickets.html from Problem 6.  On each ticket tab, fill the Actual section from this run: which agents worked, what they delegated, and which tools they used.  Keep your Expected section so you can compare the two. 
On the Cash tab of the same output/desk_tickets.html, itemize the money: 

* starting checking balance (after the reset);
* For each ticket: how cash changed when that ticket resolved, and why (which pay/purchase, dollar amount)
* Ending checking balance- it must match cash_accounts in the working database

Wrong math loses points even if the board shows all the tickets are resolved.  Also save:

* output/resolved_tickets.json- for each ticket; id, final status, short outcome, what each agent contributed, and any human approvals
* output/resolved_board.html- a page you can double click wtih screenshot of React board for each resolved ticket (101, 102, and 103)

Append real runs to output/audit_trail.json.  Finish output/harness.md so it covers tables, MCP tools, five agents, API routes, dashboard, and safety rules.

### 2026-11-02 20:33

<task-notification>
<task-id>bnpt5nrta</task-id>
<tool-use-id>toolu_01YYNBhAYggbgssq6Bbfi9an</tool-use-id>
<output-file>C:\Users\kenri\AppData\Local\Temp\claude\C--Users-kenri-OneDrive-Documents-Yale-Canvas-Course-Info-MGT-409---AI-for-Managers--Homework-5\7ae323bb-d634-4fab-981d-7326d6b0ef7d\tasks\bnpt5nrta.output</output-file>
<status>completed</status>
<summary>Background command "Run tickets 101, 102, 103 through the API" completed (exit code 0)</summary>
</task-notification>

### 2026-11-02 20:34

Sign them as Ken Rice

### 2026-11-02 20:37

<task-notification>
<task-id>bsu60su73</task-id>
<tool-use-id>toolu_013ZsaMA6PRUpuQZPYhH88L5</tool-use-id>
<output-file>C:\Users\kenri\AppData\Local\Temp\claude\C--Users-kenri-OneDrive-Documents-Yale-Canvas-Course-Info-MGT-409---AI-for-Managers--Homework-5\7ae323bb-d634-4fab-981d-7326d6b0ef7d\tasks\bsu60su73.output</output-file>
<status>completed</status>
<summary>Background command "Re-run tickets 102, 101, 103 after the payments" completed (exit code 0)</summary>
</task-notification>

### 2026-11-02 20:38

Yes, sign #3

## <span style="color:blue"><b>Problem 10: Reflection</b></span>

### 2026-11-02 20:48

New Problem 10: Reflection

### 2026-11-02 20:53

Open output/desk_tickets.html and fill the Reflection tab.  Answer in your own vibe, and be detailed and thorough: 

* How would you evaluate the performance of the agents on each ticket and why?
* For each ticket, how did Actual compare to the Expected plan you wrote earlier? 
* What would have been simpler as one agent with tools- and why?
* Described 3 new problems Campus Customs might face that this agent team could solve with the tools you built.  
* Described 3 new problems Campus Customs might face that this agent team could NOT solve with tools you built, and explain the tools and agents you would need to solve them.

Tie every answer to THIS app and the three tickets you ran- use the tickets tabs and cash tab on the same page as your evidence. Generic AI essays without Campus Customs details will score low.

## <span style="color:blue"><b>Problem 11: Submit to Github</b></span>

### 2026-11-02 21:11

New Problem 11: Submit to Github:
Please verify that my Homework 5 folder has all of the files shown in the screenshot attached.

### 2026-11-02 21:13

Yes, create them

### 2026-11-02 21:16

Push the code to a public GitHub repository so graders can clone it.   Do NOT push the real .env to the GitHub repo.  DO include both database files under data/ (the original and my working copy) so graders can run our app easily.  
README should explain: copy original DB to the working copy when you need a clean run, start MCP server, start FastAPI backend, start the React board, reset the DB before a full three-ticket run.
