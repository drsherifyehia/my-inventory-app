import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io

st.set_page_config(page_title="Inventory Manager", layout="wide")

# --- Initialize Memory ---
if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame(columns=['Item name', 'Item Type', 'Branch amount', 'Master amount', 'Average monthly usage', 'Item price', 'Order_Month'])
if 'amu_mapping' not in st.session_state:
    st.session_state.amu_mapping = {}

# --- Smart Column Cleaner ---
def auto_fix_columns(df):
    """Automatically finds and renames columns regardless of spelling/case."""
    df.columns = [str(c).strip() for c in df.columns]
    cols = df.columns
    
    mapping = {
        'Item name': ['item', 'name', 'product', 'description', 'item name'],
        'Date created': ['date', 'created', 'time', 'timestamp', 'date created'],
        'Amount': ['amount', 'qty', 'quantity', 'total distributed'],
        'Branch amount': ['branch', 'branch qty', 'store', 'branch amount'],
        'Master amount': ['master', 'warehouse', 'main', 'master amount'],
        'Item price': ['price', 'cost', 'rate', 'item price']
    }
    
    new_cols = {}
    for standard, variations in mapping.items():
        for col in cols:
            if any(v in col.lower() for v in variations):
                if standard not in new_cols.values(): # Don't overwrite if found
                    new_cols[col] = standard
    
    return df.rename(columns=new_cols)

st.title("📦 Inventory Manager")

tab1, tab2, tab3 = st.tabs(["📊 Usage Calc", "📦 Inventory Items", "🛒 Shopping List"])

# --- TAB 1: USAGE ---
with tab1:
    st.header("Step 1: Calculate Usage")
    f1 = st.file_uploader("Upload Distribution Sheet", type=['xlsx'], key="f1")
    if f1:
        df1 = auto_fix_columns(pd.read_excel(f1))
        if 'Item name' in df1.columns and 'Date created' in df1.columns:
            df1['Date created'] = pd.to_datetime(df1['Date created'], errors='coerce')
            res = df1.groupby('Item name').agg({'Amount':'sum', 'Date created':'min'}).reset_index()
            # Calculate AMU
            days = (datetime.now() - res['Date created']).dt.days / 30.44
            res['AMU'] = (res['Amount'] / np.maximum(1, days)).round(2)
            st.session_state.amu_mapping = res.set_index('Item name')['AMU'].to_dict()
            st.success("Averages Calculated!")
            st.dataframe(res[['Item name', 'AMU']])
        else:
            st.error("Could not find 'Item Name' or 'Date' columns in this file.")

# --- TAB 2: INVENTORY ---
with tab2:
    st.header("Step 2: Current Stock")
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
        # Logic to ensure "Item name" exists before mapping
        if 'Item name' in df2.columns:
            df2['Average monthly usage'] = df2['Item name'].map(st.session_state.amu_mapping).fillna(0)
            st.session_state.master_df = df2
            st.success("Inventory Loaded!")
        else:
            st.error("This file is missing a column for 'Item Name'.")
    
    st.dataframe(st.session_state.master_df)

# --- TAB 3: SHOPPING LIST ---
with tab3:
    st.header("Step 3: Shopping List")
    if not st.session_state.master_df.empty:
        df = st.session_state.master_df.copy()
        
        # Actions
        target = st.selectbox("Select Item", df['Item name'].tolist())
        c1, c2 = st.columns(2)
        if c1.button("❌ Remove"):
            st.session_state.master_df = st.session_state.master_df[st.session_state.master_df['Item name'] != target]
            st.rerun()
        if c2.button("📅 Move Month"):
            st.session_state.master_df.loc[st.session_state.master_df['Item name'] == target, 'Order_Month'] = "Next Month"
            st.rerun()

        # Visuals
        def color(row):
            if row['Master amount'] <= 0 and row['Branch amount'] <= 0: return ['background-color: #ff4b4b']*len(row)
            if row['Master amount'] <= 0 and row['Branch amount'] > 0: return ['background-color: #f1c40f']*len(row)
            return ['']*len(row)

        st.dataframe(df.style.apply(color, axis=1))
        
        # Download
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download List", csv, "list.csv", "text/csv")
    else:
        st.info("No data yet.")
