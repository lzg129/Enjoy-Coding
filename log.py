from datetime import datetime

content = input("今天做了啥：")

with open("log.txt", "a", encoding="utf-8") as f:
    f.write(f"{datetime.now()} - {content}\n")