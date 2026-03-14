import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="Advanced Inventory Manager", layout="wide")

# --- 1. Persistence & State ---
if 'master_usage' not in st.session_state: st.session_state.master_usage = pd.DataFrame()
if 'master_inv' not in st.session_state: st.session_state.master_inv = pd.DataFrame()

now = datetime.now()
all_months = [(now + timedelta(days=30*i)).strftime('%B %Y') for i in range(12)]

# --- 2. Heavy-Duty Data Engine ---
def process_merged_data(files, schema):
    all_data = []
    map1 = {'amount':['amount','qty'], 'price':['price','cost'], 'item':['item','inventoryitem','name'], 'type':['type','inventorytype'], 'date':['date','created']}
    map2 = {'name':['name','item'], 'type':['type','inventoryitem'], 'branch':['branch','branchamount'], 'master':['master','masteramount']}
    target_map = map1 if schema == 1 else map2

    for f in files:
        df = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
        df.columns = [str(c).strip().lower() for c in df.columns]
        # Clean specific columns to avoid the "Duplicate Key" error
        rename_dict = {col: std for std, vars in target_map.items() for col in df.columns if any(v in col for v in vars)}
        df = df.rename(columns=rename_dict)
        # Keep only the essential columns per file before merging
        essential = [c for c in df.columns if c in target_map.keys()]
        all_data.append(df[essential])
    
    if not all_data: return pd.DataFrame()
    # Merge all files into one dependent list
    return pd.concat(all_data, ignore_index=True).reset_index(drop=True)

st.title("📦 Advanced Inventory Manager")
t1, t2, t3 = st.tabs(["📊 Usage Data", "📦 Current Stock", "🛒 Smart Shopping List"])

# ==========================================
# TAB 1: CONSOLIDATED USAGE
# ==========================================
with t1:
    st.header("1. Upload & Merge Usage")
    up1 = st.file_uploader("Upload All Usage Sheets", accept_multiple_files=True, key="u1")
    if up1:
        merged1 = process_merged_data(up1, 1)
        if not merged1.empty:
            merged1['date'] = pd.to_datetime(merged1['date'], errors='coerce')
            merged1['amount'] = pd.to_numeric(merged1['amount'], errors='coerce').fillna(0)
            # Grouping items to handle dependencies between multiple files
            usage_db = merged1.groupby('item').agg({'amount':'sum', 'price':'last', 'date':'min', 'type':'first'}).reset_index()
            usage_db['Months'] = ((now - usage_db['date']).dt.days / 30.44).clip(lower=0.5).round(2)
            usage_db['AMU'] = (usage_db['amount'] / usage_db['Months']).round(2)
            st.session_state.master_usage = usage_db
    
    if not st.session_state.master_usage.empty:
        st.dataframe(st.session_state.master_usage, use_container_width=True)

# ==========================================
# TAB 2: STOCK & PURPLE CHECK
# ==========================================
with t2:
    st.header("2. Master Inventory")
    up2 = st.file_uploader("Upload Inventory Sheets", accept_multiple_files=True, key="u2")
    if up2:
        merged2 = process_merged_data(up2, 2)
        if not merged2.empty:
            for c in ['branch', 'master']: merged2[c] = pd.to_numeric(merged2[c], errors='coerce').fillna(0)
            # Link AMU strictly from Tab 1
            amu_map = st.session_state.master_usage.set_index('item')['AMU'].to_dict()
            merged2['AMU'] = merged2['name'].map(amu_map).fillna(0)
            st.session_state.master_inv = merged2

    if not st.session_state.master_inv.empty:
        def purple_style(row):
            # Highlight items not present in Tab 1
            missing = row['name'] not in st.session_state.master_usage['item'].values
            return ['background-color: #e6e6fa; color: black'] * len(row) if missing else [''] * len(row)
        st.dataframe(st.session_state.master_inv.style.apply(purple_style, axis=1), use_container_width=True)

# ==========================================
# TAB 3: BURN-DOWN SHOPPING LIST
# ==========================================
with t3:
    st.header("3. Next 3 Months (Burn-Down View)")
    if not st.session_state.master_inv.empty:
        start_month = st.selectbox("Choose Start Month:", all_months)
        idx = all_months.index(start_month)
        window = all_months[idx : idx + 3]

        # Criteria: Master = 0
        shop_df = st.session_state.master_inv[st.session_state.master_inv['master'] <= 0].copy()

        # Burn-down Logic: Which month does stock run out?
        def calc_depletion(row):
            if row['AMU'] <= 0: return window[0] # Assume immediate need
            months_left = row['branch'] / row['AMU']
            if months_left < 1: return window[0]
            if months_left < 2: return window[1]
            return window[2]

        shop_df['Due_Month'] = shop_df.apply(calc_depletion, axis=1)

        def urgency_colors(row):
            b, amu = row['branch'], row['AMU']
            if b <= 0: return ['background-color: #ff4b4b; color: white'] * len(row) # Red
            if b <= amu: return ['background-color: #e67e22; color: white'] * len(row) # Orange
            return ['background-color: #f1c40f; color: black'] * len(row) # Yellow

        c1, c2, c3 = st.columns(3)
        for i, m_name in enumerate(window):
            with [c1, c2, c3][i]:
                st.subheader(m_name)
                # Only show item in its specific depletion month
                display_df = shop_df[shop_df['Due_Month'] == m_name]
                if not display_df.empty:
                    st.dataframe(display_df[['name','branch','AMU']].style.apply(urgency_colors, axis=1), use_container_width=True)
                else:
                    st.info("No orders required.")
    else:
        st.warning("Upload data to view forecast.")
