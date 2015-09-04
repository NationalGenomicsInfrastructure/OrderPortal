""" OrderPortal: Dump the database into a tar file.
The settings file may be given as the first command line argument,
otherwise it is obtained as usual.
The dump file will be called 'dump_{ISO date}.tar.gz' using today's date.
Create the dump file in the directory specified by BACKUP_DIR variable
in the settings, otherwise in the current working directory.
"""

from __future__ import print_function, absolute_import

import cStringIO
import json
import os
import tarfile
import time

from orderportal import constants
from orderportal import settings
from orderportal import utils


def get_command_line_parser():
    parser = utils.get_command_line_parser(description=
        'Dump all data into a tar file.')
    parser.add_option('-d', '--dumpfile',
                      action='store', dest='dumpfile',
                      metavar='DUMPFILE', help='name of dump file')
    return parser

def dump(db, filepath, verbose=False):
    "Dump contents of the database to a tar file, optionally gzip compressed."
    count_items = 0
    count_files = 0
    if filepath.endswith('.gz'):
        mode = 'w:gz'
    else:
        mode = 'w'
    outfile = tarfile.open(filepath, mode=mode)
    for key in db:
        if not constants.IUID_RX.match(key): continue
        doc = db[key]
        del doc['_rev']
        info = tarfile.TarInfo(doc['_id'])
        data = json.dumps(doc)
        info.size = len(data)
        outfile.addfile(info, cStringIO.StringIO(data))
        count_items += 1
        for attname in doc.get('_attachments', dict()):
            info = tarfile.TarInfo("{}_att/{}".format(doc['_id'], attname))
            attfile = db.get_attachment(doc, attname)
            if attfile is None:
                data = ''
            else:
                data = attfile.read()
                attfile.close()
            info.size = len(data)
            outfile.addfile(info, cStringIO.StringIO(data))
            count_files += 1
    outfile.close()
    if verbose:
        print('dumped', count_items, 'items and',
              count_files, 'files to', filepath, file=sys.stderr)

def undump(db, filename, verbose=False):
    """Reverse of dump; load all items from a tar file.
    Items are just added to the database, ignoring existing items.
    """
    count_items = 0
    count_files = 0
    attachments = dict()
    infile = tarfile.open(filename, mode='r')
    for item in infile:
        itemfile = infile.extractfile(item)
        itemdata = itemfile.read()
        itemfile.close()
        if item.name in attachments:
            # This relies on an attachment being after its item in the tarfile.
            db.put_attachment(doc, itemdata, **attachments.pop(item.name))
            count_files += 1
        else:
            doc = json.loads(itemdata)
            # If the account document already exists, do not load again.
            if doc[constants.DOCTYPE] == constants.ACCOUNT:
                rows = db.view('account/email', key=doc['email'])
                if len(list(rows)) != 0: continue
            atts = doc.pop('_attachments', dict())
            db.save(doc)
            count_items += 1
            for attname, attinfo in atts.items():
                key = "{}_att/{}".format(doc['_id'], attname)
                attachments[key] = dict(filename=attname,
                                        content_type=attinfo['content_type'])
    infile.close()
    if verbose:
        print('undumped', count_items, 'items and',
              count_files, 'files from', filepath, file=sys.stderr)


if __name__ == '__main__':
    parser = get_command_line_parser()
    (options, args) = parser.parse_args()
    utils.load_settings(filepath=options.settings,
                        verbose=options.verbose)
    db = utils.get_db()
    if options.dumpfile:
        filepath = options.dumpfile
    else:
        filepath = "dump_{}.tar.gz".format(time.strftime("%Y-%m-%d"))
    try:
        filepath = os.path.join(settings['BACKUP_DIR'], filepath)
    except KeyError:
        pass
    dump(db, filepath, verbose=options.verbose)
