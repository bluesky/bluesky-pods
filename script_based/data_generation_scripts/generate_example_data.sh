qserver -c environment_open
qserver -c queue_plan_add -p '{"name":"count", "args":[["det1", "det2"]]}'
qserver -c queue_plan_add -p '{"name":"scan", "args":[["det1", "det2"], "motor", -1, 1, 10]}'
qserver -c queue_start
# TODO Any way to wait until the queue is empty and then close the environment?
