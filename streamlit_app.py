import pandas as pd
import streamlit as st
from datetime import date, datetime

st.set_page_config(page_title="Cap Table App", layout="wide")

st.title("Cap Table App")
st.caption("Cap Table Management, Funding Rounds, SAFE / Note Conversion, and Exit Calculations")

CAP_COLUMNS = ["holder", "security_type", "class", "shares"]

ROUND_COLUMNS = [
    "round_type",
    "round_name",
    "round_date",
    "pre_money_valuation",
    "amount_raised",
    "valuation_cap",
    "discount_pct",
    "interest_rate_pct",
    "issue_date",
    "maturity_date",
    "liq_pref_multiple",
    "participating",
    "participation_cap_multiple",
]

FINANCING_COLUMNS = [
    "status",
    "instrument_type",
    "round_name",
    "round_date",
    "investor_name",
    "amount_invested",
    "principal_invested",
    "valuation_cap",
    "discount_pct",
    "interest_rate_pct",
    "issue_date",
    "maturity_date",
    "converted_in_round",
    "converted_on_date",
    "conversion_amount",
    "conversion_price",
    "shares_issued",
]

if "cap_table" not in st.session_state:
    st.session_state.cap_table = pd.DataFrame(columns=CAP_COLUMNS)

if "round_history" not in st.session_state:
    st.session_state.round_history = pd.DataFrame(columns=ROUND_COLUMNS)

if "financing_details" not in st.session_state:
    st.session_state.financing_details = pd.DataFrame(columns=FINANCING_COLUMNS)

if "new_holder" not in st.session_state:
    st.session_state.new_holder = ""

if "new_security_type" not in st.session_state:
    st.session_state.new_security_type = "Common"

if "new_shares" not in st.session_state:
    st.session_state.new_shares = 0.0


def empty_cap_table():
    return pd.DataFrame(columns=CAP_COLUMNS)


def empty_round_history():
    return pd.DataFrame(columns=ROUND_COLUMNS)


def empty_financing_details():
    return pd.DataFrame(columns=FINANCING_COLUMNS)


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


def normalize_financing_details(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in FINANCING_COLUMNS:
        if c not in out.columns:
            out[c] = None
    out = out[FINANCING_COLUMNS].copy()
    return out


def date_to_str(d):
    if d is None or d == "":
        return None
    if isinstance(d, str):
        return d
    return d.isoformat()


def str_to_date(value):
    if value is None or value == "" or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value)).date()
    except Exception:
        return None


def days_between(start_date, end_date):
    s = str_to_date(start_date)
    e = str_to_date(end_date)
    if s is None or e is None:
        return 0
    return max((e - s).days, 0)


def simple_interest(principal, annual_rate_pct, start_date, end_date):
    if principal is None or pd.isna(principal):
        return 0.0
    if annual_rate_pct is None or annual_rate_pct == "" or pd.isna(annual_rate_pct):
        return 0.0
    days = days_between(start_date, end_date)
    return float(principal) * (float(annual_rate_pct) / 100.0) * (days / 365.0)


def outstanding_convertibles(financing_df: pd.DataFrame) -> pd.DataFrame:
    if financing_df.empty:
        return financing_df.copy()
    out = financing_df.copy()
    out["status"] = out["status"].fillna("outstanding")
    mask = out["instrument_type"].isin(["SAFE", "Convertible Note"]) & (out["status"] == "outstanding")
    return out.loc[mask].copy()


