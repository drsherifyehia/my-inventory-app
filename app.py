import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="Inventory Manager", layout="wide")

# --- 1. Memory & Date Setup ---
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
    f1 = st.file_uploader("Upload Distribution Sheet (with Prices)", type=['xlsx'], key="f1")
    if f1:
        df1 = auto_fix_columns(pd.read_excel(f1))
        if 'Item name' in df1.columns:
            # Calculate Usage (AMU)
            if 'Date created' in df1.columns and 'Amount' in df1.columns:
                df1['Date created'] = pd.to_datetime(df1['Date created'], errors='coerce')
                res = df1.groupby('Item name').agg({'Amount':'sum', 'Date created':'min'}).reset_index()
                days = (datetime.now() - res['Date created']).dt.days / 30.44
                res['AMU'] = (res['Amount'] / np.maximum(1, days)).round(2)
                st.session_state.amu_mapping = res.set_index('Item name')['AMU'].to_dict()
            
            # Extract Prices
            if 'Item price' in df1.columns:
                price_df = df1.dropna(subset=['Item price']).drop_duplicates('Item name', keep='last')
                st.session_state.price_mapping = price_df.set_index('Item name')['Item price'].to_dict()
                st.success("Prices and Usage extracted from Tab 1!")

# ==========================================
# TAB 2: INVENTORY ITEMS
# ==========================================
with tab2:
    st.header("2. Current Stock")
    with st.expander("➕ Add Item Manually"):
        with st.form("inv_form"):
            n = st.text_input("Item Name")
            t = st.text_input("Item Type")
            b = st.number_input("Branch Qty", 0)
            m = st.number_input("Master Qty", 0)
            default_p = st.session_state.price_mapping.get(n, 0.0)
            p = st.number_input("Price", value=float(default_p))
            test_amu = st.number_input("Average Monthly Usage", 0.0)
            target_m = st.selectbox("Assign to Purchase Month:", month_options)
            
            if st.form_submit_button("Save Item"):
                final_amu = test_amu if test_amu > 0 else st.session_state.amu_mapping.get(n, 0.0)
                row = pd.DataFrame([{'Item name': n, 'Item Type': t, 'Branch amount': b, 'Master amount': m, 
                                     'Average monthly usage': final_amu, 'Item price': p, 'Order_Month': target_m}])
                st.session_state.master_df = pd.concat([st.session_state.master_df, row], ignore_index=True)
                st.rerun()

    f2 = st.file_uploader("Upload Inventory Sheet", type=['xlsx'], key="f2")
    if f2:
        df2 = auto_fix_columns(pd.read_excel(f2))
        # Logic to merge Price and AMU from Tab 1
        df2['Average monthly usage'] = df2['Item name'].map(st.session_state.amu_mapping).fillna(0)
        if 'Item price' not in df2.columns or df2['Item price'].isnull().all():
            df2['Item price'] = df2['Item name'].map(st.session_state.price_mapping).fillna(0)
        if 'Order_Month' not in df2.columns:
            df2['Order_Month'] = month_options[0]
            
        st.session_state.master_df = df2
        st.success("Inventory Loaded with Tab 1 Data!")
    
    st.write("### Master Inventory List")
    st.dataframe(st.session_state.master_df, use_container_width=True)

# ==========================================
# TAB 3: SHOPPING LIST
# ==========================================
with tab3:
    st.header("3. Monthly Shopping List")
    if not st.session_state.master_df.empty:
        df = st.session_state.master_df.copy()
        
        # SAFETY FIX: Ensure all numeric columns are actually numbers to prevent crashes
        for col in ['Master amount', 'Branch amount', 'Item price', 'Average monthly usage']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        df['Monthly Cost'] = (df['Average monthly usage'] * df['Item price']).round(2)
        
        col_f1, col_f2 = st.columns([2, 1])
        with col_f1:
            all_types = sorted(df['Item Type'].unique().astype(str))
            selected_types = st.multiselect("🏷️ Filter by Type", options=all_types, default=all_types)
        with col_f2:
            view_month = st.selectbox("📅 View Shopping List For:", month_options)

        # Apply logic for out of stock items
        mask = (df['Master amount'] <= 0) & \
               (df['Item Type'].astype(str).isin(selected_types)) & \
               (df['Order_Month'] == view_month)
        
        shopping_df = df[mask].copy()

        def apply_status_color(row):
            if row['Master amount'] <= 0 and row['Branch amount'] <= 0:
                return ['background-color: #ff4b4b; color: white'] * len(row)
            if row['Master amount'] <= 0 and row['Branch amount'] > 0:
                return ['background-color: #f1c40f; color: black'] * len(row)
            return [''] * len(row)

        if not shopping_df.empty:
            st.dataframe(shopping_df.style.apply(apply_status_color, axis=1), use_container_width=True)
            st.metric(f"Total for {view_month}", f"${shopping_df['Monthly Cost'].sum():,.2f}")
        else:
            st.info(f"No items scheduled for {view_month}.")

        st.divider()
        st.write("### ⚙️ Move Item to Different Month")
        item_to_edit = st.selectbox("Select Item", df['Item name'].unique())
        new_m = st.selectbox("New Target Month:", month_options, key="move_tool")
        if st.button("📅 Update Month"):
            st.session_state.master_df.loc[st.session_state.master_df['Item name'] == item_to_edit, 'Order_Month'] = new_m
            st.rerun()
