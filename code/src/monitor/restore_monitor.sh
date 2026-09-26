# contentHub 运维监控守护启动脚本(由 museum/code/src/monitor/restore_monitor.sh 迁移并改造为 contentHub 口径)
#
# ★ 说明:
#   - 本脚本为 **Linux 部署样例**(Windows 请用 code/src/tools/runOpsJobs.ps1 + 计划任务);
#   - 仅负责「重启文件变化守护」; 进程 kill 为**部署层面的 shell 操作**, python 侧 monitor.py
#     已按 contentHub 零网络红线剥离进程原语(不再自动 kill 业务进程);
#   - 七项指标监控请配合 chmonitor/dailyCheck.py(见 crontab.txt)。

echo restore_monitor.sh
HOME_DIR=/data/contenthub
application_name='monitor.py'
cd ${HOME_DIR}/src/monitor
#重启守护前先结束既有 monitor.py(Linux 部署层面操作)
ps aux | grep -E ${application_name} | grep -v grep | awk '{print $2}' | xargs kill
python3 ${application_name}
