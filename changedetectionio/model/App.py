from os import getenv
from changedetectionio.notification import (
    default_notification_body,
    default_notification_format,
    default_notification_title,
)

_FILTER_FAILURE_THRESHOLD_ATTEMPTS_DEFAULT = 6

class model(dict):
    base_config = {
            'note': "Hello! If you change this file manually, please be sure to restart your changedetection.io instance!",
            'watching': {},
            'settings': {
                'headers': {
                },
                'requests': {
                    'timeout': int(getenv("DEFAULT_SETTINGS_REQUESTS_TIMEOUT", "45")),  # Default 45 seconds
                    'time_between_check': {'weeks': None, 'days': None, 'hours': 3, 'minutes': None, 'seconds': None},
                    'time_schedule_check_limit': {'day_of_week': [0, 1, 2, 3, 4, 5, 6], 'time_from': '', 'time_until': ''},
                    'jitter_seconds': 0,
                    'workers': int(getenv("DEFAULT_SETTINGS_REQUESTS_WORKERS", "10")),  # Number of threads, lower is better for slow connections
                    'proxy': None # Preferred proxy connection
                },
                'application': {
                    # Custom notification content
                    'api_access_token_enabled': True,
                    'base_url' : None,
                    'empty_pages_are_a_change': False,
                    'extract_title_as_title': False,
                    'fetch_backend': getenv("DEFAULT_FETCH_BACKEND", "html_requests"),
                    'filter_failure_notification_threshold_attempts': _FILTER_FAILURE_THRESHOLD_ATTEMPTS_DEFAULT,
                    'global_ignore_text': [], # List of text to ignore when calculating the comparison checksum
                    'global_subtractive_selectors': [],
                    'ignore_whitespace': True,
                    'notification_body': default_notification_body,
                    'notification_format': default_notification_format,
                    'notification_title': default_notification_title,
                    'notification_urls': [], # Apprise URL list
                    'password': False,
                    'render_anchor_tag_content': False,
                    'schema_version' : 0,
                    'timezone': 'UTC',
                    'webdriver_delay': None,  # Extra delay in seconds before extracting text
                }
            }
        }

    def __init__(self, *arg, **kw):
        super(model, self).__init__(*arg, **kw)
        self.update(self.base_config)
