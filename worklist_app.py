import json
import sys
import os

import requests
import random

from PyQt5.QtGui import QStandardItemModel, QStandardItem, QColor, QPalette, QIntValidator
from PyQt5.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QComboBox, QLineEdit, \
    QCheckBox, QPushButton, QTableView, QHeaderView, QTabWidget, QGroupBox, QFormLayout
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QWidget
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
import chromedriver_autoinstaller

APP_NAME = 'UBC Worklist Generator 1.1.0'

# version 98.0.4758.102
BINARY_PATH = ".\\GoogleChromePortable64\\App\\Chrome-bin\\chrome.exe"
PATH = ".\\chromedriver.exe"

SAVE_PATH = 'data'

courses_dict = {}

possible_schedules = []

URL_SECTIONS_TEMPLATE = 'https://courses.students.ubc.ca/cs/courseschedule?pname=subjarea&tname=subj-course&dept={' \
                        '}&course={}'
URL_SECTION_TEMPLATE = 'https://courses.students.ubc.ca/cs/courseschedule?pname=subjarea&tname=subj-section&dept={' \
                       '}&course={}&section={} '
URL_LOGIN = 'https://cas.id.ubc.ca/ubc-cas/login'
URL_LOGIN_REDIRECT = 'https://cas.id.ubc.ca/ubc-cas/login?TARGET=https%3A%2F%2Fcourses.students.ubc.ca%2Fcs%2Fsecure' \
                     '%2Flogin%3FIMGSUBMIT.x%3D20%26IMGSUBMIT.y%3D13'
URL_SAVE_TO_WORKLIST = 'https://courses.students.ubc.ca/cs/courseschedule?pname=subjarea&tname=subj-section&dept={' \
                       '}&course={}&section={}&submit=save '
URL_NEW_WORKLIST = 'https://courses.students.ubc.ca/cs/courseschedule?pname=wlist&tname=wlist&attrSelectedWorklist=-2'
URL_SHOW_WORKLIST = 'https://courses.students.ubc.ca/cs/courseschedule?pname=timetable&tname=timetable&showSections=wl'

START_TIME = 0
END_TIME = 2400


def fits_in_schedule(section, schedule, term, breaks):
    if section['term'] != term:
        return False
    for scheduled_section in [*schedule, *breaks]:
        # a necessary evil
        is_conflict = (section['start'] < scheduled_section['end'] and section['end'] > scheduled_section['start']) or \
                      (section['start'] > scheduled_section['start'] and section['end'] < scheduled_section['end'])

        if set(scheduled_section['days']).intersection(section['days']) and is_conflict:
            # print(":: fits_in_schedule: Conflict found: " + str(section) + " and " + str(scheduled_section))
            return False
    return True


def generate_schedule(schedule, courses_to_schedule, term, breaks):
    if len(courses_to_schedule) == 0:
        # print(":: generate_schedule: Success: " + str(schedule))
        return sorted(schedule, key=lambda i: i['start'])
    course = courses_to_schedule.pop()

    possible_sections = [x for x in courses_dict[course] if fits_in_schedule(x, schedule, term, breaks)]
    if not possible_sections:
        return False

    for section in possible_sections:
        possible_schedule = schedule.copy()
        possible_schedule.append(section)
        remaining_courses = courses_to_schedule.copy()
        # print(":: generate_schedule: " + str(section['course']) + " " + str(remaining_courses))
        possible_schedule = generate_schedule(possible_schedule, remaining_courses, term, breaks)
        if possible_schedule:
            possible_schedules.append(possible_schedule)

    return False


# From https://www.jcchouinard.com/random-user-agent-with-python-and-beautifulsoup/
def get_ua():
    ua_strings = [
        "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.111 Safari/537.36",
        "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/28.0.1500.72 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10) AppleWebKit/600.1.25 (KHTML, like Gecko) Version/8.0 "
        "Safari/600.1.25",
        "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:33.0) Gecko/20100101 Firefox/33.0",
        "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.111 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.111 "
        "Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_5) AppleWebKit/600.1.17 (KHTML, like Gecko) Version/7.1 "
        "Safari/537.85.10",
        "Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko",
        "Mozilla/5.0 (Windows NT 6.3; WOW64; rv:33.0) Gecko/20100101 Firefox/33.0",
        "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.104 Safari/537.36"
    ]
    return random.choice(ua_strings)


def get_soup(course):
    headers = {'User-Agent': get_ua()}
    r = requests.get(URL_SECTIONS_TEMPLATE.format(*course.split(" ")), headers=headers)
    # print(URL_SECTIONS_TEMPLATE.format(*course.split(" ")))
    return BeautifulSoup(r.content, 'html.parser')