def build_conversion_rows(
    financing_df: pd.DataFrame,
    equity_round_name: str,
    equity_round_date,
    round_price: float,
    pre_round_fd_shares: float,
):
    outstanding = outstanding_convertibles(financing_df)
    if outstanding.empty:
        return [], financing_df.copy(), pd.DataFrame()

    cap_rows = []
    conversion_summary_rows = []
    updated_financing = financing_df.copy()

    for idx, row in outstanding.iterrows():
        instrument_type = row.get("instrument_type")
        investor_name = row.get("investor_name")

        valuation_cap = pd.to_numeric(row.get("valuation_cap"), errors="coerce")
        discount_pct = pd.to_numeric(row.get("discount_pct"), errors="coerce")
        interest_rate_pct = pd.to_numeric(row.get("interest_rate_pct"), errors="coerce")

        if instrument_type == "SAFE":
            base_amount = pd.to_numeric(row.get("amount_invested"), errors="coerce")
            accrued_interest = 0.0
        else:
            principal = pd.to_numeric(row.get("principal_invested"), errors="coerce")
            accrued_interest = simple_interest(
                principal,
                interest_rate_pct,
                row.get("issue_date"),
                equity_round_date,
            )
            base_amount = (0.0 if pd.isna(principal) else float(principal)) + accrued_interest

        if pd.isna(base_amount) or base_amount <= 0:
            continue

        candidate_prices = []

        if pd.notna(valuation_cap) and valuation_cap > 0 and pre_round_fd_shares > 0:
            cap_price = float(valuation_cap) / float(pre_round_fd_shares)
            candidate_prices.append(cap_price)
        else:
            cap_price = None

        if pd.notna(discount_pct) and discount_pct > 0:
            discount_price = round_price * (1.0 - float(discount_pct) / 100.0)
            candidate_prices.append(discount_price)
        else:
            discount_price = None

        candidate_prices.append(round_price)
        conversion_price = min([p for p in candidate_prices if p is not None and p > 0])

        shares_issued = float(base_amount) / float(conversion_price)

        cap_rows.append(
            {
                "holder": investor_name,
                "security_type": "Preferred",
                "class": equity_round_name,
                "shares": shares_issued,
            }
        )

        updated_financing.at[idx, "status"] = "converted"
        updated_financing.at[idx, "converted_in_round"] = equity_round_name
        updated_financing.at[idx, "converted_on_date"] = date_to_str(equity_round_date)
        updated_financing.at[idx, "conversion_amount"] = float(base_amount)
        updated_financing.at[idx, "conversion_price"] = float(conversion_price)
        updated_financing.at[idx, "shares_issued"] = float(shares_issued)

        conversion_summary_rows.append(
            {
                "investor_name": investor_name,
                "instrument_type": instrument_type,
                "converted_in_round": equity_round_name,
                "conversion_amount": float(base_amount),
                "accrued_interest": float(accrued_interest),
                "cap_price": cap_price,
                "discount_price": discount_price,
                "round_price": float(round_price),
                "conversion_price": float(conversion_price),
                "shares_issued": float(shares_issued),
            }
        )

    summary_df = pd.DataFrame(conversion_summary_rows)
    return cap_rows, updated_financing, summary_df


def add_starting_row():
    holder = st.session_state.get("new_holder", "").strip()
    security_type = st.session_state.get("new_security_type", "Common")
    shares = st.session_state.get("new_shares", 0.0)

    if holder and shares > 0:
        class_name = "Common" if security_type == "Common" else "Option Pool"
        new_row = pd.DataFrame(
            [{
                "holder": holder,
                "security_type": security_type,
                "class": class_name,
                "shares": shares,
            }]
        )
        st.session_state.cap_table = pd.concat(
            [st.session_state.cap_table, new_row], ignore_index=True
        )
        st.session_state.new_holder = ""
        st.session_state.new_security_type = "Common"
        st.session_state.new_shares = 0.0
    else:
        st.session_state["_add_row_error"] = "Enter a holder name and shares greater than 0."


def build_exit_scenarios(low_value: float, high_value: float, num_points: int = 8):
    if low_value < 0 or high_value < 0:
        return []
    if high_value < low_value:
        return []
    if low_value == high_value:
        return [float(low_value)]

    step = (high_value - low_value) / (num_points - 1)
    return [low_value + i * step for i in range(num_points)]


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
        "Exit Analysis",
        "Downloads / Uploads",
    ]
)

with tab1:
    st.subheader("Build starting cap table")

    col1, col2, col3 = st.columns(3)
    col1.text_input("Holder name", key="new_holder")
    col2.selectbox("Security type", ["Common", "Option Pool"], key="new_security_type")
    col3.number_input(
        "Shares",
        min_value=0.0,
        value=0.0,
        step=1.0,
        format="%g",
        key="new_shares",
        on_change=add_starting_row,
    )

    if st.button("Add row"):
        add_starting_row()
        st.rerun()

    if "_add_row_error" in st.session_state:
        st.error(st.session_state["_add_row_error"])
        del st.session_state["_add_row_error"]

    if not st.session_state.cap_table.empty:
        st.write("Current starting table")
        display_df = recalc_ownership(st.session_state.cap_table)
        display_df["ownership_pct"] = display_df["ownership_pct"].map(lambda x: f"{x:.2%}")
        st.dataframe(display_df, use_container_width=True)

    if st.button("Clear all data"):
        st.session_state.cap_table = empty_cap_table()
        st.session_state.round_history = empty_round_history()
        st.session_state.financing_details = empty_financing_details()
        st.session_state.new_holder = ""
        st.session_state.new_security_type = "Common"
        st.session_state.new_shares = 0.0
        st.rerun()

with tab2:
    st.subheader("Add funding round")

    if st.session_state.cap_table.empty:
        st.info("Add at least one starting cap table row first, or upload prior CSVs in Downloads / Uploads.")
    else:
        round_type = st.selectbox("Round type", ["Equity", "SAFE", "Convertible Note"])
        round_name = st.text_input("Round name / label", value="")
        round_date = st.date_input("Round / close date", value=date.today())

        pre_money_valuation = None
        valuation_cap = None
        discount_pct = None
        interest_rate_pct = None
        issue_date = round_date
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
            issue_date = st.date_input("SAFE issue date", value=round_date, key="safe_issue_date")

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
            issue_date = st.date_input("Note issue date", value=round_date, key="note_issue_date")
            maturity_date = st.date_input("Maturity date", value=round_date, key="note_maturity_date")

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
                    "round_date": date_to_str(round_date),
                    "pre_money_valuation": pre_money_valuation,
                    "amount_raised": total_raised,
                    "valuation_cap": valuation_cap,
                    "discount_pct": discount_pct,
                    "interest_rate_pct": interest_rate_pct,
                    "issue_date": date_to_str(issue_date),
                    "maturity_date": date_to_str(maturity_date),
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
                pre_round_shares = pd.to_numeric(updated_cap_table["shares"], errors="coerce").fillna(0.0).sum()

                if pre_round_shares <= 0 or not pre_money_valuation or pre_money_valuation <= 0:
                    st.error("Need a valid pre-money valuation and at least one existing share.")
                else:
                    round_price = float(pre_money_valuation) / float(pre_round_shares)

                    preferred_rows = []
                    for inv in investors:
                        if inv["investor_name"] and inv["amount"] > 0:
                            shares_issued = float(inv["amount"]) / float(round_price)
                            preferred_rows.append(
                                {
                                    "holder": inv["investor_name"],
                                    "security_type": "Preferred",
                                    "class": clean_round_name,
                                    "shares": shares_issued,
                                }
                            )

                    convertible_rows, financing_updated, conversion_summary = build_conversion_rows(
                        st.session_state.financing_details,
                        clean_round_name,
                        round_date,
                        round_price,
                        pre_round_shares,
                    )

                    if preferred_rows:
                        updated_cap_table = pd.concat(
                            [updated_cap_table, pd.DataFrame(preferred_rows)],
                            ignore_index=True,
                        )

                    if convertible_rows:
                        updated_cap_table = pd.concat(
                            [updated_cap_table, pd.DataFrame(convertible_rows)],
                            ignore_index=True,
                        )

                    st.session_state.cap_table = updated_cap_table
                    st.session_state.financing_details = financing_updated

                    equity_financing_rows = []
                    for inv in investors:
                        if inv["investor_name"] and inv["amount"] > 0:
                            equity_financing_rows.append(
                                {
                                    "status": "issued",
                                    "instrument_type": "Equity",
                                    "round_name": clean_round_name,
                                    "round_date": date_to_str(round_date),
                                    "investor_name": inv["investor_name"],
                                    "amount_invested": inv["amount"],
                                    "principal_invested": None,
                                    "valuation_cap": None,
                                    "discount_pct": None,
                                    "interest_rate_pct": None,
                                    "issue_date": date_to_str(round_date),
                                    "maturity_date": None,
                                    "converted_in_round": None,
                                    "converted_on_date": None,
                                    "conversion_amount": None,
                                    "conversion_price": round_price,
                                    "shares_issued": float(inv["amount"]) / float(round_price),
                                }
                            )

                    if equity_financing_rows:
                        st.session_state.financing_details = pd.concat(
                            [st.session_state.financing_details, pd.DataFrame(equity_financing_rows)],
                            ignore_index=True,
                        )

                    st.success(f"Equity round applied at ${round_price:,.4f} per share.")

                    if not conversion_summary.empty:
                        st.write("### Converted SAFE / Note instruments")
                        show_conv = conversion_summary.copy()
                        for col in [
                            "conversion_amount",
                            "accrued_interest",
                            "cap_price",
                            "discount_price",
                            "round_price",
                            "conversion_price",
                        ]:
                            if col in show_conv.columns:
                                show_conv[col] = show_conv[col].apply(
                                    lambda x: f"${x:,.4f}" if pd.notnull(x) else ""
                                )
                        st.dataframe(show_conv, use_container_width=True)

            elif round_type == "SAFE":
                safe_rows = []
                for inv in investors:
                    if inv["investor_name"] and inv["amount"] > 0:
                        safe_rows.append(
                            {
                                "status": "outstanding",
                                "instrument_type": "SAFE",
                                "round_name": clean_round_name,
                                "round_date": date_to_str(round_date),
                                "investor_name": inv["investor_name"],
                                "amount_invested": inv["amount"],
                                "principal_invested": None,
                                "valuation_cap": valuation_cap,
                                "discount_pct": discount_pct,
                                "interest_rate_pct": None,
                                "issue_date": date_to_str(issue_date),
                                "maturity_date": None,
                                "converted_in_round": None,
                                "converted_on_date": None,
                                "conversion_amount": None,
                                "conversion_price": None,
                                "shares_issued": None,
                            }
                        )
                if safe_rows:
                    st.session_state.financing_details = pd.concat(
                        [st.session_state.financing_details, pd.DataFrame(safe_rows)],
                        ignore_index=True,
                    )
                st.session_state.cap_table = updated_cap_table
                st.success("SAFE round stored. It will convert automatically in a later equity round.")

            else:
                note_rows = []
                for inv in investors:
                    if inv["investor_name"] and inv["amount"] > 0:
                        note_rows.append(
                            {
                                "status": "outstanding",
                                "instrument_type": "Convertible Note",
                                "round_name": clean_round_name,
                                "round_date": date_to_str(round_date),
                                "investor_name": inv["investor_name"],
                                "amount_invested": None,
                                "principal_invested": inv["amount"],
                                "valuation_cap": valuation_cap,
                                "discount_pct": discount_pct,
                                "interest_rate_pct": interest_rate_pct,
                                "issue_date": date_to_str(issue_date),
                                "maturity_date": date_to_str(maturity_date),
                                "converted_in_round": None,
                                "converted_on_date": None,
                                "conversion_amount": None,
                                "conversion_price": None,
                                "shares_issued": None,
                            }
                        )
                if note_rows:
                    st.session_state.financing_details = pd.concat(
                        [st.session_state.financing_details, pd.DataFrame(note_rows)],
                        ignore_index=True,
                    )
                st.session_state.cap_table = updated_cap_table
                st.success("Convertible note round stored. It will convert automatically in a later equity round.")

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
        money_cols = [
            "pre_money_valuation",
            "amount_raised",
            "valuation_cap",
        ]
        for col in money_cols:
            if col in history_show.columns:
                history_show[col] = history_show[col].apply(
                    lambda x: f"${x:,.2f}" if pd.notnull(x) and x != "" else ""
                )
        st.dataframe(history_show, use_container_width=True)

    st.subheader("Financing details")
    if st.session_state.financing_details.empty:
        st.info("No SAFE, note, or equity financing detail yet.")
    else:
        details_show = st.session_state.financing_details.copy()
        money_cols = [
            "amount_invested",
            "principal_invested",
            "valuation_cap",
            "conversion_amount",
            "conversion_price",
        ]
        for col in money_cols:
            if col in details_show.columns:
                details_show[col] = details_show[col].apply(
                    lambda x: f"${x:,.2f}" if pd.notnull(x) and x != "" else ""
                )
        st.dataframe(details_show, use_container_width=True)

