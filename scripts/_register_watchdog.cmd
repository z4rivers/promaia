schtasks /Create /TN "PromaiaWatchdog" /TR "'C:\Python314\python.exe' 'C:\Users\Zachary Turner\dev\promaia\scripts\watchdog.py'" /SC HOURLY /MO 1 /F /RL HIGHEST
