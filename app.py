import streamlit as st
import pandas as pd
import sqlite3
import re
from pathlib import Path
from datetime import date, datetime

# =========================================================
# NOZ HUB - MULTI-SPORT PREDICTION CENTER
# =========================================================

st.set_page_config(
    page_title="NOZ HUB",
    page_icon="🏆",
    layout="wide"
)

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "noz_hub.db"

SPORTS = [
    "Soccer",
    "NBA",
    "WNBA",
    "China CBA",
    "Argentina Basketball",
    "Brazil Basketball",
    "European Basketball",
    "EuroLeague",
    "NFL",
    "MLB",
    "Ice Hockey",
    "UFC"
]

COLUMNS = [
    "id",
    "Date",
    "Sport",
    "League",
    "Match",
    "Scores24 Pick",
    "DRatings Pick",
    "VSiN Pick",
    "Model Pick",
    "Confidence (%)",
    "Final Result",
    "Notes",
    "Created At"
]

PICK_COLUMNS = [
    "Scores24 Pick",
    "DRatings Pick",
    "VSiN Pick"
]


# =========================================================
# DATABASE
# =========================================================

def get_connection():
    return sqlite3.connect(DB_PATH)


def initialize_database():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                sport TEXT NOT NULL,
                league TEXT,
                match_name TEXT NOT NULL,
                scores24_pick TEXT,
                dratings_pick TEXT,
                vsin_pick TEXT,
                model_pick TEXT,
                confidence REAL,
                final_result TEXT,
                notes TEXT,
                created_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_predictions_date
            ON predictions(date)
        """)


def load_predictions():
    with get_connection() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM predictions ORDER BY date DESC, id DESC",
            conn
        )

    if df.empty:
        return pd.DataFrame(columns=COLUMNS)

    df.columns = COLUMNS
    return df


def save_prediction(data):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO predictions (
                date, sport, league, match_name,
                scores24_pick, dratings_pick, vsin_pick,
                model_pick, confidence, final_result,
                notes, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(data["Date"]),
            str(data["Sport"]),
            str(data["League"]),
            str(data["Match"]),
            str(data["Scores24 Pick"]),
            str(data["DRatings Pick"]),
            str(data["VSiN Pick"]),
            str(data["Model Pick"]),
            float(data["Confidence (%)"]),
            str(data["Final Result"]),
            str(data["Notes"]),
            datetime.now().isoformat(timespec="seconds")
        ))


def update_result(prediction_id, result):
    with get_connection() as conn:
        conn.execute("""
            UPDATE predictions
            SET final_result = ?
            WHERE id = ?
        """, (result, int(prediction_id)))


def delete_prediction(prediction_id):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM predictions WHERE id = ?",
            (int(prediction_id),)
        )


def import_predictions(df):
    """Import rows using the dashboard's column names."""

    required = ["Date", "Sport", "Match"]

    for column in required:
        if column not in df.columns:
            raise ValueError(
                f"Missing required CSV column: {column}"
            )

    imported = 0

    for _, row in df.iterrows():
        sport = str(row.get("Sport", "")).strip()
        match_name = str(row.get("Match", "")).strip()

        if not sport or not match_name:
            continue

        raw_date = str(row.get("Date", date.today()))

        try:
            parsed_date = pd.to_datetime(
                raw_date, errors="raise"
            ).date().isoformat()
        except Exception:
            continue

        def get_text(column):
            value = row.get(column, "")
            if pd.isna(value):
                return ""
            return str(value).strip()

        try:
            confidence = float(
                row.get("Confidence (%)", 0) or 0
            )
        except (TypeError, ValueError):
            confidence = 0

        confidence = max(0, min(100, confidence))

        save_prediction({
            "Date": parsed_date,
            "Sport": sport,
            "League": get_text("League"),
            "Match": match_name,
            "Scores24 Pick": get_text("Scores24 Pick"),
            "DRatings Pick": get_text("DRatings Pick"),
            "VSiN Pick": get_text("VSiN Pick"),
            "Model Pick": get_text("Model Pick"),
            "Confidence (%)": confidence,
            "Final Result": get_text("Final Result"),
            "Notes": get_text("Notes")
        })

        imported += 1

    return imported


initialize_database()


# =========================================================
# CONSENSUS ENGINE
# =========================================================

def normalize_pick(value):
    """
    Normalize simple text differences without pretending
    different markets are equivalent.
    """

    if value is None or pd.isna(value):
        return ""

    value = str(value).strip().lower()
    value = re.sub(r"\s+", " ", value)

    missing_values = {
        "", "nan", "none", "n/a", "na", "unknown", "-"
    }

    if value in missing_values:
        return ""

    return value


