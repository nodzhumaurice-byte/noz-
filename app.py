import streamlit as st
import pandas as pd
from datetime import date

st.set_page_config(
    page_title="Multi-Sport Prediction Agent",
    page_icon="🏆",
    layout="wide"
)

SPORTS = [
    "Soccer", "NBA", "WNBA", "China CBA",
    "Argentina Basketball", "Brazil Basketball",
    "European Basketball", "EuroLeague",
    "NFL", "MLB", "Ice Hockey", "UFC"
]

COLUMNS = [
    "Date", "Sport", "League", "Match",
    "Scores24 Pick", "Model Pick",
    "Confidence (%)", "Final Result", "Notes"
]

if "predictions" not in st.session_state:
    st.session_state.predictions = pd.DataFrame(columns=COLUMNS)

st.title("🏆 Multi-Sport Prediction Agent")
st.write(
    "Analyze matchups, record predictions, and compare "
    "your model against Scores24."
)

st.info(
    "Starter version: predictions are entered manually. "
    "Live sports feeds and automated Scores24 integration "
    "will be added separately."
)

# SIDEBAR: ADD PREDICTIONS
with st.sidebar:
    st.header("➕ Add a Prediction")

    match_date = st.date_input("Match date", value=date.today())
    sport = st.selectbox("Sport", SPORTS)
    league = st.text_input("League or competition")
    match = st.text_input("Matchup", placeholder="Team A vs Team B")

    scores24_pick = st.text_input(
        "Scores24 prediction",
        placeholder="Home win"
    )

    model_pick = st.text_input(
        "Our model prediction",
        placeholder="Home win"
    )

    confidence = st.slider(
        "Estimated confidence (%)",
        min_value=1,
        max_value=99,
        value=60
    )

    notes = st.text_area("Analysis notes")

    if st.button("Save Prediction", type="primary"):
        if not match.strip() or not model_pick.strip():
            st.error("Enter the matchup and model prediction.")
        else:
            new_row = pd.DataFrame([{
                "Date": str(match_date),
                "Sport": sport,
                "League": league,
                "Match": match,
                "Scores24 Pick": scores24_pick,
                "Model Pick": model_pick,
                "Confidence (%)": confidence,
                "Final Result": "",
                "Notes": notes
            }])

            st.session_state.predictions = pd.concat(
                [st.session_state.predictions, new_row],
                ignore_index=True
            )

            st.success("Prediction saved!")
            st.rerun()

# PREPARE DATA
df = st.session_state.predictions.copy()

if not df.empty:
    scores = df["Scores24 Pick"].fillna("").astype(str).str.strip()
    model = df["Model Pick"].fillna("").astype(str).str.strip()

    compared = scores.ne("")
    agreements = compared & scores.str.casefold().eq(
        model.str.casefold()
    )

    disagreements = compared & ~agreements

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Predictions", len(df))
    col2.metric("Agreements", int(agreements.sum()))
    col3.metric("Disagreements", int(disagreements.sum()))

    average = pd.to_numeric(
        df["Confidence (%)"], errors="coerce"
    ).mean()

    col4.metric(
        "Average Confidence",
        f"{average:.1f}%" if pd.notna(average) else "—"
    )

else:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Predictions", 0)
    col2.metric("Agreements", 0)
    col3.metric("Disagreements", 0)
    col4.metric("Average Confidence", "—")

# DASHBOARD TABS
tab1, tab2, tab3, tab4 = st.tabs([
    "📅 Today's Picks",
    "🤝 Scores24 Comparison",
    "📊 Results Tracker",
    "📁 Import & Export"
])

with tab1:
    st.subheader("Predictions")

    if not df.empty:
        available_sports = sorted(df["Sport"].dropna().unique())

        selected_sports = st.multiselect(
            "Filter by sport",
            available_sports,
            default=available_sports
        )

        filtered = df[df["Sport"].isin(selected_sports)].copy()

        filtered["Date"] = pd.to_datetime(
            filtered["Date"], errors="coerce"
        ).dt.date

        filtered = filtered[
            filtered["Date"] >= date.today()
        ]

        st.dataframe(
            filtered.sort_values("Confidence (%)", ascending=False),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.write("No predictions yet. Add one using the sidebar.")

with tab2:
    st.subheader("Scores24 vs. Our Model")

    if not df.empty:
        comparison = df.copy()

        scores = comparison["Scores24 Pick"].fillna("").astype(str).str.strip()
        model = comparison["Model Pick"].fillna("").astype(str).str.strip()

        comparison["Comparison"] = "Not compared"

        has_scores24 = scores.ne("")

        same = scores.str.casefold().eq(model.str.casefold())

        comparison.loc[has_scores24 & same, "Comparison"] = "✅ Agree"
        comparison.loc[has_scores24 & ~same, "Comparison"] = "⚠️ Disagree"

        choice = st.selectbox(
            "Show",
            ["All", "Agreements", "Disagreements", "Not compared"]
        )

        if choice == "Agreements":
            comparison = comparison[
                comparison["Comparison"] == "✅ Agree"
            ]
        elif choice == "Disagreements":
            comparison = comparison[
                comparison["Comparison"] == "⚠️ Disagree"
            ]
        elif choice == "Not compared":
            comparison = comparison[
                comparison["Comparison"] == "Not compared"
            ]

        st.dataframe(
            comparison,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.write("Add predictions to start comparing.")

with tab3:
    st.subheader("Results and Performance")

    if not df.empty:
        st.caption(
            "Enter final results in your CSV and re-import the file "
            "to maintain your results. Automatic grading comes later."
        )

        st.dataframe(df, use_container_width=True, hide_index=True)

        completed = df["Final Result"].fillna("").astype(str).str.strip().ne("")
        st.metric("Recorded Final Results", int(completed.sum()))
    else:
        st.write("Your prediction history will appear here.")

with tab4:
    st.subheader("Import and Export")

    st.write("Download your predictions to keep a copy.")

    if not df.empty:
        csv = df.to_csv(index=False).encode("utf-8")

        st.download_button(
            "⬇️ Download Predictions CSV",
            data=csv,
            file_name="sports_predictions.csv",
            mime="text/csv"
        )

    uploaded = st.file_uploader(
        "Import predictions from CSV",
        type=["csv"]
    )

    if uploaded is not None:
        try:
            imported = pd.read_csv(uploaded)

            if "Match" not in imported.columns:
                st.error("Your CSV must include a Match column.")
            else:
                for column in COLUMNS:
                    if column not in imported.columns:
                        imported[column] = ""

                imported = imported[COLUMNS]

                st.dataframe(
                    imported,
                    use_container_width=True,
                    hide_index=True
                )

                if st.button("Import Predictions"):
                    st.session_state.predictions = pd.concat(
                        [
                            st.session_state.predictions,
                            imported
                        ],
                        ignore_index=True
                    )

                    st.success("Predictions imported.")
                    st.rerun()

        except Exception as error:
            st.error(f"Could not import CSV: {error}")

st.divider()

st.caption(
    "This is a dashboard starter, not a trained prediction model. "
    "Confidence percentages are estimates, not guarantees. "
    "Predictions currently remain in session memory, so export "
    "your records regularly."
)
