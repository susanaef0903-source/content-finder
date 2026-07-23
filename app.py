"""Content Finder — search a streaming content catalog in seconds.

Built for the content coordinator role (StreamVault scenario):
type a title, genre, year, country, or keyword and get the best
matches with previews, instead of digging through spreadsheets.
"""

from pathlib import Path

import pandas as pd
import streamlit as st

SAMPLE_CSV = Path(__file__).parent / "sample_data" / "sample_catalog.csv"

# Columns the search looks through, in order of how people usually ask.
SEARCH_COLUMNS = ["title", "listed_in", "description", "country", "director", "cast"]

st.set_page_config(page_title="Content Finder", page_icon="🔎", layout="wide")


@st.cache_data
def load_catalog(uploaded_file=None) -> pd.DataFrame:
    """Load the catalog: an uploaded CSV if provided, otherwise the sample."""
    df = pd.read_csv(uploaded_file if uploaded_file is not None else SAMPLE_CSV)
    # Make sure every expected column exists so search never crashes.
    for col in SEARCH_COLUMNS + ["release_year", "rating", "duration", "date_added", "type"]:
        if col not in df.columns:
            df[col] = ""
    df["release_year"] = pd.to_numeric(df["release_year"], errors="coerce")
    return df


def search_catalog(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """Return rows matching the query, best matches first.

    A row matches if every word in the query appears somewhere in its
    searchable columns (title, genre, description, country, people) or
    equals its release year. Title hits rank above other hits.
    """
    words = query.lower().split()
    if not words:
        return df

    haystack = (
        df[SEARCH_COLUMNS]
        .fillna("")
        .astype(str)
        .agg(" ".join, axis=1)
        .str.lower()
    )
    years = df["release_year"].fillna(0).astype(int).astype(str)

    match_all = pd.Series(True, index=df.index)
    for word in words:
        match_all &= haystack.str.contains(word, regex=False) | (years == word)

    results = df[match_all].copy()
    # Rank: titles that contain the whole query first, then title word hits.
    title = results["title"].fillna("").str.lower()
    results["_rank"] = 0
    results.loc[title.str.contains(query.lower(), regex=False), "_rank"] = 2
    for word in words:
        results.loc[title.str.contains(word, regex=False), "_rank"] += 1
    return results.sort_values(["_rank", "title"], ascending=[False, True]).drop(columns="_rank")


# ---------------------------------------------------------------- sidebar
st.sidebar.title("🔎 Content Finder")
st.sidebar.caption("Find any title in the catalog without digging through spreadsheets.")

uploaded = st.sidebar.file_uploader(
    "Upload your own catalog (CSV)",
    type="csv",
    help="Optional. Needs the same columns as the sample catalog. "
         "Leave empty to use the built-in StreamVault sample.",
)
catalog = load_catalog(uploaded)
st.sidebar.success(f"Catalog loaded: {len(catalog):,} titles")

st.sidebar.subheader("Filters")
type_filter = st.sidebar.multiselect(
    "Type", sorted(catalog["type"].dropna().unique().tolist())
)
all_genres = sorted(
    {g.strip() for row in catalog["listed_in"].dropna() for g in str(row).split(",")}
)
genre_filter = st.sidebar.multiselect("Genre", all_genres)

years = catalog["release_year"].dropna()
if len(years) and years.min() < years.max():
    year_range = st.sidebar.slider(
        "Release year",
        int(years.min()), int(years.max()),
        (int(years.min()), int(years.max())),
    )
else:
    year_range = None

# ---------------------------------------------------------------- search
st.title("Content Finder")
st.caption(
    "Type a title, genre, year, country, or keyword — for example "
    "**documentaries norway**, **2023 thriller**, or **payroll**."
)

query = st.text_input("Search the catalog", placeholder="What are you looking for?")

results = search_catalog(catalog, query.strip())
if type_filter:
    results = results[results["type"].isin(type_filter)]
if genre_filter:
    results = results[
        results["listed_in"].fillna("").apply(
            lambda cell: any(g in cell for g in genre_filter)
        )
    ]
if year_range:
    results = results[
        results["release_year"].between(year_range[0], year_range[1], inclusive="both")
    ]

st.subheader(f"{len(results):,} match{'es' if len(results) != 1 else ''}")

if results.empty:
    st.info("No matches. Try fewer words, or clear a filter in the sidebar.")
else:
    preview = results[
        ["title", "type", "release_year", "rating", "duration", "listed_in", "country", "description"]
    ].rename(
        columns={
            "title": "Title", "type": "Type", "release_year": "Year",
            "rating": "Rating", "duration": "Length", "listed_in": "Genre",
            "country": "Country", "description": "Preview",
        }
    )
    st.dataframe(preview, use_container_width=True, hide_index=True)

    # ------------------------------------------------------- detail view
    st.subheader("Title details")
    chosen = st.selectbox("Select a title to see its full record", results["title"].tolist())
    row = results[results["title"] == chosen].iloc[0]
    left, right = st.columns([2, 1])
    with left:
        st.markdown(f"### {row['title']}")
        st.write(row["description"])
        if str(row.get("director", "")).strip():
            st.write(f"**Director:** {row['director']}")
        if str(row.get("cast", "")).strip():
            st.write(f"**Cast:** {row['cast']}")
    with right:
        year = row["release_year"]
        st.metric("Release year", int(year) if pd.notna(year) else "—")
        st.write(f"**Type:** {row['type']}")
        st.write(f"**Rating:** {row['rating']}")
        st.write(f"**Length:** {row['duration']}")
        st.write(f"**Genre:** {row['listed_in']}")
        st.write(f"**Country:** {row['country']}")
        st.write(f"**Added to catalog:** {row['date_added']}")

    # ------------------------------------------------------- report
    st.download_button(
        "⬇️ Download these results as a report (CSV)",
        results.to_csv(index=False).encode("utf-8"),
        file_name="content-finder-report.csv",
        mime="text/csv",
    )
