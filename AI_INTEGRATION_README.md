# Gemini AI Integration - Setup Instructions

## ✅ Integration Complete!

The Tableau Dashboard Cropper web application now includes **Google Gemini AI insights** in generated Word documents!

## 🔑 How to Add Your Gemini API Key

### Step 1: Open config.py
The file is located at:
```
/Users/bharathmounika/Documents/Sharath/TableauDashboardCropper-tableau/config.py
```

### Step 2: Replace the API Key
Find line 7 in `config.py`:
```python
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE"  # Replace with your actual Gemini API key
```

Replace `YOUR_GEMINI_API_KEY_HERE` with your actual API key:
```python
GEMINI_API_KEY = "AIzaSy..."  # Your actual key
```

### Step 3: Save and Run
Save the file and start your web application!

## 🚀 How It Works

1. **Login** → Use the web interface to login to Tableau
2. **Select** → choose your workbook and dashboards
3. **Crop** → Crop the dashboard images as needed
4. **Generate** → When you generate the Word document, AI insights are **automatically added**!

## 📄 What Gets Added

Each dashboard in the Word document will now include:

```
Dashboard 1
-----------
Project: Sales
Workbook: Q4 Analysis
Dashboard: Overview
Exported: 2026-01-24 11:30:00

🤖 AI Insights:
------------------------------
1. Revenue shows 23% YoY growth driven by EMEA expansion
2. Q4 margins compressed 15% requiring investigation
3. Product Category A leads with 45% of total sales
4. Strategic opportunity to optimize underperforming regions
```

## ⚙️ Configuration Options

In `config.py` you can also:

- **Disable AI Insights**: Set `ENABLE_AI_INSIGHTS = False`
- **Change Model**: Set `GEMINI_MODEL = "different-model-name"`

## 🔧 Installation

If you haven't installed dependencies yet:

```bash
cd "/Users/bharathmounika/Documents/Sharath/TableauDashboardCropper-tableau"
pip install -r requirements.txt
```

## 🎉 Features

✅ **Non-Intrusive**: Existing functionality unchanged  
✅ **Automatic**: No extra steps needed - insights are auto-generated  
✅ **Graceful Degradation**: If AI fails, Word document still generates  
✅ **Configurable**: Easy to enable/disable via config.py  
✅ **Professional**: Business-focused insights with metrics  

## 📝 Testing

1. Make sure your API key is set in `config.py`
2. Run the web app: `python app.py`
3. Login, select dashboards, crop, and generate report
4. Check the Word document - AI insights will be in the right column!

---

**Your API Key Goes In:** `config.py` → Line 7 → Replace `"YOUR_GEMINI_API_KEY_HERE"`
