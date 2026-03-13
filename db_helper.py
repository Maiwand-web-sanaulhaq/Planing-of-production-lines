import sqlite3
import pandas as pd
import os

DB_PATH = os.path.join(os.path.dirname(
    os.path.abspath(__file__)), "production_planning.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    return conn


def init_db():
    """Create tables if they don't exist and insert sample data."""
    conn = get_connection()
    cursor = conn.cursor()

    # Create products table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product TEXT UNIQUE,
            category TEXT,
            past_demand_week1 INTEGER,
            past_demand_week2 INTEGER,
            past_demand_week3 INTEGER,
            past_demand_week4 INTEGER,
            past_demand_week5 INTEGER,
            past_demand_week6 INTEGER,
            lead_time_days INTEGER,
            setup_cost REAL,
            holding_cost_per_unit REAL,
            unit_cost REAL,
            safety_stock INTEGER,
            initial_inventory INTEGER
        )
    """)

    # Create BOM table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bom (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_product TEXT,
            component TEXT,
            quantity_per_unit REAL,
            component_lead_time_days INTEGER,
            component_unit_cost REAL
        )
    """)

    # Insert sample data only if tables are empty
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        sample_products = [
            ("Wooden Chair", "Furniture", 120, 130, 125,
             140, 135, 145, 3, 500, 2.0, 25, 20, 50),
            ("Wooden Table", "Furniture", 80, 75, 85,
             90, 88, 92, 5, 800, 3.5, 60, 15, 30),
            ("Office Desk", "Furniture", 60, 65, 70,
             68, 72, 75, 4, 700, 3.0, 55, 10, 20),
            ("Bookshelf", "Furniture", 45, 50, 48,
             52, 55, 58, 6, 600, 2.5, 40, 8, 15),
            ("Metal Cabinet", "Furniture", 30, 35,
             32, 38, 36, 40, 7, 900, 4.0, 75, 5, 10),
            ("Plastic Container", "Packaging", 200, 210,
             190, 220, 215, 230, 2, 200, 0.5, 5, 30, 60),
            ("LED Monitor", "Electronics", 150, 160, 155,
             170, 165, 175, 3, 400, 5.0, 120, 25, 40),
            ("Keyboard", "Electronics", 300, 310, 290,
             320, 305, 330, 1, 150, 1.0, 15, 50, 80),
            ("Mouse", "Electronics", 500, 480, 510,
             520, 530, 540, 1, 100, 0.5, 8, 80, 100),
            ("Laptop Stand", "Electronics", 90, 95, 88,
             100, 105, 110, 2, 300, 2.0, 35, 15, 25),
        ]
        cursor.executemany("""
            INSERT INTO products (product, category, past_demand_week1, past_demand_week2,
            past_demand_week3, past_demand_week4, past_demand_week5, past_demand_week6,
            lead_time_days, setup_cost, holding_cost_per_unit, unit_cost, safety_stock, initial_inventory)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_products)

    cursor.execute("SELECT COUNT(*) FROM bom")
    if cursor.fetchone()[0] == 0:
        sample_bom = [
            ("Wooden Chair", "Wood Plank", 4, 2, 8),
            ("Wooden Chair", "Screws", 12, 1, 0.1),
            ("Wooden Chair", "Varnish", 0.5, 1, 5),
            ("Wooden Table", "Wood Plank", 8, 2, 8),
            ("Wooden Table", "Screws", 20, 1, 0.1),
            ("Office Desk", "Wood Plank", 6, 2, 8),
            ("Office Desk", "Metal Frame", 1, 3, 25),
            ("Office Desk", "Screws", 16, 1, 0.1),
            ("LED Monitor", "LCD Panel", 1, 5, 60),
            ("LED Monitor", "Circuit Board", 1, 4, 45),
        ]
        cursor.executemany("""
            INSERT INTO bom (parent_product, component, quantity_per_unit,
            component_lead_time_days, component_unit_cost)
            VALUES (?, ?, ?, ?, ?)
        """, sample_bom)

    conn.commit()
    conn.close()


def load_products():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM products", conn)
    conn.close()
    # Rename columns to match app expectations
    df.columns = [
        "ID", "Product", "Category",
        "Past_Demand_Week1", "Past_Demand_Week2", "Past_Demand_Week3",
        "Past_Demand_Week4", "Past_Demand_Week5", "Past_Demand_Week6",
        "Lead_Time_Days", "Setup_Cost", "Holding_Cost_Per_Unit",
        "Unit_Cost", "Safety_Stock", "Initial_Inventory"
    ]
    return df


def load_bom():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM bom", conn)
    conn.close()
    df.columns = [
        "ID", "Parent_Product", "Component", "Quantity_Per_Unit",
        "Component_Lead_Time_Days", "Component_Unit_Cost"
    ]
    return df


def add_product(product, category, demands, lead_time, setup_cost, holding_cost, unit_cost, safety_stock):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO products (product, category, past_demand_week1, past_demand_week2,
        past_demand_week3, past_demand_week4, past_demand_week5, past_demand_week6,
        lead_time_days, setup_cost, holding_cost_per_unit, unit_cost, safety_stock, initial_inventory)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
    """, (product, category, *demands, lead_time, setup_cost, holding_cost, unit_cost, safety_stock))
    conn.commit()
    conn.close()


def delete_product(product_name):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE product = ?", (product_name,))
    conn.commit()
    conn.close()


def add_bom_entry(parent, component, qty, lead_time, cost):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO bom (parent_product, component, quantity_per_unit,
        component_lead_time_days, component_unit_cost)
        VALUES (?, ?, ?, ?, ?)
    """, (parent, component, qty, lead_time, cost))
    conn.commit()
    conn.close()