def build_sections_info(data):
    for course in data:
        sections_added = 0

        activity_to_check = {
            'Lecture',
            'Discussion',
            'Tutorial',
            'Laboratory',
            'Seminar',
            'Lecture-Discussion',
            'Lecture-Laboratory',
            'Lecture-Seminar'
        }
        certificate = {}
        for activity in activity_to_check:
            verifier = {
                'exists': False,
                'added': False
            }
            certificate[activity] = verifier

        soup = get_soup(course['course'])
        for x in soup.findAll('tr'):
            if x.has_attr('class') and x['class'][0] in ['section1', 'section2']:
                try:
                    elements = x.findAll('td')
                    section = {
                        'course': course['course'],
                        'status': elements[0].text,
                        'section': elements[1].text.split()[2],
                        'activity': elements[2].text,
                        'term': int(elements[3].text),
                        'days': elements[6].text.split(),
                        'start': int(elements[7].text.replace(':', '')),
                        'end': int(elements[8].text.replace(':', ''))
                    }

                    if section['activity'] in certificate:
                        certificate[section['activity']]['exists'] = True

                    # if section['activity'] != 'Waiting List':
                    # if section['activity'] == 'Lecture':
                    if section['activity'] != 'Waiting List' and section['status'].strip() in [*course['preferences'],
                                                                                               '']:
                        # to support lecture, lab, tutorial, etc.
                        key = course['course'] + ' ' + section['activity']
                        if key in courses_dict:
                            sections_list = courses_dict[key]
                        else:
                            sections_list = []
                            courses_dict[key] = sections_list

                        if section['activity'] in certificate:
                            certificate[section['activity']]['added'] = True

                        sections_added = sections_added + 1
                        sections_list.append(section)
                except ValueError as e:
                    print(':: build_sections_info: ValueError: ' + str(e) + ": " + course['course'])

        for activity in activity_to_check:
            c = certificate[activity]
            if c['exists'] and not c['added']:
                raise KeyError('No section added for ' + course['course'] + ': ' + activity)

        if not sections_added:
            raise KeyError('No valid sections found for ' + course['course'] + ' with the given parameters')
        else:
            print(':: build_sections_info: ' + str(sections_added) + ' section(s) added for ' + course['course'])

    print(':: build_sections_info: Finished building courses_list')
    # print(':: build_sections_info: ' + str(courses_dict))


def schedule_to_links(schedule, url_template):
    result = []
    for section in schedule:
        if section['course'] != 'BREAK':
            result.append(url_template.format(*section['course'].split(), section['section']))
    return result


def schedules_to_links(schedules, url_template):
    return list(map(lambda x: schedule_to_links(x, url_template), schedules))


def generate_schedules(schedule, data, term, breaks):
    global courses_dict
    courses_dict = {}

    build_sections_info(data)
    generate_schedule(schedule, list(courses_dict.keys()), term, breaks)
    print(':: generate_schedule: Number of possible schedules: ' + str(len(possible_schedules)))


def create_worklists(login, amount):
    session = WorklistSession()
    return session.login_and_generate_worklists(schedules_to_links(possible_schedules, URL_SAVE_TO_WORKLIST), login,
                                                amount)


# to prevent closing the window automatically
global browser


class WorklistSession(object):

    def __init__(self):
        global browser
        options = webdriver.ChromeOptions()
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        options.binary_location = BINARY_PATH
        browser = webdriver.Chrome(PATH, options=options)
        self.browser = browser

    def login_and_generate_worklists(self, links, login, amount):
        if self.is_valid_login(login):
            # self.try_login(URL_LOGIN_REDIRECT, login)
            self.browser.get(URL_LOGIN_REDIRECT)

            # Check for logout button to confirm login
            WebDriverWait(self.browser, 30).until(EC.presence_of_element_located((By.ID, 'cwl-logout')))

            self.generate_worklists(links, amount)
            # self.browser.quit()
            self.browser.get(URL_SHOW_WORKLIST)
            return 'Success'
        else:
            self.browser.quit()
            return 'Invalid login'

    def generate_worklists(self, links, amount):
        for i in range(min(amount, len(links))):
            self.browser.get(URL_NEW_WORKLIST)
            elem = self.browser.find_element(By.ID, 'attrWorklistName')
            elem.send_keys("__worklist_" + str(i + 1))
            elem = self.browser.find_element(By.CSS_SELECTOR, 'input[class="btn btn-primary"]')
            elem.click()
            WebDriverWait(self.browser, 30).until(EC.presence_of_element_located((By.CLASS_NAME, 'alert-success')))
            for link in links[i]:
                self.browser.get(link)

    def try_login(self, url, login):
        self.browser.get(url)
        elem = self.browser.find_elements(By.CLASS_NAME, 'required')
        for i in range(2):
            elem[i].clear()
            elem[i].send_keys(login[i])
        elem = self.browser.find_element(By.CLASS_NAME, 'btn-submit')
        elem.click()

    def is_valid_login(self, login):
        self.try_login(URL_LOGIN, login)
        element = WebDriverWait(self.browser, 15) \
            .until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "span, .alert-success")))
        result = element[0].text
        return "Log In Successful" in result


