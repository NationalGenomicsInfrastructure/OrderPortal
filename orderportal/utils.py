"OrderPortal: Various utility functions."

from __future__ import print_function, absolute_import

import collections
import datetime
import hashlib
import logging
import mimetypes
import optparse
import os
import socket
import sys
import time
import unicodedata
import urllib
import urlparse
import uuid

import couchdb
import tornado.web
import yaml

import orderportal
from . import constants
from . import settings


def get_command_line_parser(usage='usage: %prog [options]', description=None):
    "Get the base command line argument parser."
    # optparse is used (rather than argparse) since
    # this code must be possible to run under Python 2.6
    parser = optparse.OptionParser(usage=usage, description=description)
    parser.add_option('-s', '--settings',
                      action='store', dest='settings', default=None,
                      metavar="FILE", help="filename of settings YAML file")
    parser.add_option('-v', '--verbose',
                      action="store_true", dest="verbose", default=False,
                      help='verbose output of actions taken')
    parser.add_option('-f', '--force',
                      action="store_true", dest="force", default=False,
                      help='force action, rather than ask for confirmation')
    return parser

def load_settings(filepath=None, verbose=False):
    """Load and return the settings from the file path given by
    1) the argument to this procedure,
    2) the environment variable ORDERPORTAL_SETTINGS,
    3) the first existing file in a predefined list of filepaths.
    Raise ValueError if no settings file was given.
    Raise IOError if settings file could not be read.
    Raise KeyError if a settings variable is missing.
    Raise ValueError if the settings variable value is invalid.
    """
    if not filepath:
        filepath = os.environ.get('ORDERPORTAL_SETTINGS')
    if not filepath:
        basedir = constants.ROOT
        hostname = socket.gethostname().split('.')[0]
        for filepath in [os.path.join(basedir, "{}.yaml".format(hostname)),
                         os.path.join(basedir, 'default.yaml')]:
            if os.path.exists(filepath) and os.path.isfile(filepath):
                break
        else:
            raise ValueError('no settings file specified')
    if verbose:
        print('settings from', filepath, file=sys.stderr)
    with open(filepath) as infile:
        settings.update(yaml.safe_load(infile))
    # Expand environment variables and the constants.ROOT
    for key, value in settings.items():
        if isinstance(value, (str, unicode)):
            settings[key] = expand_filepath(value)
    # Set logging state
    if settings.get('LOGGING_DEBUG'):
        kwargs = dict(level=logging.DEBUG)
    else:
        kwargs = dict(level=logging.INFO)
    try:
        kwargs['format'] = settings['LOGGING_FORMAT']
    except KeyError:
        pass
    try:
        kwargs['filename'] = settings['LOGGING_FILENAME']
    except KeyError:
        pass
    try:
        kwargs['filemode'] = settings['LOGGING_FILEMODE']
    except KeyError:
        pass
    logging.basicConfig(**kwargs)
    # Read order state definitions and transitions
    settings['ORDER_STATUSES'] = \
        yaml.safe_load(open(settings['ORDER_STATUSES_FILENAME']))
    lookup = dict()
    for status in settings['ORDER_STATUSES']:
        if status['identifier'] in lookup:
            raise ValueError("order status '%s' redefined" %
                             status['identifier'])
        lookup[status['identifier']] = status
    settings['ORDER_STATUSES_LOOKUP'] = lookup
    settings['ORDER_TRANSITIONS'] = \
        yaml.safe_load(open(settings['ORDER_TRANSITIONS_FILENAME']))
    # Check settings
    for key in ['BASE_URL', 'DB_SERVER', 'COOKIE_SECRET', 'DATABASE']:
        if key not in settings:
            raise KeyError("no settings['{}'] item".format(key))
        if not settings[key]:
            raise ValueError("settings['{}'] has invalid value".format(key))
    if len(settings.get('COOKIE_SECRET', '')) < 10:
        raise ValueError("settings['COOKIE_SECRET'] not set, or too short")
    # Read universities lookup
    try:
        filepath = os.path.join(settings['SITE_DIR'],
                                settings['UNIVERSITIES_FILENAME'])
        unis = yaml.safe_load(open(filepath))
    except (IOError, KeyError):
        unis = dict()
    unis = unis.items()
    unis.sort(lambda i,j: cmp((i[1].get('rank'), i[0]),
                              (j[1].get('rank'), j[0])))
    settings['UNIVERSITIES'] = collections.OrderedDict(unis)
    # Settings computable from others
    settings['DB_SERVER_VERSION'] = couchdb.Server(settings['DB_SERVER']).version()
    if 'PORT' not in settings:
        parts = urlparse.urlparse(settings['BASE_URL'])
        items = parts.netloc.split(':')
        if len(items) == 2:
            settings['PORT'] = int(items[1])
        elif parts.scheme == 'http':
            settings['PORT'] =  80
        elif parts.scheme == 'https':
            settings['PORT'] =  443
        else:
            raise ValueError('could not determine port from BASE_URL')

def expand_filepath(filepath):
    "Expand environment variables and the constants.ROOT in filepaths."
    filepath = os.path.expandvars(filepath)
    return filepath.replace('{ROOT}', constants.ROOT)

def get_dbserver():
    return couchdb.Server(settings['DB_SERVER'])

def get_db(create=False):
    """Return the handle for the CouchDB database.
    If 'create' is True, then create the database if it does not exist.
    """
    server = get_dbserver()
    name = settings['DATABASE']
    try:
        return server[name]
    except couchdb.http.ResourceNotFound:
        if create:
            return server.create(name)
        else:
            raise KeyError("CouchDB database '%s' does not exist" % name)

def get_iuid():
    "Return a unique instance identifier."
    return uuid.uuid4().hex

def timestamp(days=None):
    """Current date and time (UTC) in ISO format, with millisecond precision.
    Add the specified offset in days, if given.
    """
    instant = datetime.datetime.utcnow()
    if days:
        instant += datetime.timedelta(days=days)
    instant = instant.isoformat()
    return instant[:-9] + "%06.3f" % float(instant[-9:]) + "Z"

def to_ascii(value):
    "Convert any non-ASCII character to its closest ASCII equivalent."
    if not isinstance(value, unicode):
        value = unicode(value, 'utf-8')
    return unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')

def to_bool(value):
    "Convert the value into a boolean, interpreting various string values."
    if not value: return False
    lowvalue = value.lower()
    if lowvalue in constants.TRUE: return True
    if lowvalue in constants.FALSE: return False
    raise ValueError("invalid boolean: '{}'".format(value))

def convert(type, value):
    "Convert the string representation to the given type."
    if value is None: return None
    if value == '': return None
    if type == 'int':
        return int(value)
    elif type == 'float':
        return float(value)
    elif type == 'boolean':
        return to_bool(value)
    else:
        return value

def cmp_modified(i, j):
    "Compare the two documents by their 'modified' values."
    return cmp(i['modified'], j['modified'])

def absolute_path(filename):
    "Return the absolute path given the current directory."
    return os.path.join(constants.ROOT, filename)

def hashed_password(password):
    "Return the password in hashed form."
    sha256 = hashlib.sha256(settings['PASSWORD_SALT'])
    sha256.update(password)
    return sha256.hexdigest()
