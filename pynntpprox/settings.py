# generic settings module

SERVERS = {
        'default': {
            'HOST': 'news.usenetserver.com',
            'PORT': 563,
            'USER': 'clone00',
            'PASS': 'serpent01',
            'SECURE': 'SSL',
            'CONNECTIONS': 6,
            ## unused..
            'RETENTION': 1577,
        }
    }
# python 2 compat..
PICKLE_PROTOCOL = 2
