from paste.httpserver import serve
from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config

import logging
from subprocess import Popen, PIPE
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

    return success(uid=uid, name=name)

@view_config(route_name='job', renderer='json', request_method='DELETE')
def stop_job(request):
    return None

@view_config(route_name='job', renderer='json', request_method='GET')
def read_from_job(request):
    return None

@view_config(route_name='job', renderer='json', request_method='POST')
def write_to_job(request):
    return None

def main(global_config, **settings):

    config = Configurator(settings=settings)
    config.add_route('jobs', '/jobs')
    config.add_route('job', '/jobs/{uid}')

    config.scan()

    return config.make_wsgi_app()
