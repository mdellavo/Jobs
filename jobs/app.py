from pyramid.view import view_config

from jobs.job import Job

import logging
from operator import itemgetter

log = logging.getLogger(__name__)

# GET /jobs > status.json
# PUT /jobs < $task-name > PID/UID
# POST /jobs/$UID/stdin < data
# GET /jobs/$UID/std[out|err] > data
# DELETE /jobs/$UID 

Jobs = dict()

# FIXME streaming
# FIXME communicate() 
# FIXME top-like stats with psutil
# FIXME long poll for events

# FIXME ui

# FIXME detach jobs from server

# FIXME set logger to run dir

# FIXME callback
# FIXME retstartable ?
# FIXME arguments to job

response = lambda status, **kwargs: dict(status=status, **kwargs)
success = lambda **kwargs: response('ok', **kwargs)
error = lambda msg, **kwargs: response('error', msg=msg, **kwargs)

@view_config(route_name='root', renderer='root.mako')
def root(request):
    return {}

@view_config(route_name='jobs', renderer='json')
def status(request):
    jobs = sorted((job.to_dict() for job in Jobs.values()), 
                  key=itemgetter('started'), reverse=True)
    return success(jobs=jobs)

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
