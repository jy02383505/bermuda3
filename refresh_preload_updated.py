#encoding=utf-8
from util.check_refresh_url_preload import run
import threading
import os
import time


def main():
    while True:
        run()
        time.sleep(5)


if __name__ == "__main__":
    main()
    os._exit(0)
