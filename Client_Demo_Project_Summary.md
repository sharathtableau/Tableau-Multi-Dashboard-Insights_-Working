# Snapshot Insights — Client Demo Overview

## Purpose

Organizations using Tableau invest significant time in manually exporting dashboards, screenshotting the right charts, gathering underlying data, and assembling polished reports for stakeholders. This process is repetitive, error-prone, and slow — particularly when multiple dashboards and metrics are involved.

**Snapshot Insights** was built to eliminate this bottleneck. Its purpose is to provide a single, seamless web platform where a user can:
- Securely connect to their Tableau environment
- Visually select and crop only the metrics that matter
- Let the system automatically extract the exact underlying backend data for that visual
- Generate an AI-powered, insight-rich report ready for distribution

In short: **from dashboard to decision-ready report in minutes, not hours.**

---

## Outcome

By the end of a typical session with Snapshot Insights, a user will have:

1. **Exported** high-fidelity PDFs of up to 6 Tableau dashboards directly from their Tableau server
2. **Cropped** the exact chart segments they need using a drag-and-drop browser interface
3. **Received** the precise raw backend data (crosstab tables) that power those visuals — extracted via a headless browser session
4. **Obtained** a professionally formatted **Word or PDF report** containing:
   - The cropped dashboard image
   - Project, Workbook, and Dashboard metadata
   - A timestamp and contextual reference
   - **AI-generated business insights** (powered by Google Gemini) synthesized from both the visual and the raw data numbers

The result is a document that a manager or executive can review immediately, with no manual formatting, data-gathering, or narrative writing required.

---

## Business Impact

| Impact Area | Before Snapshot Insights | After Snapshot Insights |
|---|---|---|
| **Report Preparation Time** | 2–4 hours per cycle | 5–10 minutes |
| **Data Accuracy** | Prone to manual copy/paste errors | Directly tied to backend Tableau data |
| **Insights Quality** | Analyst writes narrative manually | AI synthesizes visual + data narrative  |
| **Consistency** | Format varies by person | Standardized layout every time |
| **Scalability** | Limited by human bandwidth | Handles 6 dashboards simultaneously |
| **Tool Dependency** | Requires Tableau Desktop + Office skills | Browser-only, zero installation |

Key business benefits:
- **Productivity**: Analysts reclaim hours every reporting cycle to focus on strategic thinking
- **Accuracy**: Eliminates manual copy errors by grounding insights in live backend data
- **Decision Speed**: Stakeholders receive reports instantly — not after a multi-step manual process
- **Standardization**: Every report follows the same professional template, regardless of who generates it
- **AI Advantage**: Business narratives explain *why* a metric looks the way it does, not just *what* the number is

---

## Who Is This Most Useful For?

### Primary Users

| Persona | Why They Benefit |
|---|---|
| **Business Analysts** | Automates the most repetitive parts of their reporting workflow — no more Export → Screenshot → Paste → Format cycles |
| **Data / BI Managers** | Centralize report generation without requiring everyone to have Tableau Desktop or advanced Excel skills |
| **Project Managers** | Quickly extract the specific KPIs relevant to their project from shared dashboards without needing a BI team |
| **Executives / Leadership** | Receive clean, summarized reports proactively, with AI-written analysis of the metrics that matter |

### Industry Fit

This tool is especially valuable in:
- **Retail & E-Commerce** — monitoring sales, AOV, regional performance dashboards weekly
- **SaaS / Technology** — tracking product metrics, feature adoption, and revenue across business units
- **Finance & Consulting** — preparing client-ready reports from internal analytics platforms
- **Healthcare / Operations** — standardizing periodic performance reporting across departments

### Team Profile
Any team that:
- Uses **Tableau Online or Tableau Server** for their analytics
- Prepares **regular reports** for stakeholders or leadership
- Wants to **reduce manual effort** and **add AI-powered narrative** to their dashboards

---

## Overview

This application is an end-to-end automated platform that streamlines the extraction, cropping, and report generation of Tableau dashboards. It reduces manual reporting efforts from hours to minutes by allowing users to securely log in, select specific dashboards, visually crop key metrics, automatically extract the corresponding backend data, and generate an AI-enhanced business report in Word or PDF format.

---

## Core Features & Workflow

1. **Secure Authentication**: Users authenticate using Tableau Server or Tableau Cloud credentials.
2. **Dashboard Selection**: The app uses the Tableau REST API to fetch a hierarchical list of accessible Projects, Workbooks, and Dashboards.
3. **Automated Extraction**: Selected dashboards are exported as PDFs and converted to high-resolution PNG images.
4. **Interactive Cropping UI**: Users can interactively crop visually relevant sections of a dashboard directly from the browser.
5. **Headless Data Extraction**: Bypasses API limitations by securely simulating a user session to download raw backend crosstab data associated with the cropped visuals.
6. **Smart Visual-Data Bridge**: Gemini Vision AI matches the visual crop to its underlying data columns, filtering out irrelevant metrics.
7. **AI Report Generation**: Combines the cropped image, contextual metadata (Project, Workbook, Timestamp), and an AI-generated business insight into a styled Word or PDF document.

---

## Technology Stack, Tools & Libraries

### 1. Web Framework & Backend
- **Flask (`Flask`)**: The core Python-based micro-framework handling routing, HTTP requests, session management, and the overall web application logic.
- **Gunicorn (`gunicorn`)**: A Python WSGI HTTP Server used for serving the Flask application securely in a production environment (Render.com).

### 2. Integration & APIs
- **Tableau REST API (`requests`)**: Used for secure authentication, retrieving workbook hierarchies, and triggering the server-side PDF generation of dashboards.
- **Selenium (`selenium`, `webdriver-manager`)**: Drives a headless browser to emulate a user interacting with Tableau's web interface. Its role is strictly to extract raw backend crosstab (Excel/CSV) data that isn't easily accessible via the REST API.

### 3. Data Processing & AI
- **Google GenAI (`google-genai`)**: Integrates Google's Multimodal Gemini models.
  - *Vision Matching*: Identifies which data columns correspond to the user's visual crop.
  - *Insight Generation*: Synthesizes the visual chart and raw data (pandas DataFrame) into human-readable business narratives.
- **Pandas (`pandas`)**: Parses, cleans, and restructures the messy Excel cross-tab files downloaded via Selenium into a structured format readable by the AI.

### 4. Image & PDF Processing
- **Pillow (`pillow`, PIL)**: Manages all image manipulations, specifically sizing and cropping the dashboard boundaries defined by the user frontend.
- **pdf2image (`pdf2image`, requires Poppler)**: Converts the high-fidelity PDF outputs from Tableau's server into PNG format for the web cropping interface.

### 5. Document Generation
- **python-docx (`python-docx`)**: Programmatically creates Microsoft Word documents, dynamically injecting images, text formatting, and AI insight blocks.
- **fpdf2 (`fpdf2`)**: An alternative engine used for directly generating PDF versions of the final reports.

### 6. Frontend
- **HTML, CSS, JS, Bootstrap**: Classic stack powering the user interface, utilizing drag-and-drop bounding boxes for the cropping experience while communicating with the Flask backend.

---
*Created for the purpose of a client demo and architectural overview.*

## Overview
This application is an end-to-end automated platform that streamlines the extraction, cropping, and report generation of Tableau dashboards. It reduces manual reporting efforts from hours to minutes by allowing users to securely log in, select specific dashboards, visually crop key metrics, automatically extract the corresponding backend data, and generate an AI-enhanced business report in Word or PDF format.

## Business Value
- **Significant Time Savings**: Automates manual screenshotting, downloading, and formatting of reports.
- **Enhanced Accuracy**: Directly matches visual crops with backend data to generate insights, eliminating human error in metric reporting.
- **Intelligent Insights**: Uses state-of-the-art multimodal AI to analyze both visual charts and backend numbers, generating meaningful business narrative automatically.

## Core Features & Workflow
1. **Secure Authentication**: Users authenticate using Tableau Server or Tableau Cloud credentials.
2. **Dashboard Selection**: The app uses the Tableau REST API to fetch a hierarchical list of accessible Projects, Workbooks, and Dashboards.
3. **Automated Extraction**: Selected dashboards are exported as PDFs and converted to high-resolution PNG images.
4. **Interactive Cropping UI**: Users can interactively crop visually relevant sections of a dashboard directly from the browser.
5. **Headless Data Extraction**: Bypasses API limitations by securely simulating a user session to download raw backend crosstab data associated with the cropped visuals.
6. **Smart Visual-Data Bridge**: Gemini Vision AI matches the visual crop to its underlying data columns, filtering out irrelevant metrics.
7. **AI Report Generation**: Combines the cropped image, contextual metadata (Project, Workbook, Timestamp), and an AI-generated business insight into a styled Word or PDF document.

## Technology Stack, Tools & Libraries

### 1. Web Framework & Backend
- **Flask (`Flask`)**: The core Python-based micro-framework handling routing, HTTP requests, session management, and the overall web application logic.
- **Gunicorn (`gunicorn`)**: A Python WSGI HTTP Server used for serving the Flask application securely in a production environment (Render.com).

### 2. Integration & APIs
- **Tableau REST API (`requests`)**: Used for secure authentication, retrieving workbook hierarchies, and triggering the server-side PDF generation of dashboards.
- **Selenium (`selenium`, `webdriver-manager`)**: Drives a headless browser to emulate a user interacting with Tableau's web interface. Its role is strictly to extract raw backend crosstab (Excel/CSV) data that isn't easily accessible via the REST API.

### 3. Data Processing & AI
- **Google GenAI (`google-genai`)**: Integrates Google's Multimodal Gemini models. 
  - *Vision Matching*: Identifies which data columns correspond to the user's visual crop.
  - *Insight Generation*: Synthesizes the visual chart and raw data (pandas Dataframe) into human-readable business narratives.
- **Pandas (`pandas`)**: Parses, cleans, and restructures the messy Excel cross-tab files downloaded via Selenium into a structured format readable by the AI.

### 4. Image & PDF Processing
- **Pillow (`pillow`, PIL)**: Manages all image manipulations, specifically sizing and cropping the dashboard boundaries defined by the user frontend.
- **pdf2image (`pdf2image`, requires Poppler)**: Converts the high-fidelity PDF outputs from Tableau's server into PNG format for the web cropping interface.

### 5. Document Generation
- **python-docx (`python-docx`)**: Programmatically creates Microsoft Word documents, dynamically injecting images, text formatting, and AI insight blocks.
- **fpdf2 (`fpdf2`)**: An alternative engine used for directly generating PDF versions of the final reports.

### 6. Frontend
- **HTML, CSS, JS, Bootstrap**: Classic stack powering the user interface, utilizing drag-and-drop bounding boxes for the cropping experience while communicating with the Flask backend.

---
*Created for the purpose of a client demo and architectural overview.*
