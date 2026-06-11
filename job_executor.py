import os
import logging
import smtplib
import tempfile
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime
import shutil

from tableau_api import TableauAPI, TableauHyperExtractor
from image_processor import ImageProcessor
from PIL import Image
import config

def execute_preset_workflow(preset_data, server_url=None, site_id=None, token_name=None, token_key=None):
    """
    Executes a preset workflow: Exports dashboards, processes images, and builds report.
    Can be run from a web request or a background job.
    """
    print(f"\n{'='*50}", flush=True)
    print(f"[JOB] execute_preset_workflow CALLED", flush=True)
    print(f"[JOB] Preset: {preset_data.get('name','?')} | Workbooks: {len(preset_data.get('workbooks',[]))}", flush=True)
    print(f"{'='*50}", flush=True)
    try:
        # 1. Determine Credentials
        # Use provided credentials or fallback to config defaults
        server = server_url or config.TABLEAU_SERVER_URL
        site = site_id or config.TABLEAU_SITE_ID
        t_name = token_name or config.AUTO_TABLEAU_TOKEN_NAME
        t_key = token_key or config.AUTO_TABLEAU_TOKEN_KEY

        if not (t_name and t_key):
             raise Exception("Automation credentials (PAT) not configured in config.py")

        # 2. Initialize APIs
        tableau = TableauAPI(server, site)
        tableau.authenticate_pat(t_name, t_key)
        
        processor = ImageProcessor()
        
        # Use system temp dir so path stays short on Windows (avoids WinError 206)
        job_id = preset_data.get('id', 'manual')
        temp_dir = tempfile.mkdtemp(prefix=f"snap_{job_id[:8]}_")
        
        cropped_paths = []
        summary_data = []
        
        # 3. Process Dashboards
        print(f"\n[JOB] Starting job. Total workbooks: {len(preset_data.get('workbooks', []))}", flush=True)
        for i, wb_config in enumerate(preset_data.get('workbooks', [])):
            print(f"[JOB] Processing workbook {i+1}: {wb_config['workbook']} / {wb_config['dashboard']}", flush=True)
            logging.info(f"Processing {wb_config['workbook']} / {wb_config['dashboard']}")

            # Find workbook by name
            workbooks = tableau.list_workbooks_in_project(wb_config['project'])
            target_workbook = next((w for w in workbooks if w['name'] == wb_config['workbook']), None)

            if not target_workbook:
                logging.warning(f"Workbook not found: {wb_config['workbook']}")
                continue

            # Find dashboard by name
            dashboards = tableau.get_views_in_workbook(target_workbook['id'])
            target_dashboard = next((d for d in dashboards if d['name'] == wb_config['dashboard']), None)

            if not target_dashboard:
                logging.warning(f"Dashboard not found: {wb_config['dashboard']}")
                continue

            # Export View as PDF with saved filters
            saved_filters = wb_config.get('filters', {})
            logging.info(f"Applying saved filters: {saved_filters}")
            print(f"[JOB] Exporting PDF from Tableau for: {wb_config['dashboard']}...", flush=True)
            pdf_content = tableau.export_view_as_pdf(target_dashboard['id'], filters=saved_filters)
            print(f"[JOB] PDF exported. Size: {len(pdf_content)} bytes", flush=True)
            pdf_path = os.path.join(temp_dir, f"wb_{i}.pdf")
            with open(pdf_path, 'wb') as f:
                f.write(pdf_content)

            # Convert to PNG, then trim whitespace margins so crop coordinates
            # (which were saved relative to the trimmed image) align correctly.
            png_path = processor.pdf_to_png(pdf_path)
            png_path = processor.trim_to_dashboard_size(png_path)
            logging.info(f"PNG ready (after trim): {png_path}")

            # Apply Crop — coordinates are relative to the trimmed PNG
            crop_data = wb_config.get('crop_data')
            if crop_data:
                cropped_path = processor.crop_image(png_path, crop_data)
                cropped_paths.append(cropped_path)
            else:
                cropped_path = png_path
                cropped_paths.append(png_path)

            # ── Extract CSV data for AI insights ──────────────────────────────
            # Download the workbook, run zone-mapping with the saved crop coords
            # so only the matched sheet(s) data is passed to the AI.
            csv_data = ''
            try:
                extractor = TableauHyperExtractor(
                    server_url=server,
                    site_id=site,
                    token=tableau.token,
                    output_dir=temp_dir
                )
                wb_content = extractor.download_workbook(target_workbook['id'])
                dashboard_name = wb_config['dashboard']

                if crop_data:
                    # Pass png_path so zone-mapping can pixel-scan for y_offset
                    trimmed_img = Image.open(png_path)
                    orig_w, orig_h = trimmed_img.size
                    crop_with_path = dict(crop_data)
                    crop_with_path['_png_path'] = png_path
                    df_master, matched_sheets, worksheet_defs = extractor.extract_and_parse(
                        wb_content, dashboard_name,
                        crop_data=crop_with_path,
                        image_size=(orig_w, orig_h),
                        applied_filters=saved_filters
                    )
                else:
                    df_master, matched_sheets, worksheet_defs = extractor.extract_and_parse(
                        wb_content, dashboard_name,
                        applied_filters=saved_filters
                    )

                csv_data = extractor.reconstruct_csv(df_master, matched_sheets, worksheet_defs)
                logging.info(f"CSV extracted for preset slide {i+1}: {len(csv_data)} chars, sheets={matched_sheets}")
            except Exception as csv_err:
                logging.warning(f"CSV extraction failed for preset slide {i+1} (non-fatal): {csv_err}")

            # ─────────────────────────────────────────────────────────────────

            # Get data source info for this workbook
            datasource_info = []
            try:
                datasource_info = tableau.get_workbook_datasources(target_workbook['id'])
            except Exception as ds_err:
                logging.warning(f"Could not fetch datasource info for {wb_config['workbook']}: {ds_err}")

            summary_data.append({
                'project': wb_config['project'],
                'workbook': wb_config['workbook'],
                'dashboard': wb_config['dashboard'],
                'applied_filters': wb_config.get('filters', {}),
                'datasources': datasource_info,
                'csv_data': csv_data,           # ← now populated for AI insights
            })
        
        if not cropped_paths:
            raise Exception("No dashboards could be processed")

        # 4. Combine to Report — honour the format saved on the preset (default PPTX)
        output_format = (preset_data.get('output_format') or 'pptx').lower()
        print(f"[JOB] All {len(cropped_paths)} dashboards processed. Now generating {output_format.upper()} with AI insights...", flush=True)
        base_filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if output_format == 'pdf':
            output_path = processor.combine_to_pdf_with_details(cropped_paths, temp_dir, base_filename, summary_data)
        elif output_format == 'docx':
            output_path = processor.combine_to_word_with_details(cropped_paths, temp_dir, base_filename, summary_data)
        else:
            output_path = processor.combine_to_pptx_with_details(cropped_paths, temp_dir, base_filename, summary_data)
        print(f"[JOB] Report generated: {output_path}")
        
        # Move final file to output folder
        final_filename = os.path.basename(output_path)
        final_path = os.path.join('output', final_filename)
        shutil.copy(output_path, final_path)
        
        # 5. Cleanup temp files
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        return final_path
        
    except Exception as e:
        logging.error(f"Workflow execution failed: {str(e)}")
        raise e

def send_email_report(recipient_list, attachment_path, preset_name, custom_message=None):
    """Sends the generated report via Email (Gmail/Outlook)"""
    if not recipient_list:
        logging.warning("No recipients specified for email report")
        return False
        
    sender = config.EMAIL_SENDER
    password = config.EMAIL_PASSWORD
    server_addr = config.EMAIL_SMTP_SERVER
    port = config.EMAIL_SMTP_PORT
    
    if sender == "sharathtableaupoc@gmail.com" and password == "fged vfzd pzgu lfbd":
        # Using user-provided credentials
        pass
    elif sender == "your-email@gmail.com":
        logging.error("Email sender not configured in config.py")
        return False

    try:
        # Create a single SMTP connection for all recipients
        server = smtplib.SMTP(server_addr, port)
        server.starttls()
        server.login(sender, password)
        
        for recipient in recipient_list:
            msg = MIMEMultipart()
            msg['From'] = sender
            msg['To'] = recipient.strip()
            msg['Subject'] = f"Automated Tableau Report: {preset_name} - {datetime.now().strftime('%Y-%m-%d')}"
            
            body_text = custom_message if custom_message else f"Attached is the automated Tableau reports for {preset_name}."
            body_text += f"\n\nGenerated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            msg.attach(MIMEText(body_text, 'plain'))
            
            # Attach the file
            with open(attachment_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
                msg.attach(part)
            
            server.send_message(msg)
            logging.info(f"Report emailed successfully to {recipient}")
            
        server.quit()
        return True
        
    except Exception as e:
        logging.error(f"Failed to send email: {str(e)}")
        return False
