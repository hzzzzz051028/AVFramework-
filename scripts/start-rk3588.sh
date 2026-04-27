#!/bin/bash
# RK3588 投屏器启动脚本 (带保底方案)

INSTALL_DIR="/opt/screencast"
LOG_DIR="/var/log/screencast"
PID_FILE="/var/run/screencast.pid"

# 创建日志目录
mkdir -p $LOG_DIR

# 启动函数
start_service() {
    echo "启动投屏服务..."

    cd $INSTALL_DIR/backend

    # 导出环境变量
    export PYTHONUNBUFFERED=1
    export GST_DEBUG=2
    export GST_PLUGIN_SCANNER=/usr/lib/aarch64-linux-gnu/gstreamer-1.0/gst-plugin-scanner

    # 启动服务
    /usr/bin/python3 server.py >> $LOG_DIR/screencast.log 2>&1 &
    echo $! > $PID_FILE

    echo "服务已启动，PID: $(cat $PID_FILE)"
    echo "日志文件: $LOG_DIR/screencast.log"
}

# 停止函数
stop_service() {
    if [ -f $PID_FILE ]; then
        PID=$(cat $PID_FILE)
        echo "停止服务 (PID: $PID)..."
        kill $PID 2>/dev/null || true
        rm -f $PID_FILE
        echo "服务已停止"
    else
        echo "服务未运行"
    fi
}

# 状态检查
check_status() {
    if [ -f $PID_FILE ]; then
        PID=$(cat $PID_FILE)
        if ps -p $PID > /dev/null 2>&1; then
            echo "服务运行中，PID: $PID"
            return 0
        else
            echo "PID 文件存在但进程未运行"
            rm -f $PID_FILE
            return 1
        fi
    else
        echo "服务未运行"
        return 1
    fi
}

# 主逻辑
case "$1" in
    start)
        if check_status; then
            echo "服务已在运行"
            exit 0
        fi
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        stop_service
        sleep 2
        start_service
        ;;
    status)
        check_status
        ;;
    logs)
        tail -f $LOG_DIR/screencast.log
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac
