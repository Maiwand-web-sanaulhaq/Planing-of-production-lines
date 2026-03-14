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

# ========== SMOOTH SCROLLING CSS ==========
st.markdown("""
<style>
    html {
        scroll-behavior: smooth;
    }
</style>
""", unsafe_allow_html=True)

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
        schedule.append({"Week": i + 1, "Demand": d, "Net_Requirement": net_req,
                         "Production_Order": production, "Ending_Inventory": inventory})
    return pd.DataFrame(schedule), total_produced


def eoq_planning(demands, initial_inv, safety_stock, setup_cost, holding_cost):
    demands = [float(x) for x in demands]
    avg_demand = np.mean(demands)
    holding_cost = float(holding_cost) if float(holding_cost) > 0 else 0.01
    setup_cost = float(setup_cost)
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
        schedule.append({"Week": i + 1, "Demand": d, "EOQ": eoq,
                         "Production_Order": production, "Ending_Inventory": inventory})
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
        schedule.append({"Week": i + 1, "Demand": demands[i],
                         "Production_Order": production, "Ending_Inventory": inventory})
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
    "ℹ️ About", "📊 Dashboard", "📦 Product Data", "📋 Bill of Materials",
    "📥 Data Collection", "📈 Demand Forecast", "🏭 Production Planning",
    "🔧 MRP Explosion", "📉 Cost Analysis"
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

    In this project, we aim to develop an application for **planning and scheduling of different production types** 
    based on given data related to their past demands, consumption coefficients, lead-times, and costs.

    Different types of production planning methods with different objective functions are implemented. 
    The data related to products is collected from **real-life cases**.
    """)

    st.header("🎯 Key Features")
    st.markdown("""
    #### 📊 Data Management
    - ✅ **Real-life products' data** — collected from actual factories and suppliers
    - ✅ **SQLite Database** — all data persists between sessions
    - ✅ **Data Collection Portal** — team members can enter factory data easily
    - ✅ **Bulk CSV Upload** — import multiple products at once
    
    #### 📈 Analysis & Planning
    - ✅ **Multiple production planning methods** — L4L, EOQ, Fixed Period, MRP
    - ✅ **Demand Forecasting** — predict future demand using weighted moving averages
    - ✅ **Cost Optimization** — compare methods and find the cheapest strategy
    - ✅ **Material Requirements Planning** — explode BOM into component needs
    
    #### 💻 Application Features
    - ✅ **Interactive Web Application** — solve production planning problems in real-time
    - ✅ **Professional Dashboards** — visualize demand trends and metrics
    - ✅ **Downloadable Reports** — export results as CSV for presentations
    - ✅ **Smooth User Interface** — intuitive navigation across 9 pages
    """)

    st.header("🔧 Production Planning Methods")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1️⃣ Lot-for-Lot (L4L)")
        st.markdown("""
        - Produce **exactly what is needed** each period
        - **Zero excess inventory**
        - Best for: **Expensive items, custom/make-to-order**
        - ✅ Low holding cost | ❌ High setup cost
        """)

        st.subheader("2️⃣ Economic Order Quantity (EOQ)")
        st.markdown("""
        - Calculates **optimal batch size** that minimizes total cost
        - Balances **setup cost vs holding cost**
        - Best for: **Stable demand, repetitive manufacturing**
        - ✅ Balanced costs | ❌ Assumes constant demand
        """)

    with col2:
        st.subheader("3️⃣ Fixed Period Requirements")
        st.markdown("""
        - Groups demand over **fixed time periods** (e.g., every 3 weeks)
        - Produces in **batches** to cover multiple periods
        - Best for: **Batch production, seasonal items**
        - ✅ Fewer setups | ❌ Higher inventory levels
        """)

        st.subheader("4️⃣ MRP (Material Requirements Planning)")
        st.markdown("""
        - **Explodes** finished product orders into **component requirements**
        - Uses **Bill of Materials (BOM)** to calculate raw material needs
        - Best for: **Assembly operations, complex products**
        - ✅ Precise material planning | ❌ Requires accurate BOM data
        """)

    st.markdown("---")
    st.header("👥 Team & Data Collection")
    st.markdown("""
    | Team Member | Role | Data Responsibility |
    |---|---|---|
    | **Software Engineer** | Lead Developer | App development, system integration |
    | **Industrial Engineer 1** | Data Collection | Collect furniture/manufacturing data from real factories |
    | **Industrial Engineer 2** | Data Engineer | Collect electronics/packaging data from real suppliers |

    ### 📋 Data to Collect from Real Factories:
    1. **Product names** and categories
    2. **Weekly/monthly demand** data (at least 6 periods)
    3. **Lead times** — how long it takes to produce each product
    4. **Setup costs** — cost to start a production run
    5. **Holding costs** — cost to store one unit per period
    6. **Bill of Materials** — what components/raw materials are needed
    7. **Component quantities** — how many of each component per finished product
    """)

    st.markdown("---")
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

# ========== PAGE: DASHBOARD ==========
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
    fig = px.line(demand_melted, x="Week", y="Demand",
                  color="Product", title="Historical Demand", markers=True)
    st.plotly_chart(fig, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        cat_demand = products_df.groupby(
            "Category")[demand_cols[-1]].sum().reset_index()
        cat_demand.columns = ["Category", "Latest_Week_Demand"]
        fig2 = px.pie(cat_demand, values="Latest_Week_Demand",
                      names="Category", title="Latest Week Demand")
        st.plotly_chart(fig2, use_container_width=True)
    with col_b:
        fig3 = px.bar(products_df, x="Product", y="Lead_Time_Days",
                      title="Lead Times", color="Category")
        st.plotly_chart(fig3, use_container_width=True)

# ========== PAGE: PRODUCT DATA ==========
elif page == "📦 Product Data":
    st.title("📦 Product Data Management")
    st.subheader("Current Products")
    st.dataframe(products_df.drop(columns=["ID"]), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Add New Product")
        with st.form("add_product"):
            new_name = st.text_input("Product Name")
            new_cat = st.selectbox(
                "Category", ["Furniture", "Electronics", "Packaging", "Other"])
            new_lt = st.number_input("Lead Time (days)", min_value=1, value=3)
            cols = st.columns(6)
            new_demands = [cols[i].number_input(
                f"W{i+1}", min_value=0, value=50) for i in range(6)]
            cols2 = st.columns(4)
            new_setup = cols2[0].number_input(
                "Setup Cost", min_value=0, value=300)
            new_hold = cols2[1].number_input(
                "Holding Cost", min_value=0.0, value=1.0)
            new_unit = cols2[2].number_input(
                "Unit Cost", min_value=0, value=20)
            new_ss = cols2[3].number_input(
                "Safety Stock", min_value=0, value=10)
            if st.form_submit_button("Add Product"):
                if new_name:
                    add_product(new_name, new_cat, new_demands,
                                new_lt, new_setup, new_hold, new_unit, new_ss)
                    st.success(f"Added '{new_name}'!")
                    st.rerun()

    with col2:
        st.subheader("Delete Product")
        if len(products_df) > 0:
            del_product = st.selectbox(
                "Select to delete", products_df["Product"].tolist())
            if st.button("🗑️ Delete"):
                delete_product(del_product)
                st.success(f"Deleted '{del_product}'!")
                st.rerun()

# ========== PAGE: BILL OF MATERIALS ==========
elif page == "📋 Bill of Materials":
    st.title("📋 Bill of Materials (BOM)")
    if len(bom_df) > 0:
        st.dataframe(bom_df.drop(columns=["ID"]), use_container_width=True)
        products_with_bom = bom_df["Parent_Product"].unique()
        selected = st.selectbox("View BOM for:", products_with_bom)
        filtered = bom_df[bom_df["Parent_Product"] == selected]
        fig = px.bar(filtered, x="Component", y="Quantity_Per_Unit",
                     title=f"Components for {selected}")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Add BOM Entry")
    with st.form("add_bom"):
        cols = st.columns(5)
        bom_parent = cols[0].selectbox("Parent Product", products_df["Product"].tolist(
        ) if len(products_df) > 0 else ["No products"])
        bom_comp = cols[1].text_input("Component Name")
        bom_qty = cols[2].number_input(
            "Qty Per Unit", min_value=0.1, value=1.0)
        bom_lt = cols[3].number_input("Lead Time (days)", min_value=1, value=2)
        bom_cost = cols[4].number_input("Unit Cost", min_value=0.0, value=5.0)
        if st.form_submit_button("Add BOM") and bom_comp:
            add_bom_entry(bom_parent, bom_comp, bom_qty, bom_lt, bom_cost)
            st.success(f"Added '{bom_comp}'!")
            st.rerun()

# ========== PAGE: DATA COLLECTION ==========
elif page == "📥 Data Collection":
    st.title("📥 Data Collection Portal")

    collector_name = st.text_input("Your Name")
    data_source = st.text_input("Data Source (e.g., 'ABC Factory, Kabul')")

    with st.form("collect_product"):
        st.subheader("Product Information")
        cols = st.columns(3)
        c_name = cols[0].text_input("Product Name")
        c_cat = cols[1].selectbox(
            "Category", ["Furniture", "Electronics", "Packaging", "Other"])
        c_lt = cols[2].number_input("Lead Time (days)", min_value=1, value=3)

        st.subheader("Weekly Demand (6 weeks)")
        cols = st.columns(6)
        c_demands = [cols[i].number_input(
            f"Week {i+1}", min_value=0, value=0, key=f"d{i}") for i in range(6)]

        st.subheader("Cost Information")
        cols = st.columns(4)
        c_setup = cols[0].number_input("Setup Cost", min_value=0, value=0)
        c_hold = cols[1].number_input("Holding Cost", min_value=0.0, value=0.0)
        c_unit = cols[2].number_input("Unit Cost", min_value=0, value=0)
        c_ss = cols[3].number_input("Safety Stock", min_value=0, value=0)

        c_notes = st.text_area("Notes")
        if st.form_submit_button("Submit"):
            if c_name and collector_name and sum(c_demands) > 0:
                add_product(c_name, c_cat, c_demands, c_lt,
                            c_setup, c_hold, c_unit, c_ss)
                st.success(f"✅ Product added by {collector_name}!")
                st.balloons()
                st.rerun()

    st.markdown("---")
    st.header("📥 Bulk Upload via CSV")
    sample_csv = pd.DataFrame({
        "Product": ["Example"],
        "Category": ["Furniture"],
        "Demand_W1": [100], "Demand_W2": [110], "Demand_W3": [105],
        "Demand_W4": [120], "Demand_W5": [115], "Demand_W6": [125],
        "Lead_Time_Days": [3],
        "Setup_Cost": [500], "Holding_Cost": [2.0],
        "Unit_Cost": [25], "Safety_Stock": [20],
    })
    st.dataframe(sample_csv)
    st.download_button("📄 Download CSV Template",
                       sample_csv.to_csv(index=False), "template.csv")

    uploaded = st.file_uploader("Upload CSV", type=["csv"])
    if uploaded:
        csv_df = pd.read_csv(uploaded)
        st.dataframe(csv_df)
        if st.button("📥 Import All"):
            for _, r in csv_df.iterrows():
                demands = [int(r.get(f"Demand_W{i+1}", 0)) for i in range(6)]
                add_product(str(r["Product"]), str(r["Category"]), demands,
                            int(r["Lead_Time_Days"]), float(r["Setup_Cost"]),
                            float(r["Holding_Cost"]), float(r["Unit_Cost"]), int(r["Safety_Stock"]))
            st.success("✅ All imported!")

# ========== PAGE: DEMAND FORECAST ==========
elif page == "📈 Demand Forecast":
    st.title("📈 Demand Forecasting")
    selected_product = st.selectbox(
        "Select Product", products_df["Product"].tolist())
    row = products_df[products_df["Product"] == selected_product].iloc[0]
    history = [float(row[c]) for c in demand_cols]
    forecast_periods = st.slider("Forecast periods", 1, 12, 6)
    forecast = forecast_demand(history, forecast_periods)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Historical")
        hist_df = pd.DataFrame(
            {"Week": [f"W{i+1}" for i in range(len(history))], "Demand": history})
        st.dataframe(hist_df)
    with col2:
        st.subheader("Forecasted")
        fc_df = pd.DataFrame(
            {"Week": [f"W{len(history)+i+1}" for i in range(len(forecast))], "Forecast": forecast})
        st.dataframe(fc_df)

    all_weeks = [f"W{i+1}" for i in range(len(history) + len(forecast))]
    chart_df = pd.DataFrame({"Week": all_weeks, "Demand": history + forecast,
                            "Type": ["Historical"]*len(history) + ["Forecast"]*len(forecast)})
    fig = px.line(chart_df, x="Week", y="Demand", color="Type",
                  markers=True, title=f"Forecast - {selected_product}")
    st.plotly_chart(fig, use_container_width=True)

# ========== PAGE: PRODUCTION PLANNING ==========
elif page == "🏭 Production Planning":
    st.title("🏭 Production Planning")
    selected_product = st.selectbox(
        "Select Product", products_df["Product"].tolist())
    row = products_df[products_df["Product"] == selected_product].iloc[0]
    history = [float(row[c]) for c in demand_cols]
    forecast = forecast_demand(history, 6)
    use_forecast = st.checkbox("Use forecast", value=True)
    demands = forecast if use_forecast else history

    method = st.selectbox(
        "Method", ["Lot-for-Lot (L4L)", "EOQ", "Fixed Period"])

    if method == "Lot-for-Lot (L4L)":
        schedule, total = lot_for_lot(
            demands, row["Initial_Inventory"], row["Safety_Stock"])
        st.subheader("L4L Schedule")
        st.dataframe(schedule)
        st.info(f"Total: {total} units")
    elif method == "EOQ":
        schedule, total, eoq = eoq_planning(
            demands, row["Initial_Inventory"], row["Safety_Stock"], row["Setup_Cost"], row["Holding_Cost_Per_Unit"])
        st.subheader(f"EOQ Schedule (EOQ = {eoq})")
        st.dataframe(schedule)
        st.info(f"Total: {total} units")
    elif method == "Fixed Period":
        periods = st.slider("Periods", 2, 6, 3)
        schedule, total = fixed_period_planning(
            demands, row["Initial_Inventory"], row["Safety_Stock"], periods)
        st.subheader(f"Fixed Period (every {periods} weeks)")
        st.dataframe(schedule)
        st.info(f"Total: {total} units")

    fig = go.Figure()
    fig.add_trace(
        go.Bar(x=schedule["Week"], y=schedule["Production_Order"], name="Production"))
    fig.add_trace(go.Scatter(x=schedule["Week"], y=schedule["Demand"],
                  mode="lines+markers", name="Demand", line=dict(color="red")))
    fig.add_trace(go.Scatter(x=schedule["Week"], y=schedule["Ending_Inventory"],
                  mode="lines+markers", name="Inventory", line=dict(color="green")))
    st.plotly_chart(fig, use_container_width=True)

# ========== PAGE: MRP EXPLOSION ==========
elif page == "🔧 MRP Explosion":
    st.title("🔧 MRP - Material Requirements Planning")
    products_with_bom = bom_df["Parent_Product"].unique().tolist()
    if len(products_with_bom) == 0:
        st.warning("No BOM data available")
    else:
        selected_product = st.selectbox("Select Product", products_with_bom)
        row = products_df[products_df["Product"] == selected_product].iloc[0]
        history = [float(row[c]) for c in demand_cols]
        forecast = forecast_demand(history, 6)
        schedule, _ = lot_for_lot(
            forecast, row["Initial_Inventory"], row["Safety_Stock"])
        planned_orders = schedule["Production_Order"].tolist()
        st.subheader("Planned Orders")
        st.dataframe(schedule[["Week", "Demand", "Production_Order"]])
        mrp_result = mrp_explosion(selected_product, planned_orders, bom_df)
        if mrp_result is not None:
            st.subheader("Component Requirements")
            st.dataframe(mrp_result)
            st.metric("Total Cost",
                      f"${mrp_result['Component_Cost'].sum():,.2f}")

# ========== PAGE: COST ANALYSIS ==========
elif page == "📉 Cost Analysis":
    st.title("📉 Cost Comparison")
    selected_product = st.selectbox(
        "Select Product", products_df["Product"].tolist())
    row = products_df[products_df["Product"] == selected_product].iloc[0]
    history = [float(row[c]) for c in demand_cols]
    forecast = forecast_demand(history, 6)

    l4l_sched, l4l_total = lot_for_lot(
        forecast, row["Initial_Inventory"], row["Safety_Stock"])
    eoq_sched, eoq_total, eoq_val = eoq_planning(
        forecast, row["Initial_Inventory"], row["Safety_Stock"], row["Setup_Cost"], row["Holding_Cost_Per_Unit"])
    fpr_sched, fpr_total = fixed_period_planning(
        forecast, row["Initial_Inventory"], row["Safety_Stock"], 3)

    def calc_cost(sched_df, setup_cost, holding_cost):
        num_orders = (sched_df["Production_Order"] > 0).sum()
        total_holding = sched_df["Ending_Inventory"].sum(
        ) * float(holding_cost)
        total_setup = num_orders * float(setup_cost)
        return total_setup + total_holding, total_setup, total_holding

    l4l_cost, l4l_s, l4l_h = calc_cost(
        l4l_sched, row["Setup_Cost"], row["Holding_Cost_Per_Unit"])
    eoq_cost, eoq_s, eoq_h = calc_cost(
        eoq_sched, row["Setup_Cost"], row["Holding_Cost_Per_Unit"])
    fpr_cost, fpr_s, fpr_h = calc_cost(
        fpr_sched, row["Setup_Cost"], row["Holding_Cost_Per_Unit"])

    comparison = pd.DataFrame({
        "Method": ["L4L", "EOQ", "Fixed Period"],
        "Setup Cost": [round(l4l_s, 2), round(eoq_s, 2), round(fpr_s, 2)],
        "Holding Cost": [round(l4l_h, 2), round(eoq_h, 2), round(fpr_h, 2)],
        "Total Cost": [round(l4l_cost, 2), round(eoq_cost, 2), round(fpr_cost, 2)],
    })

    st.dataframe(comparison, use_container_width=True)
    best = comparison.loc[comparison["Total Cost"].idxmin(), "Method"]
    best_cost = comparison["Total Cost"].min()
    st.success(f"🏆 Best: **{best}** (${best_cost:,.2f})")

    fig = px.bar(comparison, x="Method", y=[
                 "Setup Cost", "Holding Cost"], barmode="stack", title="Cost Breakdown")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("📄 Download Reports")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button("📥 Cost Comparison", comparison.to_csv(
            index=False), f"cost_{selected_product}.csv")
    with col2:
        st.download_button("📥 L4L Schedule", l4l_sched.to_csv(
            index=False), f"l4l_{selected_product}.csv")
    with col3:
        st.download_button("📥 EOQ Schedule", eoq_sched.to_csv(
            index=False), f"eoq_{selected_product}.csv")
