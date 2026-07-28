"""Content Finder — search a streaming content catalog in seconds.

Built for the content coordinator role (StreamVault scenario):
type a title, genre, year, country, or keyword and get the best
matches with previews, instead of digging through spreadsheets.
"""

from pathlib import Path

import pandas as pd
import streamlit as st

# Default catalog: the real Kaggle Netflix dataset (8,807 titles, through 2021).
# The 40-row fictional sample in sample_data/ remains for quick tests.
DEFAULT_CSV = Path(__file__).parent / "data" / "netflix_titles.csv"

# Columns the search looks through, in order of how people usually ask.
SEARCH_COLUMNS = ["title", "listed_in", "description", "country", "director", "cast"]

st.set_page_config(page_title="Content Finder", page_icon="🔎", layout="wide")

# Streamlit leaves a lot of empty space above the title; tighten it.
# Also bump the base text size, which defaults too small to read easily.
st.markdown(
    "<style>"
    ".block-container {padding-top: 2rem;} "
    ".stMarkdown p, .stCaption, label, .stTextInput input, "
    ".stSelectbox div, .stAlert p {font-size: 1.1rem !important;} "
    "[data-testid='stTab'] p "
    "{font-size: 1.3rem !important; font-weight: 600;} "
    ".stTextInput [data-testid='stWidgetLabel'] p "
    "{font-size: 1.3rem !important;}"
    "</style>",
    unsafe_allow_html=True,
)


@st.cache_data
def load_catalog(uploaded_file=None) -> pd.DataFrame:
    """Load the catalog: an uploaded CSV if provided, otherwise the sample."""
    df = pd.read_csv(uploaded_file if uploaded_file is not None else DEFAULT_CSV)
    # Make sure every expected column exists so search never crashes.
    for col in SEARCH_COLUMNS + ["release_year", "rating", "duration", "date_added", "type"]:
        if col not in df.columns:
            df[col] = ""
    df["release_year"] = pd.to_numeric(df["release_year"], errors="coerce")
    return df


def has_value(value) -> bool:
    """True if the cell has a real entry — not blank, NaN, or the text 'nan'."""
    if pd.isna(value):
        return False
    return str(value).strip().lower() not in ("", "nan", "none")


def word_variants(word: str) -> set:
    """The word plus simple singular/plural forms, so 'comedy' finds 'Comedies'."""
    variants = {word}
    if word.endswith("ies") and len(word) > 4:
        variants.add(word[:-3] + "y")
    if word.endswith("s") and len(word) > 3:
        variants.add(word[:-1])
    if word.endswith("y") and len(word) > 2:
        variants.add(word[:-1] + "ies")
    else:
        variants.add(word + "s")
    return variants


