# In-Spec Team Work Journal  
## Simple User Manual

**App website:** https://inspecworkjournal.streamlit.app/

This guide is for crew members and supervisors who use the journal day to day.  
You do not need any technical setup to use the app—only the website link and your login.

---

## 1. What this app is for

The **In-Spec Team Work Journal** is a shared daily log for the crew.

Use it to:

- Record what was done each day on a job site  
- Note weather, hours, materials, issues, and safety  
- Look up past entries  
- Download an **Excel spreadsheet** overview of the logs  

Everyone who has a login uses the **same** shared journal.

---

## 2. How to open the app

1. Open a web browser on your phone, tablet, or computer  
   (Safari, Chrome, Edge, etc.).
2. Go to:  
   **https://inspecworkjournal.streamlit.app/**
3. Sign in with the **email and password** given to you by your admin.

**Tips**

- Bookmark the page so you can open it quickly.  
- The first load of the day can take a few seconds while the site wakes up.  
- Use **Sign out** (sidebar) when you finish on a shared device.

If you do not have a login, ask your admin—they add accounts; you cannot create one yourself.

---

## 3. The menu (left side)

After you sign in, use the **left sidebar** to move between pages:

| Menu item | What it does |
|-----------|----------------|
| **New entry** | Write today’s (or any day’s) work log |
| **Journal** | Browse, search, edit, or delete past logs |
| **Excel export** | Download a spreadsheet of entries |
| **Crew & projects** | Manage worker names and job sites (usually admin) |

Your name and email appear in the sidebar when you are signed in.

---

## 4. New entry — daily log (most common task)

**When:** End of shift, or whenever work for a day should be recorded.

### Steps

1. Open **New entry**.  
2. Fill in the form:

| Field | Required? | What to enter |
|-------|-----------|----------------|
| **Date** | Yes | Day the work was done (defaults to today) |
| **Worker** | Yes | Who did the work (your name or the person logging) |
| **Project / job site** | Yes | Which site or project |
| **Weather** | Yes | Pick from the list |
| **Hours worked** | Yes | Hours for that day (e.g. 8, 7.5) |
| **Work performed** | **Yes** | Main description of what was done |
| **Crew notes** | No | Who was on site, subs, headcount |
| **Materials** | No | Deliveries, materials used, shortages |
| **Issues / delays** | No | Weather delays, missing materials, access problems |
| **Safety notes** | No | Incidents, near misses, toolbox talks, PPE |

3. Tap or click **Save entry**.  
4. You should see a success message (and a short thumbs-up celebration).  
5. The form clears so you can add another entry if needed.

### Tips for good logs

- Be specific: *“Formed north wall footings; rebar inspection passed”* is better than *“Worked on site.”*  
- One entry per person per day is typical; use more than one if needed (e.g. two different sites).  
- You can backdate the **Date** if you are catching up.

If **Worker** or **Project** lists are empty, an admin must add them under **Crew & projects** first.

---

## 5. Journal — view and fix past entries

1. Open **Journal**.  
2. Use **Filters** if you want:
   - **From / To** dates  
   - **Worker**  
   - **Project**  
3. Browse the list. Each card shows date, person, site, hours, weather, and notes.  
4. To change an entry: choose **Edit** on that card, update fields, then **Update entry**.  
5. To remove an entry: choose **Delete**, then confirm.

**Note:** Deleting an entry cannot be undone. Prefer **Edit** if you only need a correction.

---

## 6. Excel export — spreadsheet overview

Use this when you need a file for the office, a client, or payroll review.

1. Open **Excel export**.  
2. Set the date range (and worker/project filters if you want a subset).  
3. Review the preview table on screen.  
4. Click **Download Excel spreadsheet**.  
5. Open the file in Excel, Google Sheets, or Numbers.

### What’s inside the file

| Sheet | Contents |
|-------|----------|
| **Export Info** | When it was created, filters used, totals |
| **All Entries** | Every matching log (one row per entry) |
| **By Worker** | Entry count and total hours per person |
| **By Project** | Entry count and total hours per job site |

**Tip:** Export regularly as a backup of your records.

---

## 7. Crew & projects — names and job sites

Usually managed by a supervisor or admin.

### Workers

- **Add worker** — type a name and add them so they appear in **New entry**.  
- **Deactivate** — person leaves or is not currently working; they drop off new-entry lists, but **old logs still show their name**.  
- **Activate** — bring them back to the lists.  
- **Delete** — only available if that person has **no** journal entries (e.g. a typo name). If they have logs, use **Deactivate** instead.

### Projects / job sites

Same idea:

- **Add project** for each job site or contract name.  
- **Deactivate** finished sites.  
- **Delete** only when the project has **no** linked entries.

This protects history: past logs stay accurate.

---

## 8. Quick daily checklist

| Step | Action |
|------|--------|
| 1 | Open the app link and sign in |
| 2 | Go to **New entry** |
| 3 | Choose date, worker, project, weather, hours |
| 4 | Write **Work performed** (required) |
| 5 | Add optional notes (crew, materials, issues, safety) |
| 6 | **Save entry** |
| 7 | Sign out if using a shared phone or computer |

Weekly or monthly: open **Excel export**, pick the period, download the spreadsheet.

---

## 9. Common questions

**I forgot my password.**  
Ask your admin to set a new password for your account. You cannot reset it yourself in the app.

**The website is slow the first time.**  
Normal on free hosting—wait a few seconds and try again. After it loads, moving between pages is usually faster.

**I don’t see my name or a job site.**  
Ask an admin to add or **Activate** them under **Crew & projects**.

**Can other people see my entries?**  
Yes. Everyone with a login shares the same journal. Only invited people with a password can open the app.

**Where is the data stored?**  
In a secure online database (Supabase), not only on your phone. Entries from any device show up for the whole team.

**Can I use it offline?**  
No. You need an internet connection.

**I saved the wrong day.**  
Open **Journal**, find the entry, **Edit**, change the date, and update.

---

## 10. Who to contact

| Issue | Contact |
|-------|---------|
| Need a login or password change | Your app admin / office contact |
| Wrong crew names or job sites | Admin — **Crew & projects** |
| App not loading or technical problems | Admin (they can check Streamlit / hosting) |

---

## 11. Do’s and don’ts

**Do**

- Log work the same day when possible  
- Use clear work descriptions  
- Deactivate people/sites instead of deleting when they have history  
- Export Excel for important periods  

**Don’t**

- Share your password  
- Delete entries unless you are sure  
- Expect the app to work without internet  
- Delete a worker or project that already has log entries (the app will block this)  

---

*In-Spec Team Work Journal — User Manual*  
*For everyday use by the crew. Technical setup (accounts, hosting, database) is handled by the administrator.*
