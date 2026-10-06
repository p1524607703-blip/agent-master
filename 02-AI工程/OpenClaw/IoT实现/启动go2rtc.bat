@echo off
REM 启动 go2rtc v1.9.13 (Windows 原生)
REM 小米C700摄像头 → RTSP/WebRTC/MJPEG 桥接
REM 运行后访问: http://localhost:1984/

echo 启动 go2rtc v1.9.13...
echo 访问: http://localhost:1984/
echo 流地址: rtsp://localhost:8554/xiaomi_cam
echo 截图API: http://localhost:1984/api/frame.jpeg?src=xiaomi_cam
echo.

start "" "%~dp0go2rtc.exe" -config "%~dp0configs\go2rtc.yaml"
timeout /t 2 /nobreak
