from gevent import monkey; monkey.patch_socket()
from gevent.pywsgi import WSGIServer 
from gevent import socket, spawn, sleep

from paste.httpserver import serve
from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config

from jobs.subprocess import Popen, PIPE
from datetime import datetime
import logging
import fcntl
import uuid
import os

log = logging.getLogger('job-server')

# GET /jobs > status.json
# PUT /jobs < $task-name > PID/UID
# POST /jobs/$UID/stdin < data
# GET /jobs/$UID/std[out|err] > data
# DELETE /jobs/$UID 

Jobs = dict()

# FIXME flush query param to make sure whole data is feed in stdin
# FIXME streaming
# FIXME communicate() 
# FIXME get for single job

# FIXME interface

# FIXME job status dir
# FIXME detach jobs from server

# FIXME poller to cache stats
# FIXME logger to log output

# FIXME callback
# FIXME retstartable ?
# FIXME arguments to job

class Job(object):

    EXTENSIONS = ('.sh', '.py')

    def __init__(self, name, path):
        self.name = name
        self.path = path
        self.uid = str(uuid.uuid4())
        self.started = None
        self.ended = None
        self.process = None

    @classmethod
    def find_job(cls, name, relative_to):
        for ext in cls.EXTENSIONS:
            path = os.path.join(relative_to, name + ext)

            if os.path.exists(path) and os.access(path, os.X_OK):
                return cls(name, path)

    def start(self):

        def poller():
            self.process = Popen(
                self.path, stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=True
            )

            self.poll()

            self.started = datetime.now()

            while self.running:
                sleep(1)
                self.poll()
                
            self.ended = datetime.now()

        spawn(poller)

    def terminate(self):
        self.process.terminate()

    def kill(self):
        self.process.kill()

    @property
    def stdin(self):
        return self.process.stdin if self.process else None

    @property
    def stdout(self):
        return self.process.stdout if self.process else None

    @property
    def stderr(self):
        return self.process.stderr if self.process else None
        
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

    job = Job.find_job(name, request.registry.settings['jobs_dir'])

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

def read_from_job(request, job, f, key):
    try:
        if 'wait' in request.params:
            socket.wait_read(f.fileno())

        data = os.read(f.fileno(), 8192)
    except OSError, e:
        data = None
        
    return success(**{key: data})

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
    if 'data' not in request.params:
        return error('No data specified')

    data = request.params['data']

    if 'wait' in requet.params:
        socket.wait_write(job.stdin.fileno())

    bytes = os.write(job.stdin.fileno(), (data))

    return success(bytes=bytes)

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
