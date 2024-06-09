import os
from comp_sys_site.services.all_conferences import all_areas
from comp_sys_site.services.file_utils import file_utilities
from comp_sys_site.services.data_processing import data_processor
from comp_sys_site.services.area_conference_mapping import categorize_venue


def get_required_data(required_conferences, start_year, end_year):
    current_path = file_utilities.get_current_file_path()
    school_data = file_utilities.read_dict_from_file(current_path)

    areas_to_rank = set()

    for conf in required_conferences:
        category = categorize_venue.categorize_venue(conf)
        areas_to_rank.add(category)

    filtered_school_data = data_processor.filter_school_data(
        formatted_school_data=school_data,
        needed_conferences=required_conferences,
        needed_areas=areas_to_rank,
        low_year=start_year,
        high_year=end_year
    )
    filtered_school_data = data_processor.format_university_data(filtered_school_data)
    sorted_school_ranks = data_processor.sort_institutions_by_average_count(filtered_school_data)
    data_processor.sort_authors_by_total_score(sorted_school_ranks)

    return sorted_school_ranks


def get_author_pub_distribution_data(institution_name, author):
    file_path = os.path.join('comp_sys_site', 'static', 'required_files', 'formatted', 'formatted_data.json')
    data = file_utilities.read_dict_from_file(file_path)

    if institution_name in data and author in data[institution_name]['authors']:
        author_data = data[institution_name]['authors'][author]['area_paper_counts']
        pub_distribution = {area: 0 for area in all_areas}

        for area, area_data in author_data.items():
            if area != 'area_adjusted_score' and area != 'area_paper_count':
                pub_count = area_data.get('area_paper_count', 0)
                pub_distribution[area] = pub_count

        return pub_distribution

    return None
