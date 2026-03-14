import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="Advanced Inventory Manager", layout="wide")

# --- 1. Persistence Setup ---
if 'tab1_data' not in st.session_state:
    st.session_state.tab1_data = pd.DataFrame()
if 'tab2_data' not in st.session_state:
    st.session_state.tab2_data = pd.DataFrame()

current_date = datetime.now()
m1, m2, m3 = [ (current_date + timedelta(days=30*i)).strftime('%B %Y') for i in range(3) ]
month_options = [m1, m2, m3]

# --- 2. Smart Column Detection ---
def process_upload(files, tab_type):
    all_dfs = []
    for f in files:
        df = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
        df.columns = [str(c).strip().lower() for c in df.columns]
        all_dfs.append(df)
    
    combined = pd.concat(all_dfs, ignore_index=True).reset_index(drop=True)
    
    if tab_type == 1:
        mapping = {'amount':['amount','qty'], 'price':['price','cost'], 'inventoryitem':['inventoryitem','item'], 'inventorytype':['inventorytype','type'], 'created':['created','date']}
    else:
        mapping = {'name':['name','item'], 'type':['type','inventoryitem'], 'branchamount':['branchamount','branch'], 'masteramount':['masteramount','master'], 'created':['created','date']}
    
    new_cols = {}
    for std, vars in mapping.items():
        for col in combined.columns:
            if any(v in col for v in vars) and std not in new_cols.values():
                new_cols[col] = std
    return combined.rename(columns=new_cols)

st.title("📦 Advanced Inventory Manager")
tab1, tab2, tab3 = st.tabs(["📊 Usage Transactions", "📦 Current Inventory", "🛒 3-Month Shopping List"])

# ==========================================
# TAB 1: USAGE & AMU
# ==========================================
with tab1:
    st.header("1. Upload Usage & Calculate AMU")
    f1 = st.file_uploader("Upload Distribution Sheet(s)", accept_multiple_files=True, key="u1")
    if f1:
        df1 = process_upload(f1, 1)
        df1['created'] = pd.to_datetime(df1['created'], errors='coerce')
        df1['amount'] = pd.to_numeric(df1['amount'], errors='coerce').fillna(0)
        
        # Consolidation Logic
        res = df1.groupby('inventoryitem').agg({'amount':'sum', 'price':'last', 'created':'min', 'inventorytype':'first'}).reset_index()
        res['Months'] = ((current_date - res['created']).dt.days / 30.44).clip(lower=0.1).round(2)
        res['AMU'] = (res['amount'] / res['Months']).round(2)
        st.session_state.tab1_data = res.rename(columns={'inventoryitem':'Item','inventorytype':'Type','amount':'TotalUsed','price':'Price','created':'OldestDate'})

    if not st.session_state.tab1_data.empty:
        s1 = st.text_input("🔍 Search Usage...", key="s1").lower()
        view1 = st.session_state.tab1_data.copy()
        if s1: view1 = view1[view1['Item'].astype(str).str.lower().str.contains(s1)]
        st.dataframe(view1.style.set_properties(subset=['Months','AMU'], **{'background-color':'#e1f5fe'}))

# ==========================================
# TAB 2: INVENTORY & PURPLE CHECK
# ==========================================
with tab2:
    st.header("2. Current Stock")
    f2 = st.file_uploader("Upload Inventory Sheet(s)", accept_multiple_files=True, key="u2")
    if f2:
        df2 = process_upload(f2, 2)
        df2['branchamount'] = pd.to_numeric(df2['branchamount'], errors='coerce').fillna(0)
        df2['masteramount'] = pd.to_numeric(df2['masteramount'], errors='coerce').fillna(0)
        df2['TotalStock'] = df2['branchamount'] + df2['masteramount']
        
        amu_map = st.session_state.tab1_data.set_index('Item')['AMU'].to_dict() if not st.session_state.tab1_data.empty else {}
        df2['AMU'] = df2['type'].map(amu_map).fillna(0)
        df2['Order_Month'] = m1
        st.session_state.tab2_data = df2

    if not st.session_state.tab2_data.empty:
        s2 = st.text_input("🔍 Search Inventory...", key="s2").lower()
        view2 = st.session_state.tab2_data.copy()
        if s2: view2 = view2[view2['name'].astype(str).str.lower().str.contains(s2)]

        def purple_style(row):
            tab1_items = st.session_state.tab1_data['Item'].tolist() if not st.session_state.tab1_data.empty else []
            color = 'background-color: #e6e6fa' if row['type'] not in tab1_items else ''
            return [color] * len(row)
        
        st.dataframe(view2.style.apply(purple_style, axis=1))

# ==========================================
# TAB 3: SHOPPING & COLOR LOGIC
# ==========================================
with tab3:
    if not st.session_state.tab2_data.empty:
        df3 = st.session_state.tab2_data.copy()
        types = st.multiselect("Filter Type", options=df3['type'].unique(), default=df3['type'].unique())
        
        # Trigger: Master must be 0
        shop_pool = df3[(df3['masteramount'] <= 0) & (df3['type'].isin(types))]

        def shop_color(row):
            b, amu = row['branchamount'], row['AMU']
            if b <= 0: return ['background-color: #ff4b4b; color: white'] * len(row) # RED
            if b <= amu: return ['background-color: #e67e22; color: white'] * len(row) # ORANGE
            return ['background-color: #f1c40f; color: black'] * len(row) # YELLOW

        cols = st.columns(3)
        for i, month in enumerate(month_options):
            with cols[i]:
                st.subheader(month)
                m_df = shop_pool[shop_pool['Order_Month'] == month]
                if not m_df.empty:
                    st.dataframe(m_df[['name','branchamount','AMU']].style.apply(shop_color, axis=1))
