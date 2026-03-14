import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="Advanced Inventory Manager", layout="wide")

# --- 1. Memory Setup & Date Logic ---
if 'tab1_data' not in st.session_state:
    st.session_state.tab1_data = pd.DataFrame()
if 'tab2_data' not in st.session_state:
    st.session_state.tab2_data = pd.DataFrame()

current_date = datetime.now()
m1 = current_date.strftime('%B %Y')
m2 = (current_date + timedelta(days=30)).strftime('%B %Y')
m3 = (current_date + timedelta(days=60)).strftime('%B %Y')
month_options = [m1, m2, m3]

# --- 2. Smart Column Fixers ---
def fix_tab1_columns(df):
    df.columns = [str(c).strip().lower() for c in df.columns]
    col_map = {
        'amount': ['amount', 'qty', 'quantity', 'distributed'],
        'price': ['price', 'cost', 'unit price'],
        'inventoryitem': ['inventoryitem', 'item', 'name', 'product'],
        'inventorytype': ['inventorytype', 'category', 'group'],
        'created': ['created', 'date', 'timestamp', 'time']
    }
    new_cols = {}
    for standard, variations in col_map.items():
        for col in df.columns:
            if any(v in col.lower() for v in variations) and standard not in new_cols.values():
                new_cols[col] = standard
    df = df.rename(columns=new_cols)
    for req in ['inventoryitem', 'inventorytype', 'amount', 'price', 'created']:
        if req not in df.columns:
            df[req] = np.nan
    return df

def fix_tab2_columns(df):
    df.columns = [str(c).strip().lower() for c in df.columns]
    col_map = {
        'name': ['name', 'item', 'product', 'description'],
        'type': ['type', 'inventoryitem', 'category'], 
        'branchamount': ['branchamount', 'branch', 'clinic'],
        'masteramount': ['masteramount', 'master', 'warehouse'],
        'created': ['created', 'date', 'timestamp']
    }
    new_cols = {}
    for standard, variations in col_map.items():
        for col in df.columns:
            if any(v in col.lower() for v in variations) and standard not in new_cols.values():
                new_cols[col] = standard
    df = df.rename(columns=new_cols)
    for req in ['name', 'type', 'branchamount', 'masteramount', 'created']:
        if req not in df.columns:
            df[req] = np.nan
    return df

st.title("📦 Advanced Inventory Manager")

tab1, tab2, tab3 = st.tabs(["📊 Usage Transactions", "📦 Current Inventory", "🛒 3-Month Shopping List"])

# ==========================================
# TAB 1: USAGE TRANSACTIONS & AMU
# ==========================================
with tab1:
    st.header("1. Upload Usage & Calculate AMU")
    f1_list = st.file_uploader("Upload Distribution Sheet(s)", type=['xlsx', 'csv'], accept_multiple_files=True, key="f1")
    
    if f1_list:
        all_dfs = [fix_tab1_columns(pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)) for f in f1_list]
        raw_t1 = pd.concat(all_dfs, ignore_index=True)
        raw_t1['created'] = pd.to_datetime(raw_t1['created'], errors='coerce')
        raw_t1['amount'] = pd.to_numeric(raw_t1['amount'], errors='coerce').fillna(0)
        raw_t1['price'] = pd.to_numeric(raw_t1['price'], errors='coerce').fillna(0)
        
        res = raw_t1.groupby('inventoryitem').agg({
            'amount': 'sum', 'price': 'last', 'created': 'min', 'inventorytype': 'first'
        }).reset_index()
        
        res['Months'] = ((current_date - res['created']).dt.days / 30.44).round(2)
        res['Months'] = np.where(res['Months'] < 0.03, 0.03, res['Months']) 
        res['AMU'] = (res['amount'] / res['Months']).round(2)
        
        res = res.rename(columns={'inventoryitem': 'InventoryItem', 'inventorytype': 'InventoryType', 'amount': 'Total Amount', 'price': 'Latest Price', 'created': 'Oldest Date'})
        st.session_state.tab1_data = res
        st.success("Usage Data Processed!")

    if not st.session_state.tab1_data.empty:
        search_t1 = st.text_input("🔍 Search Usage Data...", key="search1").lower()
        df1 = st.session_state.tab1_data.copy()
        if search_t1:
            df1 = df1[df1['InventoryItem'].astype(str).str.lower().str.contains(search_t1)]
            
        styled_df1 = df1.style.set_properties(subset=['Months', 'AMU'], **{'background-color': '#e1f5fe', 'color': 'black'})
        st.dataframe(styled_df1, use_container_width=True)

