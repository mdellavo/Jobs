from gevent import monkey; monkey.patch_socket()
from gevent.pywsgi import WSGIServer 
from gevent import socket, spawn, sleep
from gevent.queue import Queue

from paste.httpserver import serve
from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config

from jobs.subprocess import Popen, PIPE
from datetime import datetime
import logging
import fcntl
import uuid
import json
import os

log = logging.getLogger('job-server')

# GET /jobs > status.json
# PUT /jobs < $task-name > PID/UID
# POST /jobs/$UID/stdin < data
# GET /jobs/$UID/std[out|err] > data
# DELETE /jobs/$UID 

Jobs = dict()

# FIXME streaming
# FIXME communicate() 
# FIXME top-like stats

# FIXME ui

# FIXME detach jobs from server

# FIXME set logger to run dir

# FIXME callback
# FIXME retstartable ?
# FIXME arguments to job

class Job(object):

    EXTENSIONS = ('.sh', '.py')

    def __init__(self, name, path, run_path):
        self.name = name
        self.path = path
        self.uid = str(uuid.uuid4())
        self.started = None
        self.ended = None
        self.last_poll = None
        self.process = None

        self.stdin = Queue()
        self.stdout = Queue()
        self.stderr = Queue()

        self.run_path = os.path.join(run_path, self.uid)
        os.makedirs(self.run_path)

    @classmethod
    def find_job(cls, name, relative_to, run_dir):
        for ext in cls.EXTENSIONS:
            path = os.path.join(relative_to, name + ext)

            if os.path.exists(path) and os.access(path, os.X_OK):
                return cls(name, path, run_dir)

    def poller(self):
        self.process = Popen(
            self.path, stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=True
        )

        self.poll()        
        self.started = datetime.now()

        spawn(self.reader, self.process.stdout, self.stdout, 'stdout')
        spawn(self.reader, self.process.stderr, self.stderr, 'stderr')
        spawn(self.writer, self.process.stdin, self.stdin)

        def log_status():
            with open(os.path.join(self.run_path, 'status'), 'w') as out:
                out.write(json.dumps(self.to_dict()))
        
        while self.running:
            sleep(1)
            self.poll()
            self.last_poll = datetime.now()
            log_status()

        self.ended = datetime.now()

        log_status()

    def reader(self, f, queue, key):
        fd = f.fileno()

        while self.running:
            try:
                socket.wait_read(fd)
                data = os.read(fd, 8192)

                with open(os.path.join(self.run_path, key), 'a') as out:
                    out.write(data)
                    
                queue.put(data)
            except OSError, e:
                break
        
    def writer(self, f, queue):
        fd = f.fileno()

        while self.running:
            data = queue.get()

            total = len(data)
            while total > 0:
                socket.wait_write(fd)
                total -= os.write(fd, data)
                            
    def start(self):
        spawn(self.poller)

    def terminate(self):
        self.process.terminate()

    def kill(self):
        self.process.kill()

    @property
    def pid(self):
        return self.process.pid if self.process else None

    @property
    def running(self):
        return self.process and self.process.returncode is None

    @property
    def return_code(self):
        return self.process.returncode if self.process else None

    def poll(self):
        if self.process:
            self.process.poll()
    
    def wait(self):
        if self.process:
            self.process.wait()

    def to_dict(self):

        fmt_dt = lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if x else None

        return {
            'name': self.name,
            'started': fmt_dt(self.started),
            'ended': fmt_dt(self.ended),
            'last_poll': fmt_dt(self.last_poll),
            'path': self.path,
            'uid': self.uid, 
            'pid': self.pid,
            'running': self.running,
            'return_code': self.return_code
        }

response = lambda status, **kwargs: dict(status=status, **kwargs)
success = lambda **kwargs: response('ok', **kwargs)
error = lambda msg, **kwargs: response('error', msg=msg, **kwargs)

@view_config(route_name='jobs', renderer='json')
def status(request):
    return success(jobs=[job.to_dict() for job in Jobs.values()])

@view_config(route_name='jobs', renderer='json', request_method='PUT')
def start_job(request):
    if 'name' not in request.params:
        return error('No job name specified')

    name = request.params['name']

    if not name:
        return error('Bad job name')

    job = Job.find_job(name,
                       request.registry.settings['jobs_dir'], 
                       request.registry.settings['run_dir'])

    if not job:
        return error('Unknown job')
    
    job.start()
    Jobs[job.uid] = job

    return success(job=job.to_dict())

def validate_job_uid(func):
    def _validate_job_uid(request):
        
        if 'uid' not in request.matchdict:
            return error('No UID specified')

        uid = request.matchdict['uid']
        
        if uid not in Jobs:
            return error('Unknown UID')

        return func(request, Jobs[uid])

    return _validate_job_uid

@view_config(route_name='job', renderer='json')
@validate_job_uid
def job_status(request, job):
    return success(job=job.to_dict())

@view_config(route_name='job', renderer='json', request_method='DELETE')
@validate_job_uid
def stop_job(request, job):
    if 'kill' in request.params:
        job.kill()
    else:
        job.terminate()

    if 'wait' in request.params:
        job.wait()

    return success(job=job.to_dict())

def read_from_job(request, job, queue, key):
    block = 'wait' in request.params

    if not self.running and queue.qsize == 0:
        return error('No more data')

    data = []
    while queue.qsize() > 0:
        data.append(queue.get(block))

    return success(**{key: ''.join(data)})

@view_config(route_name='job-stdout', renderer='json', request_method='GET')
@validate_job_uid
def read_from_stdout(request, job):
    return read_from_job(request, job, job.stdout, 'stdout')

@view_config(route_name='job-stderr', renderer='json', request_method='GET')
@validate_job_uid
def read_from_stder(request, job):
    return read_from_job(request, job, job.stderr, 'stderr')

@view_config(route_name='job-stdin', renderer='json', request_method='POST')
@validate_job_uid
def write_to_job(request, job):

    if not self.running:
        return error('Job has ended')

    if 'data' not in request.params:
        return error('No data specified')

    data = request.params['data']
    block = 'wait' in requet.params
    job.stdin.put(data, block)
    return success()

def main(global_config, **settings):
    config = Configurator(settings=settings)
    config.add_route('jobs', '/jobs')
    config.add_route('job', '/jobs/{uid}')
    config.add_route('job-stdout', '/jobs/{uid}/stdout')
    config.add_route('job-stderr', '/jobs/{uid}/stderr')
    config.add_route('job-stdin', '/jobs/{uid}/stdin')

    config.scan()

    return config.make_wsgi_app()

def server_runner(app, global_conf, host, port, spawn='default', **kwargs): 
    WSGIServer((host, int(port)), app).serve_forever()
