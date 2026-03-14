import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="Inventory Manager", layout="wide")

# --- 1. Persistence & Date Setup ---
if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame()
if 'amu_mapping' not in st.session_state:
    st.session_state.amu_mapping = {}
if 'price_mapping' not in st.session_state:
    st.session_state.price_mapping = {}

current_date = datetime.now()
month_options = [(current_date + timedelta(days=30*i)).strftime('%B %Y') for i in range(12)]

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
        'Item price': ['price', 'cost', 'rate', 'unit price'],
        'Order_Month': ['month', 'order month', 'purchase month']
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
    st.header("1. Reference Data (Usage & Prices)")
    
    with st.expander("➕ Add Item Reference Manually"):
        with st.form("manual_usage_form"):
            m_name = st.text_input("Item Name")
            m_price = st.number_input("Unit Price", min_value=0.0, step=0.01)
            m_amu = st.number_input("Average Monthly Usage", min_value=0.0, step=0.1)
            if st.form_submit_button("Save Reference"):
                if m_name:
                    st.session_state.amu_mapping[m_name] = m_amu
                    st.session_state.price_mapping[m_name] = m_price
                    st.rerun()

    if st.session_state.amu_mapping or st.session_state.price_mapping:
        st.write("### 📝 Manual Reference List")
        
        # --- HEADER ROW ---
        h1, h2, h3, h4 = st.columns([3, 2, 2, 1])
        h1.markdown("**Item Name**")
        h2.markdown("**Item Price**")
        h3.markdown("**:blue[AMU (Calc)]**") # Highlighted title
        h4.write("")

        all_ref_items = sorted(set(list(st.session_state.amu_mapping.keys()) + list(st.session_state.price_mapping.keys())))
        for item in all_ref_items:
            c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
            c1.write(item)
            c2.write(f"${st.session_state.price_mapping.get(item, 0.0)}")
            # --- HIGHLIGHTED CALCULATED COLUMN ---
            amu_val = st.session_state.amu_mapping.get(item, 0.0)
            c3.markdown(f'<div style="background-color: #e1f5fe; padding: 5px; border-radius: 5px;">{amu_val}</div>', unsafe_allow_html=True)
            
            if c4.button("🗑️", key=f"del_ref_{item}"):
                st.session_state.amu_mapping.pop(item, None)
                st.session_state.price_mapping.pop(item, None)
                st.rerun()

    st.divider()
    f1 = st.file_uploader("Upload Distribution Sheet (Excel)", type=['xlsx'])
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
                st.success("Excel data imported!")

# ==========================================
# TAB 2: INVENTORY ITEMS
# ==========================================
with tab2:
    st.header("2. Current Stock")
    with st.expander("➕ Add New Stock Manually"):
        with st.form("inv_form"):
            n = st.text_input("Item Name")
            t = st.text_input("Item Type")
            b = st.number_input("Branch Qty", 0)
            m = st.number_input("Master Qty", 0)
            p = st.number_input("Price", value=float(st.session_state.price_mapping.get(n, 0.0)))
            if st.form_submit_button("Add to List"):
                row = pd.DataFrame([{'Item name': n, 'Item Type': t, 'Branch amount': b, 'Master amount': m, 
                                     'Average monthly usage': st.session_state.amu_mapping.get(n, 0.0), 
                                     'Item price': p, 'Order_Month': month_options[0]}])
                st.session_state.master_df = pd.concat([st.session_state.master_df, row], ignore_index=True)
                st.rerun()

    f2 = st.file_uploader("Upload Inventory Sheet", type=['xlsx'])
    if f2:
        df2 = auto_fix_columns(pd.read_excel(f2))
        df2['Average monthly usage'] = df2['Item name'].map(st.session_state.amu_mapping).fillna(0)
        if 'Item price' not in df2.columns:
            df2['Item price'] = df2['Item name'].map(st.session_state.price_mapping).fillna(0)
        if 'Order_Month' not in df2.columns:
            df2['Order_Month'] = month_options[0]
        st.session_state.master_df = df2
        st.success("Inventory Updated!")
    
    st.write("### 📋 Master Inventory List")
    if not st.session_state.master_df.empty:
        # --- HEADER ROW ---
        h1, h2, h3, h4, h5, h6 = st.columns([3, 2, 2, 2, 2, 1])
        h1.markdown("**Item (Type)**")
        h2.markdown("**Branch**")
        h3.markdown("**Master**")
        h4.markdown("**:blue[AMU (Calc)]**")
        h5.markdown("**:blue[Price]**")
        h6.write("")

        for i, row in st.session_state.master_df.iterrows():
            c1, c2, c3, c4, c5, c6 = st.columns([3, 2, 2, 2, 2, 1])
            c1.write(f"{row['Item name']} ({row['Item Type']})")
            c2.write(str(row['Branch amount']))
            c3.write(str(row['Master amount']))
            
            # --- HIGHLIGHTED CALCULATED COLUMNS ---
            c4.markdown(f'<div style="background-color: #e1f5fe; padding: 5px; border-radius: 5px;">{row["Average monthly usage"]}</div>', unsafe_allow_html=True)
            c5.markdown(f'<div style="background-color: #e1f5fe; padding: 5px; border-radius: 5px;">${row["Item price"]}</div>', unsafe_allow_html=True)
            
            if c6.button("🗑️", key=f"del_inv_{i}"):
                st.session_state.master_df = st.session_state.master_df.drop(i).reset_index(drop=True)
                st.rerun()
    else:
        st.info("Inventory is empty.")

# ==========================================
# TAB 3: SHOPPING LIST
# ==========================================
with tab3:
    st.header("3. Monthly Shopping List")
    if not st.session_state.master_df.empty:
        df = st.session_state.master_df.copy()
        for col in ['Master amount', 'Item price', 'Average monthly usage']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        search_q = st.text_input("🔍 Search items...", "").lower()
        view_month = st.selectbox("📅 Select Month:", month_options)
        
        mask = (df['Master amount'] <= 0) & \
               (df['Order_Month'] == view_month) & \
               (df['Item name'].astype(str).str.lower().str.contains(search_q))
        
        shop_df = df[mask].copy()

        if not shop_df.empty:
            shop_df['Cost'] = (shop_df['Average monthly usage'] * shop_df['Item price']).round(2)
            st.dataframe(shop_df[['Item name', 'Item Type', 'Branch amount', 'Average monthly usage', 'Cost']], use_container_width=True)
            st.metric(f"Total Estimate", f"${shop_df['Cost'].sum():,.2f}")
