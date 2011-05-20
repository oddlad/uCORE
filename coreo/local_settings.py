import logging

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = '/home/core/webapps/static_media/'

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = 'http://www.layeredintel.com/media/'
ADMIN_MEDIA_PREFIX = 'http://www.layeredintel.com/media/admin/'

SITE_ROOT = 'http://www.layeredintel.com/' 


SECRET_KEY = 'foo'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    '/home/core/webapps/ucore/coreo/templates/ucore/',
)

logging.basicConfig(
    level=logging.DEBUG,
    filename='/home/core/logs/user/ucore.log',
    filemode = 'w'
)
