# Expose using UPnP a LAN port to WAN or IAN 

Using an ideea from [Matt's Codecave](http://mattscodecave.com/posts/using-python-and-upnp-to-forward-a-port.html) I made a small module to control the router - [blog announcement](http://rainbowheart.ro/526).

The solution works both on Windows and Linux. Use it with caution on private networks: it will expose your redirected ports to anyone from Internet.

On Linux you must install netifaces: **pip install netifaces**, on Windows it works without **netifaces**.

License-free software.
 
Feel free to use this software for both personal and commercial.

A sample webserver in [python](https://www.python.org/) with [bottle py](http://bottlepy.org/) is included into repository.

```python

import os
from upnpgwcontrol import UpnpGWControl

PORT=os.getenv("PORT",8089)
gwc = UpnpGWControl()
if gwc.findGateway(5):
    print "Gateway ip =", gwc.gateway_ip
    print "Local ip =", gwc.myip
    gwc.GetExternalIPAddress()
    print "External ip =", gwc.myexternalip
    gwc.DeletePortMapping(PORT)
    gwc.AddPortMapping(PORT, PORT, "TCP", "Webserver port {}".format(PORT))
    #start server
    print "Start Server, port=",PORT
    ...
	...
else:
    print "Error findGateway"

```
A better sample is included in module.
