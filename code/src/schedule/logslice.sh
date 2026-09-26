#log slice and backup 
lastday=`/bin/date -d last-day +%Y%m%d`
logsourcedir=/data/contenthub/log
logbackupdir=/data/contenthub/log/backup
tarbackupdir=/data/contenthub/log/tarbackup

fileName=datacleanlog
/bin/cp ${logsourcedir}/${fileName}  ${logbackupdir}/${fileName}$lastday 
/bin/echo '' > ${logsourcedir}/${fileName}

fileName=databackuplog
/bin/cp ${logsourcedir}/${fileName}  ${logbackupdir}/${fileName}$lastday 
/bin/echo '' > ${logsourcedir}/${fileName}

fileName=filecleanlog
/bin/cp ${logsourcedir}/${fileName}  ${logbackupdir}/${fileName}$lastday 
/bin/echo '' > ${logsourcedir}/${fileName}

fileName=transfermysqllog
/bin/cp ${logsourcedir}/${fileName}  ${logbackupdir}/${fileName}$lastday 
/bin/echo '' > ${logsourcedir}/${fileName}

fileName=tencentCOSlog
/bin/cp ${logsourcedir}/${fileName}  ${logbackupdir}/${fileName}$lastday 
/bin/echo '' > ${logsourcedir}/${fileName}

fileName=mysqllog
/bin/cp ${logsourcedir}/${fileName}  ${logbackupdir}/${fileName}$lastday 
/bin/echo '' > ${logsourcedir}/${fileName}

fileName=pymysqllog
/bin/cp ${logsourcedir}/${fileName}  ${logbackupdir}/${fileName}$lastday 
/bin/echo '' > ${logsourcedir}/${fileName}

fileName=recvfileslog
/bin/cp ${logsourcedir}/${fileName}  ${logbackupdir}/${fileName}$lastday 
/bin/echo '' > ${logsourcedir}/${fileName}

fileName=selffilelog
/bin/cp ${logsourcedir}/${fileName}  ${logbackupdir}/${fileName}$lastday 
/bin/echo '' > ${logsourcedir}/${fileName}

fileName=hwinforeporterlog
/bin/cp ${logsourcedir}/${fileName}  ${logbackupdir}/${fileName}$lastday 
/bin/echo '' > ${logsourcedir}/${fileName}

#contenthub 

fileName=chtestlog
/bin/cp ${logsourcedir}/${fileName}  ${logbackupdir}/${fileName}$lastday 
/bin/echo '' > ${logsourcedir}/${fileName}

fileName=chweblog
/bin/cp ${logsourcedir}/${fileName}  ${logbackupdir}/${fileName}$lastday 
/bin/echo '' > ${logsourcedir}/${fileName}


#backup 

cd ${logbackupdir}
backday=`date -d "-7 days" +%Y%m%d`
#tar and backup
tar -czf backup_$backday.tar.gz *$backday *$backday??
mv backup_$backday.tar.gz ${tarbackupdir}
rm -f *$backday *$backday??

cd ${tarbackupdir}
tarRemoveDay=`date -d "-30 days" +%Y%m%d`
rm -f backup_$tarRemoveDay.tar.gz

#remove nginx log
#cd /usr/local/nginx/logs
#/bin/echo '' > access.log
#/bin/echo '' > error.log
