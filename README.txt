
ИНСТРУКЦИЯ ПО ЗАПУСКУ БОТА НА TIMEWEB:

1. Зайдите в файловый менеджер Timeweb или подключитесь через WinSCP.
2. Загрузите все файлы из архива в одну папку, например /root/sales_bot/
3. Зайдите в терминал (через SSH или браузер).
4. Выполните:
   sudo apt update
   sudo apt install python3-pip screen -y
   pip3 install -r requirements.txt

5. Запустите бота в фоновом режиме:
   screen -S bot
   python3 bot.py

6. Чтобы свернуть экран: нажмите Ctrl + A, затем D

7. Чтобы снова открыть:
   screen -r bot

8. Бот будет работать постоянно.
