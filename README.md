# Construction Work Journal

A simple daily log app for a small construction crew. Workers record what they did each day; you can filter the journal and export everything to an Excel spreadsheet.

## Features

- **New entry** — date, worker, project/job site, weather, hours, work performed, crew notes, materials, issues/delays, safety notes
- **Journal** — browse, filter (date range / worker / project), edit, delete
- **Crew & projects** — add workers and job sites; deactivate old ones without losing history
- **Excel export** — one `.xlsx` with:
  - **Export Info** — when generated, filters used, totals
  - **All Entries** — every log row (filterable columns in Excel)
  - **By Worker** — entry count and total hours per person
  - **By Project** — entry count and total hours per job site

Data is stored locally in `data/journal.db` (SQLite). No login or internet required.

## Run

```bash
cd ~/construction-journal
pip3 install -r requirements.txt
streamlit run app.py
```

Then open the URL Streamlit prints (usually http://localhost:8501).

## Suggested daily flow

1. Open **Crew & projects** once and set up real worker names and job sites.
2. Each day, open **New entry** and save a log (takes about a minute).
3. When you need a report for a client, superintendent, or payroll overview, go to **Excel export**, set the date range, and download.

## Sample data

On first launch the app seeds three sample workers and three sample projects so you can try the form immediately. Replace or deactivate them under **Crew & projects**.
