PyNNTPProx
===============

The NNTP client is a Python3 standalone.
This is because the python2.7 client has no SSL/STARTTLS support much to my dismay.
This "client" will be responsible for talking to NNTP and dispatching requests for
headers.   My assumption is that it will become its own networked daemon that
can be queries by the core Python2 components that do all the document storage
and indexing.

In general the Python 3 nntplib is more robust and just.. better.
