# UBC-Worklist-Generator
A Python 3.8 program with a graphical user interface to generate UBC worklists.
## About
UBC Worklist Generator is a tool that can generate UBC worklists that contain courses specified by the user. It uses
web-scraping to find all the valid courses to generate a worklist from. Courses with a tutorial, lab, discussion, will
automatically be identified in the worklist generator.

The worklists generated can either be exported as a .txt file or created automatically on SSC using an automated browser.

I initially wrote this application over two days as part of a self-imposed challenge.
## Notes
- Courses added to the program will be saved to disk and persist between sessions.
    - For security reasons, the user's CWL login  will *not* be saved to disk and will need to be entered again between
  sessions.
- To prevent abuse, the amount of worklists generated when using the "Generate and Login" option is limited to a maximum of ten, regardless of
  user input.
- A worklist can only be generated for one term at a time.
- Waiting list sections will not be considered when generating a worklist.
    - Usually, sections with a corresponding waiting list will be "Blocked" when the section is full, so include "Blocked"
    as one of the filters to partially circumvent this.
- A minimum start time (24h) for the worklist can be specified.
  - If a worklist is generated with a start time of 1300, then no sections that *start* before 1:00pm will be added.
- Worklists are ranked in order of increasing start times.

## Libraries used
- [PyQt5](https://pypi.org/project/PyQt5/) for GUI programming
- [BeautifulSoup4](https://pypi.org/project/beautifulsoup4/) for web-scraping
- [Selenium](https://pypi.org/project/selenium/) to facilitate automatic login and registration
## Changelog

v1.0.0:
- Initial release.
  


