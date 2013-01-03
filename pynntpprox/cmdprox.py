#!/usr/bin/env python3

## commandline script for controling NNTPClient in interactive mode
import sys

from pynntpprox import settings
from pynntpprox.nntp import NNTPClient



def printgroups(c):
    grps = c.get_group(prefix='alt.binaries.*')
    for grp in grps:
        sys.stdout.write('%s: (%s, %s)\n' % (grp['group'], grp['first'], grp['last']))

def printgroup(c, group, f, l):
    ovrs = c.get_group((f, l), group)
    for article, ovr in ovrs:
        sys.stdout.write('%s\n' % article)
        for k,v in ovr.items():
            sys.stdout.write('\t%s: %s\n' % (k, v))

if __name__ == '__main__':
    c = NNTPClient(settings.SERVERS['default'])
    #printgroups(c)
    #printgroup(c, 'alt.binaries.teevee', 332010131, 452267563)
    #printgroup(c, 'alt.binaries.teevee', 452267550, 452267563)

    articles = c.get_group((452267550, 452267563), 'alt.binaries.teevee')
    for aid, short_headers in articles:
        mid = short_headers.get('message-id', None)
        h = c.get_header(mid)

        print(h)
        break
