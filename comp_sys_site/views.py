import json
import time
from decimal import Decimal
import datetime
from django.http import JsonResponse
import heapq
import re
from datetime import datetime, timedelta
import os
import boto3
import shutil
from typing import Dict

from comp_sys_site.helpers.area_conference_mapping import categorize_venue
from comp_sys_site.helpers.all_conferences import conferences, all_areas
from django.shortcuts import render
import logging
import math

template_dir = 'comp_sys_site/'
ROW_LIMIT = 300

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

author_filtering_ignore_keys = {'area_adjusted_score', 'area_paper_count', 'dblp_link'}


def get_two_highest(data):
    """Returns the two highest values from a list as a set"""
    largest = heapq.nlargest(2, data)
    return set(largest)


def find_max_with_proximity(numbers: list[float], proximity: int) -> set:
    """
    Finds the maximum value and a nearby value within a proximity range.

    :param numbers: A list of floats
    :param proximity: A percentage (0-100) representing the allowed proximity to the maximum value.
    :return: A set containing the maximum value and a nearby value within the proximity range.
    """
    if not numbers:
        return set()  # Return empty set if list is empty

    max_value = max(numbers)
    proximity_range = max_value * (1 - proximity / 100)

    # Filter numbers within proximity
    nearby_numbers = [num for num in numbers if proximity_range <= num < max_value]

    # Combine max value and nearby values (if any) using get_two_highest
    return get_two_highest([max_value] + nearby_numbers)


def get_current_year():
    """Gets the current year as an integer."""
    current_date = datetime.now()
    current_date = current_date.strftime("%Y")
    return int(current_date)


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


def read_dict_from_file(file_path: str) -> Dict:
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
            backup_file = get_backup_file(backup_dir)
            with open(backup_file, 'r', encoding='utf-8') as file:
                data = json.load(file)
            return data
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON file: {str(e)}")
        return {}
    except IOError as e:
        logger.error(f"Error reading file: {str(e)}")
        return {}


def sort_authors(authors_per_school: dict) -> dict:
    return {
        school: dict(sorted(school_authors.items(), key=lambda x: x[1], reverse=True))
        for school, school_authors in authors_per_school.items()
    }


def sort_institutions_by_average_count(institutions_dict):
    sorted_institutions = sorted(institutions_dict.items(), key=lambda x: x[1]['average_count'], reverse=True)
    return dict(sorted_institutions)


def sum_dict_values(data: dict) -> Decimal:
    """
    Sums all the values from a dictionary and returns the result as a Decimal.

    :param data: The input dictionary.
    :return: The sum of all values as a Decimal.
    """
    total = Decimal(0)

    for value in data.values():
        if isinstance(value, (int, float, Decimal)):
            total += Decimal(value)
        else:
            raise ValueError(f"Unsupported value type: {type(value)}")

    return total


def sort_authors_by_total_score(institutions_dict):
    for institution, scores in institutions_dict.items():
        authors_dict = scores['authors']

        def calculate_author_score(author_data):
            _, author_scores = author_data
            return sum(score for metric, score in author_scores.items()
                       if metric != 'paper_count' and metric != 'area_paper_counts')

        sorted_authors = sorted(authors_dict.items(),
                                key=calculate_author_score,
                                reverse=True)

        scores['authors'] = dict(sorted_authors)

    return institutions_dict


