# helper module for talking to nntp
import logging
import nntplib
import datetime
from collections import OrderedDict
import traceback


logging.basicConfig(format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)
log.setLevel('INFO')


class ConnectionError(Exception):
    pass


    

class NNTPClient(object):
    def __init__(self, config={}):
        # connection config
        self._conf = self._getconf(config)
        # client
        self._cli = None
        # servertime offset
        self._timedelta = None
        # currently selected group
        self._group = None
        # server capabilities (also inits connection)
        self._caps = self.cli.getcapabilities()

    def __del__(self):
        self._disconnect()

    def _connect(self):
        cli = None
        log.info('Connecting to NNTP server')
        if self._conf['SECURE'] == 'STARTTLS':
            try:
                log.debug('NNTP conn')
                cli = nntplib.NNTP(self._conf['HOST'], usenetrc=False)
                log.debug('starttls')
                cli.starttls()
                log.debug('login')
                cli.login(user=self._conf['USER'], password=self._conf['PASS'],
                            usenetrc=False)

                return cli
            except nntplib.NNTPError:
                log.debug('STARTTLS failed')
                log.debug(traceback.format_exc())
                raise ConnectionError

        elif self._conf['SECURE'] == 'SSL':
            ## fallback
            try:
                log.debug('Fail to SSL on 563')
                port = self._conf['PORT'] if self._conf['PORT'] else 563
                cli = nntplib.NNTP_SSL(self._conf['HOST'], port=port,
                                        user=self._conf['USER'],
                                        password=self._conf['PASS'],
                                        usenetrc=False)
                return cli
            except nntplib.NNTPPermanentError:
                log.debug('SSL failed')
                log.debug(traceback.format_exc())
                raise ConnectionError

        else:
            raise Exception('No insecure connections yet')

    def _disconnect(self):
        log.info('Disconnecting from NNTP server')
        if self._cli:
            try:
                self._cli.quit()
            except (BrokenPipeError, EOFError):
                ## if it's dead, it's dead
                pass

    @property
    def cli(self):
        ## retries and all shall go here..
        if not self._cli:
            self._cli = self._connect()

        return self._cli

    @classmethod
    def _getconf(kls, config):
        nc = {}
        ##TODO replace this bs w/ conf obj and getattr
        for c in ['HOST', 'PORT', 'USER', 'PASS', 'SECURE', 'CONNECTIONS', 'RETENTION']:
            nc[c] = config.get(c, None)
        return nc

    def date(self, date=None):
        ## this is TZ naive currently and only figures the offset...
        ## and I do this because the date object that comes back
        ## from the server is also TZ naive... .. if we got
        ## a localtime with TZ we could naive-itze it and move on..        

        ## gets serverdate and converts it so that it reconsiles
        ## with the current date,
        ## or if a date is supplied, performs the reverse (for passing
        ## to nntlib functions that accept a date...)
        if date is None or self._timedelta is None:
            resp, sd = self.cli.date()

        if self._timedelta is None:
            ld = datetime.datetime.now()
            self._timedelta = sd - ld

        if date is None:
            return sd + self._timedelta
        else:
            return date - self._timedelta

    def get_groups(self, prefix=None):
        ## groups are converted to dicts with keys:
        ## group: full groupname
        ## first: first article
        ## last: last article
        ## flag: NNTP defined flag
        ##TODO: expand "redirects":
        ## flag: =foo.bar: Articles are filed in the foo.bar group instead.
        resp, groups = self.cli.list(prefix)
        return tuple([g._asdict() for g in groups])

    def group(self, group_name=None):
        ## if group name provided, select the current group
        ## either way return the current group data
        if group_name is not None:
            resp, c, f, l, n = self.cli.group(group_name)
            self._group = OrderedDict([
                                        ('count', c),
                                        ('first', f),
                                        ('last', l),
                                        ('group', n)
                                    ])
            v = tuple(self._group.values())
            log.debug('Set group: %s %s %s %s' % v)
        return self._group

    def get_group(self, message_spec, group_name=None):
        ## because we need to fully decode the header
        ## in python3 land, we're dealing with
        ## loading the entire thing to mem..
        ##
        ## if you need to know the # of articles
        ## get it from the currently selected group
        ##
        ## selects the current group and
        ## returns a list of headers as specified
        ## by the message_spec arg.
        ## per NNTP, message_spec is either, a message_id
        ## or otherwise a (first, last) tuple of
        ## article ids
        if group_name is not None:
            self.group(group_name)

        if isinstance(message_spec, (tuple, list)) and not self._group:
            raise Exception('Article ids supplied without group name')

        resp, overviews = self.cli.over(message_spec)
      
        log.debug(len(overviews))
        h = [] 
        for article_id, ovr in overviews:
            d = {}
            log.debug(u'BEFORE %s' % ovr['subject'])
            for k, v in ovr.items():
                ## (some) short headers from grouplists have these colon
                ## prefixes for no aparrent reason (they're not in the 
                ## raw headers).  We do this so that the response of
                ## short and long headers properly intersect (and breaks
                ## the general rule of not touching the data as much as possible)
                k = k.lstrip(':')
                d[k] = nntplib.decode_header(v)
            log.debug('AFTER %s' % d['subject'])
            h.append((article_id, d))
        return h

    def get_header(self, message_spec, group_name=None):
        if group_name is not None:
            self.group(group_name)

        if (not isinstance(message_spec, str) or not message_spec.startswith('<')) and not self._group:
            raise Exception('Article id supplied without group name')

        ## class ArticleInfo
        resp, header = self.cli.head(message_spec)
        h = {}
        for line in header.lines:
            line = line.decode(self.cli.encoding, errors=self.cli.errors)
            k, v = line.split(':', 1)
            v = nntplib.decode_header(v)
            h[k.lower()] = v.strip()
        return h

    @staticmethod
    def _parse_header(tokens):
        fields = {}
        for i, token in enumerate(tokens):
            if i >= len(fmt):
                # XXX should we raise an error? Some servers might not
                # support LIST OVERVIEW.FMT and still return additional
                # headers.
                continue
            field_name = fmt[i]
            if i >= n_defaults and not is_metadata:
                # Non-default header names are included in full in the response
                # (unless the field is totally empty)
                h = field_name + ": "
                if token and token[:len(h)].lower() != h:
                    raise nntplib.NNTPDataError("HEAD response doesn't include "
                                                "names of additional headers")
                token = token[len(h):] if token else None
            fields[fmt[i]] = token
        return fields

    def get_body(self, message_spec, group_name=None):
        raise NotImplemented

        if group_name is not None:
            self.group(group_name)

        if (not isinstance(message_spec, str) or not message_spec.startswith('<')) and not self._group:
            raise Exception('Article id supplied without group name')

        resp, body = self.cli.body(message_spec)


    def get_article(self, message_spec, group_name=None):
        raise NotImplemented

        if group_name is not None:
            self.group(group_name)

        if (not isinstance(message_spec, str) or not message_spec.startswith('<')) and not self._group:
            raise Exception('Article id supplied without group name')

        resp, info = self.cli.article(message_spec)
        info.lines

