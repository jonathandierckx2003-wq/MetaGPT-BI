# Validation Feedback Report

## Overall outcome

REJECTED

## Phase 1: Structural and technical validation

| table name | check performed | PASS/FAIL | details |
|---|---|---:|---|
| stg_customer_details | Existence and row population | PASS | Table exists and contains data: 3,900 rows. |
| stg_e_commerce_sales_data | Existence and row population | PASS | Table exists and contains data: 3,294 rows. |
| stg_product_details | Existence and row population | PASS | Table exists and contains data: 10,002 rows. |
| dim_customer | Schema presence vs. logical model | PASS | Table exists and schema matches the published logical model at a high level. |
| dim_product | Schema presence vs. logical model | PASS | Table exists and schema matches the published logical model at a high level. |
| dim_season | Schema presence vs. logical model | PASS | Table exists and schema matches the published logical model at a high level. |
| dim_date | Schema presence vs. logical model | PASS | Table exists and schema matches the published logical model at a high level. |
| dim_promo_code | Schema presence vs. logical model | PASS | Table exists and schema matches the published logical model at a high level. |
| dim_subscription_status | Schema presence vs. logical model | PASS | Table exists and schema matches the published logical model at a high level. |
| dim_geography | Schema presence vs. logical model | PASS | Table exists and schema matches the published logical model at a high level. |
| dim_age_group | Schema presence vs. logical model | PASS | Table exists and schema matches the published logical model at a high level. |
| dim_purchase_frequency_segment | Schema presence vs. logical model | PASS | Table exists and schema matches the published logical model at a high level. |
| dim_review | Schema presence vs. logical model | PASS | Table exists and schema matches the published logical model at a high level. |
| fact_commerce_interaction | Schema presence vs. logical model | PASS | Table exists and schema matches the published logical model at a high level. |
| fact_customer_segmentation | Schema presence vs. logical model | PASS | Table exists and schema matches the published logical model at a high level. |
| All transformed tables | Read-only verification of row counts, PK uniqueness, FK integrity, null/duplicate checks | FAIL | Validation queries failed due to conversion errors caused by source data formatting issues: non-ISO timestamp values in sales data and currency-formatted values in product data. Because of these failures, full structural integrity could not be verified across all transformed tables. |

## Phase 2: Requirements traceability validation

### Queries and analyses (BRD Section 4)

| query name | SUPPORTED/UNSUPPORTED | details |
|---|---|---|
| Which product categories and seasons drive the most revenue? | UNSUPPORTED | Supported in principle by the warehouse design, but cannot be confirmed as fully computable because fact table validation failed due to casting/conversion errors in source data. |
| Do subscription customers spend more, and how does discount/promo use affect order value? | UNSUPPORTED | Dimensions/facts intended to support this analysis exist, but unresolved source formatting issues prevent reliable validation of revenue, order value, discount, and promo relationships. |
| What is the conversion funnel from product views to purchases, by category? | UNSUPPORTED | The model includes fields intended for views/purchases, but fact contents and relationships could not be fully validated because warehouse queries failed. |
| How are customers distributed across US states, age groups, and purchase frequency segments? | UNSUPPORTED | Supporting dimensions and segmentation fact exist, but end-to-end traceability cannot be confirmed while transformed-table validation remains incomplete. |
| What is the average review rating per category, and does it vary by season? | UNSUPPORTED | Review-related structures are present, but the underlying fact table could not be fully validated due to source casting issues. |

### KPIs and metrics (BRD Section 5)

| KPI name | COMPUTABLE / NOT_COMPUTABLE | details |
|---|---|---|
| Total revenue | NOT_COMPUTABLE | Intended support exists, but full validation of fact data and joins failed due to source formatting/casting errors. |
| Average order value | NOT_COMPUTABLE | Cannot be confirmed because sales data contains non-ISO timestamp values and fact validation did not complete successfully. |
| Discount rate | NOT_COMPUTABLE | Metric structure exists in principle, but reliable computation cannot be confirmed without successful fact validation. |
| Promo code redemption rate | NOT_COMPUTABLE | Promo dimension exists, but metric cannot be confirmed as computable due to incomplete validation of transformed data. |
| Product conversion rate | NOT_COMPUTABLE | Views/purchases support is intended, but conversion logic cannot be validated end-to-end because warehouse queries failed. |
| Customer purchase frequency distribution | NOT_COMPUTABLE | Segmentation structures exist, but full validation of segmentation outputs and integrity checks did not complete. |
| Average review rating per category | NOT_COMPUTABLE | Review dimension exists, but fact-level validation failed, preventing confirmation of computability. |

### Data sources (BRD Section 6)

| source name | INGESTED / MISSING | details |
|---|---|---|
| `workspace\data\customer_details.csv` | INGESTED | Confirmed present via `stg_customer_details` with 3,900 rows. |
| `workspace\data\E-commerce_sales_data.csv` | INGESTED | Confirmed present via `stg_e_commerce_sales_data` with 3,294 rows. |
| `workspace\data\product_details.csv` | INGESTED | Confirmed present via `stg_product_details` with 10,002 rows. |

## Summary and next steps

1. **Structural validation of transformed tables could not be completed**
   - **What failed:** Read-only verification queries for row counts, PK uniqueness, FK integrity, and null/duplicate checks across transformed tables.
   - **What was found vs. expected:** The tables exist, but validation queries failed because source values could not be cast reliably. Expected: successful execution of integrity checks across all transformed tables.
   - **Task ID(s) to re-execute:** **Task 9** (`dim_date`), **Task 15** (`dim_review`), **Task 16** (`fact_commerce_interaction`), and any upstream transformation tasks impacted by the same casting issues, especially **Task 7** (`dim_product`) if currency-formatted product fields are being parsed there.

2. **Source data formatting issues block warehouse validation**
   - **What failed:** Conversion errors during warehouse queries.
   - **What was found vs. expected:** Non-ISO timestamp values in sales data and currency-formatted values in product data caused query failures. Expected: source values normalized to warehouse-compatible formats before transformation and validation.
   - **Task ID(s) to re-execute:** **Task 4** (`stg_e_commerce_sales_data`), **Task 5** (`stg_product_details`), and downstream transformation tasks **Task 7**, **Task 9**, **Task 15**, **Task 16**.

3. **Requirements traceability is only partial**
   - **What failed:** BRD Section 4 business questions and Section 5 KPIs could not be confirmed as fully supported/computable.
   - **What was found vs. expected:** The warehouse contains the intended analytical structures, but because fact-table contents and relationships were not fully validated, the required analyses and KPIs remain unconfirmed. Expected: end-to-end traceability from BRD requirements to validated warehouse outputs.
   - **Task ID(s) to re-execute:** **Task 16** (`fact_commerce_interaction`) and **Task 17** (`fact_customer_segmentation`), after fixing upstream source formatting issues in **Task 4** and **Task 5**.

4. **Overall validation outcome remains REJECTED**
   - **What failed:** Phase 1 and Phase 2 did not both pass.
   - **What was found vs. expected:** Staging ingestion succeeded, and transformed tables were created, but technical validation and requirements traceability were not fully verifiable due to query failures.
   - **Task ID(s) to re-execute:** Re-run the affected ingestion and transformation chain starting from **Task 4** and **Task 5**, then validate **Tasks 7, 9, 15, 16, and 17**.