class WorklistAppUi(QWidget):
    data = []

    def __init__(self):
        super().__init__()

        self.load()

        self.setWindowTitle(APP_NAME)
        self.resize(800,0)

        self.container = QHBoxLayout()
        self.left_layout = QVBoxLayout()
        self.right_layout = QVBoxLayout()

        # Left layout:Add course
        self.top_groupbox = QGroupBox("Add course")
        self.top_layout = QVBoxLayout()

        self.session = QHBoxLayout()
        self.course = QLineEdit(placeholderText="CPSC 110")
        self.session.addWidget(QLabel("Course:", self), 0)
        self.session.addWidget(self.course, 1)

        self.submit = QHBoxLayout()
        self.include_groupbox = QGroupBox("Include")
        self.include = QVBoxLayout()
        self.full = QCheckBox("Full")
        self.full.setCheckState(0)
        self.restricted = QCheckBox("Restricted")
        self.restricted.setCheckState(0)
        self.stt = QCheckBox("STT")
        self.stt.setCheckState(0)
        self.blocked = QCheckBox("Blocked")
        self.blocked.setCheckState(0)
        self.add = QPushButton("Add")
        self.add.clicked.connect(
            lambda: self.add_course(self.course.text(),
                                    [self.full.isChecked(), self.stt.isChecked(), self.restricted.isChecked(),
                                     self.blocked.isChecked()]))
        self.include.addWidget(self.full)
        self.include.addWidget(self.stt)
        self.include.addWidget(self.restricted)
        self.include.addWidget(self.blocked)

        self.top_layout.addLayout(self.session)
        self.top_layout.addWidget(self.include_groupbox)
        self.top_layout.addLayout(self.submit)
        self.top_layout.addWidget(self.add)

        self.top_groupbox.setLayout(self.top_layout)
        self.include_groupbox.setLayout(self.include)

        # Left layout:Table
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(['Course', 'Include'])
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 125)
        self.table.setColumnWidth(1, 150)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.resizeRowToContents(True)
        self.update_model()

        # Left layout: Bottom buttons
        self.remove = QPushButton('Remove')
        self.remove.clicked.connect(self.remove_selected_sections)

        # Right layout setup
        self.settings = QVBoxLayout()
        self.groupbox_login = QGroupBox('Generate')
        self.login_layout = QVBoxLayout()
        self.login = QFormLayout()
        self.groupbox_login.setLayout(self.login_layout)

        self.settings_layout = QFormLayout()
        self.term = QComboBox()
        self.term.addItems(["1", "2"])
        self.settings_layout.addRow(QLabel('Worklist term:'))
        self.settings_layout.addWidget(self.term)

        self.settings_layout.addRow(QLabel('Max amount of worklists to generate:'))
        self.amount = QLineEdit()
        self.amount.setText('1')
        self.amount.setValidator(QIntValidator())
        self.settings_layout.addWidget(self.amount)

        self.settings_layout.addRow(QLabel('Earliest start time:'))
        self.start = QLineEdit()
        self.start.setPlaceholderText('800 = 8:00am')
        self.start.setText('0')
        self.start.setValidator(QIntValidator())
        self.settings_layout.addWidget(self.start)
        # self.settings_layout.addRow(QLabel('Latest end time:'))
        self.end = QLineEdit()
        self.end.setText('2400')
        self.end.setPlaceholderText('2000 = 8:00pm')
        self.end.setValidator(QIntValidator())
        # self.settings_layout.addWidget(self.end)

        self.login_layout.addLayout(self.settings_layout)

        # Right layout: Generate and export
        self.ssc_generate = QGroupBox('Generate to worklist on SSC')
        self.ssc_generate.setLayout(self.login)
        self.usr = QLineEdit()
        self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.Password)
        self.login.addRow(QLabel('Username:'), self.usr)
        self.login.addRow(QLabel('Password:'), self.pw)
        self.testButton = QPushButton('Generate and Login')
        self.testButton.clicked.connect(self.run)
        self.status = QLabel('')

        self.settings.addWidget(self.groupbox_login)
        self.login.addWidget(self.testButton)
        self.login.addWidget(self.status)

        # Right layout: Generate and export
        self.export_generate = QGroupBox('Generate to .txt')
        self.export_layout = QVBoxLayout()
        self.export_generate.setLayout(self.export_layout)
        self.export_submit = QPushButton('Generate and export')
        self.export_submit.clicked.connect(
            lambda: run_export_only(self.data, int(self.term.currentText()), int(self.amount.text()),
                                    int(self.start.text()), int(self.end.text())))
        self.export_layout.addWidget(self.export_submit)

        self.login_layout.addWidget(self.export_generate)
        self.login_layout.addWidget(self.ssc_generate)

        # Setup
        self.left_layout.addWidget(self.top_groupbox)
        self.left_layout.addWidget(self.table)
        self.left_layout.addWidget(self.remove)
        self.right_layout.addLayout(self.settings)

        self.container.addLayout(self.left_layout)
        self.container.addLayout(self.right_layout)
        self.setLayout(self.container)

    def save(self):
        fp = open(SAVE_PATH, 'w')
        json.dump(self.data, fp)
        fp.close()

    def load(self):
        try:
            fp = open(SAVE_PATH, 'r')
            self.data = json.load(fp)
            fp.close()
        except FileNotFoundError:
            pass

    def run(self):
        set_start_end(int(self.start.text()), int(self.end.text()))
        self.status.setText(
            run([self.usr.text(), self.pw.text()], self.data, int(self.term.currentText()), int(self.amount.text())))

    def add_course(self, course, preferences):
        if len(course.split()) != 2:
            return
        translation = ['Full', 'STT', 'Restricted', 'Blocked']
        formatted_preferences = [translation[i] for i in range(len(translation)) if preferences[i]]
        course = {
            'course': course.upper(),
            'preferences': formatted_preferences
        }
        self.data.append(course)
        self.update_model()
        self.save()

    def remove_selected_sections(self):
        selected = self.table.selectionModel().selectedRows()
        for i in sorted(selected, reverse=True):
            self.model.removeRow(i.row())
            del self.data[i.row()]

        self.save()

    def update_model(self):
        for x in range(len(self.data)):
            course_name = QStandardItem(self.data[x]['course'])
            course_name.setEditable(False)
            course_preferences = QStandardItem(', '.join(self.data[x]['preferences']))
            course_preferences.setEditable(False)
            self.model.setItem(x, 0, course_name)
            self.model.setItem(x, 1, course_preferences)


