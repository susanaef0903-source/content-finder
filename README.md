# Content Finder

A search tool for content coordinators who manage large streaming catalogs.

Built by **Susana Rivera** for Pursuit Cycle 2 (build-for-a-role project — Role: Content Coordinator at StreamVault).

## The Problem

The content coordinator struggles with manually digging through a massive volume of catalogs and spreadsheets to answer questions from executives and directors, because traditional database and catalog tools were built as rigid storage systems rather than flexible query engines. That means hours lost every week and operational bottlenecks during fast-moving executive meetings.

## The Solution

Content Finder lets the coordinator type what they're looking for — a title, genre, year, country, or keyword — and instantly see the best matches with clear previews. No more scrolling through spreadsheets. Results can be exported as a report for meetings.

## MVP User Flow

1. User uploads or links their content catalog (or starts with the built-in sample catalog)
2. System organizes the content by genre, name, year, and keywords
3. User types their question into the search bar
4. System shows the best matches with short previews
5. User selects the correct title to see full details
6. User downloads a report of the results

## Running It

```
pip install -r requirements.txt
streamlit run app.py
```

## Data

Week 3 uses a fictional sample catalog (`sample_data/sample_catalog.csv`) whose columns mirror a real streaming-catalog dataset (title, type, country, release year, rating, genre, date added), so a real open dataset can be swapped in for Week 4 without code changes.
