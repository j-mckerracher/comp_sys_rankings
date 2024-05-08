import json
from decimal import Decimal

from django.http import HttpResponse
from django.shortcuts import render
from . import views_helpers as vh
from datetime import datetime
import logging

template_dir = 'comp_sys_site/'
ROW_LIMIT = 300

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def common_entries(*dictionaries):
    """
    Iterate over multiple dictionaries simultaneously and yield common entries.

    Args:
        *dictionaries: Variable number of dictionaries.

    Yields:
        tuple: A tuple containing the common key and the corresponding values
               from each dictionary.

    Description:
        This function takes a variable number of dictionaries as arguments and
        iterates over their common entries. It yields a tuple for each common
        entry, where the first element is the key itself, and the subsequent
        elements are the corresponding values from each dictionary.

    Example:
        dict1 = {'a': 1, 'b': 2, 'c': 3}
        dict2 = {'a': 4, 'b': 5, 'd': 6}
        dict3 = {'a': 7, 'c': 8, 'd': 9}

        for entry in common_entries(dict1, dict2, dict3):
            print(entry)

        Output:
            ('a', 1, 4, 7)

    Note:
        - If no dictionaries are provided, the function returns immediately.
        - The order of the dictionaries passed to the function determines the
          order of the values in the yielded tuples.
        - Only the keys present in all the dictionaries are considered common
          and included in the iteration.
    """
    if not dictionaries:
        return
    for i in set(dictionaries[0]).intersection(*dictionaries[1:]):
        yield (i,) + tuple(d[i] for d in dictionaries)


def home(request):
    template = f'{template_dir}home.html'
    school_authors = {'UCSC': {'Emanuele Trucco': Decimal('4.239108887328701570187638301'),
                               'Annalu Waller': Decimal('6.640949633441893503813008455')
                               },
                      'Purdue': {'huirbnv': Decimal('4.239108887328701570187638301'),
                                 'nreuiovn': Decimal('6.640949633441893503813008455')
                                 },
                      'USC': {'Trucco': Decimal('4.239108887328701570187638301'),
                              'Waller': Decimal('6.640949633441893503813008455')
                              }
                      }

    # get current ranking data
    with open('comp_sys_site/static/required_files/rankings.json') as rankings:
        ranks = json.load(rankings)
        sorted_ranks = dict(sorted(ranks.items(), key=lambda x: x[1], reverse=True))
        logger.info(sorted_ranks)

        # Convert Decimal objects to float
        for school, data in sorted_ranks.items():
            authors = school_authors.get(school, {})
            for author, score in authors.items():
                authors[author] = float(score)
            sorted_ranks[school] = {"score": data, "school_authors": authors}

        return render(request, template, {'sorted_ranks': sorted_ranks})
