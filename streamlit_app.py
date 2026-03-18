import pandas as pd
import streamlit as st
from datetime import date, datetime

st.set_page_config(page_title="Cap Table App", layout="wide")

st.title("Cap Table App")
st.caption("Cap Table Management, Funding Rounds, and Exit Calculations")

CAP_COLUMNS = ["holder", "security_type", "class", "shares", "issue_date"]

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
    "price_per_share_override",
    "minimum_financing_amount",
    "option_pool_timing",
    "pre_money_fd_shares_override",
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
    "safe_type",
    "capitalization_basis",
    "interest_method",
    "interest_compounding_frequency",
    "converts_accrued_interest",
    "conversion_trigger",
    "minimum_financing_amount",
    "shadow_preferred",
    "converted_in_round",
    "converted_on_date",
    "conversion_amount",
    "conversion_price",
    "conversion_price_source",
    "cap_price",
    "discount_price",
    "round_price_at_conversion",
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

if "new_shares" not in st.session_state:
    st.session_state.new_shares = "0"

if "new_issue_date" not in st.session_state:
    st.session_state.new_issue_date = date.today()

if "option_pool_shares" not in st.session_state:
    st.session_state.option_pool_shares = "0"

if "option_pool_issue_date" not in st.session_state:
    st.session_state.option_pool_issue_date = date.today()


def empty_cap_table():
    return pd.DataFrame(columns=CAP_COLUMNS)


def empty_round_history():
    return pd.DataFrame(columns=ROUND_COLUMNS)


def empty_financing_details():
    return pd.DataFrame(columns=FINANCING_COLUMNS)


def parse_numeric(value, default=0.0):
    if value is None:
        return default
    if isinstance(value, (int, float)):
        if pd.isna(value):
            return default
        return float(value)
    cleaned = str(value).strip().replace(",", "")
    if cleaned == "":
        return default
    try:
        return float(cleaned)
    except Exception:
        return default


def format_number_for_input(value, decimals=0):
    try:
        numeric = float(value)
    except Exception:
        numeric = 0.0
    if decimals == 0:
        return f"{numeric:,.0f}"
    return f"{numeric:,.{decimals}f}"


def text_numeric_input(label, key, value="0", help_text=None):
    return st.text_input(label, value=value, key=key, help=help_text)


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
    for c in CAP_COLUMNS:
        if c not in out.columns:
            out[c] = None
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


def compute_note_accrued_interest(principal, annual_rate_pct, start_date, end_date, interest_method, compounding_frequency):
    principal = parse_numeric(principal)
    annual_rate_pct = parse_numeric(annual_rate_pct)
    if principal <= 0 or annual_rate_pct <= 0:
        return 0.0

    days = days_between(start_date, end_date)
    years = days / 365.0
    rate = annual_rate_pct / 100.0
    method = (interest_method or "simple").strip().lower()
    frequency = (compounding_frequency or "annual").strip().lower()

    if method != "compound":
        return principal * rate * years

    periods_map = {
        "annual": 1,
        "semi_annual": 2,
        "quarterly": 4,
        "monthly": 12,
        "daily": 365,
    }
    periods = periods_map.get(frequency, 1)
    amount = principal * ((1 + rate / periods) ** (periods * years))
    return max(amount - principal, 0.0)


def outstanding_convertibles(financing_df: pd.DataFrame) -> pd.DataFrame:
    if financing_df.empty:
        return financing_df.copy()
    out = financing_df.copy()
    out["status"] = out["status"].fillna("outstanding")
    mask = out["instrument_type"].isin(["SAFE", "Convertible Note"]) & (out["status"] == "outstanding")
    return out.loc[mask].copy()


def capitalization_shares_by_basis(cap_table: pd.DataFrame, basis: str) -> float:
    cap = cap_table.copy()
    if cap.empty:
        return 0.0

    cap["shares"] = pd.to_numeric(cap["shares"], errors="coerce").fillna(0.0)
    basis = (basis or "company_cap_table_fd").strip()

    if basis == "outstanding_only":
        mask = cap["security_type"].isin(["Common", "Preferred", "Option"])
    elif basis == "exclude_option_pool_reserve":
        mask = cap["security_type"].isin(["Common", "Preferred", "Option"])
    else:
        mask = cap["security_type"].isin(["Common", "Preferred", "Option", "Option Pool"])

    filtered = cap.loc[mask].copy()
    if basis == "exclude_option_pool_reserve":
        filtered = filtered[filtered["security_type"] != "Option Pool"].copy()

    return float(filtered["shares"].sum())


