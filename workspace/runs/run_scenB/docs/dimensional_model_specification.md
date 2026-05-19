# Dimensional Model Specification

## 1. Business Context
PrimeShelf requires a cloud-based BI solution to replace manual spreadsheet exports with direct SQL access to a cloud-hosted data warehouse. The solution must support historical analysis, revenue analysis by storefront, product, customer, and time, as well as customer segmentation by B2B vs. consumer, gender, and age.

## 2. Business Process
The business process modeled is marketplace purchasing activity. Each purchase transaction is captured in the `purchases` stream and can be analyzed alongside customer attributes from `users` and product attributes from `products`.

## 3. Grain
The primary fact is at the level of one purchase transaction.

- One row represents one transaction in the `purchases` stream.
- Each transaction is associated with one customer and one product.
- Storefront is available on both `products` and `purchases`.
- Purchase date supports analysis by year, month, day, and day of week.

## 4. Fact Table
### 4.1 Fact Name
`fact_purchases`

### 4.2 Fact Type
Transactional fact table

### 4.3 Measures
- `quantity`
- `revenue`

### 4.4 Degenerate Dimension
- `purchase_id`

## 5. Dimensions
### 5.1 `dim_customer`
Source: `users`
Attributes:
- `customer_id`
- `name`
- `email`
- `gender`
- `age`
- `company`
- `customer_segment` derived from `company`:
  - B2B when `company` is not null
  - consumer when `company` is null

### 5.2 `dim_product`
Source: `products`
Attributes:
- `product_id`
- `name`
- `description`
- `store_name`
- `list_price`

### 5.3 `dim_store`
Source: derived from storefront values in the source data
Attributes:
- `store_name`

### 5.4 `dim_date`
Source: derived from `purchase_date`
Attributes:
- `date_key`
- `purchase_date`
- `year`
- `month`
- `day`
- `day_of_week`

## 6. Hierarchies
### 6.1 Date Hierarchy
- Year
- Month
- Day

### 6.2 Customer Hierarchy / Segmentation
- Customer
- Customer segment
- Gender
- Age

### 6.3 Store Hierarchy
- Storefront

### 6.4 Product Hierarchy
- Product

## 7. Open Questions
The following items remain ambiguous or incomplete in the BRD and require future clarification:

1. **Age group definition**  
   The BRD requires analysis by age group, but no age group bands are defined.

2. **Day-of-week handling**  
   The BRD includes day of week in the Revenue Trend KPI, but no locale or calendar convention is specified.

3. **Top-N definition**  
   The BRD mentions top-N customers per store or overall, but the exact N is not specified.

4. **Historical preservation under full-refresh-overwrite**  
   The BRD requires historical preservation, but the ingestion mode is full-refresh-overwrite. The mechanism for preserving history is not defined.

5. **Storefront modeling ambiguity**  
   Storefront appears in both `products` and `purchases`. The BRD does not specify whether storefront should be treated as a shared conformed dimension or retained separately in each source context.

## 8. Design Notes
- The model supports direct SQL querying in Supabase/PostgreSQL.
- The model is based exclusively on the three source streams: `users`, `products`, and `purchases`.
- Historical analysis requirements are acknowledged, but the BRD does not define the implementation approach for preserving history under overwrite syncs.