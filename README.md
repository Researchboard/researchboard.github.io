# ResearchBoard

A free website that updates **every day by itself** and shows, like a stock market board:

- how many papers were **added to PubMed** each day (overall and by country)
- how many papers were **published worldwide** each day
- how many **new citations** were made each day
- the **top countries** and **top universities** of the day
- the **top 5 scientists who gained the most citations** each day
- the **most-cited scientists** and **most-cited papers** (all time, and last 12 months)
- a **country view**: daily trend, top institutions and top scientists of any country

It costs nothing to run: GitHub stores the code and hosts the website, a GitHub
robot collects new numbers every morning, and the data comes from two free
sources, PubMed (NCBI) and OpenAlex.

```
 every day 06:17 UTC
 ┌───────────────┐     ┌──────────────────────┐     ┌────────────────────┐
 │ GitHub robot  │ ──► │ scripts/update_data.py│ ──► │ data/*.json saved   │
 │ (Actions)     │     │ asks PubMed+OpenAlex  │     │ website re-published│
 └───────────────┘     └──────────────────────┘     └────────────────────┘
                                                        │
                                   visitors open  ◄─────┘  index.html draws the graphs
```

---

## Setup (about 15 minutes, no coding)

### 1. Make a GitHub account
Go to <https://github.com> and sign up (free).

### 2. Put these files in a new repository
1. Click **+ → New repository**. Name it e.g. `researchboard`, choose **Public**, click **Create**.
2. Click **uploading an existing file**, drag in **everything from this folder**
   (including the hidden `.github` folder — on Mac press `Cmd+Shift+.` to show it,
   on Windows enable *Hidden items* in File Explorer), then **Commit changes**.
   Branch must be called `main`.

### 3. Get the free API keys (recommended)
- **OpenAlex:** sign up at <https://openalex.org>, then copy your key from
  <https://openalex.org/settings/api>. Without a key the site still works, but
  you only get a tenth of the free daily allowance.
- **NCBI (optional):** in your NCBI account settings, create an API key. This
  lets PubMed answer faster.

In your repository go to **Settings → Secrets and variables → Actions →
New repository secret** and add:

| Name | Value |
|---|---|
| `OPENALEX_API_KEY` | your OpenAlex key |
| `NCBI_API_KEY` | your NCBI key (optional) |

Optional, under the **Variables** tab of the same page:

| Name | Example | What it does |
|---|---|---|
| `EXTRA_COUNTRIES` | `BD,NP,LK` | always track these countries (2-letter codes) even if they are not in the day's top 25 |
| `CONTACT_EMAIL` | `you@example.com` | sent politely to the APIs so they can contact you |

### 4. Turn on the website and run it once
1. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
2. **Actions** tab → if asked, click *I understand… enable workflows*.
3. Click **Update data and publish site → Run workflow → Run workflow**.
   The first run takes ~5–10 minutes because it fills in the last 30 days.
4. When it shows a green tick, your site is live at
   `https://<your-username>.github.io/researchboard/`

From now on it updates itself every day. Nothing else to do.

### 5. Connect your own domain: researchboard.net

**A. In GitHub:** Settings → Pages → **Custom domain** → type `researchboard.net` → Save.
(No CNAME file is needed, because this site is published by GitHub Actions.)

**B. In Namecheap:** Domain List → `researchboard.net` → **Manage** → **Advanced DNS**.
Delete the default "parking page" records, then add:

| Type | Host | Value |
|---|---|---|
| A Record | `@` | `185.199.108.153` |
| A Record | `@` | `185.199.109.153` |
| A Record | `@` | `185.199.110.153` |
| A Record | `@` | `185.199.111.153` |
| CNAME Record | `www` | `YOUR-USERNAME.github.io.` |

**C. Wait and secure:** DNS can take from a few minutes up to 24–48 hours.
When GitHub shows "DNS check successful", tick **Enforce HTTPS** (this can take up to 24 hours to become available).

Recommended: in your GitHub profile Settings → Pages → **Add a domain** to verify
`researchboard.net`. GitHub gives you one TXT record to add in Namecheap. This stops
anyone else from using your domain on GitHub.

---

## Blog and social media

- **Blog:** write posts in the `posts/` folder (see `posts/README.md`). A "Today in Research"
  report with an image card is written automatically every morning.
- **Social media:** the daily report can be posted automatically to a Facebook Page and
  LinkedIn. See **SOCIAL_SETUP.md** for the keys you need.

## What each number means (read this before trusting a graph)

| Number | Source | Exactly what is counted |
|---|---|---|
| Added to PubMed | NCBI E-utilities | records whose *Entrez date* is that day |
| PubMed by country | NCBI E-utilities | same, filtered by author affiliation text (a paper with authors in 2 countries counts in both) |
| Papers published | OpenAlex | articles, reviews, preprints, letters, conference papers and book chapters with that publication date (datasets and other records left out) |
| New citations made | OpenAlex | total references listed in that day's papers |
| Top countries / universities | OpenAlex | papers with ≥1 author from that country / institution |
| Citation gainers | OpenAlex | change in total citations since the previous daily snapshot, among the 200 most-cited scientists and the 200 most-cited journal articles of the last two years |
| Journals / Fields | OpenAlex | papers per journal and per main research field that day |
| Active institutions | OpenAlex | distinct institutions with at least one paper that day |

Things to know:
- **Each day shown is the last complete UTC day** (yesterday). The last 7 days
  are re-counted every run, because databases keep adding papers for a while —
  so the newest points rise over the next days.
- Many journals only give a month, which is stored as the 1st. Expect a spike
  on the 1st of each month in "Papers published".
- OpenAlex does not refresh every scientist's citation total every single day,
  so a "gain" can cover more than one day.
- The citation-gainers chart appears from the **second** daily run (it needs
  yesterday's snapshot).

## Running it on your own computer (optional)

```bash
python3 scripts/update_data.py          # needs internet; set OPENALEX_API_KEY first if you have one
python3 -m http.server 8000             # then open http://localhost:8000
```

## Files

```
index.html                      the website
assets/app.js, assets/style.css graphs and design (Chart.js)
scripts/update_data.py          daily collector (Python, no extra packages)
.github/workflows/daily-update.yml  the daily robot + website publishing
data/                           created by the robot: history.json, latest.json
```

## Cost and limits
About 150 API calls a day after the first run — well inside OpenAlex's free
daily allowance with a free key, and inside NCBI's free limits. GitHub Actions
and GitHub Pages are free for public repositories.
