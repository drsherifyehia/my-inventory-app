import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="Advanced Inventory Manager", layout="wide")

# --- 1. Persistence ---
if 'master_usage' not in st.session_state: st.session_state.master_usage = pd.DataFrame()
if 'master_inv' not in st.session_state: st.session_state.master_inv = pd.DataFrame()

now = datetime.now()
all_months = [(now + timedelta(days=30*i)).strftime('%B %Y') for i in range(12)]

# --- 2. Data Cleaning ---
def robust_clean(files, schema):
    all_dfs = []
    map1 = {'amount':['amount','qty'], 'price':['price','cost'], 'item':['item','inventoryitem','name'], 'type':['type','inventorytype'], 'date':['date','created']}
    map2 = {'name':['name','item'], 'type':['type','inventoryitem'], 'branch':['branch','branchamount'], 'master':['master','masteramount']}
    target = map1 if schema == 1 else map2

    for f in files:
        df = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
        df.columns = [str(c).strip().lower() for c in df.columns]
        found = {col: std for std, vars in target.items() for col in df.columns if any(v in col for v in vars)}
        df = df.rename(columns=found)
        all_dfs.append(df[[c for c in df.columns if c in target.keys()]])
    
    return pd.concat(all_dfs, ignore_index=True).reset_index(drop=True) if all_dfs else pd.DataFrame()

st.title("📦 Advanced Inventory Manager")
t1, t2, t3 = st.tabs(["📊 Usage Data", "📦 Current Stock", "🛒 Smart Shopping List"])

# ==========================================
# TAB 1: USAGE (MERGED)
# ==========================================
with t1:
    st.header("1. Consolidated Usage")
    up1 = st.file_uploader("Upload Usage Sheets", accept_multiple_files=True, key="u1")
    if up1:
        raw1 = robust_clean(up1, 1)
        if not raw1.empty:
            raw1['date'] = pd.to_datetime(raw1['date'], errors='coerce')
            raw1['amount'] = pd.to_numeric(raw1['amount'], errors='coerce').fillna(0)
            res1 = raw1.groupby('item').agg({'amount':'sum', 'price':'last', 'date':'min', 'type':'first'}).reset_index()
            # Calculate Timeframe and AMU
            res1['Months'] = ((now - res1['date']).dt.days / 30.44).clip(lower=0.5).round(2)
            res1['AMU'] = (res1['amount'] / res1['Months']).round(2)
            st.session_state.master_usage = res1
    
    if not st.session_state.master_usage.empty:
        st.dataframe(st.session_state.master_usage, use_container_width=True)

# ==========================================
# TAB 2: INVENTORY (LINKED)
# ==========================================
with t2:
    st.header("2. Master Inventory")
    up2 = st.file_uploader("Upload Inventory Sheets", accept_multiple_files=True, key="u2")
    if up2:
        raw2 = robust_clean(up2, 2)
        if not raw2.empty:
            for c in ['branch', 'master']: raw2[c] = pd.to_numeric(raw2[c], errors='coerce').fillna(0)
            # Link AMU from Tab 1 to Tab 2
            amu_map = st.session_state.master_usage.set_index('item')['AMU'].to_dict()
            raw2['AMU'] = raw2['name'].map(amu_map).fillna(0)
            st.session_state.master_inv = raw2

    if not st.session_state.master_inv.empty:
        # Purple highlight for missing usage data
        def check_usage(row):
            exists = row['name'] in st.session_state.master_usage['item'].values
            return ['background-color: #e6e6fa'] * len(row) if not exists else [''] * len(row)
        st.dataframe(st.session_state.master_inv.style.apply(check_usage, axis=1), use_container_width=True)

# ==========================================
# TAB 3: DYNAMIC SHOPPING FORECAST
# ==========================================
with t3:
    st.header("3. Next 3 Months Forecast")
    if not st.session_state.master_inv.empty:
        start_month = st.selectbox("Select Start Month:", all_months)
        s_idx = all_months.index(start_month)
        window = all_months[s_idx : s_idx + 3]

        # Only items with Master Amount 0 are considered for the shopping list
        shop_pool = st.session_state.master_inv[st.session_state.master_inv['master'] <= 0].copy()

        # Logic to determine which month the item "dies"
        def get_target_month(row):
            b, amu = row['branch'], row['AMU']
            if amu <= 0: return window[0] # If no AMU, assume immediate need
            months_left = b / amu
            if months_left < 1: return window[0] # Not enough for 1 month
            if months_left < 2: return window[1] # Enough for 1 month, out by month 2
            return window[2] # Out by month 3 or later

        shop_pool['Target_Month'] = shop_pool.apply(get_target_month, axis=1)

        def color_row(row):
            b, amu = row['branch'], row['AMU']
            if b <= 0: return ['background-color: #ff4b4b; color: white'] * len(row)
            if b <= amu: return ['background-color: #e67e22; color: white'] * len(row)
            return ['background-color: #f1c40f; color: black'] * len(row)

        c1, c2, c3 = st.columns(3)
        for i, m_name in enumerate(window):
            with [c1, c2, c3][i]:
                st.subheader(f"🗓️ {m_name}")
                # FILTER: Only show item if it is PREDICTED to be out this month
                m_df = shop_pool[shop_pool['Target_Month'] == m_name]
                if not m_df.empty:
                    st.dataframe(m_df[['name','branch','AMU']].style.apply(color_row, axis=1), use_container_width=True)
                else:
                    st.info("Stock is sufficient.")
    else:
        st.info("Upload data to see the forecast.")
