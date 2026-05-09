# Business Case — NovaMart E-Commerce Analytics
## MetaGPT-BI Scenario A: CSV files → Local DuckDB Warehouse

*PoC scenario for the thesis "Where AI Adds Value: Designing a BI development Multi-Agent Architecture" — Jonathan Dierckx, UNamur / KU Leuven, 2026.*

---

## The company

**NovaMart** is a mid-size US online retailer selling across fashion, sports, electronics, and hobby categories. It runs a subscription loyalty programme that grants members free express shipping and exclusive promo codes. A team of 5 marketing analysts currently produces commercial reports by manually manipulating weekly CSV exports — a slow, error-prone process with no shared definition of key metrics.

---

## The data

Three CSV files are exported weekly from NovaMart's operational systems:

| File | What it contains |
|------|-----------------|
| `customer_details.csv` | One row per purchase transaction — item bought, amount, customer demographics (age, gender, location), subscription status, discount/promo use, review score, payment method, purchase frequency |
| `product_details.csv` | Product catalogue — product ID, name, brand, category, list price, selling price, stock; also contains long text columns (descriptions, specs, image URLs) that are irrelevant for analytics |
| `interactions_2024.csv` | One row per platform event — customer viewed, liked, or purchased a product (user ID + product ID + event type + timestamp) |

The product ID in `interactions_2024.csv` matches the `Unique Id` in `product_details.csv`. The customer ID in `interactions_2024.csv` matches `Customer ID` in `customer_details.csv`.

---

## What NovaMart needs

A Data Warehouse that gives analysts a single, clean analytical layer to answer the following questions:

- Which product categories and seasons drive the most revenue?
- Do subscription customers spend more, and how does discount/promo use affect order value?
- What is the conversion funnel from product views to purchases, by category?
- How are customers distributed across US states, age groups, and purchase frequency segments?
- What is the average review rating per category, and does it vary by season?

**Preferred DWH technology:** Local DuckDB (no cloud infrastructure required for this PoC).  
**Refresh frequency:** Weekly batch loads.  
**Output:** Dimension and fact tables (star schema), dbt SQL models, Mermaid ERDs.

---

## Key KPIs

- Total revenue and average order value (by category, season, subscription status)
- Discount rate and promo code redemption rate
- Product conversion rate (purchases / views per category)
- Customer purchase frequency distribution
- Average review rating per category

---

*NovaMart is a fictional company. All data is synthetic and used for academic research purposes only.*
