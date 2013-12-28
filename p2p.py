import db
import time, sys, hashlib, urllib, json, threading, random

def bin_sha256(x):
    return hashlib.sha256(x).digest()

inport = int(sys.argv[1]) if len(sys.argv) >= 2 else 1242
outport = int(sys.argv[2]) if len(sys.argv) >= 3 else 1243

# Every peer is stored with a quality rating, which is an
# exponential moving average of the success rate of
# contacting the peer. We will drop peers with low quality
# rating if we have over 50 peers
peers = { '127.0.0.1:1242': 1 }
load = 0

for key, val in db.db.RangeIter():
    peers[key] = float(val)

import web

urls = (
    '/', 'index'
)

# http://stackoverflow.com/questions/14444913/web-py-specify-address-and-port
class MyApplication(web.application):
    def run(self, port=8080, *middleware):
        func = self.wsgifunc(*middleware)
        return web.httpserver.runsimple(func, ('0.0.0.0', port))

app = MyApplication(urls, globals())

def addpeer(peer):
    if peer not in peers:
        print "Adding peer: "+peer
        peers[peer] = 0.5
    else:
        peers[peer] = peers[peer] * 0.9 + 0.1
    db.db.put(peer,str(peers[peer]))

class index:
    def GET(self):
        params = web.input()
        try: addpeer(web.ctx['ip']+':'+params.myport)
        except: pass
        if params.request == 'peers':
            return json.dumps(peers.keys()) 
        elif params.request == 'getobj':
            try:
                return db.db.Get(params.hash.decode('hex'))
            except:
                return 'not found'
    def POST(self):
        data = web.data()
        try:
            d = db.db.Get(bin_sha256(data))
        except:
            db.db.Put(bin_sha256(data),data)
            # Getting data locally, broadcast it
            if web.ctx['ip'] == '127.0.0.1':
                for peer in peers:
                    urllib.urlopen('http://'+peer,data).read()
            # Getting data from a foreign source, pass it to the outport
            else:
                urllib.urlopen('http://127.0.0.1:'+str(outport),data)
        return 'ok'

def ask_for_peers():
    peer = random.sample(peers,1)[0]
    print "Connecting to peer: "+peer
    try:
        url = 'http://'+peer+'?request=peers&myport='+str(inport)
        his_peers = json.loads(urllib.urlopen(url).read())
        for newpeer in his_peers:
            addpeer(newpeer)
    except:
        peers[peer] = peers[peer] * 0.9 + 0.0
    db.db.Put(peer,str(peers[peer]))
    print "Updating quality of peer: "+peer+" to: "+str(peers[peer])
    # Limit to 50 peers, sorted by quality
    if len(peers) > 50:
        sorted_peers = sorted(peers.keys(),lambda x: -peers[x])
        for x in sorted_peers[50:]:
            print "Deleting excess peer: "+x
            del peers[x]
            db.db.Delete(x)

def loop_ask():
    while 1:
        ask_for_peers()
        time.sleep(10)

threading.Thread(target=loop_ask).start()

if __name__ == "__main__": app.run(port=inport)
