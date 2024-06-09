import json
from django.http import JsonResponse

from comp_sys_site.services.all_conferences import conferences
from comp_sys_site.services.file_utils import file_utilities
from comp_sys_site.services.data_processing import data_processor
from comp_sys_site.services.date_time_utils import get_current_year
from comp_sys_site.services.data_getters import get_required_data, get_author_pub_distribution_data
from django.shortcuts import render
import logging

template_dir = 'comp_sys_site/'
ROW_LIMIT = 300

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_author_pub_distribution(request):
    if request.method == 'POST':
        institution = request.POST.get('institution')
        author = request.POST.get('author')

        # Retrieve the publication distribution data for the specified author
        pub_distribution = get_author_pub_distribution_data(institution, author)

        return JsonResponse({'pub_distribution': pub_distribution})

    return JsonResponse({'error': 'Invalid request'}, status=400)


def home(request):
    template = f'{template_dir}home.html'
    current_year = get_current_year()
    year_range = range(1970, current_year + 1)

    if request.method == 'POST':
        selected_conferences = request.POST.getlist('areas[]')
        start_year = int(request.POST.get('start_year', 1970))
        end_year = int(request.POST.get('end_year', current_year))
        sorted_school_ranks = get_required_data(selected_conferences, start_year, end_year)
        data_processor.convert_decimals_to_float(sorted_school_ranks)
        data_processor.filter_author_areas(sorted_school_ranks)
        return JsonResponse({'sorted_ranks': sorted_school_ranks})

    # Get current ranking data
    sorted_school_ranks = get_required_data(conferences, 1970, current_year)

    # Convert Decimal objects to float
    data_processor.convert_decimals_to_float(sorted_school_ranks)
    data_processor.filter_author_areas(sorted_school_ranks)
    file_utilities.write_formatted_json(data_dict=sorted_school_ranks)

    context = {
        'sorted_ranks': json.dumps(sorted_school_ranks),
        'selected_areas': conferences,
        'year_range': year_range
    }
    return render(request, template, context)

