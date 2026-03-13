from db_helper import init_db, load_products, load_bom, add_product, delete_product, add_bom_entry
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(page_title="Planning of Production Lines",
                   page_icon="🏭", layout="wide")

init_db()


def forecast_demand(demand_history, periods_ahead=6):
    demand_history = [float(x) for x in demand_history]
    weights = np.arange(1, len(demand_history) + 1, dtype=float)
    weights /= weights.sum()
    weighted_avg = np.dot(demand_history, weights)
    trend = (demand_history[-1] - demand_history[0]) / len(demand_history)
    forecast = [max(0, round(weighted_avg + trend * i))
                for i in range(1, periods_ahead + 1)]
    return forecast


def lot_for_lot(demands, initial_inv, safety_stock):
    schedule = []
    inventory = float(initial_inv)
    total_produced = 0
    for i, d in enumerate(demands):
        d = float(d)
        net_req = max(0, d + float(safety_stock) - inventory)
        production = net_req
        inventory = inventory + production - d
        total_produced += production
        schedule.append({
            "Week": i + 1, "Demand": d, "Net_Requirement": net_req,
            "Production_Order": production, "Ending_Inventory": inventory,
        })
    return pd.DataFrame(schedule), total_produced


def eoq_planning(demands, initial_inv, safety_stock, setup_cost, holding_cost):
    demands = [float(x) for x in demands]
    avg_demand = np.mean(demands)
    holding_cost = float(holding_cost)
    setup_cost = float(setup_cost)
    if holding_cost <= 0:
        holding_cost = 0.01
    eoq = math.ceil(math.sqrt(2 * avg_demand * len(demands)
                    * setup_cost / holding_cost))
    schedule = []
    inventory = float(initial_inv)
    total_produced = 0
    for i, d in enumerate(demands):
        if inventory - d < float(safety_stock):
            net_req = d + float(safety_stock) - inventory
            production = max(eoq, net_req)
        else:
            production = 0
        inventory = inventory + production - d
        total_produced += production
        schedule.append({
            "Week": i + 1, "Demand": d, "EOQ": eoq,
            "Production_Order": production, "Ending_Inventory": inventory,
        })
    return pd.DataFrame(schedule), total_produced, eoq


def fixed_period_planning(demands, initial_inv, safety_stock, periods_per_order=3):
    demands = [float(x) for x in demands]
    schedule = []
    inventory = float(initial_inv)
    total_produced = 0
    n = len(demands)
    for i in range(n):
        if i % periods_per_order == 0:
            batch_end = min(i + periods_per_order, n)
            batch_demand = sum(demands[i:batch_end])
            net_req = max(0, batch_demand + float(safety_stock) - inventory)
            production = net_req
        else:
            production = 0
        inventory = inventory + production - demands[i]
        total_produced += production
        schedule.append({
            "Week": i + 1, "Demand": demands[i],
            "Production_Order": production, "Ending_Inventory": inventory,
        })
    return pd.DataFrame(schedule), total_produced


def mrp_explosion(product_name, planned_orders, bom_df):
    components = bom_df[bom_df["Parent_Product"] == product_name]
    if components.empty:
        return None
    results = []
    for _, comp in components.iterrows():
        for week, order_qty in enumerate(planned_orders):
            if order_qty > 0:
                results.append({
                    "Component": comp["Component"],
                    "Week_Needed": week + 1,
                    "Qty_Per_Unit": comp["Quantity_Per_Unit"],
                    "Parent_Order": order_qty,
                    "Component_Requirement": round(order_qty * comp["Quantity_Per_Unit"], 2),
                    "Order_Release_Week": max(1, week + 1 - int(comp["Component_Lead_Time_Days"]) // 7),
                    "Component_Cost": round(order_qty * comp["Quantity_Per_Unit"] * comp["Component_Unit_Cost"], 2),
                })
    return pd.DataFrame(results) if results else None


st.sidebar.title("🏭 Planning of Production Lines")
page = st.sidebar.radio("Navigation", [
    "ℹ️ About",
    "📊 Dashboard",
    "📦 Product Data",
    "📋 Bill of Materials",
    "📥 Data Collection",
    "📈 Demand Forecast",
    "🏭 Production Planning",
    "🔧 MRP Explosion",
    "📉 Cost Analysis",
])

products_df = load_products()
bom_df = load_bom()
demand_cols = [
    c for c in products_df.columns if c.startswith("Past_Demand_Week")]

if page == "ℹ️ About":
    st.title("🏭 Planning of Production Lines")
    st.caption("Capstone Project — Industrial Engineering")
    st.markdown("---")

    st.header("📌 Project Overview")
    st.markdown("""
    **Planning of Production Lines** is a capstone project developed by Industrial Engineering students.

    In this project, we aim to develop an application for **planning and scheduling
    of different production types** based on given data related to their past demands,
    consumption coefficients, lead-times (duration times), and costs.

    Different types of production planning methods with different objective functions
    are implemented. The data related to products is collected from **real-life cases**.
    """)

    st.header("🎯 Key Features")
    st.markdown("""
    - ✅ **Real-life products' data** — collected from actual factories and suppliers
    - ✅ **Multiple production planning methods** — L4L, EOQ, Fixed Period, MRP
    - ✅ **Interactive web application** — to solve production planning problems
    - ✅ **Cost optimization** — compare methods and find the cheapest strategy
    - ✅ **Material Requirements Planning** — explode BOM into component needs
    - ✅ **Demand forecasting** — predict future demand from historical data
    - ✅ **Data collection portal** — team members can enter real factory data
    """)

    st.header("🎯 What is Production Line Planning?")
    st.markdown("""
    **Production line planning** is the process of determining **what to produce,
    how much to produce, and when to produce** to meet customer demand efficiently
    while minimizing costs.

    It is used in industries such as:
    - 🪑 **Furniture Manufacturing** — Planning wood cutting, assembly, finishing lines
    - 💻 **Electronics Assembly** — Planning circuit board production, device assembly
    - 📦 **Packaging Industry** — Planning container/box production runs
    - 🚗 **Automotive** — Planning parts manufacturing and assembly sequences
    - 💊 **Pharmaceuticals** — Planning batch production of medicines
    """)

    st.header("🔧 Production Planning Methods in This App")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1️⃣ Lot-for-Lot (L4L)")
        st.markdown("""
        - Produce **exactly what is needed** each period
        - **Zero excess inventory**
        - Best for: **Expensive items, custom/make-to-order products**
        - Example: Custom furniture, specialized machinery
        - ✅ Low holding cost | ❌ High setup cost (frequent setups)
        """)

        st.subheader("2️⃣ Economic Order Quantity (EOQ)")
        st.markdown("""
        - Calculates the **optimal batch size** that minimizes total cost
        - Balances **setup cost vs holding cost**
        - Best for: **Stable demand, repetitive manufacturing**
        - Example: Electronics components, consumer goods
        - ✅ Balanced costs | ❌ Assumes constant demand
        """)

    with col2:
        st.subheader("3️⃣ Fixed Period Requirements")
        st.markdown("""
        - Groups demand over **fixed time periods** (e.g., every 3 weeks)
        - Produces in **batches** to cover multiple periods
        - Best for: **Batch production, seasonal items**
        - Example: Food products, pharmaceuticals
        - ✅ Fewer setups | ❌ Higher inventory levels
        """)

        st.subheader("4️⃣ MRP (Material Requirements Planning)")
        st.markdown("""
        - **Explodes** finished product orders into **component requirements**
        - Uses **Bill of Materials (BOM)** to calculate raw material needs
        - Best for: **Assembly operations, complex products**
        - Example: Cars (need engines, tires, seats), Computers (need CPU, RAM, screen)
        - ✅ Precise material planning | ❌ Requires accurate BOM data
        """)

    st.header("👥 Team & Data Collection")
    st.markdown("""
    | Team Member | Role | Data Responsibility |
    |---|---|---|
    | **Member 1** | Lead Developer | App development, system integration |
    | **Member 2** | Data Engineer | Collect furniture/manufacturing data from real factories |
    | **Member 3** | Data Engineer | Collect electronics/packaging data from real suppliers |

    ### 📋 Data to Collect from Real Factories:
    1. **Product names** and categories
    2. **Weekly/monthly demand** data (at least 6 periods)
    3. **Lead times** — how long it takes to produce each product
    4. **Setup costs** — cost to start a production run
    5. **Holding costs** — cost to store one unit per period
    6. **Bill of Materials** — what components/raw materials are needed
    7. **Component quantities** — how many of each component per finished product
    """)

    st.header("🚀 How to Use This App")
    st.markdown("""
    1. **📥 Data Collection** → Team members enter real factory data
    2. **📦 Product Data** → View/manage all products in the database
    3. **📋 Bill of Materials** → Define component relationships
    4. **📈 Demand Forecast** → Predict future demand from historical data
    5. **🏭 Production Planning** → Compare L4L, EOQ, Fixed Period methods
    6. **🔧 MRP Explosion** → Calculate raw material requirements
    7. **📉 Cost Analysis** → Find the cheapest production strategy
    """)

    st.info(
        "💡 **All data is saved in a SQLite database** — it persists between sessions!")

elif page == "📊 Dashboard":
    st.title("📊 Dashboard")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Products", len(products_df))
    col2.metric("Categories", products_df["Category"].nunique())
    col3.metric("Avg Weekly Demand", round(
        products_df[demand_cols].mean().mean(), 1))
    col4.metric("BOM Components", bom_df["Component"].nunique())

    st.subheader("Demand Overview (Last 6 Weeks)")
    demand_melted = products_df.melt(
        id_vars=["Product"], value_vars=demand_cols, var_name="Week", value_name="Demand")
    demand_melted["Week"] = demand_melted["Week"].str.replace(
        "Past_Demand_Week", "W")
    fig = px.line(demand_melted, x="Week", y="Demand", color="Product",
                  title="Historical Demand by Product", markers=True)
    st.plotly_chart(fig, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        cat_demand = products_df.groupby(
            "Category")[demand_cols[-1]].sum().reset_index()
        cat_demand.columns = ["Category", "Latest_Week_Demand"]
        fig2 = px.pie(cat_demand, values="Latest_Week_Demand",
                      names="Category", title="Latest Week Demand by Category")
        st.plotly_chart(fig2, use_container_width=True)
    with col_b:
        fig3 = px.bar(products_df, x="Product", y="Lead_Time_Days",
                      title="Lead Times", color="Category")
        st.plotly_chart(fig3, use_container_width=True)

elif page == "📦 Product Data":
    st.title("📦 Product Data Management")
    st.subheader("Current Products")
    st.dataframe(products_df.drop(columns=["ID"]), use_container_width=True)

    st.subheader("Delete Product")
    del_product = st.selectbox(
        "Select product to delete", products_df["Product"].tolist(), key="del_prod")
    if st.button("🗑️ Delete Product"):
        delete_product(del_product)
        st.success(f"Deleted '{del_product}'!")
        st.rerun()

    st.subheader("Add New Product")
    with st.form("add_product"):
        cols = st.columns(3)
        new_name = cols[0].text_input("Product Name")
        new_cat = cols[1].selectbox(
            "Category", ["Furniture", "Electronics", "Packaging", "Other"])
        new_lt = cols[2].number_input("Lead Time (days)", min_value=1, value=3)
        cols2 = st.columns(6)
        new_demands = []
        for i in range(6):
            new_demands.append(cols2[i].number_input(
                f"Demand W{i+1}", min_value=0, value=50))
        cols3 = st.columns(4)
        new_setup = cols3[0].number_input("Setup Cost", min_value=0, value=300)
        new_hold = cols3[1].number_input(
            "Holding Cost/Unit", min_value=0.0, value=1.0)
        new_unit = cols3[2].number_input("Unit Cost", min_value=0, value=20)
        new_ss = cols3[3].number_input("Safety Stock", min_value=0, value=10)
        submitted = st.form_submit_button("Add Product")
        if submitted and new_name:
            add_product(new_name, new_cat, new_demands, new_lt,
                        new_setup, new_hold, new_unit, new_ss)
            st.success(f"Added '{new_name}' to database!")
            st.rerun()

elif page == "📋 Bill of Materials":
    st.title("📋 Bill of Materials (BOM)")
    st.dataframe(bom_df.drop(columns=["ID"]), use_container_width=True)
    products_with_bom = bom_df["Parent_Product"].unique()
    if len(products_with_bom) > 0:
        selected = st.selectbox("View BOM for:", products_with_bom)
        filtered = bom_df[bom_df["Parent_Product"] == selected]
        fig = px.bar(filtered, x="Component", y="Quantity_Per_Unit", title=f"Components for {selected}",
                     text="Quantity_Per_Unit", color="Component_Unit_Cost", color_continuous_scale="blues")
        st.plotly_chart(fig, use_container_width=True)
    st.subheader("Add BOM Entry")
    with st.form("add_bom"):
        bc = st.columns(5)
        bom_parent = bc[0].selectbox(
            "Parent Product", products_df["Product"].tolist())
        bom_comp = bc[1].text_input("Component Name")
        bom_qty = bc[2].number_input("Qty Per Unit", min_value=0.1, value=1.0)
        bom_lt = bc[3].number_input(
            "Component Lead Time (days)", min_value=1, value=2)
        bom_cost = bc[4].number_input(
            "Component Unit Cost", min_value=0.0, value=5.0)
        if st.form_submit_button("Add BOM Entry") and bom_comp:
            add_bom_entry(bom_parent, bom_comp, bom_qty, bom_lt, bom_cost)
            st.success(f"Added '{bom_comp}' to BOM for '{bom_parent}'!")
            st.rerun()

elif page == "📥 Data Collection":
    st.title("📥 Data Collection Portal")
    st.markdown("""
    ### 👷 For Team Members
    Use this page to enter **real-life product data** collected from factories and suppliers.
    Each team member should collect data for their assigned industry.
    """)

    st.header("➕ Add Product with Full Details")
    collector_name = st.text_input("Your Name (Data Collector)")
    data_source = st.text_input(
        "Data Source (e.g., 'ABC Furniture Factory, Kabul')")

    with st.form("collect_product"):
        st.subheader("Product Information")
        cp = st.columns(3)
        c_name = cp[0].text_input("Product Name", key="cp_name")
        c_cat = cp[1].selectbox("Industry/Category",
                                ["Furniture", "Electronics", "Packaging", "Food & Beverage",
                                 "Automotive", "Textile", "Pharmaceutical", "Other"], key="cp_cat")
        c_lt = cp[2].number_input("Lead Time (days) — how long to produce",
                                  min_value=1, value=3, key="cp_lt")

        st.subheader("📊 Weekly Demand Data (6 weeks)")
        st.caption("Enter the actual demand/sales data from the factory records")
        cd = st.columns(6)
        c_demands = []
        for i in range(6):
            c_demands.append(cd[i].number_input(
                f"Week {i+1}", min_value=0, value=0, key=f"cp_d{i}"))

        st.subheader("💰 Cost Information")
        cc = st.columns(4)
        c_setup = cc[0].number_input("Setup Cost ($) — cost to start production run",
                                     min_value=0, value=0, key="cp_setup")
        c_hold = cc[1].number_input("Holding Cost ($/unit/week) — storage cost",
                                    min_value=0.0, value=0.0, key="cp_hold")
        c_unit = cc[2].number_input("Unit Cost ($) — cost to produce one item",
                                    min_value=0, value=0, key="cp_unit")
        c_ss = cc[3].number_input("Safety Stock — minimum inventory to keep",
                                  min_value=0, value=0, key="cp_ss")

        st.subheader("🔩 Components / Raw Materials (Optional)")
        st.caption(
            "If this product has components, add them after submitting the product via the BOM page")

        c_notes = st.text_area(
            "Notes (where did you get this data, any special conditions?)")

        if st.form_submit_button("📥 Submit Product Data"):
            if c_name and collector_name and sum(c_demands) > 0:
                add_product(c_name, c_cat, c_demands, c_lt,
                            c_setup, c_hold, c_unit, c_ss)
                st.success(
                    f"✅ Product '{c_name}' submitted by {collector_name}!")
                st.info(f"📌 Source: {data_source}")
                if c_notes:
                    st.info(f"📝 Notes: {c_notes}")
                st.balloons()
                st.rerun()
            else:
                st.error(
                    "Please fill in: your name, product name, and at least one week of demand data.")

    st.markdown("---")
    st.header("📥 Bulk Upload via CSV")
    st.markdown("""
    You can also upload a CSV file with multiple products at once.
    The CSV must have these columns:
    """)
    sample_csv = pd.DataFrame({
        "Product": ["Example Product"],
        "Category": ["Furniture"],
        "Demand_W1": [100], "Demand_W2": [110], "Demand_W3": [105],
        "Demand_W4": [120], "Demand_W5": [115], "Demand_W6": [125],
        "Lead_Time_Days": [3],
        "Setup_Cost": [500], "Holding_Cost": [2.0],
        "Unit_Cost": [25], "Safety_Stock": [20],
    })
    st.dataframe(sample_csv, use_container_width=True)
    st.download_button("📄 Download CSV Template", sample_csv.to_csv(index=False),
                       "product_template.csv", "text/csv")

    uploaded = st.file_uploader("Upload CSV file", type=["csv"])
    if uploaded is not None:
        try:
            csv_df = pd.read_csv(uploaded)
            st.dataframe(csv_df, use_container_width=True)
            if st.button("📥 Import All Products"):
                count = 0
                for _, r in csv_df.iterrows():
                    demands = [int(r.get(f"Demand_W{i+1}", 0))
                               for i in range(6)]
                    add_product(
                        str(r["Product"]), str(r["Category"]), demands,
                        int(r["Lead_Time_Days"]), float(r["Setup_Cost"]),
                        float(r["Holding_Cost"]), float(r["Unit_Cost"]),
                        int(r["Safety_Stock"])
                    )
                    count += 1
                st.success(f"✅ Imported {count} products!")
                st.rerun()
        except Exception as e:
            st.error(f"Error reading CSV: {e}")

    st.markdown("---")
    st.subheader("📊 Data Collection Progress")
    if len(products_df) > 0:
        st.metric("Products in Database", len(products_df))
        st.metric("BOM Entries", len(bom_df))
        cat_counts = products_df["Category"].value_counts().reset_index()
        cat_counts.columns = ["Category", "Count"]
        fig = px.bar(cat_counts, x="Category", y="Count",
                     title="Products per Category", color="Category")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No products yet. Start collecting data!")

elif page == "📈 Demand Forecast":
    st.title("📈 Demand Forecasting")
    selected_product = st.selectbox(
        "Select Product", products_df["Product"].tolist())
    row = products_df[products_df["Product"] == selected_product].iloc[0]
    history = [float(row[c]) for c in demand_cols]
    forecast_periods = st.slider("Forecast periods ahead", 1, 12, 6)
    forecast = forecast_demand(history, forecast_periods)
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Historical Demand")
        hist_df = pd.DataFrame(
            {"Week": [f"W{i+1}" for i in range(len(history))], "Demand": history})
        st.dataframe(hist_df, use_container_width=True)
    with col2:
        st.subheader("Forecasted Demand")
        fc_df = pd.DataFrame({"Week": [
                             f"W{len(history)+i+1}" for i in range(len(forecast))], "Forecasted_Demand": forecast})
        st.dataframe(fc_df, use_container_width=True)
    all_weeks = [f"W{i+1}" for i in range(len(history) + len(forecast))]
    all_values = history + forecast
    types = ["Historical"] * len(history) + ["Forecast"] * len(forecast)
    chart_df = pd.DataFrame(
        {"Week": all_weeks, "Demand": all_values, "Type": types})
    fig = px.line(chart_df, x="Week", y="Demand", color="Type",
                  markers=True, title=f"Demand Forecast — {selected_product}")
    st.plotly_chart(fig, use_container_width=True)

elif page == "🏭 Production Planning":
    st.title("🏭 Production Planning Methods")
    selected_product = st.selectbox(
        "Select Product", products_df["Product"].tolist())
    row = products_df[products_df["Product"] == selected_product].iloc[0]
    history = [float(row[c]) for c in demand_cols]
    forecast = forecast_demand(history, 6)
    use_forecast = st.checkbox(
        "Use forecasted demand (next 6 weeks)", value=True)
    demands = forecast if use_forecast else history
    st.write(f"**Demands:** {demands}")
    st.write(
        f"**Initial Inventory:** {row['Initial_Inventory']} | **Safety Stock:** {row['Safety_Stock']}")
    method = st.selectbox("Planning Method", [
                          "Lot-for-Lot (L4L)", "Economic Order Quantity (EOQ)", "Fixed Period Requirements"])
    schedule = None
    if method == "Lot-for-Lot (L4L)":
        schedule, total = lot_for_lot(
            demands, row["Initial_Inventory"], row["Safety_Stock"])
        st.subheader("Lot-for-Lot Schedule")
        st.dataframe(schedule, use_container_width=True)
        st.info(f"**Total Production:** {total} units")
    elif method == "Economic Order Quantity (EOQ)":
        schedule, total, eoq = eoq_planning(
            demands, row["Initial_Inventory"], row["Safety_Stock"], row["Setup_Cost"], row["Holding_Cost_Per_Unit"])
        st.subheader(f"EOQ Schedule (EOQ = {eoq} units)")
        st.dataframe(schedule, use_container_width=True)
        st.info(f"**Total Production:** {total} units | **EOQ:** {eoq}")
    elif method == "Fixed Period Requirements":
        periods = st.slider("Periods per order batch", 2, 6, 3)
        schedule, total = fixed_period_planning(
            demands, row["Initial_Inventory"], row["Safety_Stock"], periods)
        st.subheader(f"Fixed Period Schedule (batch every {periods} weeks)")
        st.dataframe(schedule, use_container_width=True)
        st.info(f"**Total Production:** {total} units")
    if schedule is not None:
        fig = go.Figure()
        fig.add_trace(
            go.Bar(x=schedule["Week"], y=schedule["Production_Order"], name="Production"))
        fig.add_trace(go.Scatter(x=schedule["Week"], y=schedule["Demand"],
                      mode="lines+markers", name="Demand", line=dict(color="red")))
        fig.add_trace(go.Scatter(x=schedule["Week"], y=schedule["Ending_Inventory"],
                      mode="lines+markers", name="Inventory", line=dict(color="green", dash="dash")))
        fig.update_layout(title=f"Production Schedule — {selected_product} ({method})",
                          xaxis_title="Week", yaxis_title="Units", barmode="overlay")
        st.plotly_chart(fig, use_container_width=True)

elif page == "🔧 MRP Explosion":
    st.title("🔧 MRP — Material Requirements Planning")
    products_with_bom = bom_df["Parent_Product"].unique().tolist()
    if len(products_with_bom) == 0:
        st.warning("No BOM data available. Add BOM entries first.")
    else:
        selected_product = st.selectbox(
            "Select Product (with BOM)", products_with_bom)
        row = products_df[products_df["Product"] == selected_product].iloc[0]
        history = [float(row[c]) for c in demand_cols]
        forecast = forecast_demand(history, 6)
        schedule, _ = lot_for_lot(
            forecast, row["Initial_Inventory"], row["Safety_Stock"])
        planned_orders = schedule["Production_Order"].tolist()
        st.subheader("Parent Planned Orders")
        st.dataframe(
            schedule[["Week", "Demand", "Production_Order"]], use_container_width=True)
        mrp_result = mrp_explosion(selected_product, planned_orders, bom_df)
        if mrp_result is not None:
            st.subheader("Component Requirements (Exploded)")
            st.dataframe(mrp_result, use_container_width=True)
            fig = px.bar(mrp_result, x="Component", y="Component_Requirement", color="Component",
                         facet_col="Week_Needed", title="Component Requirements by Week")
            st.plotly_chart(fig, use_container_width=True)
            total_cost = mrp_result["Component_Cost"].sum()
            st.metric("Total Component Cost", f"${total_cost:,.2f}")
        else:
            st.warning("No BOM data found for this product.")

elif page == "📉 Cost Analysis":
    st.title("📉 Cost Comparison Analysis")

    st.markdown("""
    ### 🎯 Objective Functions
    Each production planning method optimizes a different objective:

    | Method | Objective Function |
    |---|---|
    | **Lot-for-Lot** | Minimize **holding cost** → produce only what's needed |
    | **EOQ** | Minimize **total cost** = √(2 × Demand × Setup Cost / Holding Cost) |
    | **Fixed Period** | Minimize **setup cost** → fewer but larger production runs |

    **Total Cost = Setup Cost + Holding Cost**
    - **Setup Cost** = Number of production runs × Cost per setup
    - **Holding Cost** = Total ending inventory × Cost per unit per period
    """)

    selected_product = st.selectbox(
        "Select Product", products_df["Product"].tolist())
    row = products_df[products_df["Product"] == selected_product].iloc[0]
    history = [float(row[c]) for c in demand_cols]
    forecast = forecast_demand(history, 6)
    init_inv = row["Initial_Inventory"]
    ss = row["Safety_Stock"]
    setup = row["Setup_Cost"]
    hold = row["Holding_Cost_Per_Unit"]
    l4l_sched, l4l_total = lot_for_lot(forecast, init_inv, ss)
    eoq_sched, eoq_total, eoq_val = eoq_planning(
        forecast, init_inv, ss, setup, hold)
    fpr_sched, fpr_total = fixed_period_planning(forecast, init_inv, ss, 3)

    def calc_cost(sched_df, setup_cost, holding_cost):
        num_orders = (sched_df["Production_Order"] > 0).sum()
        total_holding = sched_df["Ending_Inventory"].sum(
        ) * float(holding_cost)
        total_setup = num_orders * float(setup_cost)
        return total_setup + total_holding, total_setup, total_holding

    l4l_cost, l4l_s, l4l_h = calc_cost(l4l_sched, setup, hold)
    eoq_cost, eoq_s, eoq_h = calc_cost(eoq_sched, setup, hold)
    fpr_cost, fpr_s, fpr_h = calc_cost(fpr_sched, setup, hold)
    comparison = pd.DataFrame({
        "Method": ["Lot-for-Lot", "EOQ", "Fixed Period (3-week)"],
        "Total_Production": [l4l_total, eoq_total, fpr_total],
        "Num_Orders": [int((l4l_sched["Production_Order"] > 0).sum()), int((eoq_sched["Production_Order"] > 0).sum()), int((fpr_sched["Production_Order"] > 0).sum())],
        "Setup_Cost": [l4l_s, eoq_s, fpr_s],
        "Holding_Cost": [l4l_h, eoq_h, fpr_h],
        "Total_Cost": [l4l_cost, eoq_cost, fpr_cost],
    })
    st.dataframe(comparison, use_container_width=True)
    best = comparison.loc[comparison["Total_Cost"].idxmin(), "Method"]
    st.success(f"🏆 **Recommended Method: {best}** (lowest total cost)")
    fig = px.bar(comparison, x="Method", y=[
                 "Setup_Cost", "Holding_Cost"], title="Cost Breakdown by Method", barmode="stack")
    st.plotly_chart(fig, use_container_width=True)
    fig2 = px.bar(comparison, x="Method", y="Total_Production",
                  title="Total Production Units by Method", color="Method")
    st.plotly_chart(fig2, use_container_width=True)

    # Download results for report
    st.markdown("---")
    st.subheader("📄 Download Results for Report")
    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1:
        st.download_button("📥 Download Cost Comparison",
                           comparison.to_csv(index=False),
                           f"cost_comparison_{selected_product}.csv", "text/csv")
    with col_d2:
        st.download_button("📥 Download L4L Schedule",
                           l4l_sched.to_csv(index=False),
                           f"l4l_schedule_{selected_product}.csv", "text/csv")
    with col_d3:
        st.download_button("📥 Download EOQ Schedule",
                           eoq_sched.to_csv(index=False),
                           f"eoq_schedule_{selected_product}.csv", "text/csv")
