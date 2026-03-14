import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="Inventory Manager", layout="wide")

# --- 1. Memory Setup ---
if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame()
if 'amu_mapping' not in st.session_state:
    st.session_state.amu_mapping = {}
if 'price_mapping' not in st.session_state:
    st.session_state.price_mapping = {}

current_date = datetime.now()
month_options = [(current_date + timedelta(days=30*i)).strftime('%B %Y') for i in range(4)]

# --- 2. Smart Column Fixer ---
def auto_fix_columns(df):
    df.columns = [str(c).strip() for c in df.columns]
    mapping = {
        'Item name': ['item', 'name', 'product', 'description'],
        'Item Type': ['type', 'category', 'group', 'item type'],
        'Date created': ['date', 'created', 'time', 'timestamp'],
        'Amount': ['amount', 'qty', 'quantity', 'distributed'],
        'Branch amount': ['branch', 'store', 'branch amount'],
        'Master amount': ['master', 'warehouse', 'main stock'],
        'Item price': ['price', 'cost', 'rate', 'unit price']
    }
    new_cols = {}
    for standard, variations in mapping.items():
        for col in df.columns:
            if any(v in col.lower() for v in variations) and standard not in new_cols.values():
                new_cols[col] = standard
    return df.rename(columns=new_cols)

st.title("📦 Inventory & Monthly Shopping")

tab1, tab2, tab3 = st.tabs(["📊 Usage & Price Calc", "📦 Inventory Items", "🛒 Shopping List"])

# ==========================================
# TAB 1: USAGE & PRICE CALCULATION
# ==========================================
with tab1:
    st.header("1. Calculate Usage & Extract Prices")
    
    with st.expander("➕ Add Usage/Price Manually"):
        with st.form("manual_usage_form"):
            m_name = st.text_input("Item Name")
            m_price = st.number_input("Unit Price", min_value=0.0, step=0.01)
            m_amu = st.number_input("Average Monthly Usage", min_value=0.0, step=0.1)
            if st.form_submit_button("Save Reference Data"):
                if m_name:
                    st.session_state.amu_mapping[m_name] = m_amu
                    st.session_state.price_mapping[m_name] = m_price
                    st.success(f"Saved: {m_name}")
                    st.rerun()

    # --- NEW: LIST VIEW FOR MANUAL ENTRIES IN TAB 1 ---
    if st.session_state.amu_mapping or st.session_state.price_mapping:
        st.write("### 📝 Manually Added Reference Items")
        ref_data = []
        all_items = set(list(st.session_state.amu_mapping.keys()) + list(st.session_state.price_mapping.keys()))
        for item in sorted(all_items):
            ref_data.append({
                "Item Name": item,
                "Price": st.session_state.price_mapping.get(item, 0.0),
                "AMU": st.session_state.amu_mapping.get(item, 0.0)
            })
        ref_df = pd.DataFrame(ref_data)
        
        # Display list with a delete option for reference data
        for i, row in ref_df.iterrows():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
            col1.write(row["Item Name"])
            col2.write(f"${row['Price']}")
            col3.write(f"Usage: {row['AMU']}")
            if col4.button("🗑️", key=f"del_ref_{i}"):
                st.session_state.amu_mapping.pop(row["Item Name"], None)
                st.session_state.price_mapping.pop(row["Item Name"], None)
                st.rerun()

    st.divider()
    f1 = st.file_uploader("Upload Distribution Sheet (Excel)", type=['xlsx'], key="f1")
    if f1:
        df1 = auto_fix_columns(pd.read_excel(f1))
        if 'Item name' in df1.columns:
            if 'Date created' in df1.columns and 'Amount' in df1.columns:
                df1['Date created'] = pd.to_datetime(df1['Date created'], errors='coerce')
                res = df1.groupby('Item name').agg({'Amount':'sum', 'Date created':'min'}).reset_index()
                days = (datetime.now() - res['Date created']).dt.days / 30.44
                res['AMU'] = (res['Amount'] / np.maximum(1, days)).round(2)
                st.session_state.amu_mapping.update(res.set_index('Item name')['AMU'].to_dict())
            if 'Item price' in df1.columns:
                price_df = df1.dropna(subset=['Item price']).drop_duplicates('Item name', keep='last')
                st.session_state.price_mapping.update(price_df.set_index('Item name')['Item price'].to_dict())
                st.success("Data merged from Excel!")

# ==========================================
# TAB 2: INVENTORY ITEMS
# ==========================================
with tab2:
    st.header("2. Current Stock")
    with st.expander("➕ Add Item to Inventory Manually"):
        with st.form("inv_form"):
            n = st.text_input("Item Name")
            t = st.text_input("Item Type")
            b = st.number_input("Branch Qty", 0)
            m = st.number_input("Master Qty", 0)
            default_p = st.session_state.price_mapping.get(n, 0.0)
            p = st.number_input("Price", value=float(default_p))
            
            if st.form_submit_button("Save to Inventory"):
                final_amu = st.session_state.amu_mapping.get(n, 0.0)
                row = pd.DataFrame([{'Item name': n, 'Item Type': t, 'Branch amount': b, 'Master amount': m, 
                                     'Average monthly usage': final_amu, 'Item price': p, 'Order_Month': month_options[0]}])
                st.session_state.master_df = pd.concat([st.session_state.master_df, row], ignore_index=True)
                st.rerun()

    f2 = st.file_uploader("Upload Inventory Sheet", type=['xlsx'], key="f2")
    if f2:
        df2 = auto_fix_columns(pd.read_excel(f2))
        df2['Average monthly usage'] = df2['Item name'].map(st.session_state.amu_mapping).fillna(0)
        if 'Item price' not in df2.columns or df2['Item price'].isnull().all():
            df2['Item price'] = df2['Item name'].map(st.session_state.price_mapping).fillna(0)
        if 'Order_Month' not in df2.columns:
            df2['Order_Month'] = month_options[0]
        st.session_state.master_df = df2
        st.success("Inventory Loaded!")
    
    # --- NEW: MASTER LIST WITH INDIVIDUAL REMOVE BUTTONS ---
    st.write("### Master Inventory List")
    if not st.session_state.master_df.empty:
        for i, row in st.session_state.master_df.iterrows():
            c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 1])
            c1.write
