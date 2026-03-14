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

# Generate month options: Current month + 3 months advance
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
            st.success("Usage Averages Calculated!")
            st.dataframe(res[['Item name', 'AMU']], use_container_width=True)

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
            p = st.number_input("Price", 0.0)
            # --- TEST FIELD ADDED BELOW ---
            test_amu = st.number_input("Average Monthly Usage (Test Input)", 0.0)
            
            if st.form_submit_button("Save Item"):
                # Use the test_amu if it's > 0, otherwise try to get from Tab 1 mapping
                final_amu = test_amu if test_amu > 0 else st.session_state.amu_mapping.get(n, 0.0)
                
                row = pd.DataFrame([{'Item name': n, 'Item Type': t, 'Branch amount': b, 'Master amount': m, 
                                     'Average monthly usage': final_amu, 'Item price': p, 'Order_Month': month_options[0]}])
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
        st.success("Inventory Loaded Successfully!")
    
    st.write("### Master Inventory List")
    st.dataframe(st.session_state.master_df, use_container_width=True)

# ==========================================
# TAB 3: SHOPPING LIST
# ==========================================
with tab3:
    st.header("3. Monthly Shopping List")
    
    if not st.session_state.master_df.empty:
        df = st.session_state.master_df.copy()
        
        # Clean numeric data
        df['Master amount'] = pd.to_numeric(df['Master amount'], errors='coerce').fillna(0)
        df['Branch amount'] = pd.to_numeric(df['Branch amount'], errors='coerce').fillna(0)
        df['Monthly Cost'] = (df['Average monthly usage'] * df['Item price']).round(2)
        
        # --- FILTERS ---
        col_f1, col_f2 = st.columns([2, 1])
        with col_f1:
            all_types = sorted(df['Item Type'].unique().astype(str))
            selected_types = st.multiselect("🏷️ Filter by Type", options=all_types, default=all_types)
        with col_f2:
            view_month = st.selectbox("📅 View Shopping List For:", month_options)

        # --- LOGIC ---
        # Show items with 0 master stock AND matching type/month filters
        mask = (df['Master amount'] <= 0) & \
               (df['Item Type'].astype(str).isin(selected_types)) & \
               (df['Order_Month'] == view_month)
        
        shopping_df = df[mask].copy()

        # --- COLOR CODING ---
        def apply_status_color(row):
            # RED: Critical Out of Stock (Master & Branch = 0)
            if row['Master amount'] <= 0 and row['Branch amount'] <= 0:
                return ['background-color: #ff4b4b; color: white'] * len(row)
            # YELLOW: Warning (Master = 0, but Branch has stock)
            if row['Master amount'] <= 0 and row['Branch amount'] > 0:
                return ['background-color: #f1c40f; color: black'] * len(row)
            return [''] * len(row)

        if not shopping_df.empty:
            st.subheader(f"Purchase Order: {view_month}")
            st.dataframe(shopping_df.style.apply(apply_status_color, axis=1), use_container_width=True)
            
            total_cost = shopping_df['Monthly Cost'].sum()
            st.metric(f"Estimated Total for {view_month}", f"${total_cost:,.2f}")
        else:
            st.info(f"No items needing order for {view_month} based on filters.")

        st.divider()

        # --- RESCHEDULING TOOL ---
        st.write("### ⚙️ Reschedule or Remove Items")
        item_to_edit = st.selectbox("Select Item", df['Item name'].unique())
        c1, c2 = st.columns(2)
        with c1:
            new_target_month = st.selectbox("Move to Month:", month_options, key="move_tool")
            if st.button("📅 Update Month"):
                st.session_state.master_df.loc[st.session_state.master_df['Item name'] == item_to_edit, 'Order_Month'] = new_target_month
                st.rerun()
        with c2:
            if st.button("❌ Delete Item Permanently"):
                st.session_state.master_df = st.session_state.master_df[st.session_state.master_df['Item name'] != item_to_edit]
                st.rerun()
    else:
        st.warning("Inventory is empty. Add data in Tab 2 first.")