def classify_consensus(row):
    picks = [
        normalize_pick(row.get("Scores24 Pick", "")),
        normalize_pick(row.get("DRatings Pick", "")),
        normalize_pick(row.get("VSiN Pick", ""))
    ]

    available = [pick for pick in picks if pick]

    if len(available) == 0:
        return "NO DATA"

    if len(available) < 3:
        return "INCOMPLETE DATA"

    if picks[0] == picks[1] == picks[2]:
        return "ALL 3 AGREE"

    counts = {}

    for pick in picks:
        counts[pick] = counts.get(pick, 0) + 1

    if max(counts.values()) == 2:
        return "2 OF 3 AGREE"

    return "DISAGREEMENT"


def add_consensus(df):
    if df.empty:
        result = df.copy()
        result["Consensus"] = pd.Series(dtype=str)
        return result

    result = df.copy()
    result["Consensus"] = result.apply(
        classify_consensus,
        axis=1
    )

    return result


# =========================================================
# HEADER
# =========================================================

st.title("🏆 NOZ HUB")
st.subheader("Multi-Sport Prediction Center")

st.caption(
    "Your Sports. Your Predictions. Your Hub."
)

st.info(
    "NOZ HUB compares recorded predictions. "
    "Source agreement is not a guarantee of accuracy. "
    "Automatic collection requires authorized data access."
)


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title("🏆 NOZ HUB MENU")

page = st.sidebar.radio(
    "Choose a page",
    [
        "Dashboard",
        "SCAN ALL GAMES",
        "ALL 3 AGREE",
        "2 OF 3 AGREE",
        "Disagreements",
        "Add Prediction",
        "Import Predictions",
        "Results & History"
    ]
)

df = add_consensus(load_predictions())


# =========================================================
# FILTERS
# =========================================================

def apply_filters(data):
    if data.empty:
        return data

    sports_available = sorted(
        data["Sport"].dropna().unique().tolist()
    )

    selected_sports = st.multiselect(
        "Filter sports",
        sports_available,
        default=sports_available,
        key=f"sports_{page}"
    )

    filtered = data[data["Sport"].isin(selected_sports)]

    dates = pd.to_datetime(
        filtered["Date"], errors="coerce"
    )

    if not filtered.empty:
        date_min = dates.min()
        date_max = dates.max()

        if pd.notna(date_min) and pd.notna(date_max):
            selected_range = st.date_input(
                "Filter date range",
                value=(date_min.date(), date_max.date()),
                key=f"dates_{page}"
            )

            if isinstance(selected_range, tuple):
                if len(selected_range) == 2:
                    start_date, end_date = selected_range

                    filtered_dates = pd.to_datetime(
                        filtered["Date"], errors="coerce"
                    ).dt.date

                    filtered = filtered[
                        (filtered_dates >= start_date)
                        & (filtered_dates <= end_date)
                    ]

    return filtered


def show_table(data):
    if data.empty:
        st.info(
            "No matching games yet. Add predictions "
            "or import a CSV file to get started."
        )
        return

    display_columns = [
        "Date",
        "Sport",
        "League",
        "Match",
        "Scores24 Pick",
        "DRatings Pick",
        "VSiN Pick",
        "Model Pick",
        "Confidence (%)",
        "Consensus",
        "Final Result"
    ]

    st.dataframe(
        data[display_columns],
        use_container_width=True,
        hide_index=True
    )

    csv = data.to_csv(index=False).encode("utf-8")

    st.download_button(
        "📥 Download CSV",
        data=csv,
        file_name="noz_hub_predictions.csv",
        mime="text/csv"
    )


# =========================================================
# DASHBOARD
# =========================================================

