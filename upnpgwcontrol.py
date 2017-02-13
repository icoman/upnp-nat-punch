#!/usr/bin/env python2


'''
    upnp gateway control

    TCP and UDP hole punching upnp gateways

'''



import re, socket, string
import urlparse, httplib, urllib2
from xml.dom.minidom import parseString, Document



class UpnpGWControl(object):
    def __init__(self):
        self.gateway_ip = None
        self.gateway_port = None
        self.gateway_controlpath = None
        self.myip = None

    def findGateway(self, timeout=3):
        #
        # solution from
        # http://mattscodecave.com/posts/using-python-and-upnp-to-forward-a-port.html
        #
        ret = False
        try:
            SSDP_ADDR = "239.255.255.250"
            SSDP_PORT = 1900
            SSDP_MX = 2
            SSDP_ST = "urn:schemas-upnp-org:device:InternetGatewayDevice:1"

            ssdpRequest = "M-SEARCH * HTTP/1.1\r\n" + \
                            "HOST: %s:%d\r\n" % (SSDP_ADDR, SSDP_PORT) + \
                            "MAN: \"ssdp:discover\"\r\n" + \
                            "MX: %d\r\n" % (SSDP_MX, ) + \
                            "ST: %s\r\n" % (SSDP_ST, ) + "\r\n"

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            sock.sendto(ssdpRequest, (SSDP_ADDR, SSDP_PORT))
            resp = sock.recv(1024)
            #print resp

            parsed = re.findall(r'(?P<name>.*?): (?P<value>.*?)\r\n', resp)
            # get the location header
            location = filter(lambda x: x[0].lower() == "location", parsed)[0][1]
            router_path = urlparse.urlparse(location)
            self.gateway_ip = router_path.hostname
            self.gateway_port = router_path.port

            # get the profile xml file and read it into a variable
            directory = urllib2.urlopen(location).read()

            # create a DOM object that represents the `directory` document
            dom = parseString(directory)

            # find all 'serviceType' elements
            service_types = dom.getElementsByTagName('serviceType')

            # iterate over service_types until we get either WANIPConnection
            # (this should also check for WANPPPConnection, which, if I remember correctly
            # exposed a similar SOAP interface on ADSL routers.
            for service in service_types:
                # I'm using the fact that a 'serviceType' element contains a single text node, who's data can
                # be accessed by the 'data' attribute.
                # When I find the right element, I take a step up into its parent and search for 'controlURL'
                #print "service=",service
                if service.childNodes[0].data.find('WANIPConnection') > 0:
                    self.gateway_controlpath = service.parentNode.getElementsByTagName('controlURL')[0].childNodes[0].data

            #find my ip from LAN of gateway
            if self.gateway_ip:
                prefix = string.join(string.split(self.gateway_ip,'.')[:-1],'.')
                try:
                    import netifaces
                    #pip install netifaces
                    #this works on Linux and Windows
                    for interface in netifaces.interfaces():
                        #print interface
                        d = netifaces.ifaddresses(interface)
                        for i in d.keys():
                            dd = d[i][0]
                            addr = dd.get('addr','')
                            if addr.startswith(prefix):
                                self.myip = addr
                except ImportError:
                    #this works on Windows and not always in Linux
                    hostname, aliaslist, ipaddrlist = socket.gethostbyname_ex(socket.gethostname())
                    for addr in ipaddrlist:
                        if addr.startswith(prefix):
                            self.myip = addr
            ret = True
        except Exception as ex:
            print ex
        return ret

    def upnpRequest(self, function, arguments):
        #
        # solution from
        # http://mattscodecave.com/posts/using-python-and-upnp-to-forward-a-port.html
        #
        doc = Document()

        # create the envelope element and set its attributes
        envelope = doc.createElementNS('', 's:Envelope')
        envelope.setAttribute('xmlns:s', 'http://schemas.xmlsoap.org/soap/envelope/')
        envelope.setAttribute('s:encodingStyle', 'http://schemas.xmlsoap.org/soap/encoding/')

        # create the body element
        body = doc.createElementNS('', 's:Body')

        # create the function element and set its attribute
        fn = doc.createElementNS('', 'u:{}'.format(function))
        fn.setAttribute('xmlns:u', 'urn:schemas-upnp-org:service:WANIPConnection:1')

        # container for created nodes
        argument_list = []

        # iterate over arguments, create nodes, create text nodes,
        # append text nodes to nodes, and finally add the ready product
        # to argument_list
        for k, v in arguments:
            tmp_node = doc.createElement(k)
            tmp_text_node = doc.createTextNode(v)
            tmp_node.appendChild(tmp_text_node)
            argument_list.append(tmp_node)

        # append the prepared argument nodes to the function element
        for arg in argument_list:
            fn.appendChild(arg)

        # append function element to the body element
        body.appendChild(fn)

        # append body element to envelope element
        envelope.appendChild(body)

        # append envelope element to document, making it the root element
        doc.appendChild(envelope)

        # use the object returned by urlparse.urlparse to get the hostname and port
        conn = httplib.HTTPConnection(self.gateway_ip, self.gateway_port)

        # use the path of WANIPConnection (or WANPPPConnection) to target that service,
        # insert the xml payload,
        # add two headers to make tell the server what we're sending exactly.
        conn.request('POST',
            self.gateway_controlpath,
            doc.toxml(),
            {'SOAPAction': '"urn:schemas-upnp-org:service:WANIPConnection:1#{}"'.format(function),
             'Content-Type': 'text/xml'}
        )

        # wait for a response
        resp = conn.getresponse()
        return resp

    def GetExternalIPAddress(self):
        ret = None
        resp = self.upnpRequest('GetExternalIPAddress', [])
        if resp.status == 200:
            data = resp.read()
            dom = parseString(data)
            ret = dom.getElementsByTagName('NewExternalIPAddress')[0].childNodes[0].data
            self.myexternalip = ret
        return ret

    def DeletePortMapping(self, port):
        ret = False
        arguments = [
            ('NewRemoteHost', ''),
            ('NewExternalPort', str(port)),
            ('NewProtocol', 'TCP'),                 # specify protocol
        ]
        resp = self.upnpRequest('DeletePortMapping', arguments)
        if resp.status == 200:
            ret = True
        else:
            data = resp.read()
            dom = parseString(data)
            element = dom.getElementsByTagName('errorDescription')
            if element and element[0].childNodes[0].data == 'NoSuchEntryInArray':
                #ignore error
                ret = True
        return ret

    def AddPortMapping(self, internalPort, externalPort, protocol, description):
        ret = False
        arguments = [
            ('NewExternalPort', str(externalPort)),     # specify port on router
            ('NewProtocol', protocol),                  # specify protocol
            ('NewInternalPort', str(internalPort)),     # specify port on internal host
            ('NewInternalClient', self.myip),           # specify IP of internal host
            ('NewEnabled', '1'),                        # turn mapping ON
            ('NewPortMappingDescription', description), # add a description
            ('NewLeaseDuration', '0'),                  # how long should it be opened?
            ('NewRemoteHost',''),
        ]
        resp = self.upnpRequest('AddPortMapping', arguments)
        if resp.status == 200:
            ret = True
        else:
            #ignore error, return False
            pass
            #data = resp.read()
            #dom = parseString(data)
            #element = dom.getElementsByTagName('errorDescription')
            #if element:
            #    print element[0].childNodes[0].data
            #else:
            #    print "AddPortMapping: Invalid Args"
        return ret

    def GetGenericPortMappingEntry(self, index):
        ret = {}
        arguments = [
            ('NewPortMappingIndex', str(index))
        ]
        resp = self.upnpRequest('GetGenericPortMappingEntry', arguments)
        data = resp.read()
        dom = parseString(data)
        if resp.status == 200:
            #print data
            elements = dom.getElementsByTagName('m:GetGenericPortMappingEntryResponse')
            for i in elements:
                for nn in i.childNodes:
                    if nn.childNodes:
                        ret[nn.nodeName] = nn.childNodes[0].nodeValue
                    else:
                        ret[nn.nodeName] = ''
        else:
            #ignore error, return {}
            pass
            #element = dom.getElementsByTagName('errorDescription')
            #if element:
            #    print element[0].childNodes[0].data
            #else:
            #    print "GetGenericPortMappingEntry: Invalid Args"
        return ret

    def getAllMappings(self):
        index = 0
        while True:
            d = self.GetGenericPortMappingEntry(index)
            if not d:
                #no more mappings
                break
            NewRemoteHost = d['NewRemoteHost']
            if not NewRemoteHost:
                NewRemoteHost = '*'
            print "#{} {} {}:{} -> {}:{} - {}".format(index, d['NewProtocol'], NewRemoteHost, d['NewExternalPort'],
                    d['NewInternalClient'], d['NewInternalPort'], d['NewPortMappingDescription'])
            index += 1

#
# Example module usage:
#
def main():
    '''
        Test module
    '''
    print "Upnp gateway control:"
    gwc = UpnpGWControl()
    if gwc.findGateway():
        print "Gateway ip =", gwc.gateway_ip
        print "Gateway port =", gwc.gateway_port
        print "Gateway path =", gwc.gateway_controlpath
        print "Local ip =", gwc.myip
        gwc.GetExternalIPAddress()
        print "External ip =", gwc.myexternalip
        print "Test port mapping:"
        print "DeletePortMapping 8080:", gwc.DeletePortMapping(8080)
        print "AddPortMapping 8080:", gwc.AddPortMapping(8080,8080,"TCP","Test 8080")
        print "DeletePortMapping 8081:", gwc.DeletePortMapping(8081)
        print "AddPortMapping 8081:", gwc.AddPortMapping(8081,8081,"TCP","Test 8081")
        gwc.getAllMappings()
    else:
        print "Error findGateway"

if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        print ex
    raw_input("Program ends. Press Enter.")

