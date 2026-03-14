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

# Generate month list: Current month + 3 months in advance
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

tab1, tab2, tab3 = st.tabs(["📊 Usage Calc", "📦 Inventory Items", "🛒 Shopping List"])

# ==========================================
# TAB 1: USAGE CALCULATION
# ==========================================
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

# ==========================================
# TAB 2: INVENTORY ITEMS
# ==========================================
with tab2:
    st.header("2. Current Stock")
    with st.expander("➕ Add Item Manually"):
        with st.form("inv_form"):
            n = st.text_input("Item Name")
            t = st.text_input("Item Type (e.g., Crown, Implants)")
            b = st.number_input("Branch Qty", 0)
            m = st.number_input("Master Qty", 0)
            p = st.number_input("Price", 0.0)
            sel_m = st.selectbox("Select Month", month_options)
            if st.form_submit_button("Save"):
                amu = st.session_state.amu_mapping.get(n, 0.0)
                row = pd.DataFrame([{'Item name': n, 'Item Type': t, 'Branch amount': b, 'Master amount': m, 'Average monthly usage': amu, 'Item price': p, 'Order_Month': sel_m}])
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
            df2['Order_Month'] = month_options[0]
        if 'Item Type' not in df2.columns:
            df2['Item Type'] = "General"
        st.session_state.master_df = df2
        st.success("Inventory Loaded!")
    
    st.dataframe(st.session_state.master_df, use_container_width=True)

# ==========================================
# TAB 3: SHOPPING LIST (FIXED MOBILE VIEW)
# ==========================================
with tab3:
    st.header("3. Monthly Shopping List")
    
    if not st.session_state.master_df.empty:
        df = st.session_state.master_df.copy()
        df['Monthly Cost'] = (df['Average monthly usage'] * df['Item price']).round(2)
        
        # --- HORIZONTAL TYPE FILTER (MOBILE FRIENDLY) ---
        st.write("### 🏷️ Filter by Type")
        all_types = sorted(df['Item Type'].unique().astype(str))
        
        # Using a Multiselect which is much better for long lists on mobile
        selected_types = st.multiselect("Select Categories to Display", options=all_types, default=all_types)
        
        # --- APPLY FILTERS ---
        df_filtered = df[df['Item Type'].astype(str).isin(selected_types)]
        to_buy = df_filtered[df_filtered['Master amount'] <= 0].copy()
        
        if not to_buy.empty:
            for month in month_options:
                m_df = to_buy[to_buy['Order_Month'] == month]
                if not m_df.empty:
                    st.subheader(f"📅 {month}")
                    st.dataframe(m_df[['Item name', 'Item Type', 'Branch amount', 'Master amount', 'Item price', 'Monthly Cost']], use_container_width=True)
                    st.metric(f"Total for {month}", f"${m_df['Monthly Cost'].sum():,.2f}")
                    st.divider()
        else:
            st.info("No items match your filters or everything is in stock.")

        # --- ACTIONS ---
        st.write("### ⚙️ Move / Edit Items")
        target = st.selectbox("Select Item", df['Item name'].unique())
        
        col_act1, col_act2 = st.columns(2)
        if col_act1.button("❌ Remove Item"):
            st.session_state.master_df = st.session_state.master_df[st.session_state.master_df['Item name'] != target]
            st.rerun()
        
        move_month = st.selectbox("Move to Month", month_options, key="move_m")
        if col_act2.button("📅 Move Month"):
            st.session_state.master_df.loc[st.session_state.master_df['Item name'] == target, 'Order_Month'] = move_month
            st.success(f"Moved {target} to {move_month}")
            st.rerun()
            
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download All (CSV)", csv, "inventory.csv", "text/csv")
    else:
        st.info("Inventory is empty. Please add items in Tab 2.")
