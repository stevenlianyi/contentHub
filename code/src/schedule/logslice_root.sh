#log slice and backup 2022/6/16
lastday=`/bin/date -d last-day +%Y%m%d`
logsourcedir=/data/museum/log
logbackupdir=/data/museum/log/backup
tarbackupdir=/data/museum/log/tarbackup

#remove nginx log
cd /usr/local/nginx/logs
/bin/echo '' > access.log
/bin/echo '' > error.log
