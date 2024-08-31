import math
import re
from decimal import Decimal
import heapq
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataProcessing:
    def __init__(self):
        self.author_filtering_ignore_keys = {'area_adjusted_score', 'area_paper_count', 'dblp_link'}

    def get_two_highest(self, data):
        """Returns the two highest values from a list as a set"""
        largest = heapq.nlargest(2, data)
        return set(largest)

    def find_max_with_proximity(self, numbers: list[float], proximity: int) -> set:
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
        return self.get_two_highest([max_value] + nearby_numbers)

    @staticmethod
    def sort_authors(authors_per_school: dict) -> dict:
        return {
            school: dict(sorted(school_authors.items(), key=lambda x: x[1], reverse=True))
            for school, school_authors in authors_per_school.items()
        }

    @staticmethod
    def sort_institutions_by_average_count(institutions_dict):
        sorted_institutions = sorted(institutions_dict.items(), key=lambda x: x[1]['average_count'], reverse=True)
        return dict(sorted_institutions)

    @staticmethod
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

        return round(total, 2)

    @staticmethod
    def sort_authors_by_total_score(institutions_dict):
        for institution, scores in institutions_dict.items():
            authors_dict = scores['authors']

            def calculate_author_score(author_data):
                _, author_scores = author_data
                return sum(score for metric, score in author_scores.items()
                           if metric != 'paper_count' and metric != 'area_paper_counts' and metric != 'dblp_link')

            sorted_authors = sorted(authors_dict.items(),
                                    key=calculate_author_score,
                                    reverse=True)

            scores['authors'] = dict(sorted_authors)

        return institutions_dict

    def convert_decimals_to_float(self, data):
        try:
            if isinstance(data, dict):
                return {key: self.convert_decimals_to_float(value) for key, value in data.items()}
            elif isinstance(data, list):
                return [self.convert_decimals_to_float(item) for item in data]
            elif isinstance(data, Decimal):
                # Convert Decimal to float and round to two decimal places
                return round(float(data), 2)
            else:
                return data
        except Exception as e:
            logger.error(f"convert_decimals_to_float encountered an error! {e}")
            raise e

    def format_university_names(self, name):
        words = name.lower().split()
        formatted_words = []

        for word in words:
            if '-' in word:
                parts = word.split('-')
                formatted_parts = [self.capitalize_word(part) for part in parts]
                formatted_words.append(' '.join(formatted_parts))
            elif "&" in word:
                formatted = self.capitalize_word(word)
                formatted_words.append(formatted)
            else:
                formatted_words.append(self.capitalize_word(word))

        result = ' '.join(formatted_words)
        if "Purdue University" in result:
            result = result[0:17]

        return result

    def format_author_names(self, data):
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

    def capitalize_word(self, word):
        # Words that should not be capitalized
        lowercase_exceptions = {"at", "of", "in"}
        # Words that should remain fully uppercase
        uppercase_exceptions = {"suny", "a&m", "cuny"}
        if word in lowercase_exceptions:
            return word
        if word in uppercase_exceptions:
            return word.upper()

        return word.capitalize()

    def calculate_average_count(self, n, adjusted_counts):
        if n == 0:
            return 0

        product = 1
        for i in range(1, n + 1):
            product *= (adjusted_counts.get(i, 0) + 1)

        average_count = math.pow(product, 1 / n)
        return average_count

    def format_university_data(self, school_data: dict):
        formatted_school_data = {}

        for school, data in school_data.items():
            formatted_name = self.format_university_names(school)

            # Calculate the school's average count using this formula
            n = len(data['area_scores'])
            adjusted_counts = {i: count for i, count in enumerate(data['area_scores'].values(), start=1)}
            average_count = self.calculate_average_count(n, adjusted_counts)

            # Add the average count to the formatted data
            data['average_count'] = average_count

            formatted_school_data[formatted_name] = data

        formatted_school_data = self.format_author_names(formatted_school_data)

        return formatted_school_data

    def get_area_adjusted_score_and_paper_count(self, filtered_area_data: dict):
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

    def build_filtered_author_dict_at_area_counts(self, needed_areas, needed_confs, lowest_year, highest_year,
                                                  unfiltered_dict):
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
                    adj_score, paper_count = self.get_area_adjusted_score_and_paper_count(filtered_area_dict)
                    filtered_area_dict['area_adjusted_score'] += adj_score
                    filtered_area_dict['area_paper_count'] = paper_count
                    filtered_author_dict_at_area_counts[area] = filtered_area_dict

        return filtered_author_dict_at_area_counts

    def filter_all_school_author_data(self, author_scores: dict, filtered_data, needed_conferences, needed_areas,
                                      low_year,
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
                        filtered_author_dict_at_area_counts = self.build_filtered_author_dict_at_area_counts(
                            needed_areas=needed_areas,
                            needed_confs=needed_conferences,
                            lowest_year=low_year,
                            highest_year=high_year,
                            unfiltered_dict=value
                        )
                        filtered_author_data['area_paper_counts'] = filtered_author_dict_at_area_counts
                    elif item == 'dblp_link':
                        filtered_author_data['dblp_link'] = value

                areas, area_scores, total_paper_count = [], [], 0
                for area, area_data in filtered_author_data['area_paper_counts'].items():
                    areas.append(area)
                    area_score = 0
                    for pub, pub_data in area_data.items():
                        if pub not in self.author_filtering_ignore_keys:
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

    def filter_university_level_data(self, university: str, unfiltered_uni_data: dict, filtered_data: dict):
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
                elif author_data == 'dblp_link':
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

    def filter_school_data(self, formatted_school_data, needed_conferences, needed_areas, low_year, high_year):
        filtered_school_data = {}

        # for each uni, build a dict called filtered_data that contains only the data needed for the needed areas and
        # confs
        for university, data in formatted_school_data.items():
            filtered_data = {}

            # filter all author data
            self.filter_all_school_author_data(
                data.get('authors', None),
                filtered_data,
                needed_conferences,
                needed_areas,
                low_year,
                high_year
            )

            # filter the uni level data
            self.filter_university_level_data(university, data, filtered_data)

            # add this school's filtered data to the result
            filtered_school_data[university] = filtered_data

        return filtered_school_data

    def filter_author_areas(self, school_data):
        for uni, uni_data in school_data.items():
            for author, author_data in uni_data['authors'].items():
                this_author_scores = []
                for pub_area, pub_area_score in author_data.items():
                    if pub_area != 'paper_count' and pub_area != 'area_paper_counts' and pub_area != 'dblp_link':
                        this_author_scores.append(pub_area_score)
                author_top_scores = self.find_max_with_proximity(this_author_scores, proximity=5)
                top_areas = []
                for pub_area, pub_area_score in author_data.items():
                    if pub_area != 'paper_count' and pub_area != 'area_paper_counts':
                        if pub_area_score in author_top_scores:
                            top_areas.append(pub_area)
                author_data['top_areas'] = top_areas


data_processor = DataProcessing()
