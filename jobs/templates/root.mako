<!DOCTYPE html>
<html>
  <head> 
    <title>Jobs Admin</title>

    <link rel="stylesheet" href="/static/css/blueprint/screen.css" type="text/css" media="screen, projection"/>
    <link rel="stylesheet" href="/static/css/blueprint/print.css" type="text/css" media="print"/> 
    <!--[if lt IE 8]>
    <link rel="stylesheet" href="/static/css/blueprint/ie.css" type="text/css" media="screen, projection"/>
    <![endif]-->
    <link rel="stylesheet" href="/static/css/blueprint/buttons.css" type="text/css" media="screen, projection"/> 
    <link rel="stylesheet" href="/static/css/base.css" type="text/css" media="screen, projection"/> 

    <script 
       type="text/javascript"
       src="http://code.jquery.com/jquery-1.7.min.js"></script>

    <script type="text/javascript" src="/static/js/tiger.js"></script>
    <script type="text/javascript" src="/static/js/jobs.js"></script>

  </head>
  <body>
    <div class="container">

      <div id="header">
        <h1>Jobs</h1>
      </div>

      <fieldset>
        <legend>Start a Job</legend>

        <form id="start-job" method="PUT" action="/jobs">
          <input type="text" name="name" />
          <button type="submit">
            <img src="/static/img/icons/add.png"/>
            <span>Start</span>
          </button>
        </form>      
      </fieldset>
        
      <div class="header">
        <div class="span-2">Name</div>
        <div class="span-7">UID</div>
        <div class="span-2">Running</div>
        <div class="span-4">Started</div>
        <div class="span-4">Ended</div>
        <div class="span-2">Exit Code</div>
        <div class="span-3 last">Actions</div>
      </div>
      <div id="jobs">
      </div>

    </div>

    <%text>
    <script type="text/tiger" id="job">
      <div class="job clear" id="${job.uid}">
        <div class="span-2">
          ${job.name}
        </div>
        <div class="span-7">
          ${job.uid}
        </div>
        <div class="span-2">${job.running ? 'Yes' : 'No'}</div>
        <div class="span-4">${job.started}</div>         
        <div class="span-4">${job.ended ? job.ended : '-'}</div>
        <div class="span-2">${job.return_code !== null ? '' + job.return_code : '-'}</div>
        <div class="span-3 last">
          
          %if(job.running)
          <form class="stop-job" method="DELETE" action="/jobs/${job.uid}">
            <input type="image" src="/static/img/icons/delete.png"/>
          </form>      
          %endif

        </div>
      </div>
    </script>
    </%text>
  </body>
</html>
