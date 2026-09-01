# IBM Customer Stories — Simple Instructions for Anita

Welcome! This guide tells you exactly what to do, step by step.
You do not need to know anything about programming.

---

## What You Have

Inside this folder you will find four files with numbers in their names.
You run them in order by **double-clicking** them, just like opening any file.

| File | What it does | When to run it |
|---|---|---|
| `1_SETUP.bat` | Installs Python + Node.js packages and saves your Tavily key | **Once only** — the very first time |
| `2_TEST_10_STORIES.bat` | Downloads 10 IBM customer stories as a test | After setup — to check everything works |
| `3_RUN_ALL_STORIES.bat` | Downloads ALL IBM customer stories (Python / Tavily) | After approving the test |
| `4_OPEN_DASHBOARD.bat` | Opens the explorer in your browser | Any time you want to look at the data |
| `5_SAVE_API_KEY.bat` | Saves your Tavily API key (finds more stories) | If you have a Tavily key |
| `6_REBUILD_DASHBOARD.bat` | Rebuilds the dashboard from the Crawlee output | After a successful Crawlee crawl |

To run the full Crawlee crawler (finds 1,000+ stories from IBM.com):
```
node node_modules/ts-node/dist/bin.js scripts/crawl-ibm-case-studies.ts
```
Or open a Command Prompt in this folder and run `npm run crawl`.

---

## Step-by-Step Instructions

### Step 1 — Run setup (do this once only)

1. Double-click **`1_SETUP.bat`**
2. A black window will appear and show you what it is doing.
3. It will install all required tools, then ask you for a **Tavily API key**.
4. Follow the on-screen instructions to get your free key (takes 2 minutes — see below).
5. Paste the key into the window and press **Enter**.
6. Wait for it to say **"SETUP COMPLETE — You are ready to go!"**
7. Press any key to close the window.

> If it shows an error about Python not being found, please install Python from
> https://www.python.org/downloads/ — tick the box that says **"Add Python to PATH"** — then try again.

---

### 🔑 Getting your free Tavily API key

Tavily is a free search service that finds **many more IBM stories** than the website alone shows.
Without it the tool finds ~33 stories. With it, it can find 100–300+.

1. Go to **https://app.tavily.com/sign-up**
2. Sign up with your email address (no credit card needed)
3. Your API key appears on the dashboard — it starts with **`tvly-`**
4. Copy it and paste it when `1_SETUP.bat` asks

> You only need to do this once. The key is saved privately on your computer in a file called `.env`.
> Free tier = 1,000 searches per month, which is more than enough.

---

### Step 2 — Run the 10-story test

1. Double-click **`2_TEST_10_STORIES.bat`**
2. The black window will show you what it is downloading. This takes about 30–60 seconds.
3. When it finishes, your browser will open automatically with the dashboard.
4. The test Excel file will be created at: `output\IBM_Customer_Stories_TEST.xlsx`

**Please review the results before running the full collection.**

---

### Step 3 — Run the full collection (only after approving the test)

1. Double-click **`3_RUN_ALL_STORIES.bat`**
2. This will take longer — possibly 15–60 minutes depending on how many stories exist.
3. The window will show progress as it goes.
4. When finished, the full Excel file will be at: `output\IBM_Customer_Stories.xlsx`

> **Important:** Do not close the black window while it is running.

---

### Step 4 — Open the dashboard any time

Double-click **`4_OPEN_DASHBOARD.bat`** to open the filter dashboard in your browser
without re-running anything.

---

## What You Get

### Excel Workbook (`output\IBM_Customer_Stories.xlsx`)

It has **7 tabs**:

| Tab | What's in it |
|---|---|
| **Executive Summary** | Counts, coverage scores, top gaps at a glance |
| **Story Inventory** | One row per IBM case study with all details |
| **Proof Inventory** | One row per individual metric, quote or outcome |
| **Coverage Matrix** | Grid showing strong/weak coverage by GTM motion and region |
| **Evidence Pipeline** | Prioritised list of gaps with suggested next actions |
| **QA Exceptions** | Fields the tool couldn't identify — flagged for your review |
| **Run Log** | Record of every time you ran the tool |

### Dashboard (`output\dashboard\index.html`)

A webpage that opens in your browser (no internet needed).
You can filter by:
- Customer name
- Industry
- Geography / region
- IBM product
- GTM motion
- Open / Governed / Hybrid
- Structured or unstructured data
- Proof strength (Strong, Medium, Weak, Restricted)
- How old the story is

---

## Important Notes

- **Nothing is invented.** When the tool cannot identify a value (e.g. the geography), it writes
  "Needs review" and adds it to the QA Exceptions tab for you to check.
- **Everything is saved locally.** No data leaves your computer. No login is needed.
- **The cache saves time.** Pages you have already downloaded are not downloaded again.
  You can run the tool again and it will only fetch new pages.
- **Proof-strength explained:**
  - 🟢 **Strong** — Named company + real number + IBM product credited
  - 🔵 **Medium** — Named company + qualitative outcome or quote
  - 🟡 **Weak** — Product adoption mentioned but no clear outcome
  - ⚪ **Restricted** — Projected, estimated, partner-reported or unnamed customer

---

## If Something Goes Wrong

1. Look at the black window — it will show an error message.
2. Check the log file: `logs\run_log.txt` (open it in Notepad).
3. Try running `1_SETUP.bat` again.
4. If the problem persists, share the content of `logs\run_log.txt` with your technical contact.

---

## Folder Map

```
IBM_Customer_Stories\
│
├── 1_SETUP.bat               ← Run once to set up
├── 2_TEST_10_STORIES.bat     ← Run to test 10 stories
├── 3_RUN_ALL_STORIES.bat     ← Run to collect everything
├── 4_OPEN_DASHBOARD.bat      ← Open the dashboard
│
├── output\
│   ├── IBM_Customer_Stories_TEST.xlsx   ← Test results
│   ├── IBM_Customer_Stories.xlsx        ← Full results
│   └── dashboard\
│       └── index.html                   ← Dashboard webpage
│
├── cache\                    ← Downloaded pages (do not delete)
├── logs\
│   └── run_log.txt           ← Log of all runs
└── src\                      ← Application code (do not edit)
```

---

*Questions? Share this folder and the `logs\run_log.txt` file with your technical contact.*
