import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="Inventory Manager", layout="wide")

# --- Initialize Session State ---
if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame(columns=['Item name', 'Item Type', 'Branch amount', 'Master amount', 'Average monthly usage', 'Item price', 'Order_Month'])

# --- Sidebar Manual Entry ---
st.sidebar.header("➕ Add Item Manually")
with st.sidebar.form("add_form"):
    new_name = st.text_input("Item Name")
    new_type = st.text_input("Item Type")
    new_branch = st.number_input("Branch Stock", min_value=0)
    new_master = st.number_input("Master Stock", min_value=0)
    new_amu = st.number_input("Avg Monthly Usage", min_value=0.0)
    new_price = st.number_input("Price", min_value=0.0)
    
    submit_add = st.form_submit_button("Add to Inventory")
    if submit_add and new_name:
        new_row = pd.DataFrame([{
            'Item name': new_name, 'Item Type': new_type, 'Branch amount': new_branch,
            'Master amount': new_master, 'Average monthly usage': new_amu, 'Item price': new_price,
            'Order_Month': datetime.now().strftime('%B %Y')
        }])
        st.session_state.master_df = pd.concat([st.session_state.master_df, new_row], ignore_index=True)
        st.success(f"Added {new_name}")

# --- Main Tabs ---
tab1, tab2, tab3 = st.tabs(["📊 Usage Calc", "📦 Inventory", "🛒 Shopping List"])

with tab1:
    st.header("Upload Distribution Data")
    file1 = st.file_uploader("Upload Excel", type=['xlsx'])
    if file1:
        # (Logic for processing Tab 1 remains the same as previous)
        st.info("File uploaded. Processed data will appear in Tab 2.")

with tab2:
    st.header("Master Inventory")
    # Button to clear all and start fresh
    if st.button("🗑️ Clear All Data"):
        st.session_state.master_df = pd.DataFrame(columns=['Item name', 'Item Type', 'Branch amount', 'Master amount', 'Average monthly usage', 'Item price', 'Order_Month'])
    
    # Upload and Merge
    file2 = st.file_uploader("Upload Master Sheet", type=['xlsx'], key="m_up")
    if file2:
        uploaded_df = pd.read_excel(file2)
        st.session_state.master_df = uploaded_df
    
    st.dataframe(st.session_state.master_df, use_container_width=True)

with tab3:
    st.header("Shopping List Actions")
    
    df = st.session_state.master_df.copy()
    
    if not df.empty:
        # Add Calculated Columns
        df['Total_Value'] = df['Master amount'] * df['Item price'] # Example calc
        
        # --- BUTTONS INTERFACE ---
        col1, col2, col3 = st.columns(3)
        
        with col1:
            item_to_remove = st.selectbox("Select Item to Remove", options=df['Item name'].tolist())
            if st.button("❌ Remove Item"):
                st.session_state.master_df = st.session_state.master_df[st.session_state.master_df['Item name'] != item_to_remove]
                st.rerun()

        with col2:
            item_to_move = st.selectbox("Select Item to Delay", options=df['Item name'].tolist())
            if st.button("📅 Move to Next Month"):
                # Logic: Find item and update its Order_Month
                next_month = (datetime.now() + timedelta(days=32)).strftime('%B %Y')
                st.session_state.master_df.loc[st.session_state.master_df['Item name'] == item_to_move, 'Order_Month'] = next_month
                st.success(f"Moved {item_to_move} to {next_month}")
                st.rerun()
        
        with col3:
            st.write("**Budget Management**")
            monthly_limit = st.number_input("Monthly Budget", value=1000.0)

        # --- Shopping List Logic (Highlighting) ---
        def apply_styles(row):
            if row['Master amount'] == 0 and row['Branch amount'] == 0:
                return ['background-color: #ff4b4b'] * len(row) # Red
            if row['Master amount'] == 0 and row['Branch amount'] > 0:
                return ['background-color: #ffeb3b'] * len(row) # Yellow
            return [''] * len(row)

        st.subheader("Final Order List")
        # Sorting is built-in to st.dataframe: click the column header!
        st.dataframe(df.style.apply(apply_styles, axis=1), use_container_width=True)
        
        total_cost = df['Total_Value'].sum()
        st.metric("Total Order Value", f"${total_cost:,.2f}", delta=f"{monthly_limit - total_cost} vs Budget")
    else:
        st.warning("No items in list. Add them manually or upload in Tab 2.")

