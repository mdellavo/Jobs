from jobs.subprocess import Popen, PIPE

from gevent import socket, spawn, sleep
from gevent.queue import Queue

import os
import uuid
import json

from datetime import datetime

import logging

log = logging.getLogger(__name__)

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

        while self.running:
            sleep(1)
            self.poll()

        self.ended = datetime.now()

        self.poll()

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

            with open(os.path.join(self.run_path, 'status'), 'w') as out:
                out.write(json.dumps(self.to_dict()))
        

            self.last_poll = datetime.now()
    
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
