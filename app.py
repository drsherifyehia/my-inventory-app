import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="Advanced Inventory Manager", layout="wide")

# --- 1. Global Session State ---
if 'master_usage' not in st.session_state: st.session_state.master_usage = pd.DataFrame()
if 'master_inv' not in st.session_state: st.session_state.master_inv = pd.DataFrame()

now = datetime.now()
# Full year of months for the dropdown
all_months = [(now + timedelta(days=30*i)).strftime('%B %Y') for i in range(12)]

# --- 2. Data Cleaning Engine ---
def robust_clean(files, schema):
    all_dfs = []
    # Key variations to match your uploaded Excel headers
    map1 = {'amount':['amount','qty'], 'price':['price','cost'], 'item':['item','inventoryitem','name'], 'type':['type','inventorytype'], 'date':['date','created']}
    map2 = {'name':['name','item'], 'type':['type','inventoryitem','category'], 'branch':['branch','branchamount'], 'master':['master','masteramount'], 'date':['date','created']}
    target = map1 if schema == 1 else map2

    for f in files:
        df = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        # Rename based on best match
        found = {}
        for std, vars in target.items():
            for col in df.columns:
                if any(v in col for v in vars) and std not in found.values():
                    found[col] = std
        
        df = df.rename(columns=found)
        # Keep only what we need to prevent "Duplicate Key" errors
        keep = [c for c in df.columns if c in target.keys()]
        all_dfs.append(df[keep])
    
    if not all_dfs: return pd.DataFrame()
    return pd.concat(all_dfs, ignore_index=True).reset_index(drop=True)

st.title("📦 Advanced Inventory Manager")
t1, t2, t3 = st.tabs(["📊 Usage Transactions", "📦 Current Inventory", "🛒 3-Month Forecast"])

# ==========================================
# TAB 1: USAGE (Consolidated)
# ==========================================
with t1:
    st.header("1. Upload Usage & Calculate AMU")
    up1 = st.file_uploader("Upload Usage Sheets", accept_multiple_files=True, key="u1")
    
    if up1:
        # Merge all uploaded files into one dependent dataset
        raw1 = robust_clean(up1, 1)
        if not raw1.empty:
            raw1['date'] = pd.to_datetime(raw1['date'], errors='coerce')
            raw1['amount'] = pd.to_numeric(raw1['amount'], errors='coerce').fillna(0)
            
            # Consolidate: Sum amounts, find oldest date for timeframe
            res1 = raw1.groupby('item').agg({'amount':'sum', 'price':'last', 'date':'min', 'type':'first'}).reset_index()
            res1['Months'] = ((now - res1['date']).dt.days / 30.44).clip(lower=0.5).round(2)
            res1['AMU'] = (res1['amount'] / res1['Months']).round(2)
            st.session_state.master_usage = res1
            st.success("All usage sheets merged and AMU calculated!")

    if not st.session_state.master_usage.empty:
        st.dataframe(st.session_state.master_usage.style.set_properties(subset=['AMU'], **{'background-color': '#e1f5fe'}))

# ==========================================
# TAB 2: INVENTORY (Linked to Tab 1)
# ==========================================
with t2:
    st.header("2. Inventory Status")
    up2 = st.file_uploader("Upload Inventory Sheets", accept_multiple_files=True, key="u2")
    
    if up2:
        raw2 = robust_clean(up2, 2)
        if not raw2.empty:
            for c in ['branch', 'master']: raw2[c] = pd.to_numeric(raw2[c], errors='coerce').fillna(0)
            
            # LINKING LOGIC: Pull AMU from the merged Tab 1 data
            amu_map = st.session_state.master_usage.set_index('item')['AMU'].to_dict()
            raw2['AMU'] = raw2['name'].map(amu_map).fillna(0) # Match by Name
            
            raw2['TotalStock'] = raw2['branch'] + raw2['master']
            raw2['Order_Month'] = all_months[0]
            st.session_state.master_inv = raw2

    if not st.session_state.master_inv.empty:
        def purple_missing(row):
            exists = row['name'] in st.session_state.master_usage['item'].values
            return ['background-color: #e6e6fa'] * len(row) if not exists else [''] * len(row)
        
        st.dataframe(st.session_state.master_inv.style.apply(purple_missing, axis=1))

# ==========================================
# TAB 3: ROLLING 3-MONTH SHOPPING
# ==========================================
with t3:
    st.header("3. Shopping Forecast")
    if not st.session_state.master_inv.empty:
        # Rolling Month Dropdown
        start_month = st.selectbox("Select Starting Month:", all_months)
        start_idx = all_months.index(start_month)
        
        # Determine the 3 visible months based on selection
        window = all_months[start_idx : start_idx + 3]
        
        # Urgency Colors
        def get_color(row):
            b, amu = row['branch'], row['AMU']
            if b <= 0: return ['background-color: #ff4b4b; color: white'] * len(row)
            if b <= amu: return ['background-color: #e67e22; color: white'] * len(row)
            return ['background-color: #f1c40f; color: black'] * len(row)

        c1, c2, c3 = st.columns(3)
        # Filter for items with Master Amount = 0
        shop_data = st.session_state.master_inv[st.session_state.master_inv['master'] <= 0]
        
        for i, m_name in enumerate(window):
            with [c1, c2, c3][i]:
                st.subheader(f"🗓️ {m_name}")
                # For this logic, we assume items are assigned to their respective forecast slot
                # (You can add a column to 'move' items between months if needed)
                st.dataframe(shop_data[['name','branch','AMU']].style.apply(get_color, axis=1))
    else:
        st.info("Upload data in Tabs 1 and 2 to see the forecast.")