def build_conversion_rows(
    financing_df: pd.DataFrame,
    cap_table_for_conversion: pd.DataFrame,
    equity_round_name: str,
    equity_round_date,
    round_price: float,
    pre_round_fd_shares: float,
    total_new_money: float = 0.0,
    minimum_financing_amount: float = 0.0,
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
        capitalization_basis = row.get("capitalization_basis") or "company_cap_table_fd"
        converts_accrued_interest = row.get("converts_accrued_interest")
        conversion_trigger = row.get("conversion_trigger") or "qualified_financing"
        instrument_min_financing = parse_numeric(row.get("minimum_financing_amount"))
        shadow_preferred = bool(row.get("shadow_preferred"))

        effective_min_financing = max(parse_numeric(minimum_financing_amount), instrument_min_financing)
        round_qualified = True if effective_min_financing <= 0 else parse_numeric(total_new_money) >= effective_min_financing
        if conversion_trigger == "qualified_financing" and not round_qualified:
            continue

        if instrument_type == "SAFE":
            base_amount = pd.to_numeric(row.get("amount_invested"), errors="coerce")
            accrued_interest = 0.0
        else:
            principal = pd.to_numeric(row.get("principal_invested"), errors="coerce")
            accrued_interest = compute_note_accrued_interest(
                principal,
                interest_rate_pct,
                row.get("issue_date"),
                equity_round_date,
                row.get("interest_method"),
                row.get("interest_compounding_frequency"),
            )
            if pd.isna(converts_accrued_interest):
                converts_accrued_interest = True
            base_amount = (0.0 if pd.isna(principal) else float(principal)) + (accrued_interest if bool(converts_accrued_interest) else 0.0)

        if pd.isna(base_amount) or base_amount <= 0:
            continue

        cap_basis_shares = capitalization_shares_by_basis(cap_table_for_conversion, capitalization_basis)
        if pre_round_fd_shares > 0 and capitalization_basis == "company_cap_table_fd":
            cap_basis_shares = pre_round_fd_shares

        candidate_prices = []
        price_labels = []

        if pd.notna(valuation_cap) and valuation_cap > 0 and cap_basis_shares > 0:
            cap_price = float(valuation_cap) / float(cap_basis_shares)
            candidate_prices.append(cap_price)
            price_labels.append((cap_price, "cap_price"))
        else:
            cap_price = None

        if pd.notna(discount_pct) and discount_pct > 0:
            discount_price = round_price * (1.0 - float(discount_pct) / 100.0)
            candidate_prices.append(discount_price)
            price_labels.append((discount_price, "discount_price"))
        else:
            discount_price = None

        candidate_prices.append(round_price)
        price_labels.append((round_price, "round_price"))

        valid_prices = [p for p in candidate_prices if p is not None and p > 0]
        if not valid_prices:
            continue

        conversion_price = min(valid_prices)
        conversion_price_source = next((label for price, label in price_labels if abs(price - conversion_price) < 1e-12), "round_price")
        shares_issued = float(base_amount) / float(conversion_price)
        issued_class = f"{equity_round_name} Shadow" if shadow_preferred else equity_round_name

        cap_rows.append(
            {
                "holder": investor_name,
                "security_type": "Preferred",
                "class": issued_class,
                "shares": shares_issued,
                "issue_date": date_to_str(equity_round_date),
            }
        )

        updated_financing.at[idx, "status"] = "converted"
        updated_financing.at[idx, "converted_in_round"] = equity_round_name
        updated_financing.at[idx, "converted_on_date"] = date_to_str(equity_round_date)
        updated_financing.at[idx, "conversion_amount"] = float(base_amount)
        updated_financing.at[idx, "conversion_price"] = float(conversion_price)
        updated_financing.at[idx, "conversion_price_source"] = conversion_price_source
        updated_financing.at[idx, "cap_price"] = cap_price
        updated_financing.at[idx, "discount_price"] = discount_price
        updated_financing.at[idx, "round_price_at_conversion"] = float(round_price)
        updated_financing.at[idx, "shares_issued"] = float(shares_issued)

        conversion_summary_rows.append(
            {
                "investor_name": investor_name,
                "instrument_type": instrument_type,
                "converted_in_round": equity_round_name,
                "capitalization_basis": capitalization_basis,
                "conversion_trigger": conversion_trigger,
                "minimum_financing_amount": float(effective_min_financing),
                "conversion_amount": float(base_amount),
                "accrued_interest": float(accrued_interest),
                "cap_basis_shares": float(cap_basis_shares),
                "cap_price": cap_price,
                "discount_price": discount_price,
                "round_price": float(round_price),
                "conversion_price": float(conversion_price),
                "conversion_price_source": conversion_price_source,
                "shares_issued": float(shares_issued),
                "shadow_preferred": shadow_preferred,
                "issued_class": issued_class,
            }
        )

    summary_df = pd.DataFrame(conversion_summary_rows)
    return cap_rows, updated_financing, summary_df


def add_starting_row():
    holder = st.session_state.get("new_holder", "").strip()
    shares = parse_numeric(st.session_state.get("new_shares", "0"))
    issue_date = st.session_state.get("new_issue_date", date.today())

    if holder and shares > 0:
        new_row = pd.DataFrame(
            [{
                "holder": holder,
                "security_type": "Common",
                "class": "Common",
                "shares": shares,
                "issue_date": date_to_str(issue_date),
            }]
        )
        st.session_state.cap_table = pd.concat(
            [st.session_state.cap_table, new_row], ignore_index=True
        )
        st.session_state["_reset_new_common_form"] = True
    else:
        st.session_state["_add_row_error"] = "Enter a holder name and shares greater than 0."


def apply_common_equity_change():
    change_type = st.session_state.get("common_change_type", "Increase existing holder")
    selected_holder = st.session_state.get("common_change_holder", "")
    new_holder_name = st.session_state.get("common_change_new_holder", "").strip()
    shares = parse_numeric(st.session_state.get("common_change_shares", "0"))
    issue_date = st.session_state.get("common_change_issue_date", date.today())

    if shares <= 0:
        st.session_state["_common_change_error"] = "Enter common shares greater than 0."
        return

    if change_type == "Increase existing holder":
        if not selected_holder:
            st.session_state["_common_change_error"] = "Select an existing common holder."
            return

        new_row = pd.DataFrame(
            [{
                "holder": selected_holder,
                "security_type": "Common",
                "class": "Common",
                "shares": shares,
                "issue_date": date_to_str(issue_date),
            }]
        )
    else:
        if not new_holder_name:
            st.session_state["_common_change_error"] = "Enter a new holder name."
            return

        new_row = pd.DataFrame(
            [{
                "holder": new_holder_name,
                "security_type": "Common",
                "class": "Common",
                "shares": shares,
                "issue_date": date_to_str(issue_date),
            }]
        )

    st.session_state.cap_table = pd.concat(
        [st.session_state.cap_table, new_row], ignore_index=True
    )
    st.session_state.common_change_shares = "0"
    st.session_state.common_change_new_holder = ""


def apply_pending_widget_resets():
    pending = st.session_state.get("_pending_widget_state_updates", {})
    if pending:
        for key, value in pending.items():
            st.session_state[key] = value
        st.session_state["_pending_widget_state_updates"] = {}


def clear_all_app_data():
    st.session_state.cap_table = empty_cap_table()
    st.session_state.round_history = empty_round_history()
    st.session_state.financing_details = empty_financing_details()

    reset_values = {
        "new_holder": "",
        "new_shares": "0",
        "new_issue_date": date.today(),
        "option_pool_shares": "0",
        "option_pool_issue_date": date.today(),
        "common_change_type": "Increase existing holder",
        "common_change_holder": "",
        "common_change_new_holder": "",
        "common_change_shares": "0",
        "common_change_issue_date": date.today(),
        "option_grant_holder": "",
        "option_grant_shares": "0",
        "option_grant_issue_date": date.today(),
    }

    for key, value in reset_values.items():
        st.session_state[key] = value


def set_option_pool():
    pool_shares = parse_numeric(st.session_state.get("option_pool_shares", "0"))
    issue_date = st.session_state.get("option_pool_issue_date", date.today())

    cap = st.session_state.cap_table.copy()
    cap = cap[cap["holder"] != "Option Pool Reserve"].copy()

    if pool_shares > 0:
        pool_row = pd.DataFrame(
            [{
                "holder": "Option Pool Reserve",
                "security_type": "Option Pool",
                "class": "Option Pool",
                "shares": pool_shares,
                "issue_date": date_to_str(issue_date),
            }]
        )
        cap = pd.concat([cap, pool_row], ignore_index=True)

    st.session_state.cap_table = cap


def build_exit_scenarios(low_value: float, high_value: float, num_points: int = 8):
    if low_value < 0 or high_value < 0:
        return []
    if high_value < low_value:
        return []
    if low_value == high_value:
        return [float(low_value)]

    step = (high_value - low_value) / (num_points - 1)
    return [low_value + i * step for i in range(num_points)]


def get_exit_eligible_cap_table(cap_table: pd.DataFrame) -> pd.DataFrame:
    if cap_table.empty:
        return cap_table.copy()
    out = cap_table.copy()
    out["shares"] = pd.to_numeric(out["shares"], errors="coerce").fillna(0.0)
    out = out[out["shares"] > 0].copy()
    out = out[out["holder"] != "Option Pool Reserve"].copy()
    out = out[out["security_type"] != "Option Pool"].copy()
    return out


def build_preferred_class_terms(cap_table: pd.DataFrame, round_history: pd.DataFrame, financing_details: pd.DataFrame) -> pd.DataFrame:
    eligible = get_exit_eligible_cap_table(cap_table)
    preferred = eligible[eligible["security_type"] == "Preferred"].copy()

    if preferred.empty:
        return pd.DataFrame(
            columns=[
                "class",
                "shares",
                "original_investment",
                "liq_pref_multiple",
                "participating",
                "participation_cap_multiple",
                "round_date",
                "round_order",
            ]
        )

    preferred_summary = (
        preferred.groupby("class", dropna=False, as_index=False)["shares"].sum()
        .rename(columns={"shares": "shares"})
    )

    issued_equity = financing_details.copy()
    if not issued_equity.empty:
        issued_equity = issued_equity[
            (issued_equity["instrument_type"] == "Equity") & (issued_equity["status"] == "issued")
        ].copy()
    if issued_equity.empty:
        investment_summary = pd.DataFrame(columns=["round_name", "original_investment"])
    else:
        issued_equity["amount_invested"] = pd.to_numeric(issued_equity["amount_invested"], errors="coerce").fillna(0.0)
        investment_summary = (
            issued_equity.groupby("round_name", as_index=False)["amount_invested"].sum()
            .rename(columns={"round_name": "class", "amount_invested": "original_investment"})
        )

    equity_rounds = round_history.copy()
    if not equity_rounds.empty:
        equity_rounds = equity_rounds[equity_rounds["round_type"] == "Equity"].copy().reset_index(drop=True)
        equity_rounds["round_order"] = equity_rounds.index
        equity_rounds = equity_rounds[
            [
                "round_name",
                "round_date",
                "liq_pref_multiple",
                "participating",
                "participation_cap_multiple",
                "round_order",
            ]
        ].rename(columns={"round_name": "class"})
    else:
        equity_rounds = pd.DataFrame(
            columns=[
                "class",
                "round_date",
                "liq_pref_multiple",
                "participating",
                "participation_cap_multiple",
                "round_order",
            ]
        )

    out = preferred_summary.merge(investment_summary, on="class", how="left")
    out = out.merge(equity_rounds, on="class", how="left")

    out["shares"] = pd.to_numeric(out["shares"], errors="coerce").fillna(0.0)
    out["original_investment"] = pd.to_numeric(out["original_investment"], errors="coerce").fillna(0.0)
    out["liq_pref_multiple"] = pd.to_numeric(out["liq_pref_multiple"], errors="coerce").fillna(1.0)
    out["participation_cap_multiple"] = pd.to_numeric(out["participation_cap_multiple"], errors="coerce")
    out["participating"] = out["participating"].fillna(False).astype(bool)
    out["round_order"] = pd.to_numeric(out["round_order"], errors="coerce").fillna(-1)
    out["round_date_parsed"] = out["round_date"].apply(str_to_date)
    return out


def allocate_capped_pro_rata(total_amount: float, participant_df: pd.DataFrame) -> dict:
    if total_amount <= 0 or participant_df.empty:
        return {}

    working = participant_df.copy()
    working["shares"] = pd.to_numeric(working["shares"], errors="coerce").fillna(0.0)
    working["cap_remaining"] = pd.to_numeric(working["cap_remaining"], errors="coerce")
    working = working[working["shares"] > 0].copy()

    allocations = {k: 0.0 for k in working["participant_id"]}
    remaining = float(total_amount)

    while remaining > 1e-9 and not working.empty:
        active = working[(working["shares"] > 0)].copy()
        if active.empty:
            break

        active_shares = active["shares"].sum()
        if active_shares <= 0:
            break

        active["provisional"] = remaining * active["shares"] / active_shares
        capped = active[
            active["cap_remaining"].notna() & (active["provisional"] > active["cap_remaining"] + 1e-9)
        ].copy()

        if capped.empty:
            for _, row in active.iterrows():
                allocations[row["participant_id"]] += float(row["provisional"])
            remaining = 0.0
            break

        capped_ids = set(capped["participant_id"])
        capped_total = 0.0
        for _, row in capped.iterrows():
            payout = max(float(row["cap_remaining"]), 0.0)
            allocations[row["participant_id"]] += payout
            capped_total += payout

        remaining = max(remaining - capped_total, 0.0)
        working = working[~working["participant_id"].isin(capped_ids)].copy()

    return allocations


def build_waterfall_for_exit(
    cap_table: pd.DataFrame,
    round_history: pd.DataFrame,
    financing_details: pd.DataFrame,
    exit_value: float,
):
    eligible = get_exit_eligible_cap_table(cap_table)
    if eligible.empty:
        return pd.DataFrame(), pd.DataFrame()

    eligible["shares"] = pd.to_numeric(eligible["shares"], errors="coerce").fillna(0.0)
    eligible = eligible[eligible["shares"] > 0].copy()

    total_exit_shares = eligible["shares"].sum()
    if total_exit_shares <= 0:
        return pd.DataFrame(), pd.DataFrame()

    class_terms = build_preferred_class_terms(cap_table, round_history, financing_details)

    common_rows = eligible[eligible["security_type"].isin(["Common", "Option"])].copy()
    common_shares = common_rows["shares"].sum()

    class_summaries = []

    if not class_terms.empty:
        for _, row in class_terms.iterrows():
            shares = float(row["shares"])
            investment = float(row["original_investment"])
            liq_pref_multiple = float(row["liq_pref_multiple"]) if pd.notnull(row["liq_pref_multiple"]) else 1.0
            as_converted_value = float(exit_value) * shares / total_exit_shares if total_exit_shares > 0 else 0.0
            pref_claim = investment * liq_pref_multiple
            participating = bool(row["participating"])
            convert_to_common = (not participating) and (as_converted_value > pref_claim)

            class_summaries.append(
                {
                    "class": row["class"],
                    "shares": shares,
                    "original_investment": investment,
                    "liq_pref_multiple": liq_pref_multiple,
                    "participating": participating,
                    "participation_cap_multiple": row.get("participation_cap_multiple"),
                    "round_date": row.get("round_date"),
                    "round_order": row.get("round_order"),
                    "round_date_parsed": row.get("round_date_parsed"),
                    "as_converted_value": as_converted_value,
                    "pref_claim": pref_claim,
                    "convert_to_common": convert_to_common,
                    "pref_allocated": 0.0,
                    "residual_allocated": 0.0,
                    "total_payout": 0.0,
                }
            )

    class_summary_df = pd.DataFrame(class_summaries)

    remaining_exit = float(exit_value)

    if not class_summary_df.empty:
        pref_classes = class_summary_df[~class_summary_df["convert_to_common"]].copy()
        if not pref_classes.empty:
            pref_classes["sort_date"] = pref_classes["round_date_parsed"].apply(
                lambda x: x.toordinal() if x is not None else -1
            )
            pref_classes = pref_classes.sort_values(
                by=["sort_date", "round_order"],
                ascending=[False, False],
            )

            for _, row in pref_classes.iterrows():
                pref_claim = max(float(row["pref_claim"]), 0.0)
                pref_paid = min(pref_claim, remaining_exit)
                class_summary_df.loc[class_summary_df["class"] == row["class"], "pref_allocated"] = pref_paid
                remaining_exit = max(remaining_exit - pref_paid, 0.0)

        participants = []
        if common_shares > 0:
            participants.append(
                {
                    "participant_id": "COMMON_POOL",
                    "shares": common_shares,
                    "cap_remaining": None,
                }
            )

        for _, row in class_summary_df.iterrows():
            if bool(row["participating"]):
                cap_multiple = row.get("participation_cap_multiple")
                cap_remaining = None
                if pd.notnull(cap_multiple) and float(cap_multiple) > 0:
                    cap_total = float(cap_multiple) * float(row["original_investment"])
                    cap_remaining = max(cap_total - float(row["pref_allocated"]), 0.0)
                participants.append(
                    {
                        "participant_id": f"CLASS::{row['class']}",
                        "shares": float(row["shares"]),
                        "cap_remaining": cap_remaining,
                    }
                )
            elif bool(row["convert_to_common"]):
                participants.append(
                    {
                        "participant_id": f"CLASS::{row['class']}",
                        "shares": float(row["shares"]),
                        "cap_remaining": None,
                    }
                )

        participant_df = pd.DataFrame(participants)
        residual_allocations = allocate_capped_pro_rata(remaining_exit, participant_df)

        common_pool_payout = residual_allocations.get("COMMON_POOL", 0.0)

        class_summary_df["residual_allocated"] = class_summary_df["class"].apply(
            lambda c: residual_allocations.get(f"CLASS::{c}", 0.0)
        )
        class_summary_df["total_payout"] = (
            class_summary_df["pref_allocated"] + class_summary_df["residual_allocated"]
        )
    else:
        common_pool_payout = float(exit_value)

    holder_rows = []

    if common_shares > 0:
        for _, row in common_rows.iterrows():
            payout = common_pool_payout * float(row["shares"]) / common_shares if common_shares > 0 else 0.0
            holder_rows.append(
                {
                    "holder": row["holder"],
                    "security_type": row["security_type"],
                    "class": row["class"],
                    "shares": float(row["shares"]),
                    "issue_date": row.get("issue_date"),
                    "exit_proceeds": payout,
                }
            )

    preferred_rows = eligible[eligible["security_type"] == "Preferred"].copy()
    if not preferred_rows.empty and not class_summary_df.empty:
        class_totals = class_summary_df.set_index("class")["total_payout"].to_dict()
        class_shares = class_summary_df.set_index("class")["shares"].to_dict()

        for _, row in preferred_rows.iterrows():
            class_name = row["class"]
            total_payout = float(class_totals.get(class_name, 0.0))
            total_class_shares = float(class_shares.get(class_name, 0.0))
            payout = total_payout * float(row["shares"]) / total_class_shares if total_class_shares > 0 else 0.0
            holder_rows.append(
                {
                    "holder": row["holder"],
                    "security_type": row["security_type"],
                    "class": class_name,
                    "shares": float(row["shares"]),
                    "issue_date": row.get("issue_date"),
                    "exit_proceeds": payout,
                }
            )

    holder_df = pd.DataFrame(holder_rows)
    if not holder_df.empty:
        holder_df = holder_df.groupby(["holder", "security_type", "class", "issue_date"], as_index=False)[["shares", "exit_proceeds"]].sum()

    if class_summary_df.empty:
        class_summary_df = pd.DataFrame(
            columns=[
                "class",
                "shares",
                "original_investment",
                "liq_pref_multiple",
                "participating",
                "participation_cap_multiple",
                "as_converted_value",
                "pref_claim",
                "convert_to_common",
                "pref_allocated",
                "residual_allocated",
                "total_payout",
            ]
        )
    else:
        class_summary_df = class_summary_df[
            [
                "class",
                "shares",
                "original_investment",
                "liq_pref_multiple",
                "participating",
                "participation_cap_multiple",
                "as_converted_value",
                "pref_claim",
                "convert_to_common",
                "pref_allocated",
                "residual_allocated",
                "total_payout",
            ]
        ].copy()

    return holder_df, class_summary_df


def build_exit_sensitivity_table(
    cap_table: pd.DataFrame,
    round_history: pd.DataFrame,
    financing_details: pd.DataFrame,
    exit_values: list[float],
) -> pd.DataFrame:
    eligible = get_exit_eligible_cap_table(cap_table)
    if eligible.empty or not exit_values:
        return pd.DataFrame()

    base = eligible[["holder", "security_type", "class", "shares", "issue_date"]].copy()
    base["shares"] = pd.to_numeric(base["shares"], errors="coerce").fillna(0.0)
    result = base.groupby(["holder", "security_type", "class", "issue_date"], as_index=False)["shares"].sum()

    total_shares = result["shares"].sum()
    result["ownership_pct_ex_option_pool"] = result["shares"] / total_shares if total_shares > 0 else 0.0

    for exit_value in exit_values:
        holder_df, _ = build_waterfall_for_exit(
            cap_table=cap_table,
            round_history=round_history,
            financing_details=financing_details,
            exit_value=float(exit_value),
        )
        col_name = f"${exit_value:,.0f}"
        payout_map = {}
        if not holder_df.empty:
            payout_map = holder_df.set_index(["holder", "security_type", "class", "issue_date"])["exit_proceeds"].to_dict()

        result[col_name] = result.apply(
            lambda r: payout_map.get((r["holder"], r["security_type"], r["class"], r["issue_date"]), 0.0),
            axis=1,
        )

    return result


def validate_round_inputs(
    round_type: str,
    round_name: str,
    investors: list,
    pre_money_valuation,
    valuation_cap,
    discount_pct,
):
    errors = []

    clean_round_name = round_name.strip() or round_type

    valid_investors = [
        inv for inv in investors if inv["investor_name"].strip() and float(inv["amount"] or 0.0) > 0
    ]

    if not clean_round_name:
        errors.append("Enter a round name.")

    if not valid_investors:
        errors.append("Enter at least one investor with a name and amount greater than 0.")

    blank_name_with_amount = [inv for inv in investors if not inv["investor_name"].strip() and float(inv["amount"] or 0.0) > 0]
    if blank_name_with_amount:
        errors.append("Each non-zero investment amount needs an investor name.")

    if round_type == "Equity" and (pre_money_valuation is None or float(pre_money_valuation) <= 0):
        errors.append("Equity rounds require a pre-money valuation greater than 0.")

    if round_type in ["SAFE", "Convertible Note"]:
        if (valuation_cap is None or float(valuation_cap) <= 0) and (discount_pct is None or float(discount_pct) <= 0):
            errors.append("Enter either a valuation cap, a discount, or both for SAFEs and notes.")

    return clean_round_name, valid_investors, errors


def format_money_columns(df: pd.DataFrame, columns: list[str], decimals: int = 2) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col in out.columns:
            out[col] = out[col].apply(
                lambda x: f"${x:,.{decimals}f}" if pd.notnull(x) and x != "" else ""
            )
    return out


def format_share_columns(df: pd.DataFrame, columns: list[str], decimals: int = 0) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col in out.columns:
            out[col] = out[col].apply(
                lambda x: f"{x:,.0f}" if pd.notnull(x) and x != "" else ""
            )
    return out


apply_pending_widget_resets()

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "Common Equity",
        "Funding Round",
        "Current Cap Table",
        "Exit Analysis",
        "Downloads / Uploads",
    ]
)

