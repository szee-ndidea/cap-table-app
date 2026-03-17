import io
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Cap Table App", layout="wide")

st.title("Cap Table App")
st.caption("Simple starting cap table + next funding round")

if "cap_table" not in st.session_state:
    st.session_state.cap_table = pd.DataFrame(
        columns=["holder", "security_type", "class", "shares"]
    )

if "round_history" not in st.session_state:
    st.session_state.round_history = pd.DataFrame(
        columns=[
            "round_type",
            "round_name",
            "pre_money_valuation",
            "amount_raised",
            "valuation_cap",
            "discount_pct",
            "interest_rate_pct",
            "maturity_date",
        ]
    )

def recalc_ownership(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        out["ownership_pct"] = []
        return out
    total = out["shares"].sum()
    out["ownership_pct"] = out["shares"] / total if total > 0 else 0
    return out

def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")

tab1, tab2, tab3, tab4 = st.tabs(
    ["Starting Cap Table", "Next Round", "Current Cap Table", "Downloads"]
)

with tab1:
    st.subheader("Build starting cap table")

    with st.form("add_holder_form", clear_on_submit=True):
        col1, col2, col3, col4 = st.columns(4)
        holder = col1.text_input("Holder name")
        security_type = col2.selectbox("Security type", ["Common", "Preferred", "Option Pool"])
        class_name = col3.text_input("Class", value="Common")
        shares = col4.number_input("Shares", min_value=0.0, step=1.0)
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

        if st.button("Clear starting cap table"):
            st.session_state.cap_table = pd.DataFrame(
                columns=["holder", "security_type", "class", "shares"]
            )
            st.rerun()

with tab2:
    st.subheader("Add next funding round")

    if st.session_state.cap_table.empty:
        st.info("Add at least one starting cap table row first.")
    else:
        round_type = st.selectbox("Round type", ["Equity", "SAFE", "Convertible Note"])
        round_name = st.text_input("Round name / label", value="")
        pre_money_valuation = None
        valuation_cap = None
        discount_pct = None
        interest_rate_pct = None
        maturity_date = None

        if round_type == "Equity":
            pre_money_valuation = st.number_input("Pre-money valuation", min_value=0.0, step=1000.0)
        elif round_type == "SAFE":
            valuation_cap = st.number_input("Valuation cap", min_value=0.0, step=1000.0)
            discount_pct = st.number_input("Discount %", min_value=0.0, max_value=100.0, step=0.5)
        else:
            valuation_cap = st.number_input("Valuation cap", min_value=0.0, step=1000.0)
            discount_pct = st.number_input("Discount %", min_value=0.0, max_value=100.0, step=0.5)
            interest_rate_pct = st.number_input("Interest rate %", min_value=0.0, max_value=100.0, step=0.5)
            maturity_date = st.text_input("Maturity date")

        st.markdown("### Investor entries")
        investor_count = st.number_input("Number of investors in this round", min_value=1, step=1, value=1)

        investors = []
        total_raised = 0.0

        for i in range(int(investor_count)):
            st.markdown(f"**Investor {i+1}**")
            c1, c2 = st.columns(2)
            investor_name = c1.text_input(f"Investor name {i+1}", key=f"inv_name_{i}")
            amount = c2.number_input(f"Amount invested {i+1}", min_value=0.0, step=1000.0, key=f"inv_amt_{i}")
            investors.append({"investor_name": investor_name.strip(), "amount": amount})
            total_raised += amount

        st.write(f"Total raised: **${total_raised:,.2f}**")

        new_common = st.number_input("New common shares issued outside the round", min_value=0.0, step=1.0, value=0.0)
        new_option_pool = st.number_input("Option pool increase", min_value=0.0, step=1.0, value=0.0)

        if st.button("Apply next round"):
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
                st.success(f"{round_type} round stored in round history. Cap table only changed for any common or option updates.")

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
        st.dataframe(st.session_state.round_history, use_container_width=True)

with tab4:
    st.subheader("Download files")

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
