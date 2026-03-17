import pandas as pd
import streamlit as st

st.set_page_config(page_title="Cap Table App", layout="wide")

st.title("Cap Table App")
st.caption("Cap Table Management, Funding Rounds, and Exit Calculations")

CAP_COLUMNS = ["holder", "security_type", "class", "shares"]
ROUND_COLUMNS = [
    "round_type",
    "round_name",
    "pre_money_valuation",
    "amount_raised",
    "valuation_cap",
    "discount_pct",
    "interest_rate_pct",
    "maturity_date",
    "liq_pref_multiple",
    "participating",
    "participation_cap_multiple",
]

if "cap_table" not in st.session_state:
    st.session_state.cap_table = pd.DataFrame(columns=CAP_COLUMNS)

if "round_history" not in st.session_state:
    st.session_state.round_history = pd.DataFrame(columns=ROUND_COLUMNS)


def empty_cap_table():
    return pd.DataFrame(columns=CAP_COLUMNS)


def empty_round_history():
    return pd.DataFrame(columns=ROUND_COLUMNS)


def recalc_ownership(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        out["ownership_pct"] = []
        return out
    out["shares"] = pd.to_numeric(out["shares"], errors="coerce").fillna(0.0)
    total = out["shares"].sum()
    out["ownership_pct"] = out["shares"] / total if total > 0 else 0
    return out


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def normalize_cap_table(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    missing = [c for c in CAP_COLUMNS if c not in out.columns]
    if missing:
        raise ValueError(f"Missing cap table columns: {missing}")
    out = out[CAP_COLUMNS].copy()
    out["holder"] = out["holder"].astype(str)
    out["security_type"] = out["security_type"].astype(str)
    out["class"] = out["class"].astype(str)
    out["shares"] = pd.to_numeric(out["shares"], errors="coerce").fillna(0.0)
    return out


def normalize_round_history(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in ROUND_COLUMNS:
        if c not in out.columns:
            out[c] = None
    out = out[ROUND_COLUMNS].copy()
    return out


def parse_exit_values(text: str):
    values = []
    for part in text.split(","):
        cleaned = part.strip().replace("$", "").replace(",", "")
        if cleaned == "":
            continue
        try:
            val = float(cleaned)
            if val >= 0:
                values.append(val)
        except ValueError:
            pass
    return values


def build_exit_sensitivity_table(cap_table: pd.DataFrame, exit_values: list[float]) -> pd.DataFrame:
    current = recalc_ownership(cap_table)
    if current.empty or not exit_values:
        return pd.DataFrame()

    result = current[["holder", "security_type", "class", "shares", "ownership_pct"]].copy()

    for exit_value in exit_values:
        col_name = f"${exit_value:,.0f}"
        result[col_name] = result["ownership_pct"] * exit_value

    return result


tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "Starting Cap Table",
        "Funding Round",
        "Current Cap Table",
        "Downloads / Uploads",
        "Exit Analysis",
    ]
)

with tab1:
    st.subheader("Build starting cap table")

    with st.form("add_holder_form", clear_on_submit=True):
        col1, col2, col3, col4 = st.columns(4)
        holder = col1.text_input("Holder name")
        security_type = col2.selectbox("Security type", ["Common", "Preferred", "Option Pool"])
        class_name = col3.text_input("Class", value="Common")
        shares = col4.number_input("Shares", min_value=0.0, value=0.0, step=1.0, format="%g")
        submitted = st.form_submit_button("Add row")

        if submitted:
            if holder.strip() and shares > 0:
                new_row = pd.DataFrame(
                    [{
                        "holder": holder.strip(),
                        "security_type": security_type,
                        "class": class_name.strip() if class_name.strip() else security_type,
                        "shares": shares,
                    }]
                )
                st.session_state.cap_table = pd.concat(
                    [st.session_state.cap_table, new_row], ignore_index=True
                )
                st.success("Row added.")
            else:
                st.error("Enter a holder name and shares greater than 0.")

    if not st.session_state.cap_table.empty:
        st.write("Current starting table")
        display_df = recalc_ownership(st.session_state.cap_table)
        display_df["ownership_pct"] = display_df["ownership_pct"].map(lambda x: f"{x:.2%}")
        st.dataframe(display_df, use_container_width=True)

    if st.button("Clear all data"):
        st.session_state.cap_table = empty_cap_table()
        st.session_state.round_history = empty_round_history()
        st.rerun()

with tab2:
    st.subheader("Add funding round")

    if st.session_state.cap_table.empty:
        st.info("Add at least one starting cap table row first, or upload prior CSVs in Downloads / Uploads.")
    else:
        round_type = st.selectbox("Round type", ["Equity", "SAFE", "Convertible Note"])
        round_name = st.text_input("Round name / label", value="")
        pre_money_valuation = None
        valuation_cap = None
        discount_pct = None
        interest_rate_pct = None
        maturity_date = None
        liq_pref_multiple = None
        participating = None
        participation_cap_multiple = None

        if round_type == "Equity":
            pre_money_valuation = st.number_input(
                "Pre-money valuation ($)",
                min_value=0.0,
                value=0.0,
                step=1000.0,
                format="%g",
            )

            st.markdown("### Preferred stock terms")
            liq_pref_multiple = st.number_input(
                "Liquidation preference multiple (x)",
                min_value=0.0,
                value=1.0,
                step=0.1,
                format="%g",
            )
            participating = st.checkbox("Participating preferred", value=False)

            if participating:
                has_participation_cap = st.checkbox("Participation cap", value=False)
                if has_participation_cap:
                    participation_cap_multiple = st.number_input(
                        "Participation cap multiple (x)",
                        min_value=0.0,
                        value=3.0,
                        step=0.1,
                        format="%g",
                    )
                else:
                    participation_cap_multiple = None
            else:
                participation_cap_multiple = None

        elif round_type == "SAFE":
            valuation_cap = st.number_input(
                "Valuation cap ($)",
                min_value=0.0,
                value=0.0,
                step=1000.0,
                format="%g",
            )
            discount_pct = st.number_input(
                "Discount (%)",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=0.5,
                format="%g",
            )
        else:
            valuation_cap = st.number_input(
                "Valuation cap ($)",
                min_value=0.0,
                value=0.0,
                step=1000.0,
                format="%g",
            )
            discount_pct = st.number_input(
                "Discount (%)",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=0.5,
                format="%g",
            )
            interest_rate_pct = st.number_input(
                "Interest rate (%)",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=0.5,
                format="%g",
            )
            maturity_date = st.text_input("Maturity date")

        st.markdown("### Investor entries")
        investor_count = st.number_input(
            "Number of investors in this round",
            min_value=1,
            step=1,
            value=1,
        )

        investors = []
        total_raised = 0.0

        for i in range(int(investor_count)):
            st.markdown(f"**Investor {i+1}**")
            c1, c2 = st.columns(2)
            investor_name = c1.text_input(f"Investor name {i+1}", key=f"inv_name_{i}")
            amount = c2.number_input(
                f"Amount invested {i+1} ($)",
                min_value=0.0,
                value=0.0,
                step=1000.0,
                format="%g",
                key=f"inv_amt_{i}",
            )
            investors.append({"investor_name": investor_name.strip(), "amount": amount})
            total_raised += amount

        st.write(f"Total raised: **${total_raised:,.2f}**")

        new_common = st.number_input(
            "New common shares issued outside the round",
            min_value=0.0,
            value=0.0,
            step=1.0,
            format="%g",
        )
        new_option_pool = st.number_input(
            "Option pool increase",
            min_value=0.0,
            value=0.0,
            step=1.0,
            format="%g",
        )

        if st.button("Apply funding round"):
            clean_round_name = round_name.strip() or round_type

            round_row = pd.DataFrame(
                [{
                    "round_type": round_type,
                    "round_name": clean_round_name,
                    "pre_money_valuation": pre_money_valuation,
                    "amount_raised": total_raised,
                    "valuation_cap": valuation_cap,
                    "discount_pct": discount_pct,
                    "interest_rate_pct": interest_rate_pct,
                    "maturity_date": maturity_date,
                    "liq_pref_multiple": liq_pref_multiple,
                    "participating": participating,
                    "participation_cap_multiple": participation_cap_multiple,
                }]
            )
            st.session_state.round_history = pd.concat(
                [st.session_state.round_history, round_row], ignore_index=True
            )

            updated_cap_table = st.session_state.cap_table.copy()

            if new_common > 0:
                updated_cap_table = pd.concat(
                    [
                        updated_cap_table,
                        pd.DataFrame(
                            [{
                                "holder": "New Common Issuance",
                                "security_type": "Common",
                                "class": "Common",
                                "shares": new_common,
                            }]
                        ),
                    ],
                    ignore_index=True,
                )

            if new_option_pool > 0:
                updated_cap_table = pd.concat(
                    [
                        updated_cap_table,
                        pd.DataFrame(
                            [{
                                "holder": "Option Pool Increase",
                                "security_type": "Option Pool",
                                "class": "Option Pool",
                                "shares": new_option_pool,
                            }]
                        ),
                    ],
                    ignore_index=True,
                )

            if round_type == "Equity":
                pre_round_shares = updated_cap_table["shares"].sum()
                if pre_round_shares <= 0 or not pre_money_valuation or pre_money_valuation <= 0:
                    st.error("Need a valid pre-money valuation and at least one existing share.")
                else:
                    price_per_share = pre_money_valuation / pre_round_shares
                    preferred_rows = []

                    for inv in investors:
                        if inv["investor_name"] and inv["amount"] > 0:
                            shares_issued = inv["amount"] / price_per_share
                            preferred_rows.append(
                                {
                                    "holder": inv["investor_name"],
                                    "security_type": "Preferred",
                                    "class": clean_round_name,
                                    "shares": shares_issued,
                                }
                            )

                    if preferred_rows:
                        updated_cap_table = pd.concat(
                            [updated_cap_table, pd.DataFrame(preferred_rows)],
                            ignore_index=True,
                        )

                    st.session_state.cap_table = updated_cap_table
                    st.success(f"Equity round applied at ${price_per_share:,.4f} per share.")
            else:
                st.session_state.cap_table = updated_cap_table
                st.success(
                    f"{round_type} round stored in round history. Cap table only changed for any common or option updates."
                )

with tab3:
    st.subheader("Current cap table")

    current = recalc_ownership(st.session_state.cap_table)
    if current.empty:
        st.info("No cap table data yet.")
    else:
        show = current.copy()
        show["ownership_pct"] = show["ownership_pct"].map(lambda x: f"{x:.2%}")
        st.dataframe(show, use_container_width=True)

    st.subheader("Round history")
    if st.session_state.round_history.empty:
        st.info("No rounds added yet.")
    else:
        history_show = st.session_state.round_history.copy()
        money_cols = ["pre_money_valuation", "amount_raised", "valuation_cap"]
        for col in money_cols:
            if col in history_show.columns:
                history_show[col] = history_show[col].apply(
                    lambda x: f"${x:,.2f}" if pd.notnull(x) and x != "" else ""
                )
        st.dataframe(history_show, use_container_width=True)

with tab4:
    st.subheader("Downloads")

    current = recalc_ownership(st.session_state.cap_table)

    st.download_button(
        "Download cap table CSV",
        data=to_csv_bytes(current),
        file_name="cap_table_current.csv",
        mime="text/csv",
    )

    st.download_button(
        "Download round history CSV",
        data=to_csv_bytes(st.session_state.round_history),
        file_name="round_history.csv",
        mime="text/csv",
    )

    st.divider()
    st.subheader("Uploads / Resume")

    st.write("Upload prior CSVs here so you can resume without restarting.")

    uploaded_cap = st.file_uploader(
        "Upload cap table CSV",
        type=["csv"],
        key="uploaded_cap_table",
    )

    uploaded_rounds = st.file_uploader(
        "Upload round history CSV",
        type=["csv"],
        key="uploaded_round_history",
    )

    if st.button("Load uploaded CSVs"):
        try:
            if uploaded_cap is not None:
                cap_df = pd.read_csv(uploaded_cap)
                st.session_state.cap_table = normalize_cap_table(cap_df)

            if uploaded_rounds is not None:
                round_df = pd.read_csv(uploaded_rounds)
                st.session_state.round_history = normalize_round_history(round_df)

            st.success("Uploaded files loaded into the app.")
            st.rerun()
        except Exception as e:
            st.error(f"Could not load files: {e}")

with tab5:
    st.subheader("Exit sensitivity analysis")
    st.caption("This version uses simple pro rata ownership based on the current cap table.")

    current = recalc_ownership(st.session_state.cap_table)

    if current.empty:
        st.info("Add a cap table first before running exit analysis.")
    else:
        exit_values_text = st.text_area(
            "Enter exit values separated by commas ($)",
            value="10000000, 50000000, 100000000, 150000000, 200000000",
            help="Example: 10000000, 50000000, 100000000",
        )

        exit_values = parse_exit_values(exit_values_text)

        if st.button("Run exit sensitivity"):
            if not exit_values:
                st.error("Please enter at least one valid exit value.")
            else:
                sensitivity_df = build_exit_sensitivity_table(current, exit_values)

                display_df = sensitivity_df.copy()
                display_df["ownership_pct"] = display_df["ownership_pct"].map(lambda x: f"{x:.2%}")

                dollar_cols = [c for c in display_df.columns if c.startswith("$")]
                for col in dollar_cols:
                    display_df[col] = display_df[col].map(lambda x: f"${x:,.2f}")

                st.write("### Exit proceeds by holder")
                st.dataframe(display_df, use_container_width=True)

                st.download_button(
                    "Download exit sensitivity CSV",
                    data=to_csv_bytes(sensitivity_df),
                    file_name="exit_sensitivity.csv",
                    mime="text/csv",
                )
