import json
from decimal import Decimal

from django.shortcuts import render
import logging
import math

template_dir = 'comp_sys_site/'
ROW_LIMIT = 300

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def calculate_average_count(n, adjusted_counts):
    product = 1
    for i in range(1, n + 1):
        product *= (adjusted_counts.get(i, 0) + 1)

    average_count = math.pow(product, 1 / n)
    return average_count


def read_dict_from_file(file_path: str) -> dict:
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
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


def sort_institutions_by_total_score(institutions_dict):
    sorted_institutions = sorted(institutions_dict.items(), key=lambda x: x[1]['total_score'], reverse=True)
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
        sorted_authors = sorted(authors_dict.items(), key=lambda x: sum_dict_values(x[1]), reverse=True)
        scores['authors'] = dict(sorted_authors)
    return institutions_dict


def convert_decimals_to_float(data):
    if isinstance(data, dict):
        return {key: convert_decimals_to_float(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_decimals_to_float(item) for item in data]
    elif isinstance(data, Decimal):
        return float(data)
    else:
        return data


def get_required_data():
    school_data = read_dict_from_file('comp_sys_site/static/required_files/all-school-adjusted-counts.json')
    sorted_school_ranks = sort_institutions_by_total_score(school_data)

    sort_authors_by_total_score(sorted_school_ranks)

    return sorted_school_ranks


def home(request):
    template = f'{template_dir}home.html'

    # get current ranking data
    sorted_school_ranks = get_required_data()
    logger.info(sorted_school_ranks)

    # Convert Decimal objects to float
    convert_decimals_to_float(sorted_school_ranks)

    return render(request, template, {'sorted_ranks': sorted_school_ranks})
