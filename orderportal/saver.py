"OrderPortal: Context handler for saving an entity. "

from __future__ import unicode_literals, print_function, absolute_import

import logging

import tornado.web
import couchdb

from orderportal import constants
from orderportal import utils


class Saver(object):
    "Context handler saving the data for the entity."

    doctype = None

    def __init__(self, doc=None, rqh=None, db=None):
        assert self.doctype
        if rqh is not None:
            self.rqh = rqh
            self.db = rqh.db
            self.current_user = rqh.current_user
        elif db is not None:
            self.rqh = None
            self.db = db
            self.current_user = dict()
        else:
            raise AttributeError('neither db nor rqh given')
        self.doc = doc or dict()
        self.changed = dict()
        if '_id' in self.doc:
            assert self.doctype == self.doc[constants.DOCTYPE]
        else:
            self.doc[constants.DOCTYPE] = self.doctype
            self.doc['_id'] = utils.get_iuid()
            self.initialize()

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        if type is not None: return False # No exceptions handled here.
        self.finalize()
        try:
            self.db.save(self.doc)
        except couchdb.http.ResourceConflict:
            raise IOError('document revision update conflict')
        self.post_process()
        self.log()

    def __setitem__(self, key, value):
        "Update the key/value pair."
        try:
            checker = getattr(self, "check_{}".format(key))
        except AttributeError:
            pass
        else:
            checker(value)
        try:
            converter = getattr(self, "convert_{}".format(key))
        except AttributeError:
            pass
        else:
            value = converter(value)
        try:
            if self.doc[key] == value: return
        except KeyError:
            pass
        self.doc[key] = value
        self.changed[key] = value

    def __getitem__(self, key):
        return self.doc[key]

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def initialize(self):
        "Set the initial values for the new entity."
        try:
            if not self.rqh.current_user: raise AttributeError
        except AttributeError:
            self.doc['owner'] = None
        else:
            self.doc['owner'] = self.rqh.current_user['email']
        self.doc['created'] = utils.timestamp()

    def finalize(self):
        "Perform any final modifications before saving the entity."
        self.doc['modified'] = utils.timestamp()

    def post_process(self):
        "Perform any actions after having saved the entity."
        pass

    def log(self):
        "Create a log entry for the change."
        entry = dict(_id=utils.get_iuid(),
                     entity=self.doc['_id'],
                     changed=self.changed,
                     modified=self.doc['modified'])
        if self.rqh:
            # xheaders argument to HTTPServer takes care of X-Real-Ip
            # and X-Forwarded-For
            entry['remote_ip'] = self.rqh.request.remote_ip
            try:
                entry['user_agent'] = self.rqh.request.headers['User-Agent']
            except KeyError:
                pass
        entry[constants.DOCTYPE] = constants.LOG
        try:
            entry['user'] = self.current_user['email']
        except (TypeError, KeyError):
            pass
        self.db.save(entry)

    def save_required(self):
        self['required'] = utils.to_bool(self.rqh.get_argument('required',
                                                               False))
