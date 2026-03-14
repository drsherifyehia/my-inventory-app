# --- TAB 3: MONTHLY SHOPPING LIST ---
with tab3:
    st.header("🗓️ Monthly Purchase Plan")
    
    if not st.session_state.master_df.empty:
        df = st.session_state.master_df.copy()
        
        # 1. Clean data for calculation
        df['Master amount'] = pd.to_numeric(df['Master amount'], errors='coerce').fillna(0)
        df['Branch amount'] = pd.to_numeric(df['Branch amount'], errors='coerce').fillna(0)
        df['Item price'] = pd.to_numeric(df['Item price'], errors='coerce').fillna(0)
        df['Average monthly usage'] = pd.to_numeric(df['Average monthly usage'], errors='coerce').fillna(0)
        
        # 2. Filter logic: Only show items that need attention
        # (Items out of stock OR items already assigned to a specific month)
        shopping_mask = (df['Master amount'] <= 0) | (df['Order_Month'].notna())
        df_to_buy = df[shopping_mask].copy()
        
        # 3. Calculate Cost (Price x Monthly Usage)
        df_to_buy['Monthly Cost'] = (df_to_buy['Average monthly usage'] * df_to_buy['Item price']).round(2)
        
        # 4. Group by Month and Show Tables
        if not df_to_buy.empty:
            months = df_to_buy['Order_Month'].unique()
            
            for month in months:
                month_name = month if str(month) != 'nan' else "Unassigned/Urgent"
                st.subheader(f"📅 {month_name}")
                
                month_df = df_to_buy[df_to_buy['Order_Month'] == month]
                total_month_cost = month_df['Monthly Cost'].sum()
                
                # Show the table for this specific month
                st.dataframe(month_df[['Item name', 'Item Type', 'Branch amount', 'Master amount', 'Item price', 'Monthly Cost']], use_container_width=True)
                
                # Show Total for the month
                st.metric(f"Total for {month_name}", f"${total_month_cost:,.2f}")
                st.divider()
        
        # 5. Move Items Tool (To adjust the months)
        st.write("### ⚙️ Move Items between Months")
        target_item = st.selectbox("Select Item to Reschedule", options=df['Item name'].unique())
        new_month = st.selectbox("Move to Month:", ["March 2026", "April 2026", "May 2026", "June 2026"])
        
        if st.button("Confirm Move"):
            st.session_state.master_df.loc[st.session_state.master_df['Item name'] == target_item, 'Order_Month'] = new_month
            st.success(f"Moved {target_item} to {new_month}")
            st.rerun()

    else:
        st.info("Inventory is empty. Please upload data in Tab 2.")
