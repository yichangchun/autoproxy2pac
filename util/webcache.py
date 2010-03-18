# -*- coding: utf-8 -*-

from calendar import timegm
from datetime import datetime
from email.utils import formatdate
from functools import wraps
from hashlib import md5
from types import MethodType

class _ResponseNotModified(Exception):
    pass

def _lastModified(handler, time):
    if isinstance(time, datetime):
        time = formatdate(timegm(time.timetuple()), False, True)
    handler.response.headers['Last-Modified'] = time

    if _validate(handler): raise _ResponseNotModified

def _validate(handler):
    '''
    Validate client cache. Last-Modified and/or ETag headers should be set.

    @return: True if the page is cached (no need to generate the content)
    '''
    if handler.response.status != 200: return False

    # @see: http://tools.ietf.org/html/rfc2616#section-14.25
    ims = handler.request.headers.get('If-Modified-Since')
    if ims:
        lm = handler.response.headers.get('Last-Modified')
        if lm is None or ims != lm: return False

    # @see: http://tools.ietf.org/html/rfc2616#section-14.26
    inm = (t.strip('" ') for t in handler.request.headers.get('If-None-Match', '').split(','))
    if inm:
        et = handler.response.headers.get('ETag', '').strip('"')
        if not et or not (et in inm or '*' in inm): return False

    if ims or inm:
        # @see: http://tools.ietf.org/html/rfc2616#section-10.3.5
        handler.error(304)
        del handler.response.headers['Last-Modified']
        return True
    else:
        return False

class webcached(object):
    '''
    Decorator to enable conditional get. Add a lastModified method to the handler
    '''
    def __init__(self, cacheCtrl='no-cache', genEtag=True):
        self.cacheCtrl = cacheCtrl
        self.genEtag = genEtag

    def __call__(self, f):
        @wraps(f)
        def wrapped(handler, *args):
            handler.lastModified = MethodType(_lastModified, handler, handler.__class__)

            try:
                f(handler, *args)
            except _ResponseNotModified:
                handler.response.headers['Cache-Control'] = self.cacheCtrl
                return

            if handler.response.status == 200:
                handler.response.headers['Cache-Control'] = self.cacheCtrl
                if self.genEtag and handler.response.headers.get('ETag') is None:
                    body = handler.response.out.getvalue()
                    if isinstance(body, unicode): body = body.encode('utf-8')
                    handler.response.headers['ETag'] = '"' + md5(body).hexdigest() + '"'
                _validate(handler)
            else:
                del handler.response.headers['Last-Modified']
                del handler.response.headers['ETag']

        return wrapped
