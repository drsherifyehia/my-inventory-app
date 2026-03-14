import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io

st.set_page_config(page_title="Inventory Manager", layout="wide")

# --- 1. Initialize Session State ---
if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame(columns=[
        'Item name', 'Item Type', 'Branch amount', 'Master amount', 
        'Average monthly usage', 'Item price', 'Order_Month'
    ])
if 'amu_mapping' not in st.session_state:
    st.session_state.amu_mapping = {}

st.title("📦 Inventory & Shopping List Manager")

# --- 2. Helper Functions ---
def clean_columns(df):
    """Normalize column names to match the app logic."""
    df.columns = [str(c).strip() for c in df.columns]
    # Map common variations to our required names
    mapping = {
        'Date created': ['Date created', 'date created', 'Date', 'date', 'DATE'],
        'Item name': ['Item name', 'item name', 'Item', 'item', 'NAME'],
        'Amount': ['Amount', 'amount', 'Qty', 'QTY']
    }
    for standard, variations in mapping.items():
        for v in variations:
            if v in df.columns and standard not in df.columns:
                df.rename(columns={v: standard}, inplace=True)
    return df

# --- 3. Tabs ---
tab1, tab2, tab3 = st.tabs(["📊 Usage Calc", "📦 Inventory Items", "🛒 Shopping List"])

# TAB 1: USAGE CALCULATION
with tab1:
    st.header("Usage Analysis")
    file1 = st.file_uploader("Upload Distribution Sheet (Excel)", type=['xlsx'])
    
    if file1:
        try:
            df1 = pd.read_excel(file1)
            df1 = clean_columns(df1)
            
            if 'Date created' in df1.columns and 'Item name' in df1.columns:
                df1['Date created'] = pd.to_datetime(df1['Date created'])
                consolidated = df1.groupby('Item name').agg({'Amount':'sum', 'Date created':'min'}).reset_index()
                
                months_diff = (datetime.now() - consolidated['Date created']).dt.days / 30.44
                months_diff = np.maximum(1, months_diff)
                consolidated['AMU'] = (consolidated['Amount'] / months_diff).round(2)
                
                st.session_state.amu_mapping = consolidated.set_index('Item name')['AMU'].to_dict()
                st.success("Analysis Complete!")
                st.dataframe(consolidated[['Item name', 'Amount', 'AMU']], use_container_width=True)
            else:
                st.error("Error: The file must have 'Item name' and 'Date created' columns.")
        except Exception as e:
            st.error(f"Processing Error: {e}")

# TAB 2: INVENTORY ITEMS
with tab2:
    st.header("Inventory Management")
    with st.expander("➕ Add Item Manually"):
        with st.form("inv_form"):
            name = st.text_input("Item Name")
            b_amt = st.number_input("Branch Amount", min_value=0)
            m_amt = st.number_input("Master Amount", min_value=0)
            price = st.number_input("Price", min_value=0.0)
            if st.form_submit_button("Save"):
                amu = st.session_state.amu_mapping.get(name, 0.0)
                new_row = pd.DataFrame([{'Item name': name, 'Branch amount': b_amt, 'Master amount': m_amt, 'Average monthly usage': amu, 'Item price': price, 'Order_Month': datetime.now().strftime('%B %Y')}])
                st.session_state.master_df = pd.concat([st.session_state.master_df, new_row], ignore_index=True)
                st.rerun()

    file2 = st.file_uploader("Upload Master Sheet", type=['xlsx'])
    if file2:
        df2 = pd.read_excel(file2)
        df2 = clean_columns(df2)
        if st.session_state.amu_mapping:
            df2['Average monthly usage'] = df2['Item name'].map(st.session_state.amu_mapping).fillna(df2.get('Average monthly usage', 0))
        st.session_state.master_df = df2
        st.success("Inventory Loaded!")

# TAB 3: SHOPPING LIST
with tab3:
    st.header("Final Shopping List")
    if not st.session_state.master_df.empty:
        df = st.session_state.master_df.copy()
        
        # Action Buttons
        item_select = st.selectbox("Select Item to Edit/Move", options=df['Item name'].tolist())
        c1, c2 = st.columns(2)
        if c1.button("❌ Remove"):
            st.session_state.master_df = st.session_state.master_df[st.session_state.master_df['Item name'] != item_select]
            st.rerun()
        if c2.button("📅 Move to Next Month"):
            next_m = (datetime.now() + pd.DateOffset(months=1)).strftime('%B %Y')
            st.session_state.master_df.loc[st.session_state.master_df['Item name'] == item_select, 'Order_Month'] = next_m
            st.rerun()

        # Calculation & Highlight Logic
        df['Total Cost'] = (df['Average monthly usage'] * df['Item price']).round(2)
        
        def highlight(row):
            if row['Master amount'] <= 0 and row['Branch amount'] <= 0: return ['background-color: #ff4b4b; color: white'] * len(row)
            if row['Master amount'] <= 0 and row['Branch amount'] > 0: return ['background-color: #f1c40f; color: black'] * len(row)
            return [''] * len(row)

        st.dataframe(df.style.apply(highlight, axis=1), use_container_width=True)
        
        # --- DOWNLOAD BUTTON ---
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Shopping_List')
        st.download_button(label="📥 Download Shopping List (Excel)", data=output.getvalue(), file_name="shopping_list.xlsx", mime="application/vnd.ms-excel")
    else:
        st.info("No items. Please add them in Tab 2.")