with tab4:
    st.subheader("Exit sensitivity analysis")
    st.caption("This version uses simple pro rata ownership based on the current cap table.")

    current = recalc_ownership(st.session_state.cap_table)

    if current.empty:
        st.info("Add a cap table first before running exit analysis.")
    else:
        col1, col2 = st.columns(2)
        low_exit = col1.number_input(
            "Low exit value ($)",
            min_value=0.0,
            value=10000000.0,
            step=1000000.0,
            format="%g",
        )
        high_exit = col2.number_input(
            "High exit value ($)",
            min_value=0.0,
            value=200000000.0,
            step=1000000.0,
            format="%g",
        )

        if st.button("Run exit sensitivity"):
            exit_values = build_exit_scenarios(low_exit, high_exit, num_points=8)

            if not exit_values:
                st.error("Please enter a valid low and high exit value.")
            else:
                sensitivity_df = build_exit_sensitivity_table(current, exit_values)

                display_df = sensitivity_df.copy()
                display_df["ownership_pct"] = display_df["ownership_pct"].map(lambda x: f"{x:.2%}")

                dollar_cols = [c for c in display_df.columns if c.startswith("$")]
                for col in dollar_cols:
                    display_df[col] = display_df[col].map(lambda x: f"${x:,.2f}")

                scenario_labels = [f"${v:,.0f}" for v in exit_values]
                st.write(f"Scenarios used: {', '.join(scenario_labels)}")
                st.write("### Exit proceeds by holder")
                st.dataframe(display_df, use_container_width=True)

                st.download_button(
                    "Download exit sensitivity CSV",
                    data=to_csv_bytes(sensitivity_df),
                    file_name="exit_sensitivity.csv",
                    mime="text/csv",
                )

with tab5:
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

    st.download_button(
        "Download financing details CSV",
        data=to_csv_bytes(st.session_state.financing_details),
        file_name="financing_details.csv",
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

    uploaded_financing = st.file_uploader(
        "Upload financing details CSV",
        type=["csv"],
        key="uploaded_financing_details",
    )

    if st.button("Load uploaded CSVs"):
        try:
            if uploaded_cap is not None:
                cap_df = pd.read_csv(uploaded_cap)
                st.session_state.cap_table = normalize_cap_table(cap_df)

            if uploaded_rounds is not None:
                round_df = pd.read_csv(uploaded_rounds)
                st.session_state.round_history = normalize_round_history(round_df)

            if uploaded_financing is not None:
                financing_df = pd.read_csv(uploaded_financing)
                st.session_state.financing_details = normalize_financing_details(financing_df)

            st.success("Uploaded files loaded into the app.")
            st.rerun()
        except Exception as e:
            st.error(f"Could not load files: {e}")
