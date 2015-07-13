"OrderPortal: News page."

from __future__ import print_function, absolute_import

import logging
import tornado.web

import orderportal
from orderportal import constants
from orderportal import saver
from orderportal import settings
from orderportal import utils
from orderportal.requesthandler import RequestHandler


class NewSaver(saver.Saver):
    doctype = constants.NEW


class News(RequestHandler):
    "Page for viewing and handling all news items; creation, deletion."

    def get(self):
        self.render('news.html', news=self.get_news())

    @tornado.web.authenticated
    def post(self):
        self.check_admin()
        with NewSaver(rqh=self) as saver:
            saver['text'] = self.get_argument('text')
        self.see_other('news')


class New(RequestHandler):
    "Handle a news item."

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_xsrf_cookie()
        if self.get_argument('_http_method', None) == 'delete':
            self.delete(iuid)
            return
        raise tornado.web.HTTPError(405, reason='POST only allowed for DELETE')

    @tornado.web.authenticated
    def delete(self, iuid):
        self.check_admin()
        new = self.get_entity(iuid, constants.NEW)
        if new is None:
            raise tornado.web.HTTPError(404)
        self.db.delete(new)
        self.see_other('news')
