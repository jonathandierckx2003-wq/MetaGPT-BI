# Dimensional Model Specification

## 1. Purpose
This dimensional model supports monthly HR situation reporting for business users, covering workforce evolution, HR-related costs, absences, year-over-year comparison, and Bradford Index analysis.

The model is designed exclusively from the BRD and targets:
- monthly reporting,
- 24 months of history back from 2018,
- Supabase hosting,
- CSV-based ingestion from 6 source files,
- easy use by non-technical business users.

---

## 2. Business Process
The model supports the following business processes:
1. Workforce headcount reporting
2. Monthly IN and OUT movement reporting
3. Salary cost reporting
4. Absence reporting
5. Bradford Index reporting
6. Year-over-year comparison reporting
7. Anomaly detection support

---

## 3. Grain
The reporting grain is monthly, with person-level support where required.

### Fact grains
- **Monthly workforce snapshot**: one row per month and person/contract active status context.
- **Monthly contract movement**: one row per contract movement event by month.
- **Monthly salary cost**: one row per month and person/contract salary context.
- **Monthly absence**: one row per month and absence occurrence context.
- **Person-level Bradford Index**: one row per person.

---

## 4. Facts
The BRD explicitly requires the following measures.

### 4.1 Fact: Monthly Workforce Snapshot
Supports:
- Monthly headcount
- Headcount by age band
- Headcount by seniority
- Year-over-year comparison for headcount
- Anomaly alerts for workforce trends

**Measures**
- Headcount flag

**Notes**
- Headcount is defined as the number of active contracts in a given month.
- A contract is active when the month has at least one day between the contract start date and end date.

---

### 4.2 Fact: Monthly Contract Movement
Supports:
- Monthly IN
- Monthly OUT
- Year-over-year comparison for IN and OUT
- Anomaly alerts for workforce movements

**Measures**
- IN count
- OUT count

**Notes**
- IN = number of new contracts starting in a given month.
- OUT = number of contracts ending in a given month.

---

### 4.3 Fact: Monthly Salary Cost
Supports:
- Salary cost evolution
- Breakdown by region, age, gender, seniority
- Year-over-year comparison for salary costs
- Anomaly alerts for cost trends

**Measures**
- Salary cost

**Notes**
- The BRD does not define the exact salary cost calculation method.
- The model therefore includes a salary cost measure without specifying the source formula.

---

### 4.4 Fact: Monthly Absence
Supports:
- Absence days
- Breakdown by absence type, period, region, postal code, age
- Year-over-year comparison for absences
- Anomaly alerts for absence trends

**Measures**
- Absence days

**Notes**
- The BRD defines absence days as the number of days a specific person is absent.
- The definition of “period” is ambiguous in the BRD and remains open.

---

### 4.5 Fact: Bradford Index
Supports:
- Bradford Index analysis
- Identification of employees with the highest Bradford Index

**Measures**
- Bradford Index

**Notes**
- The BRD does not define the Bradford Index formula.
- The model stores the index value at person level.

---

## 5. Dimensions
The BRD explicitly requires analysis by the following dimensions.

### 5.1 Date Dimension
Used for monthly reporting and year-over-year comparison.

**Attributes**
- Month
- Month name
- Year
- Year-month key

**Hierarchy**
- Year > Month

---

### 5.2 Person Dimension
Used for person-level analysis and Bradford Index.

**Attributes**
- Individual FDCP
- Person identifier
- Person name

**Notes**
- The BRD explicitly mentions individual FDCP.
- Additional person attributes are not specified in the BRD and should be sourced only if present in the CSV files.

---

### 5.3 Contract Dimension
Used for workforce movement and active contract analysis.

**Attributes**
- Contract identifier
- Contract start date
- Contract end date
- Contract status

**Notes**
- The BRD refers to contracts but does not define the source structure.

---

### 5.4 Age Band Dimension
Used for headcount, salary cost, and absence analysis.

**Attributes**
- Age band

**Notes**
- The BRD does not define the age band ranges.

---

### 5.5 Seniority Dimension
Used for headcount and salary cost analysis.

**Attributes**
- Seniority

**Notes**
- The BRD does not define the seniority calculation or categories.

---

### 5.6 Gender Dimension
Used for headcount and salary cost analysis.

**Attributes**
- Gender

---

### 5.7 Region Dimension
Used for headcount, salary cost, and absence analysis.

**Attributes**
- Region

---

### 5.8 Department Dimension
Used for headcount analysis.

**Attributes**
- Department

---

### 5.9 Category Dimension
Used for headcount analysis.

**Attributes**
- Category

---

### 5.10 Postal Code Dimension
Used for headcount and absence analysis.

**Attributes**
- Postal code

---

### 5.11 Absence Type Dimension
Used for absence analysis.

**Attributes**
- Absence type

---

### 5.12 Period Dimension
Used for absence analysis.

**Attributes**
- Period

**Notes**
- The BRD states that “period” is ambiguous and requires future clarification.

---

## 6. Open Questions
The following items are explicitly ambiguous or incomplete in the BRD and are therefore not resolved in this specification:

1. **Data source structure is unknown.** The exact fields, keys, and relationships in the 6 CSV files are not defined.
2. **Definition of “period” for absence analysis is ambiguous.**
3. **Definition of “seniority” is not specified.**
4. **Definition of “age band” is not specified.**
5. **Bradford Index formula is not specified.**
6. **Anomaly alert rules are not specified.**
7. **Security model details are not specified.**
8. **Person attributes beyond individual FDCP are not specified.**
9. **Contract attributes beyond the existence of contract start and end dates are not specified.**
10. **Salary cost calculation method is not specified.**

---

## 7. Assumptions
No business assumptions beyond the BRD were introduced.

Where the BRD is incomplete, the model keeps the corresponding concept as a placeholder dimension or measure and flags it as open.

---

## 8. Scope Alignment
This model is in scope for:
- monthly HR reporting,
- historical analysis,
- workforce evolution,
- salary cost analysis,
- absence analysis,
- Bradford Index analysis,
- year-over-year comparison,
- anomaly alert support,
- Supabase hosting,
- CSV ingestion.

Out of scope per BRD:
- detailed security implementation,
- non-monthly reporting unless needed for calculation support,
- any KPI or dimension not explicitly requested.

---

## 9. Dimensional Model Summary
### Fact Tables
- Fact_Monthly_Workforce_Snapshot
- Fact_Monthly_Contract_Movement
- Fact_Monthly_Salary_Cost
- Fact_Monthly_Absence
- Fact_Bradford_Index

### Dimension Tables
- Dim_Date
- Dim_Person
- Dim_Contract
- Dim_Age_Band
- Dim_Seniority
- Dim_Gender
- Dim_Region
- Dim_Department
- Dim_Category
- Dim_Postal_Code
- Dim_Absence_Type
- Dim_Period