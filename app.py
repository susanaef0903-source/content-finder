"""Content Finder — search a streaming content catalog in seconds.

Built for the content coordinator role (StreamVault scenario):
type a title, genre, year, country, or keyword and get the best
matches with previews, instead of digging through spreadsheets.
"""

import difflib
import re
from datetime import date
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

# Default catalog: the real Kaggle Netflix dataset (8,807 titles, through 2021).
# The 40-row fictional sample in sample_data/ remains for quick tests.
DEFAULT_CSV = Path(__file__).parent / "data" / "netflix_titles.csv"

# Columns the search looks through, in order of how people usually ask.
SEARCH_COLUMNS = ["title", "listed_in", "description", "country", "director", "cast", "rating"]

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
    "{font-size: 1.3rem !important;} "
    # On phones, desktop-sized type eats the screen: shrink headings and
    # text, and tighten padding. Desktop rules above stay untouched.
    "@media (max-width: 640px) {"
    "  h1 {font-size: 1.7rem !important;} "
    "  h4 {font-size: 1.05rem !important;} "
    "  .block-container {padding-top: 1rem !important; padding-bottom: 2rem !important;} "
    "  .stMarkdown p, .stCaption, label, .stTextInput input, "
    "  .stSelectbox div, .stAlert p {font-size: 0.95rem !important;} "
    "  .stTextInput [data-testid='stWidgetLabel'] p {font-size: 1.05rem !important;} "
    "  [data-testid='stTab'] p {font-size: 1.05rem !important;} "
    "}"
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
    # A few source rows have the duration ("74 min") misfiled into the
    # rating column; move those values home and clear the rating.
    misfiled = df["rating"].astype(str).str.contains("min", regex=False, na=False)
    if misfiled.any():
        df.loc[misfiled, "duration"] = df.loc[misfiled, "rating"]
        df.loc[misfiled, "rating"] = ""
    # Movie runtimes as numbers ("90 min" -> 90), so length can be filtered.
    df["minutes"] = pd.to_numeric(
        df["duration"].astype(str).str.extract(r"(\d+)\s*min", expand=False),
        errors="coerce",
    )
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


def parse_query(query: str):
    """Split a query into quoted phrases and loose words."""
    phrases = [p.strip().lower() for p in re.findall(r'"([^"]+)"', query) if p.strip()]
    rest = re.sub(r'"[^"]*"', " ", query).lower().split()
    return phrases, rest


