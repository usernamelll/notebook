@echo off
chcp 65001 >nul 2>&1  :: 切换到UTF-8编码模式（解决控制台显示乱码）
echo 正在执行git add . ...
git add .

set /p commit_msg=请输入提交信息: 
echo 正在执行git commit ...
git commit -m "%commit_msg%"

echo 正在执行git push ...
git push

echo 操作完成！
pause