A Simple RESTful Job Management Server 

- Get a info about jobs

  GET /jobs -> list of job statuses
  GET /jobs/$uid -> job status

- Start a new job

  PUT /jobs name=$job -> job status

- Feed Input to job

  POST /jobs/$UID/stdin < data -> bytes written

- Read output from job

  GET /jobs/$UID/std[out|err] > data

- Terminate job

  DELETE /jobs/$UID -> kill job


A basic UI is available at /
