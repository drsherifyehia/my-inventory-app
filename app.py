import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="Inventory Manager", layout="wide")

# --- Initialize Session State ---
if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame(columns=[
        'Item name', 'Item Type', 'Branch amount', 'Master amount', 
        'Average monthly usage', 'Item price', 'Order_Month'
    ])

# --- Main Tabs ---
tab1, tab2, tab3 = st.tabs(["📊 Usage Calc", "📦 Inventory Items", "🛒 Shopping List"])

# TAB 1: USAGE CALCULATION
with tab1:
    st.header("Upload Distribution Data")
    file1 = st.file_uploader("Upload Excel (Tab 1)", type=['xlsx'])
    if file1:
        st.success("File received! Processing usage averages...")
        # Logic to consolidate items would go here

# TAB 2: INVENTORY ITEMS
with tab2:
    st.header("Inventory Management")
    
    # --- MANUAL ADD SECTION ---
    with st.expander("➕ Click to Add Item Manually", expanded=False):
        with st.form("manual_add"):
            col1, col2 = st.columns(2)
            name = col1.text_input("Item Name")
            itype = col2.text_input("Item Type")
            b_amt = col1.number_input("Branch Amount", min_value=0)
            m_amt = col2.number_input("Master Amount", min_value=0)
            amu = col1.number_input("Avg Monthly Usage", min_value=0.0)
            price = col2.number_input("Price", min_value=0.0)
            
            if st.form_submit_button("Save to Inventory"):
                if name:
                    new_data = pd.DataFrame([{
                        'Item name': name, 'Item Type': itype, 'Branch amount': b_amt,
                        'Master amount': m_amt, 'Average monthly usage': amu, 
                        'Item price': price, 'Order_Month': datetime.now().strftime('%B %Y')
                    }])
                    st.session_state.master_df = pd.concat([st.session_state.master_df, new_data], ignore_index=True)
                    st.rerun()
                else:
                    st.error("Please enter an Item Name")

    st.divider()
    
    # --- UPLOAD SECTION ---
    file2 = st.file_uploader("Or Upload Master Sheet", type=['xlsx'])
    if file2:
        st.session_state.master_df = pd.read_excel(file2)
    
    if st.button("🗑️ Clear All Data"):
        st.session_state.master_df = pd.DataFrame(columns=st.session_state.master_df.columns)
        st.rerun()

    st.write("### Current Stock")
    st.dataframe(st.session_state.master_df, use_container_width=True)

# TAB 3: SHOPPING LIST
with tab3:
    st.header("Shopping List Actions")
    
    if not st.session_state.master_df.empty:
        df = st.session_state.master_df.copy()
        
        # --- ACTION BUTTONS ---
        st.write("### 🛠️ Edit List")
        c1, c2 = st.columns(2)
        
        with c1:
            to_remove = st.selectbox("Select to Remove", options=df['Item name'].unique())
            if st.button("❌ Remove Item"):
                st.session_state.master_df = st.session_state.master_df[st.session_state.master_df['Item name'] != to_remove]
                st.rerun()
        
        with c2:
            to_move = st.selectbox("Select to Delay", options=df['Item name'].unique())
            if st.button("📅 Move to Next Month"):
                next_m = (datetime.now() + timedelta(days=32)).strftime('%B %Y')
                st.session_state.master_df.loc[st.session_state.master_df['Item name'] == to_move, 'Order_Month'] = next_m
                st.success(f"Moved {to_move} to {next_m}")

        st.divider()

        # --- SHOPPING LIST LOGIC & HIGHLIGHTS ---
        # Logic: Show items where Master Amount is low
        shopping_list = df.copy()
        shopping_list['Total Value'] = shopping_list['Master amount'] * shopping_list['Item price']
        
        def highlight_rows(row):
            # Red: Out in both
            if row['Master amount'] <= 0 and row['Branch amount'] <= 0:
                return ['background-color: #ff4b4b; color: white'] * len(row)
            # Yellow: Out in Master, but Branch has stock
            if row['Master amount'] <= 0 and row['Branch amount'] > 0:
                return ['background-color: #f1c40f; color: black'] * len(row)
            return [''] * len(row)

        st.write("### 🛒 Final Purchase Order")
        st.dataframe(shopping_list.style.apply(highlight_rows, axis=1), use_container_width=True)
        
        st.metric("Total Order Value", f"${shopping_list['Total Value'].sum():,.2f}")
        
    else:
        st.info("The shopping list is empty. Add items in the 'Inventory Items' tab first.")
