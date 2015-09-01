"OrderPortal: File pages; uploaded files."

from __future__ import print_function, absolute_import

import logging

import tornado.web

import orderportal
from orderportal import constants
from orderportal import saver
from orderportal import settings
from orderportal import utils
from orderportal.requesthandler import RequestHandler


class FileSaver(saver.Saver):
    doctype = constants.FILE

    def check_name(self, value):
        if not constants.NAME_RX.match(value):
            raise tornado.web.HTTPError(400, reason='invalid file name')
        try:
            self.rqh.get_entity_view('file/name', value)
        except tornado.web.HTTPError:
            pass
        else:
            raise tornado.web.HTTPError(400, reason='file name already exists')

    def post_process(self):
        "Save the file as an attachment to the document."
        # No new file uploaded, just skip out.
        if self.content is None: return
        logging.debug("self.doc %s", self.doc)
        logging.debug("len(self.content) %s", len(self.content))
        self.db.put_attachment(self.doc,
                               self.content,
                               filename=self['name'],
                               content_type=self['content_type'])
        

class File(RequestHandler):
    "Send the file data."

    def get(self, name):
        file = self.get_entity_view('file/name', name)
        filename = file['_attachments'].keys()[0]
        infile = self.db.get_attachment(file, filename)
        if infile is None:
            self.write('')
        else:
            self.write(infile.read())
            infile.close()
        self.set_header('Content-Type', file['content_type'])


class FileDownload(File):
    "Download the file."

    def get(self, name):
        super(FileDownload, self).get(name)
        self.set_header('Content-Disposition',
                        'attachment; filename="{}"'.format(name))


class FileMeta(RequestHandler):
    "Display the file metadata."

    def get(self, name):
        file = self.get_entity_view('file/name', name)
        title = file.get('title') or file['name']
        self.render('file_meta.html', file=file, title=title)

    @tornado.web.authenticated
    def post(self, name):
        self.check_xsrf_cookie()
        self.check_admin()
        if self.get_argument('_http_method', None) == 'delete':
            self.delete(name)
            return
        raise tornado.web.HTTPError(405, reason='POST only allowed for DELETE')

    @tornado.web.authenticated
    def delete(self, name):
        self.check_admin()
        file = self.get_entity_view('file/name', name)
        self.delete_logs(file['_id'])
        self.db.delete(file)
        self.see_other('files')


class FileLogs(RequestHandler):
    "File log entries page."

    @tornado.web.authenticated
    def get(self, name):
        self.check_admin()
        file = self.get_entity_view('file/name', name)
        self.render('logs.html',
                    title="Logs for file '{}'".format(name),
                    entity=file,
                    logs=self.get_logs(file['_id']))


class Files(RequestHandler):
    "List of file pages."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        view = self.db.view('file/menu', include_docs=True)
        menu_files = [r.doc for r in view]
        view = self.db.view('file/name', include_docs=True)
        rest_files = [r.doc for r in view if r.doc.get('menu') is None]
        self.render('files.html', all_files=menu_files + rest_files)


class FileCreate(RequestHandler):
    "Create a new file page."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render('file_create.html')

    @tornado.web.authenticated
    def post(self):
        self.check_xsrf_cookie()
        self.check_admin()
        with FileSaver(rqh=self) as saver:
            try:
                infile = self.request.files['file'][0]
            except (KeyError, IndexError):
                raise tornado.web.HTTPError(400, reason='no file uploaded')
            saver.content = infile['body']
            saver['name'] = self.get_argument('name',None) or infile['filename']
            saver['size'] = len(infile['body'])
            saver['content_type'] = infile['content_type'] or 'application/octet-stream'
            try:
                saver['menu'] = int(self.get_argument('menu', None))
            except (ValueError, TypeError):
                saver['menu'] = None
            saver['description'] = self.get_argument('description', None)
        self.see_other('file_meta', saver['name'])


class FileEdit(RequestHandler):
    "Edit the file page."

    @tornado.web.authenticated
    def get(self, name):
        self.check_admin()
        file = self.get_entity_view('file/name', name)
        self.render('file_edit.html', file=file)

    @tornado.web.authenticated
    def post(self, name):
        self.check_admin()
        file = self.get_entity_view('file/name', name)
        with FileSaver(doc=file, rqh=self) as saver:
            saver['title'] = self.get_argument('title', None)
            try:
                saver['menu'] = int(self.get_argument('menu', None))
            except (ValueError, TypeError):
                saver['menu'] = None
            try:
                infile = self.request.files['file'][0]
            except (KeyError, IndexError):
                # No new file upload, just leave it alone.
                saver.content = None
            else:
                saver.content = infile['body']
                saver['filename'] = infile['filename']
                saver['size'] = len(saver.content)
                saver['content_type'] = infile['content_type']
            saver['description'] = self.get_argument('description', None)
        self.see_other('file_meta', name)
