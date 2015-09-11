"OrderPortal: Account and login pages."

from __future__ import print_function, absolute_import

import logging

import tornado.web

import orderportal
from orderportal import constants
from orderportal import saver
from orderportal import settings
from orderportal import utils
from orderportal.requesthandler import RequestHandler


class AccountSaver(saver.Saver):
    doctype = constants.ACCOUNT

    def set_email(self, email):
        assert self.get('email') is None
        if not email: raise ValueError('no email given')
        if not constants.EMAIL_RX.match(email):
            raise ValueError('invalid email value')
        if len(list(self.db.view('account/email', key=email))) > 0:
            raise ValueError('email already in use')
        self['email'] = email

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


class Accounts(RequestHandler):
    """Accounts list page.
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
            view = self.db.view('account/email', include_docs=True)
            accounts = [r.doc for r in view]
            accounts = [u for u in accounts
                     if u['university'] not in settings['UNIVERSITY_LIST']]
            params['university'] = university
        elif university:
            view = self.db.view('account/university',
                                key=university,
                                include_docs=True)
            accounts = [r.doc for r in view]
            params['university'] = university
        else:
            accounts = None
        role = self.get_argument('role', '')
        if role:
            if accounts is None:
                view = self.db.view('account/role',
                                    key=role,
                                    include_docs=True)
                accounts = [r.doc for r in view]
            else:
                accounts = [u for u in accounts if u['role'] == role]
            params['role'] = role
        status = self.get_argument('status', '')
        if status:
            if accounts is None:
                view = self.db.view('account/status',
                                    key=status,
                                    include_docs=True)
                accounts = [r.doc for r in view]
            else:
                accounts = [u for u in accounts if u['status'] == status]
            params['status'] = status
        if accounts is None:
            view = self.db.view('account/email', include_docs=True)
            accounts = [r.doc for r in view]
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
            accounts.sort(lambda i, j: cmp(i.get('login'), j.get('login')),
                       reverse=descending)
        elif sort == 'name':
            if descending is None: descending = False
            accounts.sort(lambda i, j: cmp((i['last_name'], i['first_name']),
                                        (j['last_name'], j['first_name'])),
                       reverse=descending)
        elif sort == 'email':
            if descending is None: descending = False
            accounts.sort(lambda i, j: cmp(i['email'], j['email']),
                       reverse=descending)
        # Default: name
        else:
            if descending is None: descending = False
            accounts.sort(lambda i, j: cmp((i['last_name'], i['first_name']),
                                        (j['last_name'], j['first_name'])),
                       reverse=descending)
        if sort:
            params['sort'] = sort
        # Page
        page_size = self.current_user.get('page_size') or constants.DEFAULT_PAGE_SIZE
        count = len(accounts)
        max_page = (count - 1) / page_size
        try:
            page = int(self.get_argument('page', 0))
            page = max(0, min(page, max_page))
        except (ValueError, TypeError):
            page = 0
        start = page * page_size
        end = min(start + page_size, count)
        accounts = accounts[start : end]
        params['page'] = page
        #
        self.render('accounts.html',
                    accounts=accounts,
                    params=params,
                    start=start+1,
                    end=end,
                    max_page=max_page,
                    count=count)


class Account(RequestHandler):
    "Account page."

    @tornado.web.authenticated
    def get(self, email):
        account = self.get_account(email)
        self.check_owner_or_staff(account)
        self.render('account.html', account=account, deletable=self.get_deletable(account))

    @tornado.web.authenticated
    def post(self, email):
        self.check_xsrf_cookie()
        if self.get_argument('_http_method', None) == 'delete':
            self.delete(email)
            return
        raise tornado.web.HTTPError(405, reason='POST only allowed for DELETE')

    @tornado.web.authenticated
    def delete(self, email):
        "Delete a account that is pending; to get rid of spam application."
        account = self.get_account(email)
        self.check_admin()
        if not self.get_deletable(account):
            raise tornado.web.HTTPError(403, reason='account cannot be deleted')
        self.delete_logs(account['_id'])
        self.db.delete(account)
        self.see_other('home')

    def get_deletable(self, account):
        "Can the account be deleted? Pending, or disabled and no orders."
        if account['status'] == constants.PENDING: return True
        if account['status'] == constants.ENABLED: return False
        view = self.db.view('order/owner', key=account['email'])
        if len(list(view)) == 0: return True
        return False


class AccountLogs(RequestHandler):
    "Account log entries page."

    @tornado.web.authenticated
    def get(self, email):
        account = self.get_account(email)
        self.check_owner_or_staff(account)
        self.render('logs.html', entity=account, logs=self.get_logs(account['_id']))


class AccountEdit(RequestHandler):
    "Page for editing account information."

    @tornado.web.authenticated
    def get(self, email):
        account = self.get_account(email)
        self.check_owner_or_staff(account)
        self.render('account_edit.html', account=account)

    @tornado.web.authenticated
    def post(self, email):
        self.check_xsrf_cookie()
        account = self.get_account(email)
        self.check_owner_or_staff(account)
        with AccountSaver(doc=account, rqh=self) as saver:
            if self.is_admin():
                role = self.get_argument('role')
                if role not in constants.ACCOUNT_ROLES:
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
            saver['invoice_address'] = \
                self.get_argument('invoice_address', default=None)
            if not saver['invoice_address']:
                try:
                    saver['invoice_address'] = \
                        settings['UNIVERSITIES'][saver['university']]['invoice_address']
                except KeyError:
                    pass
            saver['phone'] = self.get_argument('phone', default=None)
            try:
                value = int(self.get_argument('page_size', 0))
                if value <= 1:
                    raise ValueError
            except (ValueError, TypeError):
                saver['page_size'] = None
            else:
                saver['page_size'] = value
            saver['other_data'] = self.get_argument('other_data', default=None)
        self.see_other('account', email)


class Login(RequestHandler):
    "Login to a account account. Set a secure cookie."

    def post(self):
        "Login to a account account. Set a secure cookie."
        self.check_xsrf_cookie()
        try:
            email = self.get_argument('email')
            password = self.get_argument('password')
        except tornado.web.MissingArgumentError:
            raise tornado.web.HTTPError(403, reason='missing email or password')
        try:
            account = self.get_account(email)
        except tornado.web.HTTPError:
            raise tornado.web.HTTPError(404, reason='no such account')
        if not utils.hashed_password(password) == account.get('password'):
            raise tornado.web.HTTPError(400, reason='invalid password')
        if not account.get('status') == constants.ENABLED:
            raise tornado.web.HTTPError(400, reason='disabled account account')
        self.set_secure_cookie(constants.USER_COOKIE, account['email'])
        with AccountSaver(doc=account, rqh=self) as saver:
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
    "Reset the password of a account account."

    SUBJECT = "The password for your {} portal account has been reset"
    TEXT = """The password for your account {} in the {} portal has been reset.