def convert_decimals_to_float(data):
    if isinstance(data, dict):
        return {key: convert_decimals_to_float(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_decimals_to_float(item) for item in data]
    elif isinstance(data, Decimal):
        # Convert Decimal to float and round to two decimal places
        return round(float(data), 2)
    else:
        return data


def capitalize_word(word):
    # Words that should not be capitalized
    lowercase_exceptions = {"at", "of", "in"}
    # Words that should remain fully uppercase
    uppercase_exceptions = {"suny", "a&m", "cuny"}
    if word in lowercase_exceptions:
        return word
    if word in uppercase_exceptions:
        return word.upper()

    return word.capitalize()


def format_university_names(name):
    words = name.lower().split()
    formatted_words = []

    for word in words:
        if '-' in word:
            parts = word.split('-')
            formatted_parts = [capitalize_word(part) for part in parts]
            formatted_words.append(' '.join(formatted_parts))
        elif "&" in word:
            formatted = capitalize_word(word)
            formatted_words.append(formatted)
        else:
            formatted_words.append(capitalize_word(word))

    result = ' '.join(formatted_words)
    if "Purdue University" in result:
        result = result[0:17]

    return result


def format_author_names(data):
    new_data = {}
    for university, university_data in data.items():
        new_data[university] = {}
        for key, value in university_data.items():
            if key == 'authors':
                new_data[university][key] = {}
                for author, author_data in value.items():
                    formatted_author = re.sub(r'\s*\d+\s*', '', author)
                    new_data[university][key][formatted_author] = author_data
            else:
                new_data[university][key] = value

    return new_data


def calculate_average_count(n, adjusted_counts):
    if n == 0:
        return 0

    product = 1
    for i in range(1, n + 1):
        product *= (adjusted_counts.get(i, 0) + 1)

    average_count = math.pow(product, 1 / n)
    return average_count


def format_university_data(school_data: dict):
    formatted_school_data = {}

    for school, data in school_data.items():
        formatted_name = format_university_names(school)

        # Calculate the school's average count using this formula
        n = len(data['area_scores'])
        adjusted_counts = {i: count for i, count in enumerate(data['area_scores'].values(), start=1)}
        average_count = calculate_average_count(n, adjusted_counts)

        # Add the average count to the formatted data
        data['average_count'] = average_count

        formatted_school_data[formatted_name] = data

    formatted_school_data = format_author_names(formatted_school_data)

    return formatted_school_data


def get_area_adjusted_score_and_paper_count(filtered_area_data: dict):
    adjusted_score, paper_count = 0, 0
    for pub, year in filtered_area_data.items():
        if pub != 'area_adjusted_score':
            for data, data_value in year.items():
                for k, v in data_value.items():
                    if k == 'score':
                        adjusted_score += v
                    elif k == 'year_paper_count':
                        paper_count += v

    return adjusted_score, paper_count


def build_filtered_author_dict_at_area_counts(needed_areas, needed_confs, lowest_year, highest_year, unfiltered_dict):
    filtered_author_dict_at_area_counts = {}

    for area, area_data in unfiltered_dict.items():
        if area in needed_areas:
            filtered_area_dict = {'area_adjusted_score': 0}

            for pub, pub_data in area_data.items():
                if pub in needed_confs:
                    filtered_conf_data = {}

                    for year, year_data in pub_data.items():
                        if lowest_year <= int(year) <= highest_year:
                            filtered_conf_data[year] = year_data

                    if filtered_conf_data:
                        filtered_area_dict[pub] = filtered_conf_data

            if len(filtered_area_dict) > 1:
                adj_score, paper_count = get_area_adjusted_score_and_paper_count(filtered_area_dict)
                filtered_area_dict['area_adjusted_score'] += adj_score
                filtered_area_dict['area_paper_count'] = paper_count
                filtered_author_dict_at_area_counts[area] = filtered_area_dict

    return filtered_author_dict_at_area_counts


def filter_all_school_author_data(author_scores: dict, filtered_data, needed_conferences, needed_areas, low_year,
                                  high_year):
    if author_scores:
        # for each author, build a dict that contains only the data needed for the needed areas and confs
        all_school_author_data_filtered = {}
        for author, author_data in author_scores.items():
            filtered_author_data = {}

            for item, value in author_data.items():
                if item == 'paper_count':
                    continue
                elif item == 'area_paper_counts':
                    filtered_author_dict_at_area_counts = build_filtered_author_dict_at_area_counts(
                        needed_areas=needed_areas,
                        needed_confs=needed_conferences,
                        lowest_year=low_year,
                        highest_year=high_year,
                        unfiltered_dict=value
                    )

                    filtered_author_data['area_paper_counts'] = filtered_author_dict_at_area_counts

            areas, area_scores, total_paper_count = [], [], 0
            for area, area_data in filtered_author_data['area_paper_counts'].items():
                areas.append(area)
                area_score = 0
                for pub, pub_data in area_data.items():
                    if pub not in author_filtering_ignore_keys:
                        for year, year_data in pub_data.items():
                            for data, data_value in year_data.items():
                                if data == 'score':
                                    area_score += data_value
                                elif data == 'year_paper_count':
                                    total_paper_count += data_value
                area_scores.append(area_score)
            filtered_author_data['paper_count'] = total_paper_count

            for _area, _area_score in zip(areas, area_scores):
                filtered_author_data[_area] = _area_score

            all_school_author_data_filtered[author] = filtered_author_data

        filtered_data['authors'] = all_school_author_data_filtered
    return


def filter_university_level_data(university: str, unfiltered_uni_data: dict, filtered_data: dict):
    """
    filtered_data must have the same keys as unfiltered_uni_data at the end of this function.

    :param university:
    :param unfiltered_uni_data:
    :param filtered_data:
    :return:
    """
    # add author count
    filtered_data['author_count'] = unfiltered_uni_data['author_count']

    # add area paper counts, add area scores, add total score
    total_paper_counts, total_area_scores, total_score = {}, {}, 0
    for author, author_data_dict in filtered_data['authors'].items():
        for author_data, author_data_value in author_data_dict.items():
            if author_data == 'area_paper_counts':
                for area, area_data in author_data_value.items():
                    for pub, pub_data in area_data.items():
                        if pub == 'area_paper_count':
                            if area not in total_paper_counts:
                                total_paper_counts[area] = 0
                            total_paper_counts[area] += pub_data
            elif author_data == 'paper_count':
                continue
            else:
                if author_data not in total_area_scores:
                    total_area_scores[author_data] = 0
                total_area_scores[author_data] += author_data_value

    # add area scores
    filtered_data['area_scores'] = total_area_scores

    # add total score
    for author_data_value in total_area_scores.values():
        total_score += author_data_value
    filtered_data['total_score'] = total_score

    filtered_data['area_paper_counts'] = total_paper_counts


def filter_school_data(formatted_school_data, needed_conferences, needed_areas, low_year, high_year):
    filtered_school_data = {}

    # for each uni, build a dict called filtered_data that contains only the data needed for the needed areas and confs
    for university, data in formatted_school_data.items():
        filtered_data = {}

        # filter all author data
        filter_all_school_author_data(
            data.get('authors', None),
            filtered_data,
            needed_conferences,
            needed_areas,
            low_year,
            high_year
        )

        # filter the uni level data
        filter_university_level_data(university, data, filtered_data)

        # add this school's filtered data to the result
        filtered_school_data[university] = filtered_data

    return filtered_school_data


def get_from_s3():
    try:
        s3 = boto3.client('s3')
        bucket_name = os.getenv('s3_bucket')
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


def get_current_file_path():
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
                    new_path = get_from_s3()
                    if new_path:
                        new_file_name = new_path
                        break
                else:
                    new_file_name = file
                    break

        if new_file_name:
            if old_file_name:
                old_file_path = os.path.join('comp_sys_site', 'static', 'required_files', old_file_name)
                move_old_file_to_backup_dir(backup_dir, old_file_name, old_file_path)
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


def get_required_data(required_conferences, start_year, end_year):
    school_data = read_dict_from_file(get_current_file_path())

    areas_to_rank = set()

    for conf in required_conferences:
        category = categorize_venue.categorize_venue(conf)
        areas_to_rank.add(category)

    filtered_school_data = filter_school_data(
        formatted_school_data=school_data,
        needed_conferences=required_conferences,
        needed_areas=areas_to_rank,
        low_year=start_year,
        high_year=end_year
    )
    filtered_school_data = format_university_data(filtered_school_data)
    sorted_school_ranks = sort_institutions_by_average_count(filtered_school_data)
    sort_authors_by_total_score(sorted_school_ranks)

    return sorted_school_ranks


def filter_author_areas(school_data):
    for uni, uni_data in school_data.items():
        for author, author_data in uni_data['authors'].items():
            this_author_scores = []
            for pub_area, pub_area_score in author_data.items():
                if pub_area != 'paper_count' and pub_area != 'area_paper_counts':
                    this_author_scores.append(pub_area_score)
            author_top_scores = find_max_with_proximity(this_author_scores, proximity=5)
            top_areas = []
            for pub_area, pub_area_score in author_data.items():
                if pub_area != 'paper_count' and pub_area != 'area_paper_counts':
                    if pub_area_score in author_top_scores:
                        top_areas.append(pub_area)
            author_data['top_areas'] = top_areas


def get_author_pub_distribution_data(institution_name, author):
    file_path = os.path.join('comp_sys_site', 'static', 'required_files', 'formatted', 'formatted_data.json')
    data = read_dict_from_file(file_path)

    if institution_name in data and author in data[institution_name]['authors']:
        author_data = data[institution_name]['authors'][author]['area_paper_counts']
        pub_distribution = {area: 0 for area in all_areas}

        for area, area_data in author_data.items():
            if area != 'area_adjusted_score' and area != 'area_paper_count':
                pub_count = area_data.get('area_paper_count', 0)
                pub_distribution[area] = pub_count

        return pub_distribution

    return None


def get_author_pub_distribution(request):
    if request.method == 'POST':
        institution = request.POST.get('institution')
        author = request.POST.get('author')

        # Retrieve the publication distribution data for the specified author
        pub_distribution = get_author_pub_distribution_data(institution, author)

        return JsonResponse({'pub_distribution': pub_distribution})

    return JsonResponse({'error': 'Invalid request'}, status=400)


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


def home(request):
    template = f'{template_dir}home.html'
    current_year = get_current_year()
    year_range = range(1970, current_year + 1)

    if request.method == 'POST':
        selected_conferences = request.POST.getlist('areas[]')
        start_year = int(request.POST.get('start_year', 1970))
        end_year = int(request.POST.get('end_year', current_year))
        sorted_school_ranks = get_required_data(selected_conferences, start_year, end_year)
        convert_decimals_to_float(sorted_school_ranks)
        filter_author_areas(sorted_school_ranks)
        return JsonResponse({'sorted_ranks': sorted_school_ranks})

    # get current ranking data
    sorted_school_ranks = get_required_data(conferences, 1970, current_year)

    # Convert Decimal objects to float
    convert_decimals_to_float(sorted_school_ranks)

    filter_author_areas(sorted_school_ranks)

    write_formatted_json(data_dict=sorted_school_ranks)

    context = {
        'sorted_ranks': sorted_school_ranks,
        'selected_areas': conferences,
        'year_range': year_range
    }
    return render(request, template, context)
