#!/usr/bin/env python3

## commandline script for controling NNTPClient in interactive mode
import sys
import socket
import logging
import json
import select
import queue
import traceback
import time

from pynntpprox import settings
from pynntpprox.nntp import NNTPClient, ConnectionError


logging.basicConfig(format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)
log.setLevel('DEBUG')


def printgroups(c):
    grps = c.getgroups(prefix='alt.binaries.*')
    for grp in grps:
        sys.stdout.write('%s: (%s, %s)\n' % (grp['group'], grp['first'], grp['last']))

def printgroup(c, group, f, l):
    ovrs = c.getgroup(group, (f, l))
    for article, ovr in ovrs:
        sys.stdout.write('%s\n' % article)
        for k,v in ovr.items():
            sys.stdout.write('\t%s: %s\n' % (k, v))


class Break(Exception):
    pass

if __name__ == '__main__':
    #printgroup(c, 'alt.binaries.teevee', 452267550, 452267563)

    '''
    COMMANDS:
        {'CMD': 'GROUP',
         'ARG': {kwarg dict} }


        Takes Args
        GETGROUPS: returns a list of groups 
            prefix (str)
        GROUP: select a group, returns details about it
            group_name (str)
        GETGROUP: returns a list of articles/messages with short header info
            message_spec (str or list of first/last article ids)
            group_name (str) 
        GETHEADER: gets the entire header, parsed, for a single article
            message_spec (str)
            group_name (str) 

        No Args
        DATE: gets what time the server thinks it is (naieve UTC for now)
             but only because we know that's what we get from usenetserver

    RESPONSES:
        {'RSP': 'OK',
         'ARG': <data> or (str) }
    '''
       

    host = '127.0.0.1' 
    port = 1701
    backlog = 5 
    size = 1024
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
    server.bind((host,port)) 
    server.listen(backlog) 
    server.setblocking(False)
    ## this is equivalent to the # of connections
    ## the NNTP server supports.. 
    MAX_SESSIONS = settings.SERVERS['default']['CONNECTIONS']

    sessions = {}
    inputs = [server]
    outputs = []

    try:
        while inputs: 
            ## check sessions
            #skeys = list(sessions.keys())
            #for s in skeys:
            #    if time.time() - sessions[s]['mod'] > 3 * 60:
            #        log.info('Session timed out: %s' % s)
            #        # Remove message queue
            #        keys = sessions[s].keys()
            #        for k in list(keys):
            #            del sessions[s][k]
            #        del sessions[s]

            readsock, writesock, errorsock = select.select(inputs, outputs, inputs)
            ## Handle inputs
            for s in readsock:
                ## accept
                if s is server:
                    connection, client_address = s.accept()
                    log.debug('Connection from: %s:%s' % client_address)
                    if len(sessions.keys()) >= MAX_SESSIONS:
                        log.info('Max sessions reached')
                        connection.close()
                        continue
                    # Give the connection a queue for data we want to send
                    try:
                        nntpc = NNTPClient(settings.SERVERS['default'])
                        sessions[connection] = {'q': queue.Queue(),
                                                'nntp': nntpc,
                                                'data': b'',
                                                'mod': time.time()}
                    except ConnectionError:
                        log.info('Max NNTP sessions reached')
                        connection.close()
                        continue
                        
                    connection.setblocking(0)
                    inputs.append(connection)

                ## read
                else:

                    ## This is vulnerable to failures "Connection reset by peer"
                    r, w, e = select.select([s], [], [], 0)
                    data = None
                    if r:
                        ## This is vulnerable to failures "Connection reset by peer"
                        data = s.recv(size)
                    else:
                        log.debug('Recv error')

                    if data:
                        # A readable client socket has data
                        cliaddr = '%s:%s' % s.getpeername()
                        log.debug('received %s bytes from %s' % (len(data), cliaddr))
                        sessions[s]['q'].put(data)
                        sessions[s]['mod'] = time.time()
                        # Add output channel for response
                        if s not in outputs:
                            outputs.append(s)
                    else:
                        # Stop listening for input on the connection
                        if s in outputs:
                            outputs.remove(s)
                        inputs.remove(s)
                        log.debug('closing %s for inactivity' % cliaddr) 
                        s.close()
                        keys = sessions[s].keys()
                        for k in list(keys):
                            del sessions[s][k]
                        del sessions[s]

            ## handle output
            for s in writesock:
                ## we removed it earlier..
                if s not in outputs:
                    continue

                ## succeptable to: OSError: [Errno 107] Transport endpoint is not connected
                cliaddr = '%s:%s' % s.getpeername()
                cli_data = None
                try:
                    ## this is echoing... and is where we'll move all the message proc
                    cli_data = sessions[s]['q'].get_nowait()
                    ## could be some, or all of a message
                except queue.Empty:
                    log.debug('message queue for %s is empty' % cliaddr)
                    outputs.remove(s)
                else:
                    sessions[s]['data'] += cli_data

                ## service as many messages in queue for this
                ## client as is available.
                ## PROCESS LOOP
                try:
                    while 1:
                        try:
                            eom = sessions[s]['data'].index(b"\x00")
                        except ValueError:
                            log.debug('All messages from queue serviced.')
                            raise Break('PROCESS LOOP')
                        else:
                            ## partition
                            message = sessions[s]['data'][:eom]
                            try:
                                sessions[s]['data'] = sessions[s]['data'][eom+1:]
                            except IndexError:
                                sessions[s]['data'] = b''

                            ##now we have one raw message.
                            message = message.rstrip(b"\x00").decode('utf-8')
                            log.debug([eom, message])
                            if not len(message):
                                raise Break('PROCESS LOOP')

                            mdata = json.loads(message)
                            cmd = mdata['CMD']
                            arg = mdata.get('ARG', {})
                            log.info('(%s) RECV %s' % (cliaddr, message))

                            ## perform action based on command
                            actions = {
                                    'GETGROUPS': sessions[s]['nntp'].get_groups,
                                    'GROUP': sessions[s]['nntp'].group,
                                    'GETGROUP': sessions[s]['nntp'].get_group,
                                    'GETHEADER': sessions[s]['nntp'].get_header,
                                }
                            try:
                                sdata = {'RSP': 'OK',
                                         'ARG': actions[cmd](**arg)}
                            except KeyError:
                                sdata = {'RSP': 'NO',
                                         'ARG': 'Unknown Command: %s' % cmd}
                            except Exception as e:
                                log.exception(e)
                                sdata = {'RSP': 'NO',
                                         'ARG': 'Unknown Error: %s' % e}

                            ## RESPOND
                            resp = ('%s\x00' % json.dumps(sdata))
                            resp = resp.encode('utf-8')

                            log.info('(%s) SEND %s bytes' % (cliaddr, len(resp)))
                            ## chunk response on agreed upon size..
                            while len(resp):
                                ## probably not efficient..
                                chunk = resp[:size]
                                resp = resp[size:]

                                for i in range(0, 5):
                                    try:
                                        s.send(chunk)
                                    except socket.error as e:
                                        if e.errno == 11:
                                            ## retry send if we get temporarily unavail socket
                                            time.sleep(0.5)
                                            continue
                                        else:
                                            log.error('Send error %s' % e)
                                            if s in inputs:
                                                inputs.remove(s)
                                            outputs.remove(s)
                                            s.close()
                                            # Remove message queue
                                            keys = sessions[s].keys()
                                            for k in list(keys):
                                                del sessions[s][k]
                                            del sessions[s]
                                            ## break loop even tho there is still message to send
                                            raise Break('PROCESS LOOP')
                                    else:
                                        # success
                                        break
                except Break:
                    pass
                            

            # Handle "exceptional conditions"
            for s in errorsock:
                cliaddr = '%s:%s' % s.getpeername()
                log.debug('handling error condition for %s' % cliaddr)
                # Stop listening for input on the connection
                inputs.remove(s)
                if s in outputs:
                    outputs.remove(s)
                s.close()

                # Remove message queue
                keys = sessions[s].keys()
                for k in list(keys):
                    del sessions[s][k]
                del sessions[s]
    except:
        log.debug('Fatal error')
        log.debug(traceback.format_exc())
    finally:
        ## close the entire socket if we broke the main loop
        ## e.g. above here would be some basic signal handling
        log.info('Shutting down...')
        for s in outputs + inputs:
            s.close()