def main():
    worklist_app = QApplication([])
    view = WorklistAppUi()
    view.show()
    sys.exit(worklist_app.exec_())


def set_start_end(start, end):
    global START_TIME
    global END_TIME
    START_TIME = start
    END_TIME = end


def run_export_only(data, term, amount, start, end):
    global possible_schedules
    possible_schedules = []
    set_start_end(start, end)

    # future feature
    to_add_breaks = [{'course': 'break', 'days': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'], 'start': 0, 'end': START_TIME},
                     {'course': 'break', 'days': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'], 'start': END_TIME, 'end': 2400}]

    try:
        generate_schedules([], data, term, to_add_breaks)
    except KeyError as e:
        with open('export.txt', 'w') as f:
            f.write(':: Input: ' + str(data) + '\n')
            f.write(':: generate_schedules: ERROR: ' + str(e) + '\n')
            f.close()
        os.system("notepad.exe export.txt")
        return

    possible_schedules = sorted(possible_schedules, key=lambda i: sum(item['start'] for item in i))
    links = schedules_to_links(possible_schedules, URL_SECTION_TEMPLATE)
    with open('export.txt', 'w') as f:
        f.write(':: Input (TERM {}): {}\n'.format(term, str(data)))
        if len(possible_schedules) > 0:
            f.write('--------------------------------------------------------\n')
            for i in range(min(amount, len(links))):
                f.write(':: GENERATED WORKLIST ' + str(i + 1) + ':\n')
                for link in links[i]:
                    f.write(link + "\n")
                f.write('--------------------------------------------------------\n')
        else:
            f.write(':: There are no possible worklists for the courses and parameters specified\n')
        f.close()

    os.system("notepad.exe export.txt")


def run(login, data, term, amount):
    global possible_schedules
    possible_schedules = []

    # future feature
    to_add_breaks = [{'course': 'break', 'days': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'], 'start': 0, 'end': START_TIME},
                     {'course': 'break', 'days': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'], 'start': END_TIME, 'end': 2400}]

    try:
        generate_schedules([], data, term, to_add_breaks)
    except KeyError as e:
        return 'Error: ' + str(e)
    possible_schedules = sorted(possible_schedules, key=lambda i: sum(item['start'] for item in i))
    if len(possible_schedules) > 0:
        return create_worklists(login, min(10, amount))
    else:
        return 'There are no possible worklists for the courses specified'


if __name__ == '__main__':
    main()
