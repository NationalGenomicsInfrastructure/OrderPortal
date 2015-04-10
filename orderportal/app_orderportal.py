"OrderPortal: Web application root."

from __future__ import unicode_literals, print_function, absolute_import

import os
import sys
import logging

import tornado
import tornado.web
import tornado.ioloop
import couchdb
import yaml

import orderportal
from orderportal import constants
from orderportal import settings
from orderportal import utils
from orderportal import uimodules
from orderportal.requesthandler import RequestHandler

from orderportal.home import *
from orderportal.user import *
from orderportal.field import *
from orderportal.order import *


class Dummy(RequestHandler):
    def get(self, *args, **kwargs):
        self.redirect(self.reverse_url('home'))


def get_handlers():
    URL = tornado.web.url
    return [URL(r'/', Home, name='home'),
            URL(r'/search', Dummy, name='search'),
            URL(r'/orders', Orders, name='orders'),
            URL(r'/order/([0-9a-f]{32})', Order, name='order'),
            URL(r'/order', OrderCreate, name='order_create'),
            URL(r'/order/([0-9a-f]{32})/edit', OrderEdit, name='order_edit'),
            # URL(r'/order/([0-9a-f]{32})/copy', OrderCopy, name='order_copy'),
            # URL(r'/order/([0-9a-f]{32})/log', OrderLog, name='order_log'),
            URL(r'/users', Users, name='users'),
            URL(r'/user/([^/]+)', User, name='user'),
            # URL(r'/user/([^/]+)/edit', UserEdit, name='user_edit'),
            URL(r'/login', Login, name='login'),
            URL(r'/logout', Logout, name='logout'),
            URL(r'/reset', Reset, name='reset'),
            URL(r'/password', Password, name='password'),
            URL(r'/register', Register, name='register'),
            URL(r'/user/([^/]+)/delete', UserDelete, name='user_delete'),
            URL(r'/user/([^/]+)/enable', UserEnable, name='user_enable'),
            URL(r'/user/([^/]+)/disable', UserDisable, name='user_disable'),
            # URL(r'/user/([0-9a-f]{32})/log', UserLog, name='user_log'),
            URL(r'/field', FieldCreate, name='field_create'),
            URL(r'/field/([a-zA-Z][a-zA-Z0-9_]*)', Field, name='field'),
            URL(r'/field/([a-zA-Z][a-zA-Z0-9_]*)/edit',
                FieldEdit, name='field_edit'),
            URL(r'/fields', Fields, name='fields'),
            # URL(r'/field/([0-9a-f]{32})', Field, name='field'),
            URL(r'/log/([0-9a-f]{32})', Log, name='log'),
            ]

def get_args():
    parser = utils.get_command_line_parser(description='Web app server.')
    return parser.parse_args()

def main():
    logging.info("tornado debug: %s, logging debug: %s",
                 settings['TORNADO_DEBUG'], settings['LOGGING_DEBUG'])
    logging.debug("orderportal %s, tornado %s, couchdb module %s, pyyaml %s",
                  orderportal.__version__,
                  tornado.version,
                  couchdb.__version__,
                  yaml.__version__)
    application = tornado.web.Application(
        handlers=get_handlers(),
        debug=settings.get('TORNADO_DEBUG', False),
        cookie_secret=settings['COOKIE_SECRET'],
        ui_modules=uimodules,
        template_path=settings.get('TEMPLATE_PATH', 'html'),
        static_path=settings.get('STATIC_PATH', 'static'),
        login_url=r'/home')
    application.listen(settings['PORT'], xheaders=True)
    logging.info("OrderPortal %s web server PID %s on port %s",
                 settings['DATABASE'], os.getpid(), settings['PORT'])
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    (options, args) = get_args()
    utils.load_settings(filepath=options.settings,
                        verbose=options.verbose)
    main()
