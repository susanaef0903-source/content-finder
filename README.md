# Content Finder

A search tool for content coordinators who manage large streaming catalogs.

**Live app:** https://sue-content-finder.streamlit.app/

Built by **Susana Rivera** for Pursuit Cycle 2 (build-for-a-role project — Role: Content Coordinator at StreamVault).

## The Problem

The content coordinator struggles with manually digging through a massive volume of catalogs and spreadsheets to answer questions from executives and directors, because traditional database and catalog tools were built as rigid storage systems rather than flexible query engines. That means hours lost every week and operational bottlenecks during fast-moving executive meetings.

## The Solution

Content Finder lets the coordinator type what they're looking for — a title, genre, year, country, or keyword — and instantly see the best matches with clear previews. No more scrolling through spreadsheets. Results can be exported as a report for meetings.

## MVP User Flow

1. User uploads their own content catalog (or starts with the built-in catalog of 8,807 real Netflix titles)
2. System organizes the content by genre, name, year, and keywords
3. User types their question into the search bar
4. System shows every match in a Title Table, with filters for type, genre, and release year
5. User switches to the Title Snapshot tab to see any one title's full record
6. User downloads a report of the results as a CSV

## Running It

```
pip install -r requirements.txt
streamlit run app.py
```

## Data

The app runs on the real Netflix catalog (`data/netflix_titles.csv`): 8,807 titles from the [Kaggle netflix-shows open dataset](https://www.kaggle.com/datasets/shivamb/netflix-shows), covering Netflix's US catalog through September 2021. In Week 3 I built against a fictional 40-title sample (`sample_data/sample_catalog.csv`, still in the repo) whose columns mirror the real dataset exactly — which is why swapping in the real data in Week 4 required no code changes.

One known limit worth naming: the uploader reads the raw dataset column names above, while the app's own exported reports use friendly labels (Title, Year, Length, Genre). That means an exported report can't be re-uploaded as a catalog yet — the columns won't be recognized and will show blank. Accepting the export's headers as aliases is on the roadmap.

The raw CSV is never edited. Cleaning happens in code on every load: release_year converts to numeric, blank cells stay null and empty fields are hidden in the display, three source rows with duration misfiled into the rating column are repaired, and search matches singular and plural word forms. Several of these fixes came directly from peer testing and from checking the app's counts against the same data loaded into Snowflake with SQL.