Please got to {} to set your password.
The code required to set your password is "{}".
"""

    def get(self):
        email = self.current_account and self.current_account.get('email')
        self.render('reset.html', email=email)

    def post(self):
        self.check_xsrf_cookie()
        account = self.get_account(self.get_argument('email'))
        with AccountSaver(doc=account, rqh=self) as saver:
            saver.reset_password()
        url = self.absolute_reverse_url('password',
                                        email=account['email'],
                                        code=account['code'])
        self.send_email(account['email'],
                        self.SUBJECT.format(settings['FACILITY_NAME']),
                        self.TEXT.format(account['email'],
                                         settings['FACILITY_NAME'],
                                         url,
                                         account['code']))
        self.see_other('password')


class Password(RequestHandler):
    "Set the password of a account account; requires a code."

    def get(self):
        self.render('password.html',
                    title='Set your password',
                    email=self.get_argument('email', default=''),
                    code=self.get_argument('code', default=''))

    def post(self):
        self.check_xsrf_cookie()
        account = self.get_account(self.get_argument('email'))
        if account.get('code') != self.get_argument('code'):
            raise tornado.web.HTTPError(400, reason='invalid email or code')
        password = self.get_argument('password')
        if len(password) < constants.MIN_PASSWORD_LENGTH:
            mgs = "password shorter than {} characters".format(
                constants.MIN_PASSWORD_LENGTH)
            raise tornado.web.HTTPError(400, reason=msg)
        if password != self.get_argument('confirm_password'):
            msg = 'password not the same! mistyped'
            raise tornado.web.HTTPError(400, reason=msg)
        with AccountSaver(doc=account, rqh=self) as saver:
            saver.set_password(password)
            saver['login'] = utils.timestamp() # Set login session.
        self.set_secure_cookie(constants.USER_COOKIE, account['email'])
        self.redirect(self.reverse_url('home'))
            

class Register(RequestHandler):
    "Register a new account account."

    def get(self):
        self.render('register.html')

    def post(self):
        self.check_xsrf_cookie()
        with AccountSaver(rqh=self) as saver:
            try:
                email = self.get_argument('email', '')
                saver.set_email(email)
            except ValueError, msg:
                raise tornado.web.HTTPError(400, reason=str(msg))
            try:
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
            saver['invoice_address'] = \
                self.get_argument('invoice_address', default=None)
            if not saver['invoice_address']:
                try:
                    saver['invoice_address'] = \
                        settings['UNIVERSITIES'][saver['university']]['invoice_address']
                except KeyError:
                    pass
            saver['phone'] = self.get_argument('phone', default=None)
            saver['owner'] = email
            saver['role'] = constants.USER
            saver['status'] = constants.PENDING
            saver.erase_password()
        self.see_other('home',
                       message='An activation email will be sent to you'
                       ' from the administrator when your account is enabled.')


class AccountEnable(RequestHandler):
    "Enable the account; from status pending or disabled."

    SUBJECT = "Your {} account has been enabled"
    TEXT = """Your account {} in the {} has been enabled.
Please go to {} to set your password.
"""

    @tornado.web.authenticated
    def post(self, email):
        self.check_xsrf_cookie()
        account = self.get_account(email)
        self.check_admin()
        with AccountSaver(account, rqh=self) as saver:
            saver['status'] = constants.ENABLED
            saver.reset_password()
        url = self.absolute_reverse_url('password',
                                        email=email,
                                        code=account['code'])
        self.send_email(account['email'],
                        self.SUBJECT.format(settings['SITE_NAME']),
                        self.TEXT.format(email, settings['SITE_NAME'], url))
        self.see_other('account', email)


class AccountDisable(RequestHandler):
    "Disable the account; from status pending or enabled."

    @tornado.web.authenticated
    def post(self, email):
        self.check_xsrf_cookie()
        account = self.get_account(email)
        self.check_admin()
        with AccountSaver(account, rqh=self) as saver:
            saver['status'] = constants.DISABLED
            saver.erase_password()
        self.see_other('account', email)
