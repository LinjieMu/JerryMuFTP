import os

HOST = '0.0.0.0'    # 主机ip
PORT = 20000  # 服务端口

# MIN_PASSITVE_PORT = 30000  # 最小被动端口
# MAX_PASSITVE_PORT = 31000  # 最大被动端口

BASE_DIR = os.path.dirname(os.path.dirname(__file__))   # 根目录
USER_HOME_BASE_DIR = os.path.join(BASE_DIR, 'home') # 用户文件目录
ACCOUNT_FILE = '%s/conf/accounts.ini' % BASE_DIR    # 用户信息存放目录

MAX_SOCKET_LISTEN = 5   # 最大监听数

LOG_FILE = '%s/log/server.log' % BASE_DIR