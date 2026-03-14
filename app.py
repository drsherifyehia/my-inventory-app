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
                else:
                    st.error("Please enter an Item Name")

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
            
            # Auto-pulls price from Tab 1 reference data
            default_p = st.session_state.price_mapping.get(n, 0.0)
            p = st.number_input("Price", value=float(default_p))
            
            # "Assign Month" REMOVED from here to simplify the UI
            
            if st.form_submit_button("Save to Inventory"):
                final_amu = st.session_state.amu_mapping.get(n, 0.0)
                # Defaulting to the current month automatically
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
    
    st.write("### Master Inventory List")
    st.dataframe(st.session_state.master_df, use_container_width=True)

# ==========================================
# TAB 3: SHOPPING LIST
# ==========================================
with tab3:
    st.header("3. Monthly Shopping List")
    if not st.session_state.master_df.empty:
        df = st.session_state.master_df.copy()
        
        for col in ['Master amount', 'Branch amount', 'Item price', 'Average monthly usage']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        df['Monthly Cost'] = (df['Average monthly usage'] * df['Item price']).round(2)
        
        col_f1, col_f2 = st.columns([2, 1])
        with col_f1:
            all_types = sorted(df['Item Type'].unique().astype(str))
            selected_types = st.multiselect("🏷️ Filter by Type", options=all_types, default=all_types)
        with col_f2:
            view_month = st.selectbox("📅 View Shopping List For:", month_options)

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
            st.info(f"Nothing to buy for {view_month}.")

        st.divider()
        st.write("### ⚙️ Reschedule / Move Item")
        item_to_edit = st.selectbox("Select Item", df['Item name'].unique())
        new_m = st.selectbox("Move to Month:", month_options, key="move_tool")
        if st.button("📅 Update Month"):
            st.session_state.master_df.loc[st.session_state.master_df['Item name'] == item_to_edit, 'Order_Month'] = new_m
            st.rerun()
