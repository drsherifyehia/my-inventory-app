import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io

st.set_page_config(page_title="Inventory Manager", layout="wide")

# --- 1. Memory Setup ---
if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame()
if 'amu_mapping' not in st.session_state:
    st.session_state.amu_mapping = {}

# --- 2. Smart Column Fixer ---
def auto_fix_columns(df):
    df.columns = [str(c).strip() for c in df.columns]
    mapping = {
        'Item name': ['item', 'name', 'product', 'description'],
        'Date created': ['date', 'created', 'time', 'timestamp'],
        'Amount': ['amount', 'qty', 'quantity', 'distributed'],
        'Branch amount': ['branch', 'store', 'branch amount', 'branch qty'],
        'Master amount': ['master', 'warehouse', 'main', 'master amount', 'master qty'],
        'Item price': ['price', 'cost', 'rate']
    }
    new_cols = {}
    for standard, variations in mapping.items():
        for col in df.columns:
            if any(v in col.lower() for v in variations) and standard not in new_cols.values():
                new_cols[col] = standard
    return df.rename(columns=new_cols)

st.title("📦 Inventory & Monthly Shopping")

# --- 3. Create Tabs ---
tab1, tab2, tab3 = st.tabs(["📊 Usage Calc", "📦 Inventory Items", "🛒 Shopping List"])

# ==========================================
# TAB 1: USAGE CALCULATION
# ==========================================
with tab1:
    st.header("1. Calculate Usage")
    with st.expander("➕ Add Usage Entry Manually"):
        with st.form("u_form"):
            un = st.text_input("Item Name")
            ua = st.number_input("Amount", 0)
            if st.form_submit_button("Add"):
                st.success(f"Added {ua} for {un}")

    f1 = st.file_uploader("Upload Distribution Sheet", type=['xlsx'], key="f1")
    if f1:
        df1 = auto_fix_columns(pd.read_excel(f1))
        if 'Item name' in df1.columns and 'Date created' in df1.columns:
            df1['Date created'] = pd.to_datetime(df1['Date created'], errors='coerce')
            res = df1.groupby('Item name').agg({'Amount':'sum', 'Date created':'min'}).reset_index()
            days = (datetime.now() - res['Date created']).dt.days / 30.44
            res['AMU'] = (res['Amount'] / np.maximum(1, days)).round(2)
            st.session_state.amu_mapping = res.set_index('Item name')['AMU'].to_dict()
            st.success("Averages Calculated!")
            st.dataframe(res[['Item name', 'AMU']])
        else:
            st.error("File needs 'Item Name' and 'Date' columns.")

# ==========================================
# TAB 2: INVENTORY ITEMS
# ==========================================
with tab2:
    st.header("2. Current Stock")
    with st.expander("➕ Add Item Manually"):
        with st.form("inv_form"):
            n = st.text_input("Item Name")
            b = st.number_input("Branch Qty", 0)
            m = st.number_input("Master Qty", 0)
            p = st.number_input("Price", 0.0)
            if st.form_submit_button("Save"):
                amu = st.session_state.amu_mapping.get(n, 0.0)
                row = pd.DataFrame([{'Item name': n, 'Branch amount': b, 'Master amount': m, 'Average monthly usage': amu, 'Item price': p, 'Order_Month': datetime.now().strftime('%B %Y')}])
                st.session_state.master_df = pd.concat([st.session_state.master_df, row], ignore_index=True)
                st.rerun()

    f2 = st.file_uploader("Upload Inventory Sheet", type=['xlsx'], key="f2")
    if f2:
        df2 = auto_fix_columns(pd.read_excel(f2))
        for col in ['Branch amount', 'Master amount', 'Item price']:
            if col in df2.columns:
                df2[col] = pd.to_numeric(df2[col], errors='coerce').fillna(0)
        df2['Average monthly usage'] = df2['Item name'].map(st.session_state.amu_mapping).fillna(0)
        if 'Order_Month' not in df2.columns:
            df2['Order_Month'] = datetime.now().strftime('%B %Y')
        st.session_state.master_df = df2
        st.success("Inventory Loaded!")
    
    st.dataframe(st.session_state.master_df, use_container_width=True)

# ==========================================
# TAB 3: SHOPPING LIST (MONTHLY VIEW)
# ==========================================
with tab3:
    st.header("3. Monthly Shopping List")
    if not st.session_state.master_df.empty:
        df = st.session_state.master_df.copy()
        
        # Calculate Costs
        df['Monthly Cost'] = (df['Average monthly usage'] * df['Item price']).round(2)
        
        # Filter: Only show what needs to be bought (Master is 0)
        to_buy = df[df['Master amount'] <= 0].copy()
        
        if not to_buy.empty:
            for month in sorted(to_buy['Order_Month'].unique().astype(str)):
                st.subheader(f"📅 {month}")
                m_df = to_buy[to_buy['Order_Month'] == month]
                st.dataframe(m_df[['Item name', 'Branch amount', 'Master amount', 'Item price', 'Monthly Cost']], use_container_width=True)
                st.metric(f"Total for {month}", f"${m_df['Monthly Cost'].sum():,.2f}")
                st.divider()
        else:
            st.info("Everything is in stock! Nothing to buy.")

        # Tools
        st.write("### ⚙️ Actions")
        target = st.selectbox("Select Item", df['Item name'].unique())
        c1, c2 = st.columns(2)
        if c1.button("❌ Remove Item"):
            st.session_state.master_df = st.session_state.master_df[st.session_state.master_df['Item name'] != target]
            st.rerun()
        
        new_m = st.selectbox("Move to Month", ["March 2026", "April 2026", "May 2026", "June 2026"])
        if c2.button("📅 Move Month"):
            st.session_state.master_df.loc[st.session_state.master_df['Item name'] == target, 'Order_Month'] = new_m
            st.rerun()
            
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download All", csv, "inventory.csv", "text/csv")
    else:
        st.info("No data in Inventory Items.")
