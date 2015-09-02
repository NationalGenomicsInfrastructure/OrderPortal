"OrderPortal: User and login pages."

from __future__ import print_function, absolute_import

import logging

import tornado.web

import orderportal
from orderportal import constants
from orderportal import saver
from orderportal import settings
from orderportal import utils
from orderportal.requesthandler import RequestHandler


class UserSaver(saver.Saver):
    doctype = constants.USER

    def erase_password(self):
        self['password'] = None

    def set_password(self, new):
        self.check_password(new)
        self['code'] = None
        # Bypass ordinary 'set'; avoid logging password, even if hashed.
        self.doc['password'] = utils.hashed_password(new)

    def check_password(self, password):
        if password is None: return
        if len(password) < constants.MIN_PASSWORD_LENGTH:
            raise tornado.web.HTTPError(400, reason='invalid password')

    def reset_password(self):
        "Invalidate any previous password and set activation code."
        self.erase_password()
        self['code'] = utils.get_iuid()


class Users(RequestHandler):
    """Users list page.
    Allow filtering by university, role and status.
    Allow sort by email, name and login.
    """
    @tornado.web.authenticated
    def get(self):
        self.check_staff()
        params = dict()
        # Filter list
        university = self.get_argument('university', '')
        if university == '[other]':
            view = self.db.view('user/email', include_docs=True)
            users = [r.doc for r in view]
            users = [u for u in users
                     if u['university'] not in settings['UNIVERSITY_LIST']]
            params['university'] = university
        elif university:
            view = self.db.view('user/university',
                                key=university,
                                include_docs=True)
            users = [r.doc for r in view]
            params['university'] = university
        else:
            users = None
        role = self.get_argument('role', '')
        if role:
            if users is None:
                view = self.db.view('user/role',
                                    key=role,
                                    include_docs=True)
                users = [r.doc for r in view]
            else:
                users = [u for u in users if u['role'] == role]
            params['role'] = role
        status = self.get_argument('status', '')
        if status:
            if users is None:
                view = self.db.view('user/status',
                                    key=status,
                                    include_docs=True)
                users = [r.doc for r in view]
            else:
                users = [u for u in users if u['status'] == status]
            params['status'] = status
        if users is None:
            view = self.db.view('user/email', include_docs=True)
            users = [r.doc for r in view]
        # Order; different default depending on sort key
        try:
            value = self.get_argument('descending')
            if value == '': raise ValueError
            descending = utils.to_bool(value)
        except (tornado.web.MissingArgumentError, TypeError, ValueError):
            descending = None
        else:
            params['descending'] = str(descending).lower()
        # Sort list
        sort = self.get_argument('sort', '').lower()
        if sort == 'login':
            if descending is None: descending = True
            users.sort(lambda i, j: cmp(i.get('login'), j.get('login')),
                       reverse=descending)
        elif sort == 'name':
            if descending is None: descending = False
            users.sort(lambda i, j: cmp((i['last_name'], i['first_name']),
                                        (j['last_name'], j['first_name'])),
                       reverse=descending)
        elif sort == 'email':
            if descending is None: descending = False
            users.sort(lambda i, j: cmp(i['email'], j['email']),
                       reverse=descending)
        # Default: name
        else:
            if descending is None: descending = False
            users.sort(lambda i, j: cmp((i['last_name'], i['first_name']),
                                        (j['last_name'], j['first_name'])),
                       reverse=descending)
        if sort:
            params['sort'] = sort
        # Page
        count = len(users)
        max_page = (count - 1) / constants.PAGE_SIZE
        try:
            page = int(self.get_argument('page', 0))
            page = max(0, min(page, max_page))
        except (ValueError, TypeError):
            page = 0
        start = page * constants.PAGE_SIZE
        end = min(start + constants.PAGE_SIZE, count)
        users = users[start : end]
        params['page'] = page
        #
        self.render('users.html',
                    users=users,
                    params=params,
                    start=start+1,
                    end=end,
                    max_page=max_page,
                    count=count)


