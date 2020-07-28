from bluesky.callbacks.zmq import RemoteDispatcher

def echo(name, doc):
    print(f'got a {name} document')

d = RemoteDispatcher('127.0.0.1:5678')
d.subscribe(echo)
print("REMOTE IS READY TO START")
d.start()
