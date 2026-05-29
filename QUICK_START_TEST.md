# 🚀 Quick Start - Test Crosstab Fix

## Problem
You have 2 sheets in your dashboard but the app isn't fetching their data for AI insights.

## ✅ What Was Done

1. **Fixed the export logic** - Now tries ALL views (no filtering by type)
2. **Added detailed logging** - See exactly what's happening
3. **Created test tools** - Web UI + script to debug easily
4. **Added fallback retry** - Tries without filters if needed

---

## 🔧 Step 1: Install Required Package

```bash
cd "/Users/bharathmounika/Documents/Sharath/#1 TableauDashboardCropper-tableau - Filters_Latest"
pip install openpyxl==3.1.5
```

This is required for parsing Excel crosstab files.

---

## 🧪 Step 2: Test Immediately (Choose One Method)

### Method A: Web UI (Easiest)

1. **Start Flask app** (if not running):
   ```bash
   python main.py
   ```

2. **Open browser**:
   ```
   http://localhost:5000/test_crosstab
   ```

3. **Find your workbook ID**:
   - Open the main app: `http://localhost:5000/login`
   - Login and select your dashboard with 2 sheets
   - Open browser DevTools (F12)
   - Look at console logs or Network tab for `workbook_id`
   - OR check Flask server logs

4. **Test it**:
   - Paste workbook ID in test page
   - Click "Run Test"
   - See results instantly!

### Method B: Test Script (More Detailed)

1. **Edit the script** (`test_crosstab_debug.py`, line 30):
   ```python
   TEST_WORKBOOK_ID = "YOUR_ACTUAL_WORKBOOK_ID_HERE"
   ```

2. **Run it**:
   ```bash
   python test_crosstab_debug.py
   ```

3. **Read output** - Shows everything step by step

---

## ✅ Expected Success Output

### Web UI Shows:
- ✅ Green success banner
- Views Found: **2**
- Sheets with Data: **2**
- CSV Size: ~1-5 KB
- Preview of your actual data

### Flask Logs Show:
```
INFO - Found 2 views in workbook xyz-abc-123
INFO - View: Sheet 1 | ID: abc-123 | sheetType: worksheet
INFO - View: Sheet 2 | ID: def-456 | sheetType: worksheet
INFO - Attempting to fetch CSV from all 2 views
INFO - ✓ SUCCESS: Got 45 lines from 'Sheet 1'
INFO - ✓ SUCCESS: Got 32 lines from 'Sheet 2'
INFO - ✓✓✓ SUCCESS: Combined CSV data from 2 sheets: Sheet 1, Sheet 2
```

---

## 🎯 Step 3: Test in Real Workflow

1. **Go to main app**: `http://localhost:5000/`
2. **Select your dashboard** (the one with 2 sheets)
3. **Click "Export Dashboard"**
4. **Watch Flask logs** - Should see same success messages
5. **Check UI** - Should show green alert:
   > "Data Captured for AI Insights (77 rows) — click to view"
6. **Click alert** - Opens panel showing both sheets' data
7. **Generate AI insights** - Will use actual numbers from both sheets!

---

## ❌ If It Still Fails

### Check Flask Logs For:

```
⚠️ WARNING: No CSV data returned for 'Sheet 1'
⚠️ CRITICAL: No CSV data collected from ANY sheet!
Possible causes:
1. Custom SQL doesn't support crosstab
2. All views are dashboard-level
3. Permissions issue
4. Server blocks exports
```

### Quick Fixes to Try:

1. **Verify permissions**:
   - In Tableau web, can you download underlying data manually?
   - If not, your user needs "View Data" permission

2. **Try different workbook**:
   - Test with a simple workbook first
   - One with basic worksheets (not custom SQL)

3. **Remove filters temporarily**:
   - The code retries without filters automatically
   - But try selecting dashboard without any filters applied

4. **Check sheet types in test output**:
   - Both show as "dashboard" type? → That's OK now, fix handles this
   - Both show as "worksheet" type? → Should definitely work
   - Only 1 view found? → Issue is with how Tableau published the workbook

---

## 📋 Share This Info If Still Stuck

1. **Screenshot of test page** showing views found
2. **Flask logs** (copy-paste from terminal)
3. **Workbook ID** you're testing with
4. **Manual test result**: Can YOU download data directly from Tableau web?

---

## 💡 Pro Tips

### Enable More Logging
Add to `app.py` after line 14:
```python
logging.getLogger('tableau_api').setLevel(logging.DEBUG)
```

### Watch Live Logs
Separate terminal while testing:
```bash
# If running with gunicorn
tail -f /path/to/logs/error.log

# If running directly, just watch the terminal
```

### Quick Workbook ID from Console
In browser console (F12), after selecting dashboard:
```javascript
// Find the most recent API call that fetched views
console.log(window._lastWorkbookId); // May need to check network tab instead
```

---

## 🎉 Success Looks Like This

**Before fix:**
```
⚠️ AI insights will use image only
```

**After fix:**
```
✅ Data Captured for AI Insights (77 rows) — click to view
```

**AI insights then reference actual data:**
> "**Strong Revenue Growth**"
> - Total revenue reached **$1.2M**, up **15% YoY**
> - Sheet 1 shows consistent growth across all regions
> - Sheet 2 indicates Q4 momentum continuing into Q1

---

**Ready to test?** Run the web UI test first - it's the easiest! 🚀

Questions? Check `FIX_SUMMARY.md` for full details on what was changed.
