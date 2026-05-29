# Snapshot Insights

### Tableau Dashboard Cropper & AI Insights Generator

Snapshot Insights is a powerful automation tool designed to bridge the gap between Tableau dashboards and decision-ready executive reports. It allows users to visually crop specific sections of a Tableau dashboard, automatically extract the underlying raw data, and use state-of-the-art AI (Google Gemini / Anthropic Claude) to synthesize visual and numerical context into professional reports.

---

## 🚀 Key Features

*   **Secure Tableau Integration**: Connects to Tableau Online or Tableau Server via REST API.
*   **Visual Selection**: Full interactive UI to browse Projects, Workbooks, and Dashboards.
*   **Intelligent Cropping**: Drag-and-drop interface to isolate specific charts or metrics from a dashboard view.
*   **Automated Data Bridge**: Uses headless Selenium to download the exact crosstab data powering your visual selection.
*   **AI-Powered Narrative**: 
    *   **Vision & Text Synthesis**: Maps cropped images to raw data numbers.
    *   **Automated Insights**: Generates Executive Summaries, Anomaly Detection, and Risk Assessments.
    *   **Multi-Model Support**: Integrated with Google Gemini 2.0/1.5 and Anthropic Claude 3.5.
*   **Multi-Format Export**: Generates professional reports in **Word (.docx)**, **PDF**, and **PowerPoint (.pptx)**.
*   **Scheduled Automation**: Built-in background scheduler to automate report generation and email distribution.

---

## 🛠️ Technology Stack

*   **Backend**: Python / Flask
*   **Frontend**: HTML5, CSS3 (Vanilla), JavaScript, Bootstrap
*   **AI Engine**: 
    *   `google-genai` (Gemini 2.0 Flash / 1.5 Flash)
    *   `anthropic` (Claude 3.5 Sonnet)
*   **Tableau Tools**: 
    *   Tableau REST API (Authentication & Metadata)
    *   Selenium / WebDriver Manager (Headless Data Extraction)
*   **Document Generation**: 
    *   `python-docx` (Word)
    *   `fpdf2` (PDF)
    *   `python-pptx` (PowerPoint)
*   **Scheduling**: APScheduler

---

## 📋 Prerequisites

*   Python 3.10 or higher
*   Tableau Online / Server account with Personal Access Token (PAT) or username/password.
*   Google Gemini API Key or Anthropic API Key.
*   Google Chrome (for headless data extraction).

---

## ⚙️ Installation & Setup

1.  **Clone the Repository**:
    ```bash
    git clone <repository-url>
    cd "#1 Snapshot Insights v2_Gemini API Working"
    ```

2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure the Application**:
    Open `config.py` and set your credentials:
    ```python
    # AI Keys
    GEMINI_API_KEY = "YOUR_API_KEY"
    GEMINI_MODEL = "gemini-2.0-flash"

    # Tableau Defaults (Optional)
    TABLEAU_SERVER_URL = "https://us-east-1.online.tableau.com/"
    TABLEAU_SITE_ID = "your-site-id"
    
    # Email Settings (for scheduling)
    EMAIL_SENDER = "your-email@gmail.com"
    EMAIL_PASSWORD = "your-app-password"
    ```

---

## 🏃 Running the App

1.  **Start the Flask Server**:
    ```bash
    python app.py
    ```
2.  **Access the UI**:
    Open your browser and navigate to `http://127.0.0.1:5002`.

---

## 📁 Project Structure

*   `app.py`: Main Flask entry point and API routes.
*   `image_processor.py`: Core engine for image cropping, PDF conversion, and AI insight generation.
*   `config.py`: Global configuration and environment settings.
*   `scheduler_service.py`: Handles background job scheduling for automated reports.
*   `generate_ppt.py`: Dedicated module for PowerPoint assembly.
*   `data/`: Stores presets, cached images, and temporary files.
*   `static/` & `templates/`: Frontend assets and UI layouts.

---

## 📝 Usage Notes

*   **AI Quota**: If you are on a free tier API, the system includes built-in retry logic and model fallbacks to handle rate limits.
*   **Crosstab Data**: Ensure the dashboard you are analyzing has "Download Data" permissions enabled for the authenticating user.
*   **Headless Chrome**: On first run, the system will automatically download the correct ChromeDriver via `webdriver-manager`.

---

## 👤 Author

**Sharath Kumar Kammari**
*Specialist in Tableau Automation and AI Integrations.*