if page == "Dashboard":

    st.header("📊 Dashboard Overview")

    total = len(df)

    all_three = (
        int((df["Consensus"] == "ALL 3 AGREE").sum())
        if total else 0
    )

    two_agree = (
        int((df["Consensus"] == "2 OF 3 AGREE").sum())
        if total else 0
    )

    disagreements = (
        int((df["Consensus"] == "DISAGREEMENT").sum())
        if total else 0
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Recorded Games", total)
    col2.metric("✅ All 3 Agree", all_three)
    col3.metric("🟡 2 of 3 Agree", two_agree)
    col4.metric("⚠️ Disagreements", disagreements)

    st.divider()

    st.subheader("📅 Upcoming Games")

    if not df.empty:
        today = date.today().isoformat()

        upcoming = df[df["Date"].astype(str) >= today]

        if upcoming.empty:
            st.info(
                "No upcoming games are recorded. "
                "Add games or import your fixture data."
            )
        else:
            show_table(upcoming)
    else:
        st.info(
            "Your dashboard is ready. Add predictions "
            "or import your first games to begin."
        )

    st.subheader("🔔 Dashboard Alerts")

    if all_three:
        st.success(
            f"{all_three} recorded game(s) have all "
            "three external sources agreeing."
        )
    else:
        st.caption(
            "No three-source consensus is recorded yet."
        )


# =========================================================
# SCAN ALL GAMES
# =========================================================

elif page == "SCAN ALL GAMES":

    st.header("🔎 SCAN ALL GAMES")

    st.write(
        "Review all recorded fixtures and compare the "
        "three external predictions."
    )

    st.warning(
        "This scan processes data already in NOZ HUB. "
        "It does not automatically fetch fixtures or "
        "predictions from external websites."
    )

    if st.button(
        "🔎 SCAN ALL GAMES NOW",
        type="primary",
        use_container_width=True
    ):
        df = add_consensus(load_predictions())

        st.session_state["scan_completed"] = True
        st.session_state["scan_time"] = (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        st.rerun()

    if st.session_state.get("scan_completed"):
        st.success(
            "Scan completed at "
            + st.session_state.get("scan_time", "")
        )

        df = add_consensus(load_predictions())

        counts = df["Consensus"].value_counts()

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "All 3 Agree",
            int(counts.get("ALL 3 AGREE", 0))
        )

        c2.metric(
            "2 of 3 Agree",
            int(counts.get("2 OF 3 AGREE", 0))
        )

        c3.metric(
            "Disagreements",
            int(counts.get("DISAGREEMENT", 0))
        )

        st.subheader("Complete Scan Results")
        filtered = apply_filters(df)
        show_table(filtered)


# =========================================================
# ALL 3 AGREE
# =========================================================

elif page == "ALL 3 AGREE":

    st.header("✅ ALL 3 AGREE")

    st.write(
        "Games where Scores24, DRatings, and VSiN "
        "record the same normalized prediction."
    )

    agreed = df[df["Consensus"] == "ALL 3 AGREE"].copy()

    if not agreed.empty:
        agreed = agreed.sort_values("Date", ascending=True)

    filtered = apply_filters(agreed)

    st.metric("Matching Games", len(filtered))

    show_table(filtered)


# =========================================================
# TWO OF THREE AGREE
# =========================================================

elif page == "2 OF 3 AGREE":

    st.header("🟡 TWO OF THREE AGREE")

    two = df[df["Consensus"] == "2 OF 3 AGREE"].copy()

    filtered = apply_filters(two)

    show_table(filtered)


# =========================================================
# DISAGREEMENTS
# =========================================================

elif page == "Disagreements":

    st.header("⚠️ SOURCE DISAGREEMENTS")

    st.write(
        "These games have three available predictions, "
        "but the predictions do not produce a two-source "
        "majority."
    )

    different = df[
        df["Consensus"] == "DISAGREEMENT"
    ].copy()

    filtered = apply_filters(different)

    show_table(filtered)

    st.subheader("Incomplete Source Data")

    incomplete = df[
        df["Consensus"] == "INCOMPLETE DATA"
    ].copy()

    show_table(incomplete)


# =========================================================
# ADD PREDICTION
# =========================================================

elif page == "Add Prediction":

    st.header("➕ Add Game & Predictions")

    st.caption(
        "Enter the predictions as published by each source. "
        "Leave a source blank if no prediction is available."
    )

    with st.form("add_prediction_form"):

        game_date = st.date_input(
            "Game date",
            value=date.today()
        )

        sport = st.selectbox("Sport", SPORTS)

        league = st.text_input(
            "League or competition",
            placeholder="e.g. NBA, Premier League, NHL"
        )

        match_name = st.text_input(
            "Match",
            placeholder="e.g. Home Team vs Away Team"
        )

        st.subheader("External Source Predictions")

        scores24 = st.text_input(
            "Scores24 Pick",
            placeholder="e.g. Home Team"
        )

        dratings = st.text_input(
            "DRatings Pick",
            placeholder="e.g. Home Team"
        )

        vsin = st.text_input(
            "VSiN Pick",
            placeholder="e.g. Home Team"
        )

        st.subheader("NOZ HUB Model")

        model_pick = st.text_input(
            "Model Pick",
            placeholder="Enter your model's prediction"
        )

        confidence = st.slider(
            "Model confidence (%)",
            min_value=0,
            max_value=100,
            value=50
        )

        notes = st.text_area("Notes")

        submitted = st.form_submit_button(
            "💾 Save Prediction",
            type="primary"
        )

        if submitted:

            if not match_name.strip():
                st.error("Enter a match name.")
            else:
                save_prediction({
                    "Date": game_date.isoformat(),
                    "Sport": sport,
                    "League": league,
                    "Match": match_name.strip(),
                    "Scores24 Pick": scores24,
                    "DRatings Pick": dratings,
                    "VSiN Pick": vsin,
                    "Model Pick": model_pick,
                    "Confidence (%)": confidence,
                    "Final Result": "",
                    "Notes": notes
                })

                st.success(
                    "Prediction saved successfully!"
                )

                st.rerun()


# =========================================================
# IMPORT PREDICTIONS
# =========================================================

elif page == "Import Predictions":

    st.header("📥 Import Fixtures & Predictions")

    st.write(
        "Upload a CSV file containing game information "
        "and any predictions you have permission to use."
    )

    st.markdown("""
    **Required columns:**
    - `Date`
    - `Sport`
    - `Match`

    **Optional columns:**
    - `League`
    - `Scores24 Pick`
    - `DRatings Pick`
    - `VSiN Pick`
    - `Model Pick`
    - `Confidence (%)`
    - `Final Result`
    - `Notes`
    """)

    template = pd.DataFrame([{
        "Date": date.today().isoformat(),
        "Sport": "NBA",
        "League": "NBA",
        "Match": "Example Home vs Example Away",
        "Scores24 Pick": "Example Home",
        "DRatings Pick": "Example Home",
        "VSiN Pick": "Example Home",
        "Model Pick": "Example Home",
        "Confidence (%)": 65,
        "Final Result": "",
        "Notes": "DEMO ROW - replace with real data"
    }])

    st.download_button(
        "📄 Download CSV Template",
        data=template.to_csv(index=False).encode("utf-8"),
        file_name="noz_hub_template.csv",
        mime="text/csv"
    )

    uploaded = st.file_uploader(
        "Upload predictions CSV",
        type=["csv"]
    )

    if uploaded is not None:

        try:
            import_df = pd.read_csv(uploaded)

            st.subheader("Preview")
            st.dataframe(
                import_df.head(10),
                use_container_width=True
            )

            if st.button(
                "Import CSV into NOZ HUB",
                type="primary"
            ):

                imported = import_predictions(import_df)

                st.success(
                    f"Imported {imported} row(s)."
                )

                st.rerun()

        except Exception as exc:
            st.error(f"Could not read CSV: {exc}")


# =========================================================
# RESULTS & HISTORY
# =========================================================

elif page == "Results & History":

    st.header("📚 Results & Prediction History")

    df = add_consensus(load_predictions())

    if df.empty:
        st.info(
            "No saved predictions yet. Add a prediction "
            "or import a CSV to get started."
        )

    else:
        st.subheader("Record a Final Result")

        options = {
            f'{row["id"]} | {row["Date"]} | '
            f'{row["Match"]}': int(row["id"])
            for _, row in df.iterrows()
        }

        selected = st.selectbox(
            "Select game",
            list(options.keys())
        )

        result_text = st.text_input(
            "Final result",
            placeholder="e.g. Home Team 102 - Away Team 98"
        )

        if st.button("Save Final Result"):
            if result_text.strip():
                update_result(
                    options[selected],
                    result_text.strip()
                )

                st.success("Final result saved.")
                st.rerun()
            else:
                st.error("Enter the final result.")

        st.divider()

        st.subheader("Historical Predictions")

        filtered = apply_filters(df)
        show_table(filtered)

        st.subheader("Delete a Record")

        delete_options = {
            f'{row["id"]} | {row["Match"]}': int(row["id"])
            for _, row in df.iterrows()
        }

        selected_delete = st.selectbox(
            "Select record to delete",
            list(delete_options.keys()),
            key="delete_record"
        )

        confirm_delete = st.checkbox(
            "I confirm I want to delete this record."
        )

        if st.button("Delete Selected Record"):
            if confirm_delete:
                delete_prediction(
                    delete_options[selected_delete]
                )

                st.success("Record deleted.")
                st.rerun()
            else:
                st.warning(
                    "Check the confirmation box first."
                )


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "NOZ HUB | Multi-Sport Prediction Center | "
    "For research and informational purposes. "
    "Predictions are uncertain; no outcome is guaranteed."
)
