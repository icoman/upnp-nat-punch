#!/usr/bin/env python2

'''
    Simple bottle webserver
'''

from bottle import request, route, run
import os, datetime
from upnpgwcontrol import UpnpGWControl

cnt = 0

@route('/')
def callback():
    global cnt
    cnt += 1
    now = datetime.datetime.now().strftime("%d %b %Y %H:%M.%S")
    title = "My webserver"
    REMOTE_ADDR = request.environ.get('REMOTE_ADDR','unknown')
    return '''
<html>
<head>
<META HTTP-EQUIV="REFRESH" CONTENT="1;URL=/">
<title>{}</title>
</head>
<body>
<h1>cnt = {}<br>
Date: {}<br>
REMOTE_ADDR: {}
</h1>
</body></html>'''.format(title, cnt, now, REMOTE_ADDR)



if __name__ == "__main__":
    '''
        Main function
    '''
    PORT=os.getenv("PORT",8089)
    HOST=''
    if not os.environ.get('BOTTLE_CHILD',None):
        #main task
        #upnp NAT puch
        gwc = UpnpGWControl()
        if gwc.findGateway(5):
            print "Gateway ip =", gwc.gateway_ip
            print "Local ip =", gwc.myip
            gwc.GetExternalIPAddress()
            print "External ip =", gwc.myexternalip
            gwc.DeletePortMapping(PORT)
            gwc.AddPortMapping(PORT, PORT, "TCP", "Webserver port {}".format(PORT))
        #start webserver
        print "Start Server, port=",PORT
    else:
        #child task restarted when data changed
        print "Restart server."
    run(host=HOST, port=PORT, debug=True, reloader=True)

