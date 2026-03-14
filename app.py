import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

st.set_page_config(page_title="Inventory Management System", layout="wide")

# --- 1. Initialize Session State (The App's Memory) ---
if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame(columns=[
        'Item name', 'Item Type', 'Branch amount', 'Master amount', 
        'Average monthly usage', 'Item price', 'Order_Month'
    ])
if 'amu_mapping' not in st.session_state:
    st.session_state.amu_mapping = {}

# --- 2. App Header ---
st.title("📦 Inventory & Shopping List Manager")
st.info("Tip: Upload or Add usage data in Tab 1 first to auto-calculate your Shopping List.")

# --- 3. Create Tabs ---
tab1, tab2, tab3 = st.tabs(["📊 Average Monthly Usage", "📦 Inventory Items", "🛒 Shopping List"])

# ==========================================
# TAB 1: AVERAGE MONTHLY USAGE
# ==========================================
with tab1:
    st.header("Usage Calculations")
    
    with st.expander("➕ Add Usage Entry Manually"):
        with st.form("usage_form"):
            u_name = st.text_input("Item Name")
            u_amount = st.number_input("Distributed Amount", min_value=0)
            u_date = st.date_input("Date Created", value=datetime.now())
            if st.form_submit_button("Add Entry"):
                # For manual entry, we just simulate a distribution record
                st.success(f"Recorded {u_amount} units for {u_name}")

    file1 = st.file_uploader("Upload Distribution Sheet (Excel)", type=['xlsx'])
    
    if file1:
        df1 = pd.read_excel(file1)
        # Consolidate logic
        df1['Date created'] = pd.to_datetime(df1['Date created'])
        consolidated = df1.groupby('Item name').agg({'Amount':'sum', 'Date created':'min'}).reset_index()
        
        # AMU Calculation
        months_diff = (datetime.now() - consolidated['Date created']).dt.days / 30.44
        months_diff = np.maximum(1, months_diff)
        consolidated['AMU'] = (consolidated['Amount'] / months_diff).round(2)
        
        st.session_state.amu_mapping = consolidated.set_index('Item name')['AMU'].to_dict()
        st.success("Calculations Complete!")
        st.dataframe(consolidated[['Item name', 'Amount', 'AMU']], use_container_width=True)

# ==========================================
# TAB 2: INVENTORY ITEMS
# ==========================================
with tab2:
    st.header("Inventory Management")

    with st.expander("➕ Add New Inventory Item Manually"):
        with st.form("inv_form"):
            col1, col2 = st.columns(2)
            name = col1.text_input("Item Name")
            itype = col2.text_input("Item Type")
            b_amt = col1.number_input("Branch Amount", min_value=0)
            m_amt = col2.number_input("Master Amount", min_value=0)
            price = col1.number_input("Item Price", min_value=0.0)
            
            if st.form_submit_button("Add to Master Inventory"):
                if name:
                    # Get AMU from Tab 1 if it exists
                    amu = st.session_state.amu_mapping.get(name, 0.0)
                    new_row = pd.DataFrame([{
                        'Item name': name, 'Item Type': itype, 'Branch amount': b_amt,
                        'Master amount': m_amt, 'Average monthly usage': amu, 
                        'Item price': price, 'Order_Month': datetime.now().strftime('%B %Y')
                    }])
                    st.session_state.master_df = pd.concat([st.session_state.master_df, new_row], ignore_index=True)
                    st.rerun()

    file2 = st.file_uploader("Upload Inventory Sheet (Excel)", type=['xlsx'])
    if file2:
        df2 = pd.read_excel(file2)
        # Apply Tab 1 AMU to uploaded items
        if st.session_state.amu_mapping:
            df2['Average monthly usage'] = df2['Item name'].map(st.session_state.amu_mapping).fillna(df2.get('Average monthly usage', 0))
        st.session_state.master_df = df2
        st.success("Inventory Loaded!")

    if st.button("🗑️ Clear All Data"):
        st.session_state.master_df = pd.DataFrame(columns=st.session_state.master_df.columns)
        st.rerun()

    st.write("### Current Inventory Table")
    st.dataframe(st.session_state.master_df, use_container_width=True)

# ==========================================
# TAB 3: SHOPPING LIST
# ==========================================
with tab3:
    st.header("Final Shopping List")

    if not st.session_state.master_df.empty:
        df = st.session_state.master_df.copy()
        
        # --- ACTION BUTTONS ---
        st.subheader("Edit/Move Items")
        item_select = st.selectbox("Select Item to Edit", options=df['Item name'].tolist())
        
        c1, c2, c3 = st.columns(3)
        if c1.button("❌ Remove Item"):
            st.session_state.master_df = st.session_state.master_df[st.session_state.master_df['Item name'] != item_select]
            st.rerun()
            
        if c2.button("📅 Move to Next Month"):
            next_m = (datetime.now() + pd.DateOffset(months=1)).strftime('%B %Y')
            st.session_state.master_df.loc[st.session_state.master_df['Item name'] == item_select, 'Order_Month'] = next_m
            st.success(f"Moved to {next_m}")
            st.rerun()

        budget = st.number_input("Set Monthly Budget ($)", value=5000.0)
        
        # --- LOGIC & HIGHLIGHTING ---
        # We define a "Shopping List" as items that are running low
        df['Total Cost'] = df['Average monthly usage'] * df['Item price'] # Assuming we buy 1 month of stock
        
        def highlight_stock(row):
            # 1. Out in BOTH (RED)
            if row['Master amount'] <= 0 and row['Branch amount'] <= 0:
                return ['background-color: #ff4b4b; color: white'] * len(row)
            # 2. Out in Master, but stock in Branch (YELLOW)
            if row['Master amount'] <= 0 and row['Branch amount'] > 0:
                return ['background-color: #f1c40f; color: black'] * len(row)
            return [''] * len(row)

        # Expected depletion column for Yellow items
        df['Branch Depletion Date'] = "N/A"
        mask = (df['Master amount'] <= 0) & (df['Branch amount'] > 0) & (df['Average monthly usage'] > 0)
        days_left = (df.loc[mask, 'Branch amount'] / df.loc[mask, 'Average monthly usage']) * 30.44
        df.loc[mask, 'Branch Depletion Date'] = (datetime.now() + pd.to_timedelta(days_left, unit='D')).dt.strftime('%Y-%m-%d')

        st.write("### Purchase Order Summary")
        # Sorting: Users can click column headers in the table below
        st.dataframe(df.style.apply(highlight_stock, axis=1), use_container_width=True)
        
        total_value = df['Total Cost'].sum()
        st.metric("Total Order Value", f"${total_value:,.2f}", delta=f"{budget - total_value} Remaining")
        
        if total_value > budget:
            st.warning("⚠️ You are over budget for this month!")

    else:
        st.warning("No items found. Please add items in Tab 2 or upload a file.")
