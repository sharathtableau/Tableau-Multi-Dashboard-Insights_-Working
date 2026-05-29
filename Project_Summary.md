# TableauDashboardCropper: High-Level Project Summary

## What It Does
This is a web-based tool that helps users quickly extract, customize, and compile Tableau dashboards into professional reports. Instead of manually exporting and editing each dashboard, users can log in, select multiple dashboards, crop out irrelevant parts (like focusing on key charts), and generate a single combined document (PDF, Word, or PowerPoint) with metadata and optional AI insights. It's designed for efficiency in business reporting, reducing time from hours to minutes.

## Key Technologies (Simplified)
- **Web Framework**: Flask (Python-based web app for handling user interactions).
- **Data Source**: Tableau REST API (connects to Tableau servers to fetch dashboards).
- **Image Handling**: Tools for converting PDFs to images, cropping, and resizing.
- **Document Creation**: Libraries to build PDFs, Word docs, and PowerPoint files.
- **AI Features**: Google Gemini (optional) to add smart summaries or insights to reports.
- **Frontend**: Basic web interface with drag-and-drop cropping.
- **Hosting**: Cloud platform (Render.com) for easy deployment.
- **Database**: Lightweight storage for user sessions and presets (not heavily used).

## Workflow Overview (Step-by-Step)
1. **Login**: User enters Tableau credentials to connect securely.
2. **Select Dashboards**: Choose how many dashboards to process (up to 6), then pick specific ones from Tableau (Project → Workbook → Dashboard).
3. **Export**: Automatically download selected dashboards as PDFs from Tableau.
4. **Convert & Crop**: Turn PDFs into images, then let users interactively crop unwanted sections (e.g., zoom in on charts).
5. **Preview & Confirm**: See cropped previews with details like timestamps.
6. **Generate Report**: Combine all cropped images into one file, add metadata (e.g., project names), and include AI-generated insights if enabled.
7. **Download & Cleanup**: Get the final report, and the app cleans up temp files automatically.

## How Files Work Together (High-Level Roles)
- **Main App (app.py)**: Controls the website, handles user actions, and coordinates everything.
- **Tableau Connector (tableau_api.py)**: Manages login and data pulls from Tableau.
- **Image Processor (image_processor.py)**: Handles all image tasks (conversions, cropping, report building).
- **Settings (config.py)**: Stores API keys and basic configs.
- **Web Pages (templates/)**: Simple HTML forms for login, selection, and cropping.
- **Styles/Scripts (static/)**: Makes the interface look good and enables cropping tools.
- **Entry Point (main.py)**: Starts the app locally or in production.

## Benefits for Business
- **Time-Saving**: Automates repetitive tasks in Tableau reporting.
- **User-Friendly**: No coding needed; web-based with visual cropping.
- **Flexible Output**: Supports multiple formats for different teams (e.g., PDFs for quick shares, Word for detailed reports).
- **Scalable**: Handles multiple dashboards at once; easy to deploy online.
- **Secure**: Uses Tableau's built-in auth; sessions expire safely.

This tool streamlines dashboard curation for analysts or managers who need polished reports from Tableau without manual editing. If your manager needs visuals or a demo link, the README mentions a live demo at https://tableaudashboardcropper.onrender.com/login.