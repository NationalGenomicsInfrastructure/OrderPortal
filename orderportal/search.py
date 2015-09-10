"OrderPortal: Search page."

from __future__ import print_function, absolute_import

import logging
import urlparse

import tornado.web

from . import constants
from . import saver
from . import settings
from . import utils
from .fields import Fields
from .requesthandler import RequestHandler


class Search(RequestHandler):
    "Search. Currently only orders and staff."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        orig = self.get_argument('term', '')
        # Keep this in sync with 'order/search.js'
        term = orig.replace(':', ' ')
        term = term.replace(',', ' ')
        term = term.replace("'", ' ')
        term = term.strip()
        view = self.db.view('order/keyword')
        id_sets = []
        for part in [part for part in term.split() if len(part) > 2]:
            id_sets.append(set([r.id for r in
                                view[part : part+constants.HIGH_CHAR]]))
        if id_sets:
            id_set = reduce(lambda i,j: i.intersection(j), id_sets)
            orders = [self.get_entity(id, doctype=constants.ORDER)
                      for id in id_set]
            orders.sort(lambda i,j: cmp(i['modified'], j['modified']),
                        reverse=True)
        else:
            orders = []
        items = orders
        params = dict(term=orig)
        # Page
        page_size = self.current_user.get('page_size') or constants.DEFAULT_PAGE_SIZE
        count = len(items)
        max_page = (count - 1) / page_size
        try:
            page = int(self.get_argument('page', 0))
            page = max(0, min(page, max_page))
        except (ValueError, TypeError):
            page = 0
        start = page * page_size
        end = min(start + page_size, count)
        items = items[start : end]
        params['page'] = page
        self.render('search.html',
                    items=items,
                    params=params,
                    start=start+1,
                    end=end,
                    max_page=max_page,
                    count=count)



