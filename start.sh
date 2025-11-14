#!/bin/bash
#!/bin/bash
nohup python3 app.py -c config.yaml > /dev/null 2>&1 &
PID=$!
echo $PID > alertmanager-webhook.pid
echo "服务已启动，PID: $PID"

