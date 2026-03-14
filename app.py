import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- App Configuration ---
st.set_page_config(page_title="Inventory Management System", layout="wide")
st.title("📦 Inventory & Shopping List Manager")

# Initialize session state to store data across tab clicks
if 'tab1_data' not in st.session_state:
    st.session_state.tab1_data = None
if 'tab2_data' not in st.session_state:
    st.session_state.tab2_data = None
if 'shopping_list' not in st.session_state:
    st.session_state.shopping_list = None

# --- Create Tabs ---
tab1, tab2, tab3 = st.tabs(["Average Monthly Usage", "Inventory Items", "Shopping List"])

# ==========================================
# TAB 1: AVERAGE MONTHLY USAGE
# ==========================================
with tab1:
    st.header("Master to Branch Distribution")
    st.write("Upload the distribution record sheet (Item name, Inventory type, Amount, Date created).")
    
    file1 = st.file_uploader("Upload Distribution Sheet (Excel)", type=['xlsx'], key='file1')
    
    if file1:
        df1 = pd.read_excel(file1)
        
        # Ensure correct date format
        df1['Date created'] = pd.to_datetime(df1['Date created'])
        
        # Consolidate by Item Name
        # 1. Sum the amounts
        # 2. Find the earliest date the item was created/distributed to calculate duration
        consolidated = df1.groupby('Item name').agg(
            Total_Amount=('Amount', 'sum'),
            First_Date=('Date created', 'min'),
            Inventory_type=('Inventory type', 'first')
        ).reset_index()
        
        # Calculate Average Monthly Usage (AMU)
        current_date = pd.to_datetime('today')
        # Calculate months elapsed (minimum 1 month to avoid dividing by zero or inflating numbers)
        consolidated['Months_Elapsed'] = (current_date - consolidated['First_Date']).dt.days / 30.44
        consolidated['Months_Elapsed'] = np.maximum(1, consolidated['Months_Elapsed']) 
        
        consolidated['Calculated_AMU'] = (consolidated['Total_Amount'] / consolidated['Months_Elapsed']).round(2)
        
        st.session_state.tab1_data = consolidated[['Item name', 'Calculated_AMU']]
        
        st.success("Data consolidated successfully!")
        st.dataframe(consolidated)

# ==========================================
# TAB 2: INVENTORY ITEMS
# ==========================================
with tab2:
    st.header("Current Inventory Status")
    st.write("Upload the current inventory sheet (Item name, Item Type, Branch amount, Master amount, Average monthly usage, Item price).")
    
    file2 = st.file_uploader("Upload Inventory Sheet (Excel)", type=['xlsx'], key='file2')
    
    if file2:
        df2 = pd.read_excel(file2)
        
        # Overwrite/Update Average Monthly Usage from Tab 1 if available
        if st.session_state.tab1_data is not None:
            # Merge Tab 1 AMU into Tab 2 data
            df2 = df2.merge(st.session_state.tab1_data, on='Item name', how='left')
            # Use Tab 1 calculation where available, otherwise keep original
            df2['Average monthly usage'] = df2['Calculated_AMU'].fillna(df2['Average monthly usage'])
            df2 = df2.drop(columns=['Calculated_AMU'])
            st.info("Average Monthly Usage updated using calculations from Tab 1.")
        else:
            st.warning("Tab 1 data not found. Using default Average Monthly Usage from uploaded sheet.")
            
        st.session_state.tab2_data = df2
        st.dataframe(df2)

# ==========================================
# TAB 3: SHOPPING LIST
# ==========================================
with tab3:
    st.header("Shopping List & Purchase Orders")
    
    if st.session_state.tab2_data is not None:
        df3 = st.session_state.tab2_data.copy()
        
        # Calculate expected depletion dates
        current_date = datetime.now()
        
        # Avoid division by zero for AMU
        safe_amu = np.where(df3['Average monthly usage'] > 0, df3['Average monthly usage'], 1)
        
        # Master out of stock calculation
        df3['Months_Left_Master'] = df3['Master amount'] / safe_amu
        
        # Branch out of stock calculation
        df3['Months_Left_Branch'] = df3['Branch amount'] / safe_amu
        df3['Branch_Empty_Date'] = current_date + pd.to_timedelta(df3['Months_Left_Branch'] * 30.44, unit='D')
        df3['Branch_Empty_Date'] = df3['Branch_Empty_Date'].dt.strftime('%Y-%m-%d')
        
        # Initialize order month
        if 'Order_Month' not in df3.columns:
            df3['Order_Month'] = current_date.strftime('%B %Y')
            
        # Determine items to order (Master stock is low/empty or will run out soon)
        # For this example, we auto-add items where Master stock <= AMU (less than 1 month left)
        shopping_df = df3[df3['Master amount'] <= df3['Average monthly usage']].copy()
        
        # Set default order quantity (e.g., 3 months worth of AMU)
        shopping_df['Order_Quantity'] = (shopping_df['Average monthly usage'] * 3).round(0)
        shopping_df['Total_Value'] = shopping_df['Order_Quantity'] * shopping_df['Item price']
        
        # Styling function for Red/Yellow highlights
        def highlight_stock(row):
            # Red: Out in both Master and Branch
            if row['Master amount'] <= 0 and row['Branch amount'] <= 0:
                return ['background-color: #ffcccc; color: #990000'] * len(row)
            # Yellow: Out in Master, but stock in Branch exists
            elif row['Master amount'] <= 0 and row['Branch amount'] > 0:
                return ['background-color: #ffffcc; color: #888800'] * len(row)
            return [''] * len(row)

        st.write("### Interactive Shopping List")
        st.write("Use the table below to **Edit amounts**, **Add rows**, or **Delete items**. Click column headers to **Sort**.")
        
        # Budget Input
        col1, col2 = st.columns(2)
        with col1:
            monthly_budget = st.number_input("Set Monthly Purchase Budget ($):", min_value=0.0, value=5000.0)
        
        # Interactive Editor (Fulfills Add, Remove, Edit requirements natively)
        edited_shopping_df = st.data_editor(
            shopping_df[['Item name', 'Master amount', 'Branch amount', 'Average monthly usage', 'Branch_Empty_Date', 'Item price', 'Order_Quantity', 'Total_Value', 'Order_Month']],
            num_rows="dynamic", # Enables adding/removing rows natively
            use_container_width=True
        )
        
        # Apply highlights to a static view below for clarity, as Streamlit data_editor doesn't support complex row styling yet
        st.write("### Stock Alert Status")
        st.dataframe(edited_shopping_df.style.apply(highlight_stock, axis=1), use_container_width=True)
        
        # Recalculate Totals based on edits
        edited_shopping_df['Total_Value'] = edited_shopping_df['Order_Quantity'] * edited_shopping_df['Item price']
        total_order_value = edited_shopping_df['Total_Value'].sum()
        
        # Dashboard metrics
        st.write("---")
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Order Value", f"${total_order_value:,.2f}")
        m2.metric("Monthly Budget", f"${monthly_budget:,.2f}")
        
        if total_order_value > monthly_budget:
            m3.error(f"Over Budget by: ${total_order_value - monthly_budget:,.2f}")
        else:
            m3.success(f"Remaining Budget: ${monthly_budget - total_order_value:,.2f}")
            
    else:
        st.info("Please upload data in Tab 2 to generate the Shopping List.")