with tab1:
    st.subheader("Common Equity Table")
    st.caption("Use dated common equity and option issuances so the cap table itself shows when ownership changed.")

    st.markdown("### Add starting common holder")
    if st.session_state.get("_reset_new_common_form"):
        st.session_state["new_holder"] = ""
        st.session_state["new_shares"] = "0"
        st.session_state["new_issue_date"] = date.today()
        st.session_state["_reset_new_common_form"] = False

    with st.form("add_starting_common_holder_form"):
        col1, col2, col3 = st.columns(3)
        col1.text_input("Holder name", key="new_holder")
        col2.text_input(
            "Common shares",
            value=st.session_state.get("new_shares", "0"),
            key="new_shares",
            help="You can type values with commas, like 1,250,000.",
        )
        col3.date_input("Issue date", key="new_issue_date")
        add_common_submitted = st.form_submit_button("Add common holder")

    if add_common_submitted:
        add_starting_row()
        st.rerun()

    if "_add_row_error" in st.session_state:
        st.error(st.session_state["_add_row_error"])
        del st.session_state["_add_row_error"]

    st.markdown("### Common equity changes")
    existing_common_holders = sorted(
        st.session_state.cap_table.loc[
            st.session_state.cap_table["security_type"] == "Common", "holder"
        ].dropna().astype(str).unique().tolist()
    )

    c1, c2 = st.columns(2)
    c1.selectbox(
        "Change type",
        ["Increase existing holder", "Add new holder"],
        key="common_change_type",
    )

    if st.session_state.get("common_change_type") == "Increase existing holder":
        c2.selectbox(
            "Existing common holder",
            options=[""] + existing_common_holders,
            key="common_change_holder",
        )
    else:
        c2.text_input("New holder name", key="common_change_new_holder")

    c3, c4 = st.columns(2)
    c3.text_input(
        "Additional common shares",
        value=st.session_state.get("common_change_shares", "0"),
        key="common_change_shares",
        help="You can type values with commas.",
    )
    c4.date_input("Change date", key="common_change_issue_date", value=date.today())

    if st.button("Apply common equity change"):
        apply_common_equity_change()
        st.rerun()

    if "_common_change_error" in st.session_state:
        st.error(st.session_state["_common_change_error"])
        del st.session_state["_common_change_error"]

    st.markdown("### Option grants to common holders")
    option_holders = sorted(
        st.session_state.cap_table.loc[
            st.session_state.cap_table["security_type"] == "Common", "holder"
        ].dropna().astype(str).unique().tolist()
    )

    o1, o2, o3 = st.columns(3)
    o1.selectbox(
        "Common holder receiving options",
        options=[""] + option_holders,
        key="option_grant_holder",
    )
    o2.text_input(
        "Options granted",
        value=st.session_state.get("option_grant_shares", "0"),
        key="option_grant_shares",
        help="You can type values with commas.",
    )
    o3.date_input("Option grant date", key="option_grant_issue_date", value=date.today())

    if st.button("Issue options"):
        option_holder = st.session_state.get("option_grant_holder", "")
        option_shares = parse_numeric(st.session_state.get("option_grant_shares", "0"))
        option_issue_date = st.session_state.get("option_grant_issue_date", date.today())

        pool_mask = st.session_state.cap_table["holder"] == "Option Pool Reserve"
        current_pool = 0.0
        if pool_mask.any():
            current_pool = pd.to_numeric(
                st.session_state.cap_table.loc[pool_mask, "shares"],
                errors="coerce"
            ).fillna(0.0).sum()

        if not option_holder:
            st.session_state["_option_grant_error"] = "Select a common holder to receive the option grant."
        elif option_shares <= 0:
            st.session_state["_option_grant_error"] = "Enter an option grant amount greater than 0."
        elif current_pool <= 0:
            st.session_state["_option_grant_error"] = "There is no option pool reserve available to grant from."
        elif option_shares > current_pool:
            st.session_state["_option_grant_error"] = f"Option grant exceeds remaining pool. Available pool: {current_pool:,.0f} shares."
        else:
            updated_cap = st.session_state.cap_table.copy()
            updated_cap = updated_cap[updated_cap["holder"] != "Option Pool Reserve"].copy()

            remaining_pool = current_pool - option_shares
            if remaining_pool > 0:
                pool_row = pd.DataFrame(
                    [{
                        "holder": "Option Pool Reserve",
                        "security_type": "Option Pool",
                        "class": "Option Pool",
                        "shares": remaining_pool,
                        "issue_date": date_to_str(option_issue_date),
                    }]
                )
                updated_cap = pd.concat([updated_cap, pool_row], ignore_index=True)

            option_row = pd.DataFrame(
                [{
                    "holder": option_holder,
                    "security_type": "Option",
                    "class": "Employee Option",
                    "shares": option_shares,
                    "issue_date": date_to_str(option_issue_date),
                }]
            )
            updated_cap = pd.concat([updated_cap, option_row], ignore_index=True)
            st.session_state.cap_table = updated_cap
            st.session_state["_pending_widget_state_updates"] = {
                **st.session_state.get("_pending_widget_state_updates", {}),
                "option_pool_shares": format_number_for_input(remaining_pool),
                "option_pool_issue_date": option_issue_date,
                "option_grant_shares": "0",
            }
            st.rerun()

    if "_option_grant_error" in st.session_state:
        st.error(st.session_state["_option_grant_error"])
        del st.session_state["_option_grant_error"]

    st.markdown("### Option pool reserve")
    p1, p2 = st.columns(2)
    p1.text_input(
        "Option pool reserve shares",
        value=st.session_state.get("option_pool_shares", "0"),
        key="option_pool_shares",
        help="You can type values with commas.",
    )
    p2.date_input("Option pool effective date", key="option_pool_issue_date")

    if st.button("Update option pool reserve"):
        set_option_pool()
        st.rerun()

    if not st.session_state.cap_table.empty:
        st.write("Current common equity table")
        display_df = recalc_ownership(st.session_state.cap_table)
        display_df = format_share_columns(display_df, ["shares"])
        display_df["ownership_pct"] = display_df["ownership_pct"].map(lambda x: f"{x:.2%}")
        st.dataframe(display_df, use_container_width=True)

    st.button("Clear all data", on_click=clear_all_app_data)

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

        price_per_share_override = 0.0
        minimum_financing_amount = 0.0
        option_pool_timing = None
        pre_money_fd_shares_override = 0.0
        safe_type = None
        capitalization_basis = None
        interest_method = None
        interest_compounding_frequency = None
        converts_accrued_interest = None
        conversion_trigger = None
        shadow_preferred = False

        if round_type == "Equity":
            pre_money_valuation = parse_numeric(
                text_numeric_input(
                    "Pre-money valuation ($)",
                    key="equity_pre_money_valuation",
                    value=st.session_state.get("equity_pre_money_valuation", "0"),
                    help_text="You can type values with commas, like 25,000,000.",
                )
            )

            st.markdown("### Preferred stock terms")
            liq_pref_multiple = parse_numeric(
                text_numeric_input(
                    "Liquidation preference multiple (x)",
                    key="liq_pref_multiple",
                    value=st.session_state.get("liq_pref_multiple", "1"),
                )
            )
            participating = st.checkbox("Participating preferred", value=False)

            if participating:
                has_participation_cap = st.checkbox("Participation cap", value=False)
                if has_participation_cap:
                    participation_cap_multiple = parse_numeric(
                        text_numeric_input(
                            "Participation cap multiple (x)",
                            key="participation_cap_multiple",
                            value=st.session_state.get("participation_cap_multiple", "3"),
                        )
                    )
                else:
                    participation_cap_multiple = None
            else:
                participation_cap_multiple = None

        elif round_type == "SAFE":
            valuation_cap = parse_numeric(
                text_numeric_input(
                    "Valuation cap ($)",
                    key="safe_valuation_cap",
                    value=st.session_state.get("safe_valuation_cap", "0"),
                )
            )
            discount_pct = parse_numeric(
                text_numeric_input(
                    "Discount (%)",
                    key="safe_discount_pct",
                    value=st.session_state.get("safe_discount_pct", "0"),
                )
            )
            issue_date = round_date

        else:
            valuation_cap = parse_numeric(
                text_numeric_input(
                    "Valuation cap ($)",
                    key="note_valuation_cap",
                    value=st.session_state.get("note_valuation_cap", "0"),
                )
            )
            discount_pct = parse_numeric(
                text_numeric_input(
                    "Discount (%)",
                    key="note_discount_pct",
                    value=st.session_state.get("note_discount_pct", "0"),
                )
            )
            interest_rate_pct = parse_numeric(
                text_numeric_input(
                    "Interest rate (%)",
                    key="note_interest_rate_pct",
                    value=st.session_state.get("note_interest_rate_pct", "0"),
                )
            )
            issue_date = round_date
            maturity_date = st.date_input("Maturity date", value=round_date, key="note_maturity_date")

        st.markdown("### Instrument / round terms")
        st.caption("The round date is the financing date used for this round. Separate SAFE and note issue-date entry has been removed.")
        if round_type == "Equity":
            e1, e2, e3 = st.columns(3)
            price_per_share_override = parse_numeric(
                e1.text_input(
                    "Price per share override ($)",
                    value=st.session_state.get("equity_price_per_share_override", "0"),
                    key="equity_price_per_share_override",
                    help="Optional. Leave 0 to derive from pre-money valuation and FD shares.",
                )
            )
            minimum_financing_amount = parse_numeric(
                e2.text_input(
                    "Qualified financing threshold ($)",
                    value=st.session_state.get("equity_minimum_financing_amount", "0"),
                    key="equity_minimum_financing_amount",
                )
            )
            option_pool_timing = e3.selectbox(
                "Option pool timing",
                ["pre_money", "post_money"],
                key="equity_option_pool_timing",
            )
            pre_money_fd_shares_override = parse_numeric(
                st.text_input(
                    "Pre-money fully diluted shares override",
                    value=st.session_state.get("equity_pre_money_fd_shares_override", "0"),
                    key="equity_pre_money_fd_shares_override",
                    help="Optional. Leave 0 to use current cap table fully diluted shares.",
                )
            )
        elif round_type == "SAFE":
            s1, s2, s3 = st.columns(3)
            safe_type = "post_money_safe"
            s1.markdown("**SAFE type:** Post-money SAFE")
            capitalization_basis = s2.selectbox(
                "Capitalization basis",
                ["company_cap_table_fd", "exclude_option_pool_reserve", "outstanding_only"],
                key="safe_capitalization_basis",
            )
            shadow_preferred = s3.checkbox("Shadow preferred", key="safe_shadow_preferred", value=False)
            minimum_financing_amount = parse_numeric(
                st.text_input(
                    "Qualified financing threshold ($)",
                    value=st.session_state.get("safe_minimum_financing_amount", "0"),
                    key="safe_minimum_financing_amount",
                )
            )
            conversion_trigger = st.selectbox(
                "Conversion trigger",
                ["qualified_financing", "priced_round"],
                key="safe_conversion_trigger",
            )
        else:
            n1, n2, n3 = st.columns(3)
            capitalization_basis = n1.selectbox(
                "Capitalization basis",
                ["company_cap_table_fd", "exclude_option_pool_reserve", "outstanding_only"],
                key="note_capitalization_basis",
            )
            interest_method = n2.selectbox(
                "Interest method",
                ["simple", "compound"],
                key="note_interest_method",
            )
            interest_compounding_frequency = n3.selectbox(
                "Compounding frequency",
                ["annual", "semi_annual", "quarterly", "monthly", "daily"],
                key="note_interest_compounding_frequency",
            )
            converts_accrued_interest = st.checkbox(
                "Convert accrued interest",
                key="note_converts_accrued_interest",
                value=True,
            )
            n4, n5 = st.columns(2)
            minimum_financing_amount = parse_numeric(
                n4.text_input(
                    "Qualified financing threshold ($)",
                    value=st.session_state.get("note_minimum_financing_amount", "0"),
                    key="note_minimum_financing_amount",
                )
            )
            conversion_trigger = n5.selectbox(
                "Conversion trigger",
                ["qualified_financing", "priced_round"],
                key="note_conversion_trigger",
            )
            shadow_preferred = st.checkbox("Shadow preferred", key="note_shadow_preferred", value=False)

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
            amount = parse_numeric(
                c2.text_input(
                    f"Amount invested {i+1} ($)",
                    value=st.session_state.get(f"inv_amt_{i}", "0"),
                    key=f"inv_amt_{i}",
                    help="You can type values with commas.",
                )
            )
            investors.append({"investor_name": investor_name.strip(), "amount": amount})
            total_raised += amount

        st.write(f"Total raised: **${total_raised:,.2f}**")

        if round_type == "Equity":
            outstanding = outstanding_convertibles(st.session_state.financing_details)
            if not outstanding.empty:
                st.markdown("### Outstanding SAFE / Note instruments that will be evaluated for auto-conversion")
                outstanding_cols = [
                    "instrument_type",
                    "investor_name",
                    "amount_invested",
                    "principal_invested",
                    "valuation_cap",
                    "discount_pct",
                    "interest_rate_pct",
                    "capitalization_basis",
                    "conversion_trigger",
                    "minimum_financing_amount",
                    "issue_date",
                ]
                outstanding_show = outstanding[[c for c in outstanding_cols if c in outstanding.columns]].copy()
                outstanding_show = format_money_columns(
                    outstanding_show,
                    ["amount_invested", "principal_invested", "valuation_cap", "minimum_financing_amount"],
                )
                st.dataframe(outstanding_show, use_container_width=True)

        if st.button("Apply funding round"):
            clean_round_name, valid_investors, errors = validate_round_inputs(
                round_type=round_type,
                round_name=round_name,
                investors=investors,
                pre_money_valuation=pre_money_valuation,
                valuation_cap=valuation_cap,
                discount_pct=discount_pct,
            )

            updated_cap_table = st.session_state.cap_table.copy()

            if round_type == "Equity":
                pre_round_shares = pd.to_numeric(updated_cap_table["shares"], errors="coerce").fillna(0.0).sum()
                if pre_money_fd_shares_override > 0:
                    pre_round_shares = pre_money_fd_shares_override
                if pre_round_shares <= 0:
                    errors.append("Need at least one existing share before applying an equity round.")

            if errors:
                for err in errors:
                    st.error(err)
            else:
                round_row = pd.DataFrame(
                    [{
                        "round_type": round_type,
                        "round_name": clean_round_name,
                        "round_date": date_to_str(round_date),
                        "pre_money_valuation": pre_money_valuation,
                        "amount_raised": sum(inv["amount"] for inv in valid_investors),
                        "valuation_cap": valuation_cap,
                        "discount_pct": discount_pct,
                        "interest_rate_pct": interest_rate_pct,
                        "issue_date": date_to_str(issue_date),
                        "maturity_date": date_to_str(maturity_date),
                        "liq_pref_multiple": liq_pref_multiple,
                        "participating": participating,
                        "participation_cap_multiple": participation_cap_multiple,
                        "price_per_share_override": price_per_share_override if round_type == "Equity" else None,
                        "minimum_financing_amount": minimum_financing_amount,
                        "option_pool_timing": option_pool_timing if round_type == "Equity" else None,
                        "pre_money_fd_shares_override": pre_money_fd_shares_override if round_type == "Equity" else None,
                    }]
                )
                st.session_state.round_history = pd.concat(
                    [st.session_state.round_history, round_row], ignore_index=True
                )

                if round_type == "Equity":
                    round_price = float(price_per_share_override) if price_per_share_override > 0 else float(pre_money_valuation) / float(pre_round_shares)

                    preferred_rows = []
                    for inv in valid_investors:
                        shares_issued = float(inv["amount"]) / float(round_price)
                        preferred_rows.append(
                            {
                                "holder": inv["investor_name"],
                                "security_type": "Preferred",
                                "class": clean_round_name,
                                "shares": shares_issued,
                                "issue_date": date_to_str(round_date),
                            }
                        )

                    convertible_rows, financing_updated, conversion_summary = build_conversion_rows(
                        st.session_state.financing_details,
                        updated_cap_table,
                        clean_round_name,
                        round_date,
                        round_price,
                        pre_round_shares,
                        total_new_money=sum(inv["amount"] for inv in valid_investors),
                        minimum_financing_amount=minimum_financing_amount,
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
                    for inv in valid_investors:
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
                                "safe_type": None,
                                "capitalization_basis": None,
                                "interest_method": None,
                                "interest_compounding_frequency": None,
                                "converts_accrued_interest": None,
                                "conversion_trigger": None,
                                "minimum_financing_amount": None,
                                "shadow_preferred": None,
                                "converted_in_round": None,
                                "converted_on_date": None,
                                "conversion_amount": None,
                                "conversion_price": round_price,
                                "conversion_price_source": "round_price",
                                "cap_price": None,
                                "discount_price": None,
                                "round_price_at_conversion": round_price,
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
                        money_cols = [
                            "minimum_financing_amount",
                            "conversion_amount",
                            "accrued_interest",
                            "cap_price",
                            "discount_price",
                            "round_price",
                            "conversion_price",
                        ]
                        for col in money_cols:
                            if col in show_conv.columns:
                                show_conv[col] = show_conv[col].apply(
                                    lambda x: f"${x:,.4f}" if pd.notnull(x) else ""
                                )
                        show_conv = format_share_columns(show_conv, ["cap_basis_shares", "shares_issued"])
                        st.dataframe(show_conv, use_container_width=True)

                elif round_type == "SAFE":
                    safe_rows = []
                    for inv in valid_investors:
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
                                "safe_type": safe_type,
                                "capitalization_basis": capitalization_basis,
                                "interest_method": None,
                                "interest_compounding_frequency": None,
                                "converts_accrued_interest": None,
                                "conversion_trigger": conversion_trigger,
                                "minimum_financing_amount": minimum_financing_amount,
                                "shadow_preferred": shadow_preferred,
                                "converted_in_round": None,
                                "converted_on_date": None,
                                "conversion_amount": None,
                                "conversion_price": None,
                                "conversion_price_source": None,
                                "cap_price": None,
                                "discount_price": None,
                                "round_price_at_conversion": None,
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
                    for inv in valid_investors:
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
                                "safe_type": None,
                                "capitalization_basis": capitalization_basis,
                                "interest_method": interest_method,
                                "interest_compounding_frequency": interest_compounding_frequency,
                                "converts_accrued_interest": converts_accrued_interest,
                                "conversion_trigger": conversion_trigger,
                                "minimum_financing_amount": minimum_financing_amount,
                                "shadow_preferred": shadow_preferred,
                                "converted_in_round": None,
                                "converted_on_date": None,
                                "conversion_amount": None,
                                "conversion_price": None,
                                "conversion_price_source": None,
                                "cap_price": None,
                                "discount_price": None,
                                "round_price_at_conversion": None,
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
        show = format_share_columns(show, ["shares"])
        show["ownership_pct"] = show["ownership_pct"].map(lambda x: f"{x:.2%}")
        st.dataframe(show, use_container_width=True)

    st.subheader("Round history")
    if st.session_state.round_history.empty:
        st.info("No rounds added yet.")
    else:
        history_show = st.session_state.round_history.copy()
        history_show = format_money_columns(
            history_show,
            ["pre_money_valuation", "amount_raised", "valuation_cap", "price_per_share_override", "minimum_financing_amount"],
        )
        st.dataframe(history_show, use_container_width=True)

    st.subheader("Financing details")
    if st.session_state.financing_details.empty:
        st.info("No SAFE, note, or equity financing detail yet.")
    else:
        details_show = st.session_state.financing_details.copy()
        details_show = format_money_columns(
            details_show,
            [
                "amount_invested",
                "principal_invested",
                "valuation_cap",
                "minimum_financing_amount",
                "conversion_amount",
                "cap_price",
                "discount_price",
                "conversion_price",
                "round_price_at_conversion",
            ],
        )
        details_show = format_share_columns(details_show, ["shares_issued"])
        st.dataframe(details_show, use_container_width=True)

with tab4:
    st.subheader("Exit sensitivity analysis")
    st.caption(
        "This prototype now includes a simplified liquidation waterfall using stored equity terms. It still uses planning assumptions, excludes the unallocated option pool from direct proceeds, and should not be treated as legal-grade modeling."
    )

    current = recalc_ownership(st.session_state.cap_table)

    if current.empty:
        st.info("Add a cap table first before running exit analysis.")
    else:
        col1, col2 = st.columns(2)
        low_exit = parse_numeric(
            col1.text_input(
                "Low exit value ($)",
                value=st.session_state.get("low_exit_value", "10,000,000"),
                key="low_exit_value",
                help="You can type values with commas.",
            )
        )
        high_exit = parse_numeric(
            col2.text_input(
                "High exit value ($)",
                value=st.session_state.get("high_exit_value", "200,000,000"),
                key="high_exit_value",
                help="You can type values with commas.",
            )
        )

        preview_exit = parse_numeric(
            st.text_input(
                "Single exit value preview ($)",
                value=st.session_state.get("preview_exit_value", "50,000,000"),
                key="preview_exit_value",
                help="You can type values with commas.",
            )
        )

        if st.button("Run exit sensitivity"):
            exit_values = build_exit_scenarios(low_exit, high_exit, num_points=8)

            if not exit_values:
                st.error("Please enter a valid low and high exit value.")
            else:
                sensitivity_df = build_exit_sensitivity_table(
                    st.session_state.cap_table,
                    st.session_state.round_history,
                    st.session_state.financing_details,
                    exit_values,
                )

                display_df = sensitivity_df.copy()
                display_df = format_share_columns(display_df, ["shares"])
                if "ownership_pct_ex_option_pool" in display_df.columns:
                    display_df["ownership_pct_ex_option_pool"] = display_df["ownership_pct_ex_option_pool"].map(
                        lambda x: f"{x:.2%}"
                    )

                dollar_cols = [c for c in display_df.columns if c.startswith("$")]
                for col in dollar_cols:
                    display_df[col] = display_df[col].map(lambda x: f"${x:,.2f}")

                scenario_labels = [f"${v:,.0f}" for v in exit_values]
                st.write(f"Scenarios used: {', '.join(scenario_labels)}")
                st.write("### Exit proceeds by holder")
                st.dataframe(display_df, use_container_width=True)

                preview_holder_df, preview_class_df = build_waterfall_for_exit(
                    st.session_state.cap_table,
                    st.session_state.round_history,
                    st.session_state.financing_details,
                    preview_exit,
                )

                st.write(f"### Waterfall preview at ${preview_exit:,.0f}")

                if not preview_class_df.empty:
                    preview_class_show = preview_class_df.copy()
                    preview_class_show = format_money_columns(
                        preview_class_show,
                        [
                            "original_investment",
                            "as_converted_value",
                            "pref_claim",
                            "pref_allocated",
                            "residual_allocated",
                            "total_payout",
                        ],
                    )
                    st.write("Preferred class summary")
                    st.dataframe(preview_class_show, use_container_width=True)
                else:
                    st.info("No preferred equity classes with stored liquidation terms yet. Preview is effectively common-only.")

                if not preview_holder_df.empty:
                    preview_holder_show = preview_holder_df.copy()
                    preview_holder_show = format_share_columns(preview_holder_show, ["shares"])
                    preview_holder_show = format_money_columns(preview_holder_show, ["exit_proceeds"])
                    st.write("Holder proceeds at preview exit value")
                    st.dataframe(preview_holder_show, use_container_width=True)

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

                pool_mask = st.session_state.cap_table["holder"] == "Option Pool Reserve"
                pending_updates = st.session_state.get("_pending_widget_state_updates", {})
                if pool_mask.any():
                    pending_updates["option_pool_shares"] = format_number_for_input(
                        pd.to_numeric(
                            st.session_state.cap_table.loc[pool_mask, "shares"],
                            errors="coerce"
                        ).fillna(0.0).sum()
                    )
                    pool_dates = st.session_state.cap_table.loc[pool_mask, "issue_date"].dropna().astype(str)
                    if not pool_dates.empty:
                        pending_updates["option_pool_issue_date"] = str_to_date(pool_dates.iloc[-1]) or date.today()
                else:
                    pending_updates["option_pool_shares"] = "0"
                    pending_updates["option_pool_issue_date"] = date.today()
                st.session_state["_pending_widget_state_updates"] = pending_updates

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
