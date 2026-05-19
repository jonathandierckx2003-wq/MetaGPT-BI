# Business Requirement Document (BRD)  
**Project:** NovaMart BI Solution for Customer Interactions and Sales Performance Analysis  
**Version:** 1.0  
**Date:** 2026-05-09  

---

## 1. Purpose

This document defines the business requirements for a BI solution that will enable NovaMart’s marketing and sales analysts to analyze customer interactions and sales performance using CSV-based source data. The solution will provide a single, clean analytical source of information to support weekly operational analysis and reduce manual reporting effort.

The BI solution will be implemented as a data warehouse hosted on DuckDB and connected to Power BI for dashboard development.

---

## 2. Business Background

NovaMart’s marketing and sales analysts currently rely on Excel tables and manual SQL queries over raw CSV exports to produce weekly reports. This process is time-consuming and requires approximately half a day per week.

The business needs a centralized analytical data layer that consolidates customer, product, and sales interaction data into a reliable structure for recurring analysis. The intended outcome is faster access to key commercial metrics and easier ad-hoc weekly analysis.

---

## 3. Business Goals

The BI solution must support the following business goals:

1. Provide a single, clean analytical source of information for commercial analysis.
2. Reduce the time spent on manual weekly reporting.
3. Enable analysts to answer recurring operational questions more easily.
4. Improve access to key sales, customer, and product performance metrics.
5. Support dashboarding in Power BI for weekly business review and ad-hoc analysis.

---

## 4. Business Questions to Be Answered

The BI solution must support the following business questions. Each question is directly linked to one or more business goals and/or KPIs.

1. Which product categories and seasons drive the most revenue?  
   - Linked to Goal 1, Goal 3, Goal 4  
   - Linked KPI: Total revenue

2. Do subscription customers spend more, and how does discount/promo use affect order value?  
   - Linked to Goal 1, Goal 3, Goal 4  
   - Linked KPIs: Total revenue, average order value, discount rate, promo code redemption rate

3. What is the conversion funnel from product views to purchases, by category?  
   - Linked to Goal 1, Goal 3, Goal 4  
   - Linked KPI: Product conversion rate

4. How are customers distributed across US states, age groups, and purchase frequency segments?  
   - Linked to Goal 1, Goal 3, Goal 4  
   - Linked KPI: Customer purchase frequency distribution

5. What is the average review rating per category, and does it vary by season?  
   - Linked to Goal 1, Goal 3, Goal 4  
   - Linked KPI: Average review rating per category

---

## 5. Key Performance Indicators (KPIs)

The BI solution must calculate and make available the following KPIs:

1. **Total revenue**  
   - Required breakdowns: category, season, subscription status

2. **Average order value**  
   - Required breakdowns: category, season, subscription status

3. **Discount rate**  
   - Required for analysis of discount usage impact on order value

4. **Promo code redemption rate**  
   - Required for analysis of promo usage impact on order value

5. **Product conversion rate**  
   - Defined as purchases divided by views, by category

6. **Customer purchase frequency distribution**  
   - Required for segmentation analysis

7. **Average review rating per category**  
   - Required to assess variation by season

---

## 6. Scope

### 6.1 In Scope

The solution will include:

- A data warehouse built on DuckDB
- Ingestion of the following CSV files:
  - `workspace\data\customer_details.csv`
  - `workspace\data\E-commerce_sales_data.csv`
  - `workspace\data\product_details.csv`
- Consolidation of customer, product, and interaction/sales data into a clean analytical structure
- Data preparation for Power BI consumption
- Support for weekly batch refresh
- Data structures and metrics needed to answer the business questions and calculate the KPIs listed above

### 6.2 Out of Scope

The following are out of scope based on the information provided:

- Real-time or near-real-time data refresh
- Additional data sources beyond the three listed CSV files
- Advanced machine learning or predictive modeling
- Operational transaction processing
- Non-Power BI front-end tools

---

## 7. Stakeholders and Users

### 7.1 Primary Users

- A team of 5 marketing and sales analysts at NovaMart

### 7.2 User Profile

