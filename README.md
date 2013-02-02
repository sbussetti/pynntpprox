PyNNTPProx
===============

The NNTP client is a Python3 standalone.
This is because the python2.7 client has no SSL/STARTTLS support much to my dismay.
This "client" will be responsible for talking to NNTP and dispatching requests for
headers.   My assumption is that it will become its own networked daemon that
can be queries by the core Python2 components that do all the document storage
and indexing.

In general the Python 3 nntplib is more robust and just.. better.


Communication
--------------
Although this obviously limits portability, currently the interchange format is simply dictionaries serialized by pickle.  While configurable, the default is to use the 2/3 compatible protocol 2.  This choice provides much faster (de)serialization as well as simplified unicode handling.

Commands
--------------
All commands take the format of:
{"CMD": <command name>, "ARG": <arguments for command>}

GETGROUPS: get a list of the groups on your server

GROUP: get data about a particular group. as a side effect this acts the same as the NNTP GROUP command, which sets "state" for other commands to be in the context of this group.

GETGROUP: get short-form headers for the given group

GETHEADER: get long-form headers for the given article
