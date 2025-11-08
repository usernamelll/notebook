@echo off
:: 强制切换控制台为UTF-8编码（65001），并隐藏切换提示
chcp 65001 >nul

echo 正在执行git add . ...
git add .

set /p commit_msg=请输入提交信息: 
echo 正在执行git commit ...
git commit -m "%commit_msg%"

echo 正在执行git push ...
git push

:: 加入显示提交记录的命令
echo.
echo 提交记录如下：
git log --oneline

echo 操作完成！
pause
    