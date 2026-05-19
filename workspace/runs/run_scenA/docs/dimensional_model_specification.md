# Dimensional Model Specification  
**Project:** NovaMart BI Solution for Customer Interactions and Sales Performance Analysis  
**Version:** 1.0  
**Date:** 2026-05-09  

---

## 1. Purpose

This document defines the dimensional model specification for NovaMart’s BI solution based exclusively on the published BRD. The model is intended to support weekly operational analysis of customer interactions and sales performance in DuckDB and consumption in Power BI.

---

## 2. Scope

### 2.1 In Scope
The dimensional model supports the following source files and analytical needs stated in the BRD:

- `workspace\data\customer_details.csv`
- `workspace\data\E-commerce_sales_data.csv`
- `workspace\data\product_details.csv`

The model is designed to support analysis of:

- revenue by product category and season
- average order value by category, season, and subscription status
- discount and promo code usage impact on order value
- product conversion rate by category
- customer distribution by US state, age group, and purchase frequency segment
- average review rating by category and season

### 2.2 Out of Scope
The following are out of scope because they are not specified in the BRD:

- real-time or near-real-time refresh
- additional data sources
- machine learning or predictive modeling
- operational transaction processing
- non-Power BI front-end tools

---

## 3. Business Process

The BRD describes a single analytical domain covering customer, product, and sales/interaction analysis. The dimensional model therefore centers on a consolidated commerce analytics process that combines customer details, product details, and e-commerce sales/interaction data.

---

## 4. Grain

The BRD does not provide inspected source schemas, so the exact grain cannot be confirmed from the document.

### 4.1 Intended Analytical Grain
The model is designed around the finest level of detail available in the source data, subject to source availability, to support the required KPIs and questions.

### 4.2 Grain Ambiguity
The following are explicitly unresolved in the BRD and must be confirmed later:

- whether sales data is at order line, order header, product interaction, or event level
- whether product views and purchases are stored in the same file or across multiple files
- whether order-level identifiers exist for average order value
- whether review ratings exist and in which file
- whether customer state, age, and subscription status exist in customer details
- how purchase frequency segments should be derived

---

## 5. Facts

Because the BRD does not provide source schemas, the model uses a flexible analytical design with a central fact table for commerce interactions and supporting fact-like aggregates only where explicitly needed.

### 5.1 Fact Commerce Interaction
**Purpose:** Support revenue, order value, discount, promo, conversion, and review analysis.

**Measures / additive or semi-additive metrics:**
- revenue
- order value
- discount amount
- discount rate
- promo code redemption indicator
- promo code redemption rate
- purchase count
- view count
- conversion count
- review rating

**Notes:**
- The BRD explicitly requires total revenue, average order value, discount rate, promo code redemption rate, product conversion rate, and average review rating.
- The exact calculation logic for several measures is not defined in the BRD and remains open.

### 5.2 Fact Customer Segmentation
**Purpose:** Support customer distribution analysis by US state, age group, and purchase frequency segment.

**Measures:**
- customer count

**Notes:**
- This fact may be implemented as a periodic snapshot or derived aggregate depending on source availability.
- The BRD does not specify whether segmentation attributes are stored or derived.

---

## 6. Dimensions

### 6.1 Customer Dimension
Supports:
- US state
- age group
- subscription status
- purchase frequency segment

### 6.2 Product Dimension
Supports:
- product category

### 6.3 Season Dimension
Supports:
- season

### 6.4 Date Dimension
Supports:
- weekly batch refresh analysis
- seasonal analysis if season is derived from date

### 6.5 Promo Code Dimension
Supports:
- promo code usage analysis

### 6.6 Geography Dimension
Supports:
- US state

### 6.7 Age Group Dimension
Supports:
- age group

### 6.8 Purchase Frequency Segment Dimension
Supports:
- purchase frequency segmentation

### 6.9 Subscription Status Dimension
Supports:
- subscription customer analysis

### 6.10 Review Dimension
Supports:
- review rating analysis

---

## 7. Hierarchies

The BRD explicitly requires the following analytical breakdowns and groupings:

- Product Category
- Season
- Subscription Status
- US State
- Age Group
- Purchase Frequency Segment

No additional hierarchies are specified in the BRD.

---

## 8. Measures and KPI Mapping

### 8.1 Total revenue
- Supported by: Fact Commerce Interaction
- Required breakdowns: category, season, subscription status

### 8.2 Average order value
- Supported by: Fact Commerce Interaction
- Required breakdowns: category, season, subscription status

### 8.3 Discount rate
- Supported by: Fact Commerce Interaction
- Used for analysis of discount usage impact on order value

### 8.4 Promo code redemption rate
- Supported by: Fact Commerce Interaction
- Used for analysis of promo usage impact on order value

### 8.5 Product conversion rate
- Supported by: Fact Commerce Interaction
- Defined in BRD as purchases divided by views, by category

### 8.6 Customer purchase frequency distribution
- Supported by: Fact Customer Segmentation
- Required for segmentation analysis

### 8.7 Average review rating per category
- Supported by: Fact Commerce Interaction
- Required to assess variation by season

---

## 9. Source-to-Model Mapping

### 9.1 Customer Details CSV
Expected to support:
- customer attributes
- US state
- age group
- subscription status
- purchase frequency segment

### 9.2 E-commerce Sales Data CSV
Expected to support:
- sales and interaction measures
- revenue
- order value
- discount usage
- promo code usage
- product views
- purchases
- review ratings, if present

### 9.3 Product Details CSV
Expected to support:
- product attributes
- product category
- season, if stored at product level

---

## 10. Open Questions

The BRD explicitly states the following unresolved items:

1. The exact schema and field definitions of the three CSV files were not inspected or provided.
2. The precise business definitions for:
   - revenue
   - order value
   - discount rate
   - promo code redemption rate
   - purchase frequency segments
   - conversion funnel stages
   - season
   - subscription customer
   - age groups
   are not yet specified.
3. It is not confirmed whether review ratings are present in the source data and, if so, which file contains them.
4. It is not confirmed whether product views and purchases are stored in the same source file or across multiple files.
5. It is not confirmed whether customer state, age, and subscription status are available in the customer details file.
6. It is not confirmed whether the sales data contains order-level identifiers needed to calculate average order value precisely.

---

## 11. Dimensional Model Summary

The recommended dimensional model is a star-oriented analytical structure centered on commerce interactions, with supporting dimensions for customer, product, season, geography, age group, purchase frequency, subscription status, promo code, date, and review attributes.

This design is intentionally flexible because the BRD does not provide inspected source schemas. The model supports the required business questions and KPIs while preserving the unresolved items as open questions rather than assumptions.