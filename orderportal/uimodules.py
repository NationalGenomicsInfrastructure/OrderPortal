" OrderPortal: UI modules. "

from __future__ import unicode_literals, print_function, absolute_import

import couchdb
import markdown
import tornado.web

from . import constants


ICON_TEMPLATE = """<img src="{url}" class="icon" alt="{alt}" title="{title}">"""


class IconMixin(object):

    def get_icon(self, name, title=None, label=False):
        url = self.handler.static_url(name + '.png')
        alt = name.capitalize()
        title = title or alt
        value = ICON_TEMPLATE.format(url=url, alt=alt, title=title)
        if label:
            value += """ <span class="icon">{}</span>""".format(title)
        return value


class Icon(IconMixin, tornado.web.UIModule):
    "HTML for an icon, optionally labelled with a title."

    def render(self, name, title=None, label=False):
        if not name:
            name = 'unknown'
        elif not isinstance(name, basestring):
            name = name[constants.DOCTYPE]
        return self.get_icon(name, title=title, label=label)


class Entity(tornado.web.UIModule):
    "HTML for a link to an entity with an icon."

    def render(self, entity):
        name = entity[constants.DOCTYPE]
        assert name in constants.ENTITIES
        if name == constants.USER:
            icon_url = self.handler.static_url(entity['role'] + '.png')
            title = entity['email']
            alt = entity['role']
            url = self.handler.reverse_url(name, entity['email'])
        elif name == constants.INFO:
            icon_url = self.handler.static_url(name + '.png')
            title = entity.get('title') or entity['name']
            alt = name
            url = self.handler.reverse_url(name, entity['name'])
        else:
            icon_url = self.handler.static_url(name + '.png')
            iuid = entity.get('iuid') or entity['_id']
            title = entity.get('path') or entity.get('title') or iuid
            alt = name.capitalize()
            try:
                url = self.handler.reverse_url(name, iuid)
            except KeyError, msg:
                raise KeyError(str(msg) + ':', name)
        icon = ICON_TEMPLATE.format(url=icon_url, alt=alt, title=alt)
        return """<a href="{url}">{icon} {title}</a>""".format(
            url=url, icon=icon, title=title)


class Markdown(tornado.web.UIModule):
    "Process the document containing markdown content and output."

    def render(self, doc, default=None):
        try:
            text = doc['markdown']
        except KeyError:
            if default:
                text = default
            else:
                return '<i>No markdown text defined.</i>'
        return markdown.markdown(text, output_format='html5')


class Text(tornado.web.UIModule):
    """Fetch text object from the database, process it, and output,
    with an edit button if allowed."""

    def render(self, name, default=None, origin=None):
        if self.handler.is_admin():
            url = self.handler.reverse_url('text', name)
            origin = origin or self.handler.absolute_reverse_url('home')
            result = \
"""<form action="{}"
  role="form" class="pull-right" method="GET">
  <input type="hidden" name="origin" value="{}">
  <button type="submit" class="btn btn-sm btn-default glyphicon glyphicon-edit">
   Edit
  </button>
</form>\n""".format(url, origin)
        else:
            result = ''
        try:
            doc = self.handler.get_entity_view('text/name', name)
            text = doc['markdown']
        except (tornado.web.HTTPError, KeyError):
            if default:
                text = default
            else:
                result += "<i>No text '{}' defined.</i>".format(name)
        else:
            result += markdown.markdown(text, output_format='html5')
        return result
