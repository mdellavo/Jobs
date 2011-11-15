from paste.httpserver import serve
from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config

import logging
from subprocess import Popen, PIPE
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

EXTENSIONS = ('.sh', '.py')

next_job_uid = lambda: str(uuid.uuid4())
job_path = lambda settings, name: os.path.join(settings['jobs_dir'], name)
is_job = lambda path: os.path.exists(path) and os.access(path, os.X_OK)

def find_job(settings, name):
    for ext in EXTENSIONS:
        path = job_path(settings, name + ext)
        if is_job(path):
            return path

def job(uid):
    j = Jobs[uid]
    j.poll()

    return { 
        'uid': uid, 
        'pid': j.pid,
        'running': j.returncode is None,
        'returncode': j.returncode 
    }

response = lambda status, **kwargs: dict(status=status, **kwargs)
success = lambda **kwargs: response('ok', **kwargs)
error = lambda msg, **kwargs: response('error', msg=msg, **kwargs)

@view_config(route_name='jobs', renderer='json')
def status(request):
    return success(jobs=dict((j, job(j)) for j in Jobs))

def set_nonblocking(f):
    fd = f.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

@view_config(route_name='jobs', renderer='json', request_method='PUT')
def start_job(request):
    if 'name' not in request.POST:
        return error('No job name specified')

    name = request.POST['name']

    if not name:
        return error('Bad job name')

    path = find_job(request.registry.settings, name)

    if not is_job(path):
        return error('Unknown job')

    uid = next_job_uid()

    Jobs[uid] = Popen(path, stdin=PIPE, stdout=PIPE, stderr=PIPE, 
                      close_fds=True)
    set_nonblocking(Jobs[uid].stdout)
    set_nonblocking(Jobs[uid].stderr)
    
    return success(uid=uid, name=name)

def validate_job_uid(func):
    def _validate_job_uid(request):
        
        if 'uid' not in request.matchdict:
            return error('No UID specified')

        uid = request.matchdict['uid']
        
        if uid not in Jobs:
            return error('Unknown UID')

        return func(request, uid, Jobs[uid])

    return _validate_job_uid

@view_config(route_name='job', renderer='json', request_method='DELETE')
@validate_job_uid
def stop_job(request, uid, job):
    if request.POST.get('kill') == '1':
        job.kill()
    else:
        job.terminate()

    return success()

def read_from_job(request, uid, job, f, key):
    return success(**{key: f.read()})

@view_config(route_name='job-stdout', renderer='json', request_method='GET')
@validate_job_uid
def read_from_stdout(request, uid, job):
    return read_from_job(request, uid, job, job.stdout, 'stdout')

@view_config(route_name='job-stderr', renderer='json', request_method='GET')
@validate_job_uid
def read_from_stdout(request, uid, job):
    return read_from_job(request, uid, job, job.stderr, 'stderr')

@view_config(route_name='job', renderer='json', request_method='POST')
@validate_job_uid
def write_to_job(request, uid, job):
    return None

def main(global_config, **settings):

    config = Configurator(settings=settings)
    config.add_route('jobs', '/jobs')
    config.add_route('job', '/jobs/{uid}')
    config.add_route('job-stdout', '/jobs/{uid}/stdout')
    config.add_route('job-stderr', '/jobs/{uid}/stderr')

    config.scan()

    return config.make_wsgi_app()
