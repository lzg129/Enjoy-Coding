from datetime import datetime

content = input("待到秋来九月八：")

with open("log.txt", "a", encoding="utf-8") as f:
    f.write(f"{datetime.now()} - {content}\n")