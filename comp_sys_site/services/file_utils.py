import os
import shutil
import time
import logging
import json
from datetime import datetime, timedelta
import re
from typing import Dict

import boto3

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FileUtils:
    @staticmethod
    def get_backup_file(backup_dir: str) -> str:
        try:
            files = os.listdir(backup_dir)
            if files:
                backup_file = files[0]
                backup_file_path = os.path.join(backup_dir, backup_file)
                return backup_file_path
            else:
                raise FileNotFoundError(f"No backup files found in {backup_dir}")
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Backup directory not found: {backup_dir}") from e

    def read_dict_from_file(self, file_path: str) -> Dict:
        max_count = 3
        backup_dir = os.path.join('comp_sys_site', 'static', 'required_files', 'backup')
        try:
            sleep_time, count = 1, 0
            while not os.path.exists(file_path) and count < max_count:
                time.sleep(sleep_time)
                sleep_time *= 2  # Increase sleep time exponentially (1, 2, 4 seconds)
                count += 1
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                return data
            else:
                backup_file = self.get_backup_file(backup_dir)
                with open(backup_file, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                return data
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON file: {str(e)}")
            return {}
        except IOError as e:
            logger.error(f"Error reading file: {str(e)}")
            return {}

    @staticmethod
    def move_old_file_to_backup_dir(backup_dir: str, current_file: str, current_file_path: str):
        try:
            # Move the current file to the backup directory
            backup_file_path = os.path.join(backup_dir, current_file)
            if os.path.exists(backup_file_path):
                os.remove(backup_file_path)
            shutil.move(current_file_path, backup_file_path)
            logging.info(f"Current file moved to backup: {backup_file_path}")

            # Delete all files in the backup directory except the one just moved
            for file_name in os.listdir(backup_dir):
                if file_name != current_file:
                    file_path = os.path.join(backup_dir, file_name)
                    if os.path.isfile(file_path):
                        try:
                            os.remove(file_path)
                            logging.info(f"Deleted file from backup: {file_path}")
                        except Exception as e:
                            logging.error(f"Error deleting file from backup: {file_path}. Error: {str(e)}")

            return True
        except FileNotFoundError:
            logging.error(f"Current file not found: {current_file_path}")
            return False
        except shutil.Error as e:
            logging.error(f"Error moving file to backup: {current_file_path}. Error: {str(e)}")
            return False
        except Exception as e:
            logging.error(f"Error occurred while moving file to backup: {current_file_path}. Error: {str(e)}")
            return False

    def get_current_file_path(self):
        try:
            file_dir = os.path.join('comp_sys_site', 'static', 'required_files')
            backup_dir = os.path.join('comp_sys_site', 'static', 'required_files', 'backup')
            new_file_name = None
            old_file_name = None
            creation_time_threshold = datetime.now() - timedelta(days=30)

            for file in os.listdir(file_dir):
                match = re.search(r'all-school-scores-final-(\w+)-(\d{1,2})-(\d{4})', file)
                if match:
                    month = match.group(1)
                    day = int(match.group(2))
                    year = int(match.group(3))
                    creation_time = datetime.strptime(f"{month} {day} {year}", "%B %d %Y")
                    if creation_time < creation_time_threshold:
                        old_file_name = file
                        new_path = self.get_from_s3()
                        if new_path:
                            new_file_name = new_path
                            break
                    else:
                        new_file_name = file
                        break

            if new_file_name:
                if old_file_name:
                    old_file_path = os.path.join('comp_sys_site', 'static', 'required_files', old_file_name)
                    self.move_old_file_to_backup_dir(backup_dir, old_file_name, old_file_path)
                file_path = os.path.join(file_dir, new_file_name)
                logging.info(f"Current file path: {file_path}")
                return file_path
            else:
                # Check if backup file exists
                backup_files = os.listdir(backup_dir)
                if backup_files:
                    backup_file = backup_files[0]
                    backup_file_path = os.path.join(backup_dir, backup_file)
                    logging.warning(f"No current file found. Using backup file: {backup_file_path}")
                    return backup_file_path
                else:
                    logging.error("No file found in the required directory or backup directory.")
                    return None
        except FileNotFoundError:
            logging.error("Required directories not found.")
            return None
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            return None

    def get_from_s3(self):
        try:
            s3 = boto3.client('s3')
            bucket_name = os.getenv('s3-bucket')
            current_folder = 'current/'
            backup_folder = 'backup/'

            # List objects in the 'current' folder
            current_objects = s3.list_objects_v2(Bucket=bucket_name, Prefix=current_folder)

            # Check if there is exactly one file in the 'current' folder
            if 'Contents' in current_objects and len(current_objects['Contents']) == 1:
                current_file_key = current_objects['Contents'][0]['Key']
                current_file_name = current_file_key.replace(current_folder, '')

                local_file_path = os.path.join('comp_sys_site', 'static', 'required_files', current_file_name)

                # Download the current file from S3
                s3.download_file(bucket_name, current_file_key, local_file_path)
                logging.info(f"File downloaded from S3: {local_file_path}")

                # Move the current file to the 'backup' folder in S3
                backup_file_key = backup_folder + current_file_name
                s3.copy_object(Bucket=bucket_name, CopySource={'Bucket': bucket_name, 'Key': current_file_key},
                               Key=backup_file_key)
                s3.delete_object(Bucket=bucket_name, Key=current_file_key)
                logging.info(f"File moved to backup in S3: {backup_file_key}")

                return str(local_file_path)
            else:
                logging.error("No file or multiple files found in the 'current' folder in S3.")
                return None
        except Exception as e:
            logging.error(f"Error downloading file from S3: {str(e)}")
            return None

    @staticmethod
    def write_formatted_json(data_dict: Dict):
        """
        Writes the contents of a dictionary to a file in JSON format, overwriting any existing content.

        """
        try:
            file_path = os.path.join('comp_sys_site', 'static', 'required_files', 'formatted', 'formatted_data.json')
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(data_dict, file, indent=4)
            logger.info(f"Successfully wrote data to file: {file_path}")
        except IOError as e:
            logger.error(f"An error occurred while writing to the file: {str(e)}")


file_utilities = FileUtils()