def search_catalog(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """Return rows matching the query, best matches first.

    A row matches if every word in the query appears somewhere in its
    searchable columns (title, genre, description, country, people) or
    equals its release year. Singular and plural forms of a word count
    as the same word. Title hits rank above other hits.
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
        word_match = years == word
        for variant in word_variants(word):
            word_match |= haystack.str.contains(variant, regex=False)
        match_all &= word_match

    results = df[match_all].copy()
    # Rank: exact title first, then titles containing the whole query,
    # then title word hits.
    title = results["title"].fillna("").str.lower().str.strip()
    results["_rank"] = 0
    results.loc[title.str.contains(query.lower(), regex=False), "_rank"] = 2
    for word in words:
        results.loc[title.str.contains(word, regex=False), "_rank"] += 1
    results.loc[title == query.lower(), "_rank"] += 100
    return results.sort_values(["_rank", "title"], ascending=[False, True]).drop(columns="_rank")


# ---------------------------------------------------------------- sidebar
st.sidebar.title("🔎 Content Finder")
st.sidebar.caption("Find any title in the catalog without digging through spreadsheets.")

uploaded = st.sidebar.file_uploader(
    "Upload your own catalog (CSV)",
    type="csv",
    help="Optional. Leave empty to use the real Netflix catalog "
         "(8,807 titles).",
)
with st.sidebar.expander("What columns should my CSV have?"):
    st.write(
        "Any CSV loads, and missing columns simply show up blank. "
        "For best results use these column names:\n\n"
        "`title`, `type` (Movie or TV Show), `director`, `cast`, "
        "`country`, `date_added`, `release_year`, `rating`, "
        "`duration`, `listed_in` (genres), `description`"
    )
catalog = load_catalog(uploaded)
st.sidebar.success(f"Catalog loaded: {len(catalog):,} titles")
if uploaded is None:
    st.sidebar.caption(
        "Data source: Netflix's US catalog as of September 2021 "
        "(Kaggle open dataset). It only includes what Netflix carried "
        "then, not every title ever made."
    )

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
st.markdown(f"#### :blue[Title Catalog: {len(catalog):,}]")

query = st.text_input(
    "Search a title, genre, year, country, or keyword. Try "
    "**documentaries norway**, **2021 thriller**, or **korean drama**.",
    placeholder="Type what you're looking for, then press Enter",
)
st.caption(
    "Display results in two ways: 📋 Title Table scans every match "
    "and 🎯 Title Snapshot shows one title's full record."
)

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

if len(results) != len(catalog):
    st.subheader(f"{len(results):,} match{'es' if len(results) != 1 else ''}")

if results.empty:
    st.info(
        "No matches. Try fewer words, or clear a filter in the sidebar. "
        "It's also possible the title just isn't in this catalog. "
        "It only covers what's actually in the loaded data."
    )
else:
    preview = results[
        ["title", "type", "release_year", "rating", "duration", "listed_in", "country", "description"]
    ].rename(
        columns={
            "title": "Title", "type": "Type", "release_year": "Year",
            "rating": "Rating", "duration": "Length", "listed_in": "Genre",
            "country": "Country", "description": "Description",
        }
    )
    browse_tab, snapshot_tab = st.tabs(
        ["📋 :blue[Title Table]", "🎯 :violet[Title Snapshot]"]
    )

    # ------------------------------------------------------- browse view
    with browse_tab:
        action_col, tip_col = st.columns([1, 2])
        with action_col:
            st.download_button(
                "⬇️ Download these results as a report (CSV)",
                results.to_csv(index=False).encode("utf-8"),
                file_name="content-finder-report.csv",
                mime="text/csv",
            )
        with tip_col:
            st.info(
                "More tools in the top right corner: search within results, "
                "hide columns, or view full screen. Need one title's full "
                "record? Switch to the Title Snapshot tab.",
                icon="💡",
            )
        st.dataframe(
            preview,
            use_container_width=True,
            hide_index=True,
            row_height=85,
            column_config={
                "Description": st.column_config.TextColumn(
                    "Description", width="large"
                ),
            },
        )

    # ------------------------------------------------------- snapshot view
    with snapshot_tab:
        st.caption(
            "Know which title you're after? Click the dropdown below and "
            "start typing to jump straight to it: description, credits, "
            "and catalog info."
        )
        chosen = st.selectbox(
            f"Type a title, or open the list to browse all "
            f"{len(results):,} title{'s' if len(results) != 1 else ''}",
            results["title"].tolist(),
        )
        st.info(
            "This box has its own quick search: just click and start "
            "typing, and the list narrows to matching titles as you type.",
            icon="🔍",
        )
        row = results[results["title"] == chosen].iloc[0]
        left, right = st.columns([2, 1])
        with left:
            st.markdown(f"### {row['title']}")
            if has_value(row["description"]):
                st.write(row["description"])
            if has_value(row.get("director")):
                st.write(f"**Director:** {row['director']}")
            if has_value(row.get("cast")):
                st.write(f"**Cast:** {row['cast']}")
        with right:
            year = row["release_year"]
            st.metric("Release year", int(year) if pd.notna(year) else "—")
            if has_value(row["type"]):
                st.write(f"**Type:** {row['type']}")
            if has_value(row["rating"]):
                st.write(f"**Rating:** {row['rating']}")
            if has_value(row["duration"]):
                st.write(f"**Length:** {row['duration']}")
            if has_value(row["listed_in"]):
                st.write(f"**Genre:** {row['listed_in']}")
            if has_value(row["country"]):
                st.write(f"**Country:** {row['country']}")
            if has_value(row["date_added"]):
                st.write(f"**Added to catalog:** {row['date_added']}")