# ==========================================
# TAB 2: MASTER INVENTORY
# ==========================================
with tab2:
    st.header("2. Upload Master Inventory")
    col2_1, col2_2 = st.columns([3, 1])
    
    with col2_1:
        f2_list = st.file_uploader("Upload Inventory Sheet(s)", type=['xlsx', 'csv'], accept_multiple_files=True, key="f2")
    with col2_2:
        # --- AI DATA LOGIC CHECK ---
        st.write("")
        st.write("")
        if st.button("🤖 Run Logic & Validity Check", use_container_width=True):
            st.write("### 🧠 Diagnostics Report")
            if st.session_state.tab2_data.empty or st.session_state.tab1_data.empty:
                st.warning("Please upload data to BOTH tabs before running the check.")
            else:
                errors_found = 0
                missing_types = st.session_state.tab2_data[~st.session_state.tab2_data['Type'].isin(st.session_state.tab1_data['InventoryItem'])]
                if not missing_types.empty:
                    st.error(f"⚠️ Found {len(missing_types)} items in Tab 2 with Types not present in Tab 1 (highlighted in purple below).")
                    errors_found += 1
                
                negative_stock = st.session_state.tab2_data[(st.session_state.tab2_data['Branch Amount'] < 0) | (st.session_state.tab2_data['Master Amount'] < 0)]
                if not negative_stock.empty:
                    st.error(f"⚠️ Found {len(negative_stock)} items with negative stock numbers. Please check your Excel.")
                    errors_found += 1
                    
                if errors_found == 0:
                    st.success("✅ Logic Check Passed! Data looks clean and well-linked.")

    if f2_list:
        all_dfs2 = [fix_tab2_columns(pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)) for f in f2_list]
        raw_t2 = pd.concat(all_dfs2, ignore_index=True)
        raw_t2['branchamount'] = pd.to_numeric(raw_t2['branchamount'], errors='coerce').fillna(0)
        raw_t2['masteramount'] = pd.to_numeric(raw_t2['masteramount'], errors='coerce').fillna(0)
        raw_t2['amount'] = raw_t2['branchamount'] + raw_t2['masteramount']
        
        raw_t2 = raw_t2.rename(columns={'name': 'Name', 'type': 'Type', 'amount': 'Total Amount', 'branchamount': 'Branch Amount', 'masteramount': 'Master Amount', 'created': 'Created Date'})
        
        if not st.session_state.tab1_data.empty:
            amu_dict = st.session_state.tab1_data.set_index('InventoryItem')['AMU'].to_dict()
            raw_t2['AMU (From Tab 1)'] = raw_t2['Type'].map(amu_dict).fillna(0)
        else:
            raw_t2['AMU (From Tab 1)'] = 0.0

        if 'Order_Month' not in raw_t2.columns:
            raw_t2['Order_Month'] = m1 # Default to current month

        st.session_state.tab2_data = raw_t2
        st.success("Inventory Processed!")

    if not st.session_state.tab2_data.empty:
        search_t2 = st.text_input("🔍 Search Inventory...", key="search2").lower()
        df2 = st.session_state.tab2_data.copy()
        
        if search_t2:
            df2 = df2[df2['Name'].astype(str).str.lower().str.contains(search_t2) | df2['Type'].astype(str).str.lower().str.contains(search_t2)]
            
        # --- TAB 2 PURPLE HIGHLIGHT LOGIC ---
        def tab2_styling(row):
            styles = [''] * len(row)
            tab1_items = st.session_state.tab1_data['InventoryItem'].values if not st.session_state.tab1_data.empty else []
            is_missing = row['Type'] not in tab1_items
            
            for i, col in enumerate(row.index):
                if is_missing:
                    styles[i] = 'background-color: #e6e6fa; color: black' # Soft Purple
                elif col in ['Total Amount', 'AMU (From Tab 1)']:
                    styles[i] = 'background-color: #e1f5fe; color: black' # Light Blue
            return styles
            
        st.write("*(Items highlighted in purple are missing usage data in Tab 1)*")
        st.dataframe(df2.style.apply(tab2_styling, axis=1), use_container_width=True)

# ==========================================
# TAB 3: SHOPPING LIST (3-MONTH VIEW & COLORS)
# ==========================================
with tab3:
    st.header("3. Smart Shopping List (Next 3 Months)")
    
    if not st.session_state.tab2_data.empty and not st.session_state.tab1_data.empty:
        df3 = st.session_state.tab2_data.copy()
        
        # --- FILTERS ---
        col_f1, col_f2 = st.columns([1, 2])
        with col_f1:
            search_t3 = st.text_input("🔍 Search Shopping List...", "").lower()
        with col_f2:
            all_types = sorted(df3['Type'].dropna().unique().astype(str))
            selected_types = st.multiselect("🏷️ Filter by Type (InventoryItem)", options=all_types, default=all_types)

        # Apply basic filters (MUST have Master = 0)
        mask = (df3['Master Amount'] <= 0) & \
               (df3['Type'].astype(str).isin(selected_types)) & \
               (df3['Name'].astype(str).str.lower().str.contains(search_t3))
        
        shopping_pool = df3[mask].copy()
        
        # --- RESCHEDULING TOOL ---
        st.write("### ⚙️ Assign Item to Month")
        move_col1, move_col2, move_col3 = st.columns(3)
        with move_col1:
            move_item = st.selectbox("Select Item to Move", shopping_pool['Name'].unique() if not shopping_pool.empty else [])
        with move_col2:
            new_target = st.selectbox("Assign to Month:", month_options)
        with move_col3:
            st.write("")
            if st.button("📅 Update Target Month"):
                st.session_state.tab2_data.loc[st.session_state.tab2_data['Name'] == move_item, 'Order_Month'] = new_target
                st.rerun()

        st.divider()

        # --- URGENCY COLOR LOGIC ---
        def tab3_color_logic(row):
            b = float(row['Branch Amount'])
            amu = float(row['AMU (From Tab 1)'])
            
            if b <= 0:
                return ['background-color: #ff4b4b; color: white'] * len(row) # RED (Empty everywhere)
            elif b > 0 and b > amu:
                return ['background-color: #f1c40f; color: black'] * len(row) # YELLOW (Safe for now)
            elif b > 0 and b <= amu:
                return ['background-color: #e67e22; color: white'] * len(row) # ORANGE (Getting low)
            return [''] * len(row)

        # --- 3 MONTH BOXES ---
        st.write("### 📅 Upcoming Quarter Overview")
        st.markdown("🔴 **Critical (Empty)** | 🟠 **Warning (Branch ≤ AMU)** | 🟡 **Safe (Branch > AMU)**")
        
        box1, box2, box3 = st.columns(3)
        display_cols = ['Name', 'Type', 'Branch Amount', 'AMU (From Tab 1)']
        
        with box1:
            st.subheader(f"🗓️ {m1}")
            m1_df = shopping_pool[shopping_pool['Order_Month'] == m1]
            if not m1_df.empty:
                st.dataframe(m1_df[display_cols].style.apply(tab3_color_logic, axis=1), use_container_width=True)
            else:
                st.info("No items scheduled.")
                
        with box2:
            st.subheader(f"🗓️ {m2}")
            m2_df = shopping_pool[shopping_pool['Order_Month'] == m2]
            if not m2_df.empty:
                st.dataframe(m2_df[display_cols].style.apply(tab3_color_logic, axis=1), use_container_width=True)
            else:
                st.info("No items scheduled.")
                
        with box3:
            st.subheader(f"🗓️ {m3}")
            m3_df = shopping_pool[shopping_pool['Order_Month'] == m3]
            if not m3_df.empty:
                st.dataframe(m3_df[display_cols].style.apply(tab3_color_logic, axis=1), use_container_width=True)
            else:
                st.info("No items scheduled.")
    else:
        st.info("Upload data in Tab 1 and Tab 2 to generate the Shopping List.")