class User(RequestHandler):
    "User page."

    @tornado.web.authenticated
    def get(self, email):
        user = self.get_user(email)
        self.check_owner_or_staff(user)
        self.render('user.html', user=user, deletable=self.get_deletable(user))

    @tornado.web.authenticated
    def post(self, email):
        self.check_xsrf_cookie()
        if self.get_argument('_http_method', None) == 'delete':
            self.delete(email)
            return
        raise tornado.web.HTTPError(405, reason='POST only allowed for DELETE')

    @tornado.web.authenticated
    def delete(self, email):
        "Delete a user that is pending; to get rid of spam application."
        user = self.get_user(email)
        self.check_admin()
        if not self.get_deletable(user):
            raise tornado.web.HTTPError(403, reason='user cannot be deleted')
        self.delete_logs(user['_id'])
        self.db.delete(user)
        self.see_other('home')

    def get_deletable(self, user):
        "Can the user be deleted? Pending, or disabled and no orders."
        if user['status'] == constants.PENDING: return True
        if user['status'] == constants.ENABLED: return False
        view = self.db.view('order/owner', key=user['email'])
        if len(list(view)) == 0: return True
        return False


class UserLogs(RequestHandler):
    "User log entries page."

    @tornado.web.authenticated
    def get(self, email):
        user = self.get_user(email)
        self.check_owner_or_staff(user)
        self.render('logs.html', entity=user, logs=self.get_logs(user['_id']))


class UserEdit(RequestHandler):
    "Page for editing user information."

    @tornado.web.authenticated
    def get(self, email):
        user = self.get_user(email)
        self.check_owner_or_staff(user)
        self.render('user_edit.html', user=user)

    @tornado.web.authenticated
    def post(self, email):
        self.check_xsrf_cookie()
        user = self.get_user(email)
        self.check_owner_or_staff(user)
        with UserSaver(doc=user, rqh=self) as saver:
            if self.is_admin():
                role = self.get_argument('role')
                if role not in constants.USER_ROLES:
                    raise tornado.web.HTTPError(404, reason='invalid role')
                saver['role'] = role
            saver['first_name'] = self.get_argument('first_name')
            saver['last_name'] = self.get_argument('last_name')
            university = self.get_argument('university_other', default=None)
            if not university:
                university = self.get_argument('university', default=None)
            saver['university'] = university or 'undefined'
            saver['department'] = self.get_argument('department', default=None)
            saver['address'] = self.get_argument('address', default=None)
            saver['phone'] = self.get_argument('phone', default=None)
        self.see_other('user', email)


class Login(RequestHandler):
    "Login to a user account. Set a secure cookie."

    def post(self):
        "Login to a user account. Set a secure cookie."
        self.check_xsrf_cookie()
        try:
            email = self.get_argument('email')
            password = self.get_argument('password')
        except tornado.web.MissingArgumentError:
            raise tornado.web.HTTPError(403, reason='missing email or password')
        try:
            user = self.get_user(email)
        except tornado.web.HTTPError:
            raise tornado.web.HTTPError(404, reason='no such user')
        if not utils.hashed_password(password) == user.get('password'):
            raise tornado.web.HTTPError(400, reason='invalid password')
        if not user.get('status') == constants.ENABLED:
            raise tornado.web.HTTPError(400, reason='disabled user account')
        self.set_secure_cookie(constants.USER_COOKIE, user['email'])
        with UserSaver(doc=user, rqh=self) as saver:
            saver['login'] = utils.timestamp() # Set login timestamp.
        self.redirect(self.reverse_url('home'))


class Logout(RequestHandler):
    "Logout; unset the secure cookie, and invalidate login session."

    @tornado.web.authenticated
    def post(self):
        self.check_xsrf_cookie()
        self.set_secure_cookie(constants.USER_COOKIE, '')
        self.redirect(self.reverse_url('home'))


class Reset(RequestHandler):
    "Reset the password of a user account."

    SUBJECT = "The password for your {} portal account has been reset"
    TEXT = """The password for your account {} in the {} portal has been reset.
Please got to {} to set your password.
The code required to set your password is "{}".
"""

    def get(self):
        email = self.current_user and self.current_user.get('email')
        self.render('reset.html', email=email)

    def post(self):
        self.check_xsrf_cookie()
        user = self.get_user(self.get_argument('email'))
        with UserSaver(doc=user, rqh=self) as saver:
            saver.reset_password()
        url = self.absolute_reverse_url('password',
                                        email=user['email'],
                                        code=user['code'])
        self.send_email(user['email'],
                        self.SUBJECT.format(settings['FACILITY_NAME']),
                        self.TEXT.format(user['email'],
                                         settings['FACILITY_NAME'],
                                         url,
                                         user['code']))
        self.see_other('password')


