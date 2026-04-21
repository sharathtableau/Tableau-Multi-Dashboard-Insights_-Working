# Troubleshooting Crosstab Data Fetching Issues

## Problem Description
The application is unable to fetch crosstab/CSV data from all sheets in the selected dashboard. You have 2 sheets in your dashboard but the data isn't being captured for AI insights.

## What Was Fixed

### 1. **Removed View Filtering Logic**
**Before:** The code tried to filter out "dashboard" type views, which sometimes prevented actual worksheet data from being fetched.

**After:** Now attempts to fetch CSV data from ALL views (both sheets and dashboards) since Tableau's API can be inconsistent about sheetType classification.

### 2. **Enhanced Logging**
Added detailed logging at every step so you can see exactly what's happening:
- Which views are found
- What sheetType each view has
- Which endpoint succeeds (CSV vs crosstab)
- How many rows were retrieved from each sheet

### 3. **Fallback Retry Logic**
If initial fetch fails, the code now:
- Retries without filters (sometimes filters break data export)
- Logs detailed error messages with possible causes
- Tests both CSV and Excel crosstab endpoints

## Steps to Debug Your Issue

### Step 1: Run the Test Script

1. **Update the test script** with your workbook ID:
   ```python
   # In test_crosstab_debug.py, line 30
   TEST_WORKBOOK_ID = "YOUR_ACTUAL_WORKBOOK_ID_HERE"
   ```
   
   To find your workbook ID:
   - Open your dashboard in Tableau
   - Look at the URL: `.../views/WorkbookName/DashboardName`
   - OR check the browser console when using the app - it logs the IDs

2. **Run the test script**:
   ```bash
   python test_crosstab_debug.py
   ```

3. **Review the output**:
   - Does it find your 2 sheets?
   - What sheetType does Tableau report for them?
   - Does it successfully fetch CSV data?

### Step 2: Check Application Logs

When you use the web UI and click "Export Dashboard", check the Flask server logs:

```bash
# You should see output like:
DEBUG - Attempting CSV export for view abc-123...
INFO - ✓ CSV endpoint succeeded for view abc-123
INFO - ✓ SUCCESS: Got 45 lines from 'Sheet 1' (type: worksheet)
INFO - ✓ SUCCESS: Got 32 lines from 'Sheet 2' (type: worksheet)
INFO - ✓✓✓ SUCCESS: Combined CSV data from 2 sheets: Sheet 1, Sheet 2
```

If you see errors instead:
```
WARNING - No CSV data returned for 'Sheet 1' (type: dashboard)
⚠️ CRITICAL: No CSV data collected from ANY sheet in workbook!
```

This tells us WHAT is failing, which helps diagnose WHY.

### Step 3: Verify Tableau Permissions

Make sure your Tableau user/PAT has these permissions:
- **View Data** permission (underlying data)
- **Download Summary Data** permission
- **Download Full Data** permission (ideal)

Without these, the crosstab endpoints will return empty results.

### Step 4: Check Workbook Configuration

Some workbooks have settings that block data export:
1. Open workbook in Tableau Desktop
2. Go to: **Server → Properties**
3. Check if **"Allow viewers to download summary data"** is enabled
4. For full data: **"Allow viewers to download underlying data"**

## Common Issues & Solutions

### Issue 1: Sheets Show as "dashboard" Type

**Symptom:** Both sheets report `sheetType: 'dashboard'` instead of `'worksheet'`

**Cause:** Sometimes when you publish a dashboard with multiple sheets, Tableau groups them under a single dashboard view.

**Solution:** Try accessing individual worksheets directly:
- In Tableau web URL, navigate to the specific sheet (not dashboard view)
- Use the sheet's contentUrl in the format: `WorkbookName/SheetName`
- The test script will show you the contentUrl for each view

### Issue 2: Custom SQL or Stored Procedures

**Symptom:** CSV endpoint returns empty data

**Cause:** Some custom SQL queries or stored procedures don't support crosstab export.

**Workaround:** 
- The app already tries both CSV and Excel endpoints
- If both fail, AI insights will use image analysis only (still works!)

### Issue 3: Filters Breaking Export

**Symptom:** Export works without filters but fails when filters are applied

**Cause:** Some filter values don't translate properly to the REST API format.

**Solution:** The updated code automatically retries without filters if the filtered export fails.

### Issue 4: openpyxl Not Installed

**Symptom:** Error message: `openpyxl not installed`

**Solution:**
```bash
pip install openpyxl
```

This is required for parsing Excel crosstab files.

## Expected Behavior After Fix

When you export a dashboard with 2 sheets, you should see:

1. **In Flask logs:**
   ```
   Found 2 views in workbook xyz
   View: Sheet 1 | ID: abc-123 | sheetType: worksheet
   View: Sheet 2 | ID: def-456 | sheetType: worksheet
   Attempting to fetch CSV from all 2 views
   ✓ SUCCESS: Got 45 lines from 'Sheet 1'
   ✓ SUCCESS: Got 32 lines from 'Sheet 2'
   ✓✓✓ SUCCESS: Combined CSV data from 2 sheets: Sheet 1, Sheet 2 (77 total data rows)
   ```

2. **In the UI:**
   - Green alert: "Data Captured for AI Insights (77 rows) — click to view"
   - Click to open data panel showing both sheets
   - Generate AI insights button becomes available
   - AI insights reference actual numbers from both sheets

3. **In generated reports:**
   - AI insights mention specific metrics from BOTH sheets
   - E.g., "Sheet 1 shows revenue of $1.2M while Sheet 2 indicates 15% growth"

## Still Not Working?

If you've tried everything above and still no data:

1. **Share the test script output** - Run `test_crosstab_debug.py` and share what it prints
2. **Check Flask logs** - Share the DEBUG/INFO/WARNING messages when you export
3. **Verify workbook ID** - Make sure you're testing the right workbook
4. **Try a different workbook** - Test with a simple workbook first to isolate the issue

## Technical Details

### How the Fix Works

```python
# OLD CODE (problematic):
for view in views:
    if view['sheetType'] == 'dashboard':
        continue  # Skip dashboards
    csv = fetch_csv(view['id'])

# NEW CODE (works better):
for view in views:
    csv = fetch_csv(view['id'])  # Try ALL views
    if csv and has_data(csv):
        success.append(view['name'])

# FALLBACK:
if not success:
    retry_without_filters()
```

### Why This Fixes the Issue

1. **Tableau's sheetType is unreliable** - Sometimes worksheets are labeled as dashboards
2. **Crosstab endpoint is smart** - It knows how to extract data even from dashboard views
3. **Multiple attempts increase success rate** - If one method fails, another might work

## Next Steps

1. ✅ Update `tableau_api.py` (already done - changes applied)
2. ✅ Install dependencies: `pip install openpyxl` (if not already installed)
3. 🔄 Update and run `test_crosstab_debug.py` with your workbook ID
4. 📋 Review the output and Flask logs
5. 🎯 If still failing, share the logs for further diagnosis

---

**Quick Test Command:**
```bash
cd "/Users/bharathmounika/Documents/Sharath/#1 TableauDashboardCropper-tableau - Filters_Latest"
python test_crosstab_debug.py
```

Good luck! The enhanced logging should make it very clear what's happening. 🚀
