import datetime
import os
import unittest
from unittest.mock import Mock

from base import database, DatabaseUpdater
from postcard import ImageMaker
from settings import DATE_FORMAT, PATH_TO_SAVE_TEST_POSTCARDS, TEST_POSTCARDS_DATA, PATH_TO_POSTCARD_SAMPLES
from settings import ICONS_DATA, get_norm_and_join_path, ICONS_PATH
from weather import Manager
from weather_forecast import WeatherMaker


def isolate_db(test_func):
    def wrapper(*args, **kwargs):
        with database.atomic():
            test_func(*args, **kwargs)
            database.rollback()

    return wrapper


class ForecastTest(unittest.TestCase):
    def setUp(self) -> None:
        self.predictor = WeatherMaker(res_holder=Mock(), lock=Mock(), day=datetime.date.today())
        self.db_updater = DatabaseUpdater()
        self.leader = Manager()
        self.painter = ImageMaker()

        self.days_difference = 2
        self.test_date1 = datetime.date.today()
        self.test_date2 = self.test_date1 + datetime.timedelta(days=self.days_difference)

    def test_connection(self):
        self.assertEqual(self.predictor.weather_resp.status_code, 200)

    def test_weather_type_handler(self):
        for i, data in enumerate(ICONS_DATA.values()):
            icon, colour = self.predictor._weather_type_handler(data['weather_type'].lower())

            self.assertEqual(icon, get_norm_and_join_path(ICONS_PATH, data['icon_file_name']))
            self.assertEqual(colour, data['colour'])

    @isolate_db
    def test_wrong_date(self):
        wrong_day = self.test_date1 + datetime.timedelta(weeks=2)  # today + 2 weeks
        next_wrong_day = wrong_day + datetime.timedelta(days=1)
        self.leader.get_weather_data(wrong_day, next_wrong_day)
        self.db_updater.save_weather_to_db(self.leader.weather_data)
        weather_data = self.db_updater.get_data_from_db(wrong_day, next_wrong_day)[0]

        weather_type, icon, colour = weather_data[0], weather_data[3], weather_data[4]
        self.assertEqual(weather_type, 'No data')
        self.assertIsNone(icon)
        self.assertEqual(colour, (255, 255, 255))

    @isolate_db
    def test_database(self):
        self.leader.get_weather_data(self.test_date1, self.test_date2)
        self.db_updater.save_weather_to_db(self.leader.weather_data)
        weather_data = self.db_updater.get_data_from_db(self.test_date1, self.test_date2)
        self.assertEqual(len(weather_data), self.days_difference)

    def test_postcard_generation(self):
        for i, data_unit in enumerate(TEST_POSTCARDS_DATA):
            postcard_data, postcard_sample = data_unit
            self.painter.draw_postcard(postcard_data, PATH_TO_SAVE_TEST_POSTCARDS)
            example_postcard = get_norm_and_join_path(PATH_TO_POSTCARD_SAMPLES, postcard_sample)
            result_postcard = get_norm_and_join_path(PATH_TO_SAVE_TEST_POSTCARDS, postcard_sample)

            with open(example_postcard, 'rb') as example:
                with open(result_postcard, 'rb') as result:
                    example_content = example.read()
                    res_content = result.read()

            self.assertEqual(example_content, res_content)
            os.remove(result_postcard)

    @isolate_db
    def test_count_of_postcards(self):
        count_of_postcards = self.get_count_of_postcards(PATH_TO_SAVE_TEST_POSTCARDS)

        day1, day2 = self.test_date1.strftime(DATE_FORMAT), self.test_date2.strftime(DATE_FORMAT)
        Manager(f'-f {day1} -l {day2} -p', PATH_TO_SAVE_TEST_POSTCARDS).run()

        new_count = self.get_count_of_postcards(PATH_TO_SAVE_TEST_POSTCARDS)
        count_of_created_postcards = new_count - count_of_postcards

        self.assertEqual(self.days_difference, count_of_created_postcards)

        for name in os.listdir(PATH_TO_SAVE_TEST_POSTCARDS):
            os.remove(os.path.join(PATH_TO_SAVE_TEST_POSTCARDS, name))

    @staticmethod
    def get_count_of_postcards(path: str) -> int:
        """Method returns count of files in path given. If path doesn't exist return 0

        :param path: directory to count files in"""
        if os.path.exists(path):
            return len([
                name for name in os.listdir(path) if os.path.isfile(
                    os.path.join(path, name))])
        else:
            return 0


if __name__ == '__main__':
    unittest.main()
