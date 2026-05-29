import logging
import json
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import os

from job_executor import execute_preset_workflow, send_email_report

PRESETS_FILE = 'data/presets.json'

class ReportScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        logging.info("Background Scheduler started.")

    def load_and_schedule_jobs(self):
        """Loads jobs from presets.json and schedules those with a 'schedule' field."""
        if not os.path.exists(PRESETS_FILE):
            return

        # Clear existing jobs to avoid duplicates on reload
        self.scheduler.remove_all_jobs()

        try:
            with open(PRESETS_FILE, 'r') as f:
                presets = json.load(f)
            
            for preset in presets:
                if preset.get('schedule') and preset.get('is_enabled', True):
                    # Expecting schedule format "HH:MM"
                    time_parts = preset['schedule'].split(':')
                    if len(time_parts) == 2:
                        hour = int(time_parts[0])
                        minute = int(time_parts[1])
                        
                        trigger_args = {
                            'hour': hour,
                            'minute': minute
                        }
                        
                        repeat_type = preset.get('repeat_type', 'daily')
                        interval = int(preset.get('interval', 1))

                        if repeat_type == 'weekly' and preset.get('days'):
                            trigger_args['day_of_week'] = ",".join(map(str, preset['days']))
                        elif repeat_type == 'monthly':
                            trigger_args['day'] = '1'
                        elif (repeat_type == 'daily' or repeat_type == 'hourly') and interval > 1:
                            # Run every N hours starting from specified hour
                            trigger_args['hour'] = f"{hour}-23/{interval}"
                        
                        self.scheduler.add_job(
                            func=self._run_job_wrapper,
                            trigger=CronTrigger(**trigger_args),
                            args=[preset],
                            id=preset['id'],
                            name=f"Schedule for {preset['name']}",
                            replace_existing=True
                        )
                        
                        log_msg = f"Scheduled job '{preset['name']}' at {preset['schedule']} ({repeat_type}, every {interval})."
                        if 'day_of_week' in trigger_args:
                            log_msg += f" Days: {trigger_args['day_of_week']}"
                        logging.info(log_msg)
        except Exception as e:
            logging.error(f"Error loading and scheduling jobs: {e}")

    def _run_job_wrapper(self, preset):
        """Wrapper to handle the execution and emailing of a scheduled job."""
        logging.info(f"Starting scheduled job: {preset['name']}")
        try:
            report_path = execute_preset_workflow(preset)
            
            if preset.get('recipients'):
                send_email_report(
                    preset['recipients'], 
                    report_path, 
                    preset['name'],
                    custom_message=preset.get('message')
                )
            else:
                logging.warning(f"Job '{preset['name']}' completed but no recipients specified.")
                
        except Exception as e:
            logging.error(f"Scheduled job '{preset['name']}' failed: {e}")

# Global scheduler instance
report_scheduler = ReportScheduler()
