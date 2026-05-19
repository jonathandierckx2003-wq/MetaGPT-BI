# Business Requirement Document (BRD)

## 1. Document Information

**Document Title:** HR Monthly Situation Reporting BRD  
**Version:** 1.0  
**Status:** Draft  
**Prepared For:** HR Manager and Department Heads  
**Prepared By:** AI Assistant  
**Date:** 2026-05-09  

---

## 2. Business Context and Objective

The business requires a monthly HR situation reporting solution covering **24 months of history back from 2018**. The solution must provide a clear and easy-to-use view of workforce evolution and HR-related costs and absences for business users with limited technical expertise.

The reporting solution will support:
- workforce planning,
- HR and department cost control,
- employee churn reduction,
- absence analysis,
- and future hiring decisions.

The final datamodel will be hosted in **Supabase** and populated from **6 CSV files** located in `C:\Users\jonat\MetaGPT-BI\workspace\data`.

---

## 3. Business Goals

The solution must enable each user to have a clear understanding of the workforce they manage in order to take appropriate action.

### Business Goals
1. **Provide a clear monthly view of workforce evolution**
   - Understand headcount trends over time.
   - Track new hires and exits by month.

2. **Support workforce planning**
   - Identify staffing needs based on historical trends.
   - Anticipate future hiring requirements.

3. **Improve cost control**
   - Monitor salary cost evolution by relevant dimensions.
   - Help department heads control HR-related costs.

4. **Reduce employee churn**
   - Track IN and OUT movements by month.
   - Identify patterns that may indicate turnover risks.

5. **Analyze absences**
   - Understand absence volume and distribution.
   - Identify absence causes and patterns.

6. **Enable actionable HR decision-making**
   - Provide charts, historical comparisons, and anomaly alerts.
   - Allow business users to quickly interpret workforce data.

---

## 4. Business Questions to Be Answered

The reporting solution must answer the following business questions. Each question is linked to one or more business goals and KPIs.

| ID | Business Question / Analysis | Linked Goal(s) | Linked KPI(s) |
|---|---|---|---|
| Q1 | How does headcount evolve by month? | Business Goal 1, 2 | Monthly headcount |
| Q2 | How many contracts IN and OUT occur each month? | Business Goal 1, 4 | Monthly IN, Monthly OUT |
| Q3 | How does headcount vary by age band and seniority? | Business Goal 1, 2 | Monthly headcount by age band, Monthly headcount by seniority |
| Q4 | How do salary costs evolve by region, age, gender, and seniority? | Business Goal 3 | Salary cost evolution |
| Q5 | How are absences distributed by absence type, period, region, postal code, and age? | Business Goal 5 | Absence days |
| Q6 | How do current results compare to last year? | Business Goal 1, 3, 5 | Monthly headcount, IN, OUT, salary costs, absences |
| Q7 | Which employees have the highest Bradford Index? | Business Goal 5, 6 | Bradford Index |
| Q8 | How can users identify anomalies and unusual trends in workforce, cost, or absence data? | Business Goal 6 | Monthly headcount, IN, OUT, salary costs, absences |

---

## 5. KPI Definitions and Reporting Scope

All KPIs must be calculated at **monthly level** and based on the following dimensions:
- Age band
- Seniority
- Gender
- Region
- Department
- Category
- Postal code
- Individual FDCP

### 5.1 KPI Definitions

#### 5.1.1 Monthly Headcount
- **Definition:** Number of active contracts in a given month.
- **Rule:** A contract is active when the month has at least one day between the contract start date and end date.
- **Grain:** Monthly.

#### 5.1.2 Monthly IN
- **Definition:** Number of new contracts starting in a given month.
- **Grain:** Monthly.

#### 5.1.3 Monthly OUT
- **Definition:** Number of contracts ending in a given month.
- **Grain:** Monthly.

#### 5.1.4 Headcount by Age Band
- **Definition:** Monthly headcount segmented by age band.
- **Grain:** Monthly.

#### 5.1.5 Headcount by Seniority
- **Definition:** Monthly headcount segmented by seniority.
- **Grain:** Monthly.

#### 5.1.6 Salary Cost Evolution
- **Definition:** Monthly evolution of salary costs.
- **Breakdowns required:** Region, age, gender, seniority.
- **Grain:** Monthly.

#### 5.1.7 Absence Days
- **Definition:** Number of days a specific person is absent.
- **Breakdowns required:** Absence type, period, region, postal code, age.
- **Grain:** Monthly.

#### 5.1.8 Bradford Index
- **Definition:** Ranking of employees based on Bradford Index.
- **Grain:** Individual FDCP / person level.

---

## 6. Business Requirements

### 6.1 Functional Requirements

#### FR1 — Monthly HR Reporting
The solution shall provide monthly HR reporting covering at least 24 months of history back from 2018.

#### FR2 — Workforce Headcount Analysis
The solution shall display monthly headcount evolution based on active contracts.

#### FR3 — IN and OUT Analysis
The solution shall display monthly counts of new hires (IN) and exits (OUT).

#### FR4 — Workforce Segmentation
The solution shall allow analysis of headcount by:
- age band,
- seniority,
- gender,
- region,
- department,
- category,
- postal code,
- individual FDCP.

#### FR5 — Salary Cost Analysis
The solution shall provide monthly salary cost evolution and allow breakdowns by:
- region,
- age,
- gender,
- seniority.

#### FR6 — Absence Analysis
The solution shall provide monthly absence analysis by:
- absence type,
- period,
- region,
- postal code,
- age.

#### FR7 — Year-over-Year Comparison
The solution shall support comparison to last year for the main KPIs.

#### FR8 — Bradford Index Analysis
The solution shall identify employees with the highest Bradford Index.

#### FR9 — Charts and Visual Exploration
The solution shall provide charts suitable for business users to easily interpret trends and patterns.

#### FR10 — Anomaly Alerts
The solution shall support anomaly alerts to highlight unusual workforce, cost, or absence patterns.

#### FR11 — Historical Data Access
The solution shall provide easy access to historical data.

#### FR12 — Monthly Refresh
The solution shall support a monthly refresh cycle.

#### FR13 — Initial Full Load
The solution shall support a full initial load.

#### FR14 — Data Source Integration
The solution shall use all 6 CSV files located in `C:\Users\jonat\MetaGPT-BI\workspace\data` to populate the data model.

#### FR15 — Supabase Hosting
The final datamodel shall be hosted in Supabase.

#### FR16 — Security by User Access Rights
The solution shall support access security per user based on access rights.

---

### 6.2 Non-Functional Requirements

#### NFR1 — Ease of Use
The solution shall be easy to access and understand for business users with limited technical level.

#### NFR2 — Performance
The solution shall provide responsive access to monthly historical reporting and charts.

#### NFR3 — Scalability
The solution shall be suitable for monthly refresh and historical growth over time.

#### NFR4 — Data Accessibility
The solution shall ensure easy access to historical data for end-users.

#### NFR5 — Security
The solution shall support future user-based access control, while allowing all data to be accessible in the first phase.

---

## 7. Data Requirements

### 7.1 Data Sources
- Source format: CSV files
- Source location: `C:\Users\jonat\MetaGPT-BI\workspace\data`
- Number of files: 6
- All 6 files must be used to populate the data model.

### 7.2 Data Model Hosting
- Target platform: Supabase

### 7.3 Data Granularity
- Reporting granularity: Monthly
- Entity granularity: Individual FDCP / person level where required

### 7.4 Data Scope
The solution must support analysis across:
- Firm
- Department
- Category
- Person
- Age band
- Seniority
- Gender
- Region
- Postal code
- Absence type
- Period

---

## 8. Assumptions, Constraints, and Open Questions

### 8.1 Assumptions
1. The 6 CSV files contain sufficient data to calculate the requested KPIs.
2. Monthly reporting will be based on the available contract, salary, and absence data in the source files.
3. In the first phase, all data will be accessible to users.
4. The solution will be designed for business users with limited technical expertise.

### 8.2 Constraints
1. Data sources are limited to CSV files located in the specified folder.
2. The final datamodel must be hosted in Supabase.
3. Refresh frequency is monthly.
4. The initial load is full only.

### 8.3 Open Questions Requiring Future Clarification
1. **Data source structure is unknown.** No source schemas were inspected, so the exact fields, keys, and relationships in the 6 CSV files remain to be confirmed.
2. **Definition of “period” for absence analysis is ambiguous.** It is not specified whether this refers to month, absence interval, or another time grouping.
3. **Definition of “seniority” is not specified.** The calculation method or source field for seniority is not defined.
4. **Definition of “age band” is not specified.** The age ranges to be used must be confirmed.
5. **Bradford Index formula is not specified.** The exact calculation method and thresholds are not provided.
6. **Anomaly alert rules are not specified.** The criteria for detecting anomalies must be defined later.
7. **Security model details are not specified.** User roles, access scopes, and row-level restrictions are not yet defined for the future phase.

---

## 9. Acceptance Criteria

The solution will be considered acceptable when:

1. Monthly headcount can be reported for at least 24 months of history back from 2018.
2. Monthly IN and OUT counts are available.
3. Headcount can be analyzed by age band, seniority, gender, region, department, category, postal code, and individual FDCP.
4. Salary costs can be analyzed monthly by region, age, gender, and seniority.
5. Absences can be analyzed monthly by absence type, period, region, postal code, and age.
6. Year-over-year comparison is available for the main KPIs.
7. Employees with the highest Bradford Index can be identified.
8. Charts are available for business users.
9. Anomaly alerts are supported.
10. The data model is hosted in Supabase.
11. All 6 CSV files are used as source inputs.
12. The solution supports monthly refresh and initial full load.
13. Access is secured per user in future phases, while all data remains accessible in the first phase.

---

## 10. Stakeholders

### Primary Users
- HR Manager
- Department Heads

### User Characteristics
- Business users
- Limited technical level
- Need easy access to historical data, charts, and alerts

### Business Responsibilities Supported
- Manage teams
- Control department costs including HR costs
- Reduce employee churn
- Understand absence causes
- Plan future hiring needs

---

## 11. Scope

### 11.1 In Scope
- Monthly HR reporting
- 24 months of historical analysis back from 2018
- Headcount, IN, OUT, salary cost, and absence analysis
- Breakdown by required dimensions
- Year-over-year comparison
- Bradford Index analysis
- Charts and anomaly alerts
- CSV-based data ingestion
- Supabase-hosted datamodel
- Monthly refresh and initial full load

### 11.2 Out of Scope
- Detailed security implementation for future phases
- Any data sources other than the 6 CSV files
- Non-monthly reporting granularity unless needed for calculation support
- Any KPI or dimension not explicitly requested in the elicitation history

---

## 12. Approval

This BRD reflects the requirements gathered during the elicitation phase and is ready for validation by the business stakeholders.

**Approval Required From:**
- HR Manager
- Department Heads

**Approval Status:** Pending