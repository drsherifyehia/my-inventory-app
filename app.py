import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="Advanced Inventory Manager", layout="wide")

# --- 1. Memory Management ---
if 't1_df' not in st.session_state: st.session_state.t1_df = pd.DataFrame()
if 't2_df' not in st.session_state: st.session_state.t2_df = pd.DataFrame()

now = datetime.now()
months = [(now + timedelta(days=30*i)).strftime('%B %Y') for i in range(3)]

# --- 2. Heavy Duty Data Cleaner ---
def clean_and_map(files, schema_type):
    all_data = []
    
    # Define Column Mappings
    map1 = {'amount':['amount','qty','quantity'], 'price':['price','cost'], 'item':['inventoryitem','item','name'], 'type':['inventorytype','type','category'], 'date':['created','date','timestamp']}
    map2 = {'name':['name','item','product'], 'type':['type','inventoryitem'], 'branch':['branchamount','branch'], 'master':['masteramount','master'], 'date':['created','date']}
    target_map = map1 if schema_type == 1 else map2

    for f in files:
        try:
            temp_df = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
            temp_df.columns = [str(c).strip().lower() for c in temp_df.columns]
            
            # Rename columns based on matches found
            rename_dict = {}
            for std_name, variations in target_map.items():
                for actual_col in temp_df.columns:
                    if any(v in actual_col for v in variations) and std_name not in rename_dict.values():
                        rename_dict[actual_col] = std_name
            
            temp_df = temp_df.rename(columns=rename_dict)
            
            # Keep only the mapped columns to prevent "duplicate key" errors
            valid_cols = [c for c in temp_df.columns if c in target_map.keys()]
            all_data.append(temp_df[valid_cols])
        except Exception as e:
            st.error(f"Error reading {f.name}: {e}")
            
    if not all_data: return pd.DataFrame()
    return pd.concat(all_data, ignore_index=True).reset_index(drop=True)

st.title("📦 Advanced Inventory Manager")
t1, t2, t3 = st.tabs(["📊 Usage Transactions", "📦 Current Inventory", "🛒 3-Month Shopping List"])

# ==========================================
# TAB 1: USAGE & AMU CALCULATION
# ==========================================
with t1:
    st.header("1. Upload Usage & Calculate AMU")
    up1 = st.file_uploader("Upload Usage Files", accept_multiple_files=True, key="up1")
    
    if up1:
        raw1 = clean_and_map(up1, 1)
        if not raw1.empty:
            raw1['date'] = pd.to_datetime(raw1['date'], errors='coerce')
            raw1['amount'] = pd.to_numeric(raw1['amount'], errors='coerce').fillna(0)
            
            # Consolidate by Item
            res1 = raw1.groupby('item').agg({'amount':'sum', 'price':'last', 'date':'min', 'type':'first'}).reset_index()
            res1['Months_Active'] = ((now - res1['date']).dt.days / 30.44).clip(lower=0.5).round(2)
            res1['AMU'] = (res1['amount'] / res1['Months_Active']).round(2)
            st.session_state.t1_df = res1

    if not st.session_state.t1_df.empty:
        search1 = st.text_input("🔍 Search Usage Items...", "").lower()
        view1 = st.session_state.t1_df.copy()
        if search1: view1 = view1[view1['item'].astype(str).str.lower().str.contains(search1)]
        
        st.write("### 📝 Consolidated Reference")
        st.dataframe(view1.style.set_properties(subset=['Months_Active', 'AMU'], **{'background-color': '#e1f5fe', 'color': 'black'}))

# ==========================================
# TAB 2: MASTER INVENTORY & PURPLE LOGIC
# ==========================================
with t2:
    st.header("2. Current Inventory Status")
    up2 = st.file_uploader("Upload Inventory Files", accept_multiple_files=True, key="up2")
    
    if up2:
        raw2 = clean_and_map(up2, 2)
        if not raw2.empty:
            for c in ['branch', 'master']: raw2[c] = pd.to_numeric(raw2[c], errors='coerce').fillna(0)
            raw2['TotalStock'] = raw2['branch'] + raw2['master']
            
            # Link AMU from Tab 1
            amu_lookup = st.session_state.t1_df.set_index('item')['AMU'].to_dict() if not st.session_state.t1_df.empty else {}
            raw2['AMU'] = raw2['type'].map(amu_lookup).fillna(0)
            raw2['Order_Month'] = months[0]
            st.session_state.t2_df = raw2

    if not st.session_state.t2_df.empty:
        search2 = st.text_input("🔍 Search Inventory...", "").lower()
        view2 = st.session_state.t2_df.copy()
        if search2: view2 = view2[view2['name'].astype(str).str.lower().str.contains(search2)]

        # Highlight in purple if the Type isn't found in Tab 1's usage list
        def purple_missing(row):
            t1_items = st.session_state.t1_df['item'].unique() if not st.session_state.t1_df.empty else []
            return ['background-color: #e6e6fa; color: black'] * len(row) if row['type'] not in t1_items else [''] * len(row)
        
        st.dataframe(view2.style.apply(purple_missing, axis=1))

# ==========================================
# TAB 3: COLOR-CODED SHOPPING DASHBOARD
# ==========================================
with t3:
    st.header("3. Smart Shopping List (3-Month Forecast)")
    if not st.session_state.t2_df.empty:
        df3 = st.session_state.t2_df.copy()
        
        # Multi-select for Types
        selected_types = st.multiselect("Filter by Item Type:", options=df3['type'].unique(), default=df3['type'].unique())
        
        # Basic Filter: Master Amount must be 0
        shop_base = df3[(df3['master'] <= 0) & (df3['type'].isin(selected_types))]

        def urgency_colors(row):
            b, amu = row['branch'], row['AMU']
            if b <= 0: return ['background-color: #ff4b4b; color: white'] * len(row) # RED: Empty
            if b <= amu: return ['background-color: #e67e22; color: white'] * len(row) # ORANGE: Low
            return ['background-color: #f1c40f; color: black'] * len(row) # YELLOW: Sufficient

        # 3 Column View for 3 Months
        c1, c2, c3 = st.columns(3)
        for i, m_name in enumerate(months):
            with [c1, c2, c3][i]:
                st.subheader(m_name)
                m_list = shop_base[shop_base['Order_Month'] == m_name]
                if not m_list.empty:
                    st.dataframe(m_list[['name', 'branch', 'AMU']].style.apply(urgency_colors, axis=1), use_container_width=True)
                else:
                    st.info("No items scheduled.")
    else:
        st.warning("Please upload data in Tab 1 and Tab 2 first.")
