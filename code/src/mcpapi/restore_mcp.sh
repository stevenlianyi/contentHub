HOME_DIR=/data/contenthubapp
application_sub_dir=/src/mcpapi
application_name='mcp_entry'
application_app='mcp_entry'
application_python=/data/userbin/python3/bin/python3
echo application=$application_name
echo
echo ps aux|grep -E ${application_name}|grep -v grep|awk '{print $2}'|xargs kill -9
ps aux|grep -E ${application_name}|grep -v grep|awk '{print $2}'|xargs kill -9
echo
cd ${HOME_DIR}${application_sub_dir}
echo python $application_name
$application_python $application_app.py &
