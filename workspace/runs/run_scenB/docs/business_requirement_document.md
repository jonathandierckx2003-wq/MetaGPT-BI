# Business Requirement Document (BRD)  
## PrimeShelf Marketplace Analytics BI Solution

### 1. Document Purpose
This document defines the business requirements for a cloud-based Business Intelligence (BI) solution for PrimeShelf’s marketplace analytics team. The solution will replace the current manual spreadsheet export process with a cloud data warehouse that can be queried directly using SQL, while preserving historical data.

### 2. Business Background
PrimeShelf currently relies on manual exports from the platform’s admin portal into spreadsheets. This process is fragile and limits the team’s ability to analyze marketplace performance efficiently and consistently.

The analytics team consists of 4 non-technical business users. They are comfortable with SQL basics and expect to query the data warehouse directly. The business requires a cloud-hosted solution with no local infrastructure, and data must remain accessible in the cloud.

The source data is provided through an Airbyte Cloud connector already configured in the workspace: **Sample Data (Faker)**.

### 3. Business Goals
The BI solution must support the following business goals:

1. Replace the fragile manual export process with a cloud data warehouse accessible via SQL.
2. Preserve historical data for ongoing and trend-based analysis.
3. Enable analysis of revenue by storefront, product, customer, and time.
4. Support segmentation of revenue and purchasing behavior by customer type and demographics.
5. Provide visibility into top customers, product performance, and purchase frequency.
6. Allow the analytics team to work directly with cloud-hosted data without local infrastructure.

### 4. Business Questions to Be Answered
The BI solution must support the following business questions:

1. How does revenue evolve over time by year, month, and day?
2. How does revenue vary by storefront and product?
3. What is the revenue contribution of B2B customers versus consumer customers?
4. Who are the top customers by total spend and by number of orders?
5. How do purchase patterns differ by age group and gender?
6. What is the average order quantity and revenue per product?
7. Which products are ordered most frequently?
8. What is the purchase frequency distribution across the customer base?

### 5. Key Performance Indicators (KPIs)
The solution must support the following 7 KPIs:

1. **Total Revenue**  
   Definition: `SUM(revenue)`  
   Dimensions: store, product, customer, date (year/month/day)

2. **Average Order Value**  
   Definition: `SUM(revenue) / COUNT(purchase_id)`  
   Dimensions: store, customer segment (B2B vs. consumer)

3. **Average Order Quantity**  
   Definition: `SUM(quantity) / COUNT(purchase_id)`  
   Dimensions: product, store

4. **B2B Revenue Share**  
   Definition: `SUM(revenue WHERE company IS NOT NULL) / SUM(revenue)`  
   Dimensions: overall, store

5. **Top Customers by Revenue**  
   Definition: `SUM(revenue)` ranked  
   Dimensions: top-N per store or overall

6. **Purchase Frequency per Customer**  
   Definition: `COUNT(purchase_id)` per `customer_id`  
   Output: distribution across the customer base

7. **Revenue Trend**  
   Definition: `SUM(revenue)` by year, month, and day of week

### 6. Data Sources
The only data source is the Airbyte Cloud connector **Sample Data (Faker)**, already configured in the workspace.

#### 6.1 Source Streams and Schemas

**users**  
One row per customer  
Fields:
- `id`
- `name`
- `email`
- `gender`
- `age`
- `company`

**products**  
One row per product  
Fields:
- `id`
- `name`
- `description`
- `store_name`
- `list_price`

**purchases**  
One row per transaction  
Fields:
- `id`
- `customer_id`
- `product_id`
- `quantity`
- `revenue`
- `store_name`
- `purchase_date`

### 7. Functional Requirements
The BI solution must meet the following functional requirements:

#### 7.1 Data Ingestion
- The solution must ingest data from the Airbyte Cloud source **Sample Data (Faker)**.
- The solution must load the three available streams: `users`, `products`, and `purchases`.
- The ingestion process must run daily.
- The sync mode must be **full-refresh-overwrite**.

#### 7.2 Data Storage
- The solution must use a cloud-hosted data warehouse.
- The selected warehouse must be **Supabase/PostgreSQL**.
- No local infrastructure is allowed.
- Data must remain accessible in the cloud.

#### 7.3 Data Access
- The analytics team must be able to query the warehouse directly using SQL.
- The solution must support analysis by:
  - storefront
  - product
  - customer
  - date (year, month, day)
  - customer segment (B2B vs. consumer)
  - gender
  - age group

#### 7.4 Analytical Capabilities
- The solution must support revenue analysis over time.
- The solution must support customer segmentation based on the `company` field:
  - customers with a non-null `company` field are considered B2B
  - customers with a null `company` field are considered consumer
- The solution must support product performance analysis.
- The solution must support customer-level analysis, including top customers and purchase frequency.
- The solution must support demographic analysis by age group and gender.

### 8. Open Questions / Clarifications Needed
The following items remain ambiguous or incomplete and require future clarification:

1. **Age group definition**  
   The required analysis mentions age group, but no age group bands were defined. A business decision is needed on how age groups should be segmented.

2. **Day-of-week handling for revenue trend**  
   The KPI definition includes day of week, but no specific reporting convention was provided. Clarification is needed on whether this should follow a specific locale or calendar standard.

3. **Top-N definition for top customers**  
   The requirement mentions top-N per store or overall, but the exact N value was not specified.

4. **Historical preservation under full-refresh-overwrite**  
   The goal states that historical data must not be lost, but the ingestion mode specified is full-refresh-overwrite. It is unclear whether historical preservation should be handled through downstream modeling, snapshots, or another mechanism.

### 9. Assumptions
The following assumptions are made based on the elicitation:

- The analytics team will use SQL directly against the warehouse.
- The source data provided by Airbyte Cloud is the only data source in scope.
- Revenue is analyzed using the `revenue` field from the `purchases` stream.
- Purchase quantity is analyzed using the `quantity` field from the `purchases` stream.
- Customer segmentation into B2B and consumer is determined solely by whether `company` is null or non-null.
- Storefront analysis uses the `store_name` field from both `products` and `purchases`.

### 10. Scope
#### In Scope
- Cloud-hosted BI data warehouse in Supabase/PostgreSQL
- Daily Airbyte syncs from Sample Data (Faker)
- Loading of `users`, `products`, and `purchases`
- SQL-based access for the analytics team
- Support for the defined business questions and KPIs
- Analysis by storefront, product, customer, time, gender, age, and customer segment

#### Out of Scope
- Local infrastructure
- Additional data sources beyond Sample Data (Faker)
- Technical development tooling for non-SQL users
- Any requirements not explicitly stated in the elicitation history

### 11. Success Criteria
The solution will be considered successful when:

1. The analytics team can query the warehouse directly using SQL.
2. Daily Airbyte syncs complete successfully using full-refresh-overwrite.
3. The warehouse remains cloud-accessible with no local infrastructure.
4. The team can produce the 7 defined KPIs.
5. The team can answer the listed business questions using the loaded data.
6. Historical analysis remains available for reporting and trend analysis.

### 12. Stakeholders
- **Business User / Primary Stakeholder:** PrimeShelf analytics team
- **End Users:** 4 analytics team members at PrimeShelf

### 13. Approval
This BRD reflects the requirements gathered during elicitation and is ready for review and approval by PrimeShelf stakeholders.