The users are business-oriented and comfortable with data, but they are not software engineers. They currently work with Excel tables and manual SQL queries on raw CSV exports. Their technical skill level is basic to intermediate.

### 7.3 User Needs

- Easy access to commercial metrics
- Reduced manual reporting effort
- Ability to perform weekly ad-hoc analysis
- A reliable analytical source instead of raw CSV manipulation

---

## 8. Assumptions, Constraints, and Open Questions

### 8.1 Assumptions

- The three provided CSV files contain sufficient information to support the requested analyses.
- Power BI will be used as the reporting and dashboard layer on top of the DuckDB-based data warehouse.
- Weekly batch refresh is sufficient for business needs.
- The analysts will use the curated analytical layer rather than raw CSV files for recurring reporting.

### 8.2 Constraints

- The data warehouse must be hosted on DuckDB.
- Refresh frequency must be weekly batch.
- No other specific technical constraints were provided.

### 8.3 Open Questions Requiring Future Clarification

The following items were not clarified during elicitation and should be confirmed in a later phase:

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

## 9. Functional Requirements

### 9.1 Data Ingestion

FR-1. The solution shall ingest the following CSV files:
- `workspace\data\customer_details.csv`
- `workspace\data\E-commerce_sales_data.csv`
- `workspace\data\product_details.csv`

FR-2. The solution shall load the source files into DuckDB.

FR-3. The solution shall support weekly batch refresh of the loaded data.

### 9.2 Data Preparation and Consolidation

FR-4. The solution shall consolidate customer, product, and sales/interaction data into a single analytical model.

FR-5. The solution shall prepare data for analysis by category, season, subscription status, US state, age group, and purchase frequency segment, subject to source availability.

FR-6. The solution shall support calculation of the KPIs listed in Section 5.

### 9.3 Analytical Support

FR-7. The solution shall enable analysis of revenue by product category and season.

FR-8. The solution shall enable analysis of average order value by category, season, and subscription status.

FR-9. The solution shall enable analysis of discount and promo code usage impact on order value.

FR-10. The solution shall enable analysis of product conversion rate by category.

FR-11. The solution shall enable analysis of customer distribution by US state, age group, and purchase frequency segment.

FR-12. The solution shall enable analysis of average review rating by category and season.

### 9.4 Reporting Consumption

FR-13. The solution shall provide a curated data layer suitable for Power BI dashboards.

FR-14. The solution shall support ad-hoc weekly analysis by the marketing and sales analysts.

---

## 10. Non-Functional Requirements

### 10.1 Refresh and Data Latency

NFR-1. The solution shall refresh on a weekly batch basis.

### 10.2 Platform

NFR-2. The data warehouse shall be hosted on DuckDB.

### 10.3 Usability

NFR-3. The analytical output shall be accessible to business-oriented analysts with basic to intermediate technical skills.

### 10.4 Maintainability

NFR-4. The solution shall be structured so that recurring weekly reporting can be performed with minimal manual effort.

---

## 11. Data Sources

The solution will use the following CSV files:

1. `workspace\data\customer_details.csv`
2. `workspace\data\E-commerce_sales_data.csv`
3. `workspace\data\product_details.csv`

No source schemas were inspected during elicitation.

---

## 12. Acceptance Criteria

The solution will be considered acceptable when:

1. The three specified CSV files are successfully loaded into DuckDB.
2. The data is refreshed on a weekly batch schedule.
3. Power BI can connect to the curated analytical layer.
4. Analysts can answer the five business questions listed in Section 4.
5. The KPIs listed in Section 5 are available for analysis.
6. The solution reduces reliance on manual Excel and raw SQL reporting for weekly analysis.

---

## 13. Success Measures

The project will be successful if:

- Analysts no longer need to spend half a day per week preparing manual reports.
- Commercial metrics are available in a single analytical source.
- Weekly analysis becomes faster and easier for the NovaMart marketing and sales team.
- Power BI dashboards can be built on top of the curated data warehouse.

---

## 14. Approval

This BRD reflects the requirements gathered during the elicitation phase and is ready for review and validation by NovaMart stakeholders.