import json
from decimal import Decimal
import re

from django.shortcuts import render
import logging
import math

template_dir = 'comp_sys_site/'
ROW_LIMIT = 300

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
        sorted_authors = sorted(authors_dict.items(),
                                key=lambda x: sum_dict_values({k: v for k, v in x[1].items() if k != 'paper_count'}),
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

        # Calculate the average count using the formula
        n = len(data['area_scores'])
        adjusted_counts = {i: count for i, count in enumerate(data['area_scores'].values(), start=1)}
        average_count = calculate_average_count(n, adjusted_counts)

        # Add the average count to the formatted data
        data['average_count'] = average_count

        formatted_school_data[formatted_name] = data

    formatted_school_data = format_author_names(formatted_school_data)

    return formatted_school_data


def get_required_data(areas=None):
    if areas:
        pass

    school_data = read_dict_from_file('comp_sys_site/static/required_files/all-school-adjusted-counts.json')
    formatted_school_data = format_university_data(school_data)

    sorted_school_ranks = sort_institutions_by_average_count(formatted_school_data)
    sort_authors_by_total_score(sorted_school_ranks)

    return sorted_school_ranks


def home(request):
    template = f'{template_dir}home.html'
    if request.method == 'POST':
        areas = request.POST.getlist('areas')
        print(areas)

        # get current ranking data
        sorted_school_ranks = get_required_data(areas)

        # Convert Decimal objects to float
        convert_decimals_to_float(sorted_school_ranks)

        return render(request, template, {'sorted_ranks': sorted_school_ranks, 'selected_areas': areas})

    # get current ranking data
    sorted_school_ranks = get_required_data()

    # Convert Decimal objects to float
    convert_decimals_to_float(sorted_school_ranks)

    # Define a list of all areas
    all_areas = ['ASPLOS', 'ISCA', 'MICRO', 'HPCA', 'SIGCOMM', 'NSDI', 'CONEXT', 'CCS', 'ACM-Conference',
                 'USENIX-Security', 'USENIX-Security-Symposium', 'NDSS', 'IEEE-Symposium', 'IEEE-Security-and-Privacy',
                 'RTAS', 'RTSS', 'Supercomputing', 'HPDC', 'ICS', 'MobiSys', 'MobiCom', 'SenSys', 'IPSN', 'IMC',
                 'Sigmetrics', 'SOSP', 'OSDI', 'EuroSys', 'USENIX-ATC', 'USENIX-ATC-Short', 'USENIX-FAST', 'FAST',
                 'PLDI', 'POPL', 'OOPSLA', 'ASE', 'FSE', 'SIGSOFT-FSE', 'ESEC-SIGSOFT-FSE', 'ICSE', 'DISC', 'DSN',
                 'ICDCS', 'PODC']

    return render(request, template, {'sorted_ranks': sorted_school_ranks, 'selected_areas': all_areas})