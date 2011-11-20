$(document).ready(function() {

    var job_template = tiger($('#job').text());
   
    function add_job(job) {
        var html = job_template.render({'job': job});
        $('#jobs').append(html);        
    }

    function update_jobs() {

        $.getJSON('/jobs', function(obj) {
            if(obj.status == 'ok') {
                $('#jobs').html('');

                for(var i=0; i<obj.jobs.length; i++) 
                    add_job(obj.jobs[i]);

            } else if(obj.status == 'error') {
                window.alert(obj.msg);
            }
            
        });
    } 

    window.setInterval(update_jobs, 1000);

    $('#start-job').submit(function() {
        $.ajax({
            url: this.action,
            type: this.method,
            context: this,
            data: $(this).serialize(),
            dataType: 'json',
            success: function(obj) {
                add_job(obj.job);
            },
            error: function() {
                window.alert('Error!')
            }
        });

        return false;
    });


    $('.stop-job input').live('click', function() {
        var form = this.form;
        
        $.ajax({
            url: form.action,
            type: form.method,
            context: form,
            data: $(form).serialize(),
            dataType: 'json',
            success: function(obj) {
                $('#' + obj.job.uid).remove();
                add_job(obj.job);
            },
            error: function() {
                window.alert('Error!')
            }
        });

        return false;
    });

});

