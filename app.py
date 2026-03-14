import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io

st.set_page_config(page_title="Inventory Manager", layout="wide")

# --- Memory Setup ---
if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame()
if 'amu_mapping' not in st.session_state:
    st.session_state.amu_mapping = {}

# --- Smart Column Cleaner ---
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

st.title("📦 Inventory Manager")

tab1, tab2, tab3 = st.tabs(["📊 Usage Calc", "📦 Inventory Items", "🛒 Shopping List"])

# --- TAB 1: USAGE ---
with tab1:
    st.header("1. Calculate Usage")
    f1 = st.file_uploader("Upload Distribution Sheet", type=['xlsx'], key="f1")
    if f1:
        df1 = auto_fix_columns(pd.read_excel(f1))
        if 'Item name' in df1.columns and 'Date created' in df1.columns:
            df1['Date created'] = pd.to_datetime(df1['Date created'], errors='coerce')
            res = df1.groupby('Item name').agg({'Amount':'sum', 'Date created':'min'}).reset_index()
            days = (datetime.now() - res['Date created']).dt.days / 30.44
            res['AMU'] = (res['Amount'] / np.maximum(1, days)).round(2)
            st.session_state.amu_mapping = res.set_index('Item name')['AMU'].to_dict()
            st.success("Usage Calculated!")
            st.dataframe(res[['Item name', 'AMU']])
        else:
            st.error("Missing columns: Ensure 'Item Name' and 'Date' are in the file.")

# --- TAB 2: INVENTORY ---
with tab2:
    st.header("2. Current Stock")
    with st.expander("➕ Add Manually"):
        with st.form("manual"):
            n = st.text_input("Name")
            b = st.number_input("Branch Qty", 0)
            m = st.number_input("Master Qty", 0)
            p = st.number_input("Price", 0.0)
            if st.form_submit_button("Save"):
                row = pd.DataFrame([{'Item name': n, 'Branch amount': b, 'Master amount': m, 'Average monthly usage': st.session_state.amu_mapping.get(n, 0), 'Item price': p, 'Order_Month': datetime.now().strftime('%B %Y')}])
                st.session_state.master_df = pd.concat([st.session_state.master_df, row], ignore_index=True)
                st.rerun()

    f2 = st.file_uploader("Upload Inventory Sheet", type=['xlsx'], key="f2")
    if f2:
        df2 = auto_fix_columns(pd.read_excel(f2))
        if 'Item name' in df2.columns:
            # Ensure amounts are numeric to prevent crashes
            for col in ['Branch amount', 'Master amount', 'Item price']:
                if col in df2.columns:
                    df2[col] = pd.to_numeric(df2[col], errors='coerce').fillna(0)
            
            df2['Average monthly usage'] = df2['Item name'].map(st.session_state.amu_mapping).fillna(0)
            st.session_state.master_df = df2
            st.success("Inventory Loaded!")
        else:
            st.error("Missing 'Item Name' column.")
    
    st.dataframe(st.session_state.master_df)

# --- TAB 3: SHOPPING LIST ---
with tab3:
    st.header("3. Shopping List")
    if not st.session_state.master_df.empty:
        df = st.session_state.master_df.copy()
        
        # Cleanup data for visual logic
        df['Master amount'] = pd.to_numeric(df['Master amount'], errors='coerce').fillna(0)
        df['Branch amount'] = pd.to_numeric(df['Branch amount'], errors='coerce').fillna(0)
        
        # Selection
        target = st.selectbox("Select Item", df['Item name'].unique())
        c1, c2 = st.columns(2)
        if c1.button("❌ Remove"):
            st.session_state.master_df = st.session_state.master_df[st.session_state.master_df['Item name'] != target]
            st.rerun()
        if c2.button("📅 Move Month"):
            st.session_state.master_df.loc[st.session_state.master_df['Item name'] == target, 'Order_Month'] = "Next Month"
            st.rerun()

        # Color Logic Fix
        def color_logic(row):
            m = row['Master amount']
            b = row['Branch amount']
            if m <= 0 and b <= 0: return ['background-color: #ff4b4b; color: white'] * len(row)
            if m <= 0 and b > 0: return ['background-color: #f1c40f; color: black'] * len(row)
            return [''] * len(row)

        st.dataframe(df.style.apply(color_logic, axis=1), use_container_width=True)
        
        # Simple Download
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download List", csv, "inventory_list.csv", "text/csv")
    else:
        st.info("Inventory is empty. Add items or upload a file in Tab 2.")
