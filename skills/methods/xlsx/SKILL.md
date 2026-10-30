---
name: xlsx
description: >-
  Use whenever an Excel workbook (.xlsx, .xlsm, .xls, .xlsb) must be read,
  inspected, extracted, converted, cleaned, analyzed, edited, validated, or
  written, whether the workbook is an input data source, intermediate artifact,
  or final deliverable. Also use for .csv/.tsv when spreadsheet-style output or
  Excel conversion is needed. Trigger especially for large Excel files,
  slow/failed Excel reads, memory-efficient column/sheet extraction, formula
  preservation, optional user-assisted formula verification, formatting, financial models, multi-sheet
  workbooks, and tabular cleanup exported to Excel. Do NOT use only when no
  spreadsheet file is involved, or for pure database/API/text/PDF/Word/HTML
  tasks that do not need spreadsheet parsing or output.
allowed-tools: Read Write Edit Bash Grep Glob
license: Proprietary. LICENSE.txt has complete terms
metadata: {"version": "1.1", "skill-author": "K-Dense Inc."}
compatibility: Requires Python 3.8+
---

# Requirements for Outputs

## All Excel files

### Professional Font
- Use a consistent, professional font (e.g., Arial, Times New Roman) for all deliverables unless otherwise instructed by the user

### Zero Formula Errors
- Every Excel model MUST be delivered with ZERO formula errors (#REF!, #DIV/0!, #VALUE!, #N/A, #NAME?)

### Preserve Existing Templates (when updating templates)
- Study and EXACTLY match existing format, style, and conventions when modifying files
- Never impose standardized formatting on files with established patterns
- Existing template conventions ALWAYS override these guidelines

## Financial models

### Color Coding Standards
Unless otherwise stated by the user or existing template

#### Industry-Standard Color Conventions
- **Blue text (RGB: 0,0,255)**: Hardcoded inputs, and numbers users will change for scenarios
- **Black text (RGB: 0,0,0)**: ALL formulas and calculations
- **Green text (RGB: 0,128,0)**: Links pulling from other worksheets within same workbook
- **Red text (RGB: 255,0,0)**: External links to other files
- **Yellow background (RGB: 255,255,0)**: Key assumptions needing attention or cells that need to be updated

### Number Formatting Standards

#### Required Format Rules
- **Years**: Format as text strings (e.g., "2024" not "2,024")
- **Currency**: Use $#,##0 format; ALWAYS specify units in headers ("Revenue ($mm)")
- **Zeros**: Use number formatting to make all zeros "-", including percentages (e.g., "$#,##0;($#,##0);-")
- **Percentages**: Default to 0.0% format (one decimal)
- **Multiples**: Format as 0.0x for valuation multiples (EV/EBITDA, P/E)
- **Negative numbers**: Use parentheses (123) not minus -123

### Formula Construction Rules

#### Assumptions Placement
- Place ALL assumptions (growth rates, margins, multiples, etc.) in separate assumption cells
- Use cell references instead of hardcoded values in formulas
- Example: Use =B5*(1+$B$6) instead of =B5*1.05

#### Formula Error Prevention
- Verify all cell references are correct
- Check for off-by-one errors in ranges
- Ensure consistent formulas across all projection periods
- Test with edge cases (zero values, negative numbers)
- Verify no unintended circular references

#### Documentation Requirements for Hardcodes
- Comment or in cells beside (if end of table). Format: "Source: [System/Document], [Date], [Specific Reference], [URL if applicable]"
- Examples:
  - "Source: Company 10-K, FY2024, Page 45, Revenue Note, [SEC EDGAR URL]"
  - "Source: Company 10-Q, Q2 2025, Exhibit 99.1, [SEC EDGAR URL]"
  - "Source: Bloomberg Terminal, 8/15/2025, AAPL US Equity"
  - "Source: FactSet, 8/20/2025, Consensus Estimates Screen"

# XLSX creation, editing, and analysis

## Overview

A user may ask you to create, edit, or analyze the contents of an .xlsx file. You have different tools and workflows available for different tasks.

## Installation

```bash
uv pip install openpyxl pandas
```

Optional — faster Excel reading across formats with pandas 2.2+:

```bash
uv pip install python-calamine
```

For untrusted workbook files, harden openpyxl against XML expansion attacks:

```bash
uv pip install defusedxml
```

See [openpyxl security guidance](https://openpyxl.readthedocs.io/en/stable/index.html#security).

## Formula Handling and Verification

Do not require any external spreadsheet application for ordinary spreadsheet tasks. Default workflows should read, clean, edit, format, export, and write formulas with pandas/openpyxl only.

Openpyxl preserves formulas as strings but does not calculate formula results. For ordinary deliverables, write or preserve formulas and let the user's spreadsheet application refresh them when opened.

Only start formula verification when the user explicitly asks to check formulas, validate calculated results, audit formula errors, or ensure a model has no Excel formula errors. In that case:

1. Save the workbook with formulas preserved.
2. Run static checks in Python for obvious issues such as missing sheets, broken references, empty referenced ranges, likely division by zero, and existing Excel error strings.
3. Ask the user to open the workbook in Excel or WPS, wait for formulas to refresh, save, close the file, and confirm when done.
4. Re-open the saved workbook with `openpyxl.load_workbook(path, data_only=True)` and inspect cached values for `#REF!`, `#DIV/0!`, `#VALUE!`, `#N/A`, `#NAME?`, empty key outputs, or inconsistent sampled calculations.
5. If errors are found, fix the formulas and repeat the user-refresh/read-back loop.

Do not call external spreadsheet applications from this skill; it intentionally avoids desktop-app dependencies.

## Reading and analyzing data

### Data analysis with pandas
For data analysis, visualization, and basic operations, use **pandas** which provides powerful data manipulation capabilities:

```python
import pandas as pd

# Read Excel (.xlsx default engine: openpyxl)
df = pd.read_excel('file.xlsx')  # Default: first sheet
all_sheets = pd.read_excel('file.xlsx', sheet_name=None)  # All sheets as dict

# Optional: calamine engine (pandas 2.2+) — faster, supports .xlsx/.xls/.xlsb/.xlsm/.ods
# df = pd.read_excel('file.xlsx', engine='calamine')

# Analyze
df.head()      # Preview data
df.info()      # Column info
df.describe()  # Statistics

# Write Excel
df.to_excel('output.xlsx', index=False)
```

### Large Excel files / performance

For large workbooks, roughly 50MB+ or when `pd.read_excel` is slow:
- First inspect workbook structure: sheet names, dimensions, headers, and needed columns.
- Avoid `sheet_name=None` unless every sheet is required.
- Use targeted `sheet_name`, `usecols`, `nrows`, and `dtype`.
- Prefer `engine="calamine"` when available for faster reads.
- For openpyxl inspection, use `read_only=True` and iterate rows instead of loading the workbook normally.
- Convert only needed sheets/columns to CSV or Parquet intermediates before heavy analysis when appropriate.
- For long-running extraction scripts, write progress logs with explicit flush, such as `print(..., flush=True)` or line-buffered file logging.
- If a background extraction task shows no log growth, file-size change, CPU activity, or staged output, change diagnostic action instead of repeatedly polling the same status.

## Excel File Workflows

## CRITICAL: Use Formulas, Not Hardcoded Values

**Always use Excel formulas instead of calculating values in Python and hardcoding them.** This ensures the spreadsheet remains dynamic and updateable.

### ❌ WRONG - Hardcoding Calculated Values
```python
# Bad: Calculating in Python and hardcoding result
total = df['Sales'].sum()
sheet['B10'] = total  # Hardcodes 5000

# Bad: Computing growth rate in Python
growth = (df.iloc[-1]['Revenue'] - df.iloc[0]['Revenue']) / df.iloc[0]['Revenue']
sheet['C5'] = growth  # Hardcodes 0.15

# Bad: Python calculation for average
avg = sum(values) / len(values)
sheet['D20'] = avg  # Hardcodes 42.5
```

### ✅ CORRECT - Using Excel Formulas
```python
# Good: Let Excel calculate the sum
sheet['B10'] = '=SUM(B2:B9)'

# Good: Growth rate as Excel formula
sheet['C5'] = '=(C4-C2)/C2'

# Good: Average using Excel function
sheet['D20'] = '=AVERAGE(D2:D19)'
```

This applies to ALL calculations - totals, percentages, ratios, differences, etc. The spreadsheet should be able to recalculate when source data changes.

## Common Workflow
1. **Choose tool**: pandas for data, openpyxl for formulas/formatting
2. **Create/Load**: Create new workbook or load existing file
3. **Modify**: Add/edit data, formulas, and formatting
4. **Save**: Write to file
5. **Formula verification (only when explicitly requested)**: Run static checks first. If calculated results must be verified, ask the user to open the workbook in Excel/WPS, save it after formulas refresh, then read cached values back with `openpyxl.load_workbook(path, data_only=True)` and fix any errors found.

### Creating new Excel files

```python
# Using openpyxl for formulas and formatting
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

wb = Workbook()
sheet = wb.active

# Add data
sheet['A1'] = 'Hello'
sheet['B1'] = 'World'
sheet.append(['Row', 'of', 'data'])

# Add formula
sheet['B2'] = '=SUM(A1:A10)'

# Formatting
sheet['A1'].font = Font(bold=True, color='FF0000')
sheet['A1'].fill = PatternFill('solid', start_color='FFFF00')
sheet['A1'].alignment = Alignment(horizontal='center')

# Column width
sheet.column_dimensions['A'].width = 20

wb.save('output.xlsx')
```

### Editing existing Excel files

```python
# Using openpyxl to preserve formulas and formatting
from openpyxl import load_workbook

# Load existing file
wb = load_workbook('existing.xlsx')
sheet = wb.active  # or wb['SheetName'] for specific sheet

# Working with multiple sheets
for sheet_name in wb.sheetnames:
    sheet = wb[sheet_name]
    print(f"Sheet: {sheet_name}")

# Modify cells
sheet['A1'] = 'New Value'
sheet.insert_rows(2)  # Insert row at position 2
sheet.delete_cols(3)  # Delete column 3

# Add new sheet
new_sheet = wb.create_sheet('NewSheet')
new_sheet['A1'] = 'Data'

wb.save('modified.xlsx')
```

## Formula Verification Workflow

Openpyxl can write and preserve formulas but does not evaluate them. Do not use external spreadsheet applications for automatic recalculation.

When the user explicitly asks for formula checking or result verification:

1. Perform static checks before asking the user to refresh the workbook.
2. Tell the user: "Please open the workbook in Excel or WPS, wait for formulas to refresh, save the file, close it, and tell me when it is saved."
3. After the user confirms, load the workbook with `openpyxl.load_workbook(path, data_only=True)` and scan cached values for errors such as `#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?`, `#NULL!`, `#NUM!`, and `#N/A`.
4. For important outputs, verify that cached values are present and sample-check simple calculations in Python when practical.

If the user does not perform the refresh/save step, explain that formula strings are preserved but cached results may be stale or unavailable.

## Formula Verification Checklist

Quick checks to ensure formulas work correctly:

### Essential Verification
- [ ] **Test 2-3 sample references**: Verify they pull correct values before building full model
- [ ] **Column mapping**: Confirm Excel columns match (e.g., column 64 = BL, not BK)
- [ ] **Row offset**: Remember Excel rows are 1-indexed (DataFrame row 5 = Excel row 6)

### Common Pitfalls
- [ ] **NaN handling**: Check for null values with `pd.notna()`
- [ ] **Far-right columns**: FY data often in columns 50+ 
- [ ] **Multiple matches**: Search all occurrences, not just first
- [ ] **Division by zero**: Check denominators before using `/` in formulas (#DIV/0!)
- [ ] **Wrong references**: Verify all cell references point to intended cells (#REF!)
- [ ] **Cross-sheet references**: Use correct format (Sheet1!A1) for linking sheets

### Formula Testing Strategy
- [ ] **Start small**: Test formulas on 2-3 cells before applying broadly
- [ ] **Verify dependencies**: Check all cells referenced in formulas exist
- [ ] **Test edge cases**: Include zero, negative, and very large values

## Best Practices

### Library Selection
- **pandas**: Best for data analysis, bulk operations, and simple data export
- **openpyxl**: Best for complex formatting, formulas, and Excel-specific features (current stable: 3.1.5)

### Working with openpyxl
- Cell indices are 1-based (row=1, column=1 refers to cell A1)
- Use `data_only=True` to read calculated values: `load_workbook('file.xlsx', data_only=True)`
- **Warning**: If opened with `data_only=True` and saved, formulas are replaced with values and permanently lost
- For large files: Use `read_only=True` for reading or `write_only=True` for writing
- Formulas are preserved but not evaluated by openpyxl. For result verification, ask the user to refresh/save in Excel or WPS, then read cached values with `data_only=True`

### Working with pandas
- Specify data types to avoid inference issues: `pd.read_excel('file.xlsx', dtype={'id': str})`
- For large files, read specific columns: `pd.read_excel('file.xlsx', usecols=['A', 'C', 'E'])`
- Handle dates properly: `pd.read_excel('file.xlsx', parse_dates=['date_column'])`

## Code Style Guidelines
**IMPORTANT**: When generating Python code for Excel operations:
- Write minimal, concise Python code without unnecessary comments
- Avoid verbose variable names and redundant operations
- Avoid unnecessary print statements

**For Excel files themselves**:
- Add comments to cells with complex formulas or important assumptions
- Document data sources for hardcoded values
- Include notes for key calculations and model sections