class Password(RequestHandler):
    "Set the password of a user account; requires a code."

    def get(self):
        self.render('password.html',
                    title='Set your password',
                    email=self.get_argument('email', default=''),
                    code=self.get_argument('code', default=''))

    def post(self):
        self.check_xsrf_cookie()
        user = self.get_user(self.get_argument('email'))
        if user.get('code') != self.get_argument('code'):
            raise tornado.web.HTTPError(400, reason='invalid email or code')
        password = self.get_argument('password')
        if len(password) < constants.MIN_PASSWORD_LENGTH:
            mgs = "password shorter than {} characters".format(
                constants.MIN_PASSWORD_LENGTH)
            raise tornado.web.HTTPError(400, reason=msg)
        if password != self.get_argument('confirm_password'):
            msg = 'password not the same! mistyped'
            raise tornado.web.HTTPError(400, reason=msg)
        with UserSaver(doc=user, rqh=self) as saver:
            saver.set_password(password)
            saver['login'] = utils.timestamp() # Set login session.
        self.set_secure_cookie(constants.USER_COOKIE, user['email'])
        self.redirect(self.reverse_url('home'))
            

class Register(RequestHandler):
    "Register a new user account."

    def get(self):
        self.render('register.html')

    def post(self):
        self.check_xsrf_cookie()
        with UserSaver(rqh=self) as saver:
            try:
                email = self.get_argument('email')
                if not email: raise ValueError
                if not constants.EMAIL_RX.match(email): raise ValueError
                try:
                    self.get_user(email)
                except tornado.web.HTTPError:
                    pass
                else:
                    reason = 'email address already in use'
                    raise tornado.web.HTTPError(409, reason=reason)
                saver['email'] = email
                saver['first_name'] = self.get_argument('first_name')
                saver['last_name'] = self.get_argument('last_name')
                university = self.get_argument('university_other', default=None)
                if not university:
                    university = self.get_argument('university', default=None)
                saver['university'] = university or 'undefined'
            except (tornado.web.MissingArgumentError, ValueError):
                reason = "invalid '{}' value provided".format(key)
                raise tornado.web.HTTPError(400, reason=reason)
            saver['department'] = self.get_argument('department', default=None)
            saver['address'] = self.get_argument('address', default=None)
            saver['phone'] = self.get_argument('phone', default=None)
            saver['owner'] = email
            saver['role'] = constants.USER
            saver['status'] = constants.PENDING
            saver.erase_password()
        self.see_other('password')


class UserEnable(RequestHandler):
    "Enable the user; from status pending or disabled."

    SUBJECT = "Your {} portal account has been enabled"
    TEXT = """Your account {} in the {} portal has been enabled.
Please got to {} to set your password.
"""

    @tornado.web.authenticated
    def post(self, email):
        self.check_xsrf_cookie()
        user = self.get_user(email)
        self.check_admin()
        with UserSaver(user, rqh=self) as saver:
            saver['code'] = utils.get_iuid()
            saver['status'] = constants.ENABLED
            saver.erase_password()
        url = self.absolute_reverse_url('password',
                                        email=email,
                                        code=user['code'])
        self.send_email(user['email'],
                        self.SUBJECT.format(settings['FACILITY_NAME']),
                        self.TEXT.format(email, settings['FACILITY_NAME'], url))
        self.see_other('user', email)


class UserDisable(RequestHandler):
    "Disable the user; from status pending or enabled."

    @tornado.web.authenticated
    def post(self, email):
        self.check_xsrf_cookie()
        user = self.get_user(email)
        self.check_admin()
        with UserSaver(user, rqh=self) as saver:
            saver['status'] = constants.DISABLED
            saver.erase_password()
        self.see_other('user', email)