def search_catalog(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """Return rows matching the query, best matches first.

    A row matches if every word in the query appears somewhere in its
    searchable columns (title, genre, description, country, people) or
    equals its release year. Words in quotes match as an exact phrase.
    Singular and plural forms of a word count as the same word. Title
    hits rank above other hits.
    """
    phrases, words = parse_query(query)
    if not words and not phrases:
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
    for phrase in phrases:
        pattern = r"\b" + re.escape(phrase) + r"\b"
        # A quoted year should still match the year field.
        match_all &= haystack.str.contains(pattern, regex=True) | (years == phrase)
    for word in words:
        word_match = years == word
        for variant in word_variants(word):
            # Whole words only: "office" must not match "officer",
            # nor "hanks" match "thanks".
            pattern = r"\b" + re.escape(variant) + r"\b"
            word_match |= haystack.str.contains(pattern, regex=True)
        match_all &= word_match

    results = df[match_all].copy()
    if results.empty:
        return results
    # Rank by where the match lives: exact title, then title words,
    # then people (cast and director), then everything else.
    title = results["title"].fillna("").str.lower().str.strip()
    people = (
        results[["director", "cast"]].fillna("").astype(str)
        .agg(" ".join, axis=1).str.lower()
    )
    bare_query = query.lower().replace('"', "").strip()
    results["_rank"] = 0
    results.loc[title.str.contains(bare_query, regex=False), "_rank"] = 4
    tokens = phrases + words
    people_all = pd.Series(True, index=results.index)
    for token in tokens:
        pattern = r"\b" + re.escape(token) + r"\b"
        results.loc[title.str.contains(pattern, regex=True), "_rank"] += 2
        in_people = people.str.contains(pattern, regex=True)
        results.loc[in_people, "_rank"] += 1
        people_all &= in_people
    # The whole query naming one person (a cast or director search)
    # outranks stray title-word hits.
    if len(tokens) > 1 or any(" " in p for p in phrases):
        results.loc[people_all, "_rank"] += 3
    results.loc[title == bare_query, "_rank"] += 100
    return results.sort_values(["_rank", "title"], ascending=[False, True]).drop(columns="_rank")


@st.cache_data
def build_vocabulary(df: pd.DataFrame) -> dict:
    """Every word in the searchable text with its frequency, for typo suggestions."""
    text = " ".join(
        df[SEARCH_COLUMNS].fillna("").astype(str).agg(" ".join, axis=1)
    ).lower()
    words = re.findall(r"[a-z][a-z']+", text)
    freq: dict = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    return freq


def suggest_query(query: str, vocab: dict) -> str:
    """The query with each unknown word replaced by its closest known word.

    Ties between equally close candidates go to the most frequent word,
    so 'koreen' suggests 'korean' rather than some rare lookalike.
    """
    fixed, changed = [], False
    for word in query.lower().replace('"', " ").split():
        if word in vocab:
            fixed.append(word)
            continue
        close = difflib.get_close_matches(word, vocab.keys(), n=5, cutoff=0.8)
        if close:
            best = max(close, key=lambda w: vocab.get(w, 0))
            fixed.append(best)
            changed = True
        else:
            fixed.append(word)
    return " ".join(fixed) if changed else ""


# ---------------------------------------------------------------- sidebar
st.sidebar.title("🔎 Content Finder")
st.sidebar.caption("Find any title in the catalog without digging through spreadsheets.")

uploaded = st.sidebar.file_uploader(
    "Upload your own catalog (CSV)",
    type="csv",
    help="Optional. Your file temporarily replaces the built-in Netflix "
         "catalog (8,807 titles) while you browse. Leave empty to use "
         "the built-in catalog.",
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
if uploaded is not None:
    st.sidebar.info(
        "Your file has replaced the built-in catalog while you browse. "
        "Remove it above to switch back.",
        icon="📄",
    )
else:
    st.sidebar.caption(
        "Data source: Netflix's US catalog as of September 2021 "
        "(Kaggle open dataset). It only includes what Netflix carried "
        "then, not every title ever made."
    )

st.sidebar.subheader("Filters")


def seed_list_from_url(state_key: str, url_key: str, options: list):
    """Let a shared link restore a multiselect, ignoring invalid values."""
    if state_key not in st.session_state and url_key in st.query_params:
        wanted = st.query_params[url_key].split(",")
        valid = [v for v in options if v in wanted]
        if valid:
            st.session_state[state_key] = valid


all_types = sorted(catalog["type"].dropna().unique().tolist())
seed_list_from_url("type_f", "type", all_types)
type_filter = st.sidebar.multiselect("Type", all_types, key="type_f")

# Genre and Rating options follow the selected Type, so combinations
# that can only return zero are never offered.
genre_source = catalog[catalog["type"].isin(type_filter)] if type_filter else catalog
all_genres = sorted(
    {g.strip() for row in genre_source["listed_in"].dropna() for g in str(row).split(",")}
)
seed_list_from_url("genre_f", "genre", all_genres)
genre_filter = st.sidebar.multiselect("Genre", all_genres, key="genre_f")

# Ratings run youngest to most mature within each system (movie
# ratings first, then TV), instead of one alphabetical jumble.
RATING_ORDER = [
    "G", "PG", "PG-13", "R", "NC-17", "NR", "UR",
    "TV-Y", "TV-Y7", "TV-Y7-FV", "TV-G", "TV-PG", "TV-14", "TV-MA",
]
rating_pool = {str(r).strip() for r in genre_source["rating"].dropna() if str(r).strip()}
all_ratings = [r for r in RATING_ORDER if r in rating_pool] + sorted(
    rating_pool - set(RATING_ORDER)
)
seed_list_from_url("rating_f", "rating", all_ratings)
rating_filter = st.sidebar.multiselect("Rating", all_ratings, key="rating_f")

all_countries = sorted(
    {c.strip() for row in catalog["country"].dropna() for c in str(row).split(",") if c.strip()}
)
seed_list_from_url("country_f", "country", all_countries)
country_filter = st.sidebar.multiselect("Country", all_countries, key="country_f")

years = catalog["release_year"].dropna()
if len(years) and years.min() < years.max():
    y_lo, y_hi = int(years.min()), int(years.max())
    if "year_f" not in st.session_state and "year" in st.query_params:
        try:
            lo, hi = (int(v) for v in st.query_params["year"].split("-"))
            if y_lo <= lo <= hi <= y_hi:
                st.session_state.year_f = (lo, hi)
        except ValueError:
            pass
    year_range = st.sidebar.slider(
        "Release year", y_lo, y_hi, (y_lo, y_hi), key="year_f"
    )
else:
    year_range = None

minutes = catalog["minutes"].dropna()
if len(minutes):
    m_hi = int(minutes.max())
    if "length_f" not in st.session_state and "len" in st.query_params:
        try:
            v = int(st.query_params["len"])
            if 0 <= v <= m_hi:
                st.session_state.length_f = v
        except ValueError:
            pass
    max_length = st.sidebar.slider(
        "Max movie length (minutes)",
        0, m_hi, m_hi,
        key="length_f",
        help="Set below the maximum to keep only movies that fit the time. "
             "TV shows measure in seasons and are excluded while this is active.",
    )
else:
    max_length = None


def reset_filters(year_bounds, length_max):
    # Assign defaults rather than deleting keys: deleting lets the
    # widgets resurrect their previous values on the next redraw.
    st.session_state.type_f = []
    st.session_state.genre_f = []
    st.session_state.rating_f = []
    st.session_state.country_f = []
    if year_bounds is not None:
        st.session_state.year_f = year_bounds
    if length_max is not None:
        st.session_state.length_f = length_max


st.sidebar.button(
    "Reset filters",
    on_click=reset_filters,
    args=(
        (int(years.min()), int(years.max())) if year_range is not None else None,
        int(minutes.max()) if len(minutes) else None,
    ),
)

# ---------------------------------------------------------------- search
st.title("Content Finder")
st.markdown(f"#### :blue[Title Catalog: {len(catalog):,} total]")
st.caption(
    "Snapshot from September 2021. Titles may have left streaming since, "
    "and people credits are catalog data, not a talent database."
)

if "search_q" not in st.session_state:
    st.session_state.search_q = st.query_params.get("q", "")
query = st.text_input(
    "Search a title, genre, year, country, rating, or keyword. Try "
    "**documentaries norway**, **2021 thriller**, or **korean drama**.",
    key="search_q",
    placeholder="Type what you're looking for, then press Enter",
)
# The page address is updated after filtering, further down, so a
# shared link carries the search AND the filters.
st.caption(
    "Display results three ways: 📋 Title Table scans every match, "
    "🎯 Title Snapshot shows one title's full record, and 📊 Catalog "
    "Overview charts the selection. Narrow results with the Type, "
    "Genre, Rating, Country, Release year, and movie length filters "
    "in the left sidebar. Put words in quotes to match an exact phrase; "
    "quoted phrases search every text field, descriptions included, so a "
    "quoted name can also surface producer or subject mentions."
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
if rating_filter:
    results = results[results["rating"].isin(rating_filter)]
if country_filter:
    results = results[
        results["country"].fillna("").apply(
            lambda cell: any(c in cell for c in country_filter)
        )
    ]
if year_range:
    results = results[
        results["release_year"].between(year_range[0], year_range[1], inclusive="both")
    ]
if max_length is not None and len(minutes) and max_length < int(minutes.max()):
    # An active runtime cap means "fits the time": series without a
    # runtime are excluded rather than slipping through.
    results = results[results["minutes"] <= max_length]

# Lives under the Filters section: updates as search and filters narrow
# the catalog, instead of repeating the total shown in the main panel.
# Amber at zero, so an empty result never looks like good news.
count_note = st.sidebar.warning if results.empty else st.sidebar.success
count_note(f"Showing {len(results):,} of {len(catalog):,} titles")

# Name the active filters above the results, since the controls
# themselves live in the sidebar.
active = []
if type_filter:
    active.append("Type: " + ", ".join(type_filter))
if genre_filter:
    active.append("Genre: " + ", ".join(genre_filter))
if rating_filter:
    active.append("Rating: " + ", ".join(rating_filter))
if country_filter:
    active.append("Country: " + ", ".join(country_filter))
if year_range and (year_range[0] > int(years.min()) or year_range[1] < int(years.max())):
    active.append(f"Years {year_range[0]} to {year_range[1]}")
if max_length is not None and len(minutes) and max_length < int(minutes.max()):
    active.append(f"Movies up to {max_length} min")
if active:
    st.caption("Active filters: " + " · ".join(active))

# Everything about the current selection lives in the page address,
# so a bookmarked or shared link restores search and filters alike.
url_state = {}
if query.strip():
    url_state["q"] = query.strip()
if type_filter:
    url_state["type"] = ",".join(type_filter)
if genre_filter:
    url_state["genre"] = ",".join(genre_filter)
if rating_filter:
    url_state["rating"] = ",".join(rating_filter)
if country_filter:
    url_state["country"] = ",".join(country_filter)
if year_range and (year_range[0] > int(years.min()) or year_range[1] < int(years.max())):
    url_state["year"] = f"{year_range[0]}-{year_range[1]}"
if max_length is not None and len(minutes) and max_length < int(minutes.max()):
    url_state["len"] = str(max_length)
st.query_params.from_dict(url_state)

if len(results) != len(catalog):
    st.subheader(f"{len(results):,} match{'es' if len(results) != 1 else ''}")

def apply_suggestion(text: str):
    st.session_state.search_q = text


if results.empty:
    diagnosed = False
    if (
        type_filter and "Movie" not in type_filter
        and max_length is not None and len(minutes)
        and max_length < int(minutes.max())
    ):
        st.info(
            "The movie length cap excludes TV shows, and your Type filter "
            "keeps only TV shows, so nothing can match. Clear one of the two.",
            icon="⏱️",
        )
        diagnosed = True
    if query.strip():
        suggestion = suggest_query(query.strip(), build_vocabulary(catalog))
        if suggestion:
            st.button(
                f"Did you mean: {suggestion}?",
                icon="🔎",
                on_click=apply_suggestion,
                args=(suggestion,),
            )
    if not diagnosed:
        # The generic advice steps aside when a specific diagnosis exists.
        st.info(
            "No matches. Try fewer words, or clear a filter in the sidebar. "
            "It's also possible the title just isn't in this catalog. "
            "It only covers what's actually in the loaded data."
        )
    # The tabs stay put even with nothing to show, so an empty result
    # reads as "loosen the search", not "the app broke".
    empty_tabs = st.tabs(
        [
            "📋 :blue[Title Table]",
            "🎯 :violet[Title Snapshot]",
            "📊 :green[Catalog Overview]",
        ]
    )
    for tab, message in zip(
        empty_tabs,
        [
            "No titles to list yet.",
            "No title to inspect yet.",
            "Nothing to chart yet.",
        ],
    ):
        with tab:
            st.caption(message)
else:
    preview = results[
        ["title", "type", "release_year", "rating", "duration", "listed_in",
         "country", "director", "cast", "description"]
    ].rename(
        columns={
            "title": "Title", "type": "Type", "release_year": "Year",
            "rating": "Rating", "duration": "Length", "listed_in": "Genre",
            "country": "Country", "director": "Director", "cast": "Cast",
            "description": "Description",
        }
    )
    # Missing values display as blanks, never as the word "None".
    for col in ["Title", "Type", "Rating", "Length", "Genre", "Country",
                "Director", "Cast", "Description"]:
        preview[col] = preview[col].fillna("")
    browse_tab, snapshot_tab, overview_tab = st.tabs(
        [
            "📋 :blue[Title Table]",
            "🎯 :violet[Title Snapshot]",
            "📊 :green[Catalog Overview]",
        ]
    )

    # ------------------------------------------------------- browse view
    with browse_tab:
        action_col, tip_col = st.columns([1, 2])
        with action_col:
            # The report uses the same friendly labels as the screen,
            # includes the credit columns the table does not show, and
            # keeps the internal id last.
            export = results[
                ["title", "type", "release_year", "rating", "duration",
                 "listed_in", "country", "director", "cast", "date_added",
                 "description", "show_id"]
            ].rename(columns={
                "title": "Title", "type": "Type", "release_year": "Year",
                "rating": "Rating", "duration": "Length",
                "listed_in": "Genre", "country": "Country",
                "director": "Director", "cast": "Cast",
                "date_added": "Date Added", "description": "Description",
                "show_id": "Catalog ID",
            })
            # Filename says what was selected and when it was exported,
            # so a folder of reports stays tellable-apart.
            slug_bits = []
            if query.strip():
                slug_bits.append(re.sub(r"[^a-z0-9]+", "-", query.lower().strip()).strip("-"))
            for chosen_filter in (type_filter, genre_filter, rating_filter, country_filter):
                if chosen_filter:
                    slug_bits.append(
                        re.sub(r"[^a-z0-9]+", "-", "-".join(chosen_filter).lower()).strip("-")
                    )
            slug = "_".join(slug_bits)[:60].strip("_-") or "all-titles"
            st.download_button(
                "⬇️ Download these results as a report (CSV)",
                export.to_csv(index=False).encode("utf-8"),
                file_name=f"content-finder_{slug}_{date.today().isoformat()}.csv",
                mime="text/csv",
            )
            st.caption(
                "The report carries all twelve columns, including Director "
                "and Cast, from the September 2021 catalog snapshot."
            )
        with tip_col:
            st.info(
                "More tools in the top right corner: search within results, "
                "hide columns, or view full screen. Need one title's full "
                "record? Switch to the Title Snapshot tab.",
                icon="💡",
            )
        st.session_state.compact_view = st.session_state.get("compact_view", False)
        compact = st.toggle(
            "📱 Compact view",
            key="compact_view",
            help="One card per title instead of the wide table. Best on phones.",
        )
        if compact:
            card_count = st.selectbox(
                "Cards to show", [30, 60, 120], key="card_count"
            )
            shown = preview.head(card_count)
            if len(preview) > card_count:
                st.caption(
                    f"Showing the first {card_count} of {len(preview):,} matches. "
                    "Narrow your search, or download the report for all of them."
                )
            for _, row in shown.iterrows():
                with st.container(border=True):
                    year = f" ({int(row['Year'])})" if pd.notna(row["Year"]) else ""
                    st.markdown(f"**{row['Title']}**{year}")
                    facts = " · ".join(
                        str(row[c]) for c in ["Type", "Length", "Rating"] if has_value(row[c])
                    )
                    if facts:
                        st.caption(facts)
                    if has_value(row["Genre"]):
                        st.caption(str(row["Genre"]))
        else:
            st.dataframe(
                preview,
                use_container_width=True,
                hide_index=True,
                row_height=85,
                column_config={
                    "Country": st.column_config.TextColumn("Country", width="medium"),
                    "Director": st.column_config.TextColumn("Director", width="medium"),
                    "Cast": st.column_config.TextColumn(
                        "Cast",
                        width="medium",
                        help="Long casts are trimmed here. The Title Snapshot shows the full list.",
                    ),
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

    # ------------------------------------------------------- overview
    with overview_tab:
        st.caption(
            "The shape of the current selection. Both charts update live "
            "with your search and filters."
        )
        # Fixed (non zoomable) charts: wheel scrolling must scroll the
        # page, never pan a chart into negative made-up territory.
        chart_years = results["release_year"].dropna().astype(int)
        if len(chart_years):
            st.markdown(
                f"**Titles per release year** "
                f"({int(chart_years.min())} to {int(chart_years.max())})"
            )
            year_counts = (
                chart_years.value_counts().sort_index()
                .rename_axis("year").reset_index(name="titles")
            )
            st.altair_chart(
                alt.Chart(year_counts)
                .mark_bar(color="#3d9df3")
                .encode(
                    x=alt.X(
                        "year:Q",
                        axis=alt.Axis(format="d", title=None),
                        scale=alt.Scale(nice=False),
                    ),
                    y=alt.Y("titles:Q", axis=alt.Axis(format="d", title=None)),
                ),
                use_container_width=True,
            )
        genres = (
            results["listed_in"].dropna().astype(str)
            .str.split(",").explode().str.strip()
        )
        genres = genres[genres != ""]
        if len(genres):
            st.markdown("**Top genres in this selection**")
            genre_counts = (
                genres.value_counts().head(10)
                .rename_axis("genre").reset_index(name="titles")
            )
            st.altair_chart(
                alt.Chart(genre_counts)
                .mark_bar(color="#b27eff")
                .encode(
                    x=alt.X("titles:Q", axis=alt.Axis(format="d", title=None)),
                    y=alt.Y("genre:N", sort="-x", title=None),
                ),
                use_container_width=True,
            )
