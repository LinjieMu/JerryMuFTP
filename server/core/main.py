import hashlib
import socket
from conf import settings
import json
import configparser
import os
import re
import time
import logging


class FTPserver():
    '''处理与客户端所有交互的socket server'''

    # 状态码
    STATUS_CODE = {
        100: 'Control Socket Build success',
        200: 'Passed authentication!',
        201: 'Wrong username or password!',
        300: 'File or dir not found!',
        301: 'File already exists, and this msg includes the file size!',
        350: 'Dir changed successfully!',
        351: 'Dir not found!',
        352: 'Permission denied!',
        400: 'List dir success!',
        401: 'List dir failed!',
        500: 'Create dir success!',
        501: 'Dir is already exist!',
        502: 'Dirname is illegal!',
        600: 'Delete file success!',
        601: 'Delete dir success!',
    }
    # 定义消息最长大小
    MSG_SIZE = 1024


    def __init__(self, management_instance):
        # 创建一个logger
        self.logger = logging.getLogger('ftp_server')
        self.logger.setLevel(logging.INFO)
        # 创建文件Handler
        self.log = logging.FileHandler(settings.LOG_FILE)
        self.log.setLevel(logging.DEBUG)
        # 设置格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.log.setFormatter(formatter)
        # 添加Handler
        self.logger.addHandler(self.log)
        self.logger.info('FTP服务器初始化完成')
        # 用户对象
        self.user_obj = None
        # 当前目录
        self.current_dir = None
        self.management_instance = management_instance
        # 加载用户信息
        self.accounts = self.load_accounts()
        # 实例化socket对象
        self.sock = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)
        # 端口绑定
        try:
            self.sock.bind((settings.HOST, settings.PORT))
            self.logger.info('FTP服务器绑定端口%s成功' % settings.PORT)
        except:
            self.logger.error('FTP服务器绑定端口%s失败' % settings.PORT)
            print('FTP服务器绑定端口%s失败' % settings.PORT)
            exit()
        # 端口监听
        self.sock.listen(settings.MAX_SOCKET_LISTEN)

    def run_forever(self):
        '''启动socket server'''
        # 终端显示
        print('FTP服务器在端口%s上启动成功，等待客户端连接...'%settings.PORT)
        while True:
            # 等待客户端发起连接请求
            self.request, self.addr = self.sock.accept()
            self.logger.info('接收到来自%s:%s的连接' % self.addr)
            # 处理连接的请求
            try:
                print('等待新的用户认证...')
                self.handle()
            except Exception as e:
                self.logger.error('处理请求出错，错误信息：%s' % e)
                self.request.close()

    def handle(self):
        '''处理与用户的所有指令交互'''
        while True:
            # 接收用户发来的控制信息
            raw_data = self.request.recv(self.MSG_SIZE)
            # 处理收到空消息的情况
            if not raw_data:
                # 日志记录
                self.logger.info('到%s:%s的连接已被客户端中断' % self.addr)
                # 删除用户
                self.user_obj = None
                # 关闭连接
                self.request.close()
                self.request.close()
                self.logger.info('关闭控制连接和数据连接')
                break
            # 处理用户发来的控制信息
            data = json.loads(raw_data.decode('utf-8'))
            data['fill'] = None
            print(data)
            if self.user_obj:
                self.logger.info('%s: %s'%(self.user_obj['name'],json.dumps(data)))
            # 对控制信息进行解析
            action_type = data.get('action_type')
            if action_type:
                if hasattr(self, '_%s' % action_type):
                    func = getattr(self, '_%s' % action_type)
                    func(data)
            else:
                self.logger.error('控制信息格式错误')

    def send_response(self, status_code, *args, **kwargs):
        '''
        打包发送消息给客户端
        status_code: 状态码
        '''
        # 打包数据
        data = kwargs
        data['status_code'] = status_code
        data['status_msg'] = self.STATUS_CODE.get(status_code)
        data['fill'] = ''
        # 发送数据
        bytes_data = json.dumps(data).encode('utf-8')
        # 如果数据长度小于规定的消息长度，则对齐进行填充
        if len(bytes_data) < self.MSG_SIZE:
            data['fill'] = data['fill'].zfill(self.MSG_SIZE - len(bytes_data))
            bytes_data = json.dumps(data).encode('utf-8')
        self.request.send(bytes_data)

    def _auth(self, data):
        '''处理用户认证请求'''
        username = data.get('username')
        password = data.get('password')
        if self.authenticate(username, password):
            print('用户%s登录成功' % username)
            self.logger.info('用户%s登录成功' % username)
            self.send_response(200)
        else:
            print('用户%s登录失败' % username)
            self.logger.error('用户%s登录失败' % username)
            self.send_response(201)

    def load_accounts(self):
        '''加载用户信息'''
        config = configparser.ConfigParser()
        config.read(settings.ACCOUNT_FILE)
        self.logger.info('用户信息加载完成')
        return config

    def authenticate(self, username, password):
        '''用户认证方法'''
        if username in self.accounts:
            _password = self.accounts[username]['password']
            # 对用户输入的密码进行MD5加密
            md5_obj = hashlib.md5()
            md5_obj.update(password.encode('utf-8'))
            if md5_obj.hexdigest() == _password:
                # 保存用户对象
                self.user_obj = self.accounts[username]
                # 记录用户文件目录
                self.user_obj['home'] = os.path.join(
                    settings.USER_HOME_BASE_DIR, username)
                self.current_dir = self.user_obj['home']
                return True
        return False

    def _get(self, data):
        '''处理用户下载请求
        1. 拿到文件名
        2. 判断文件是否存在
            2.1 如果文件存在，返回状态码+文件大小
                2.1.1 发送文件
            2.2 如果文件不存在，返回状态码
        '''
        filename = data.get('filename')
        full_path = os.path.join(self.current_dir, filename)
        if os.path.isfile(full_path):
            # 返回文件大小
            file_size = os.path.getsize(full_path)
            self.send_response(301, file_size=file_size)
            # 日志记录
            self.logger.info('%s: %s' % (self.user_obj['name'], '下载文件%s' % full_path))
            # 发送文件
            with open(full_path, 'rb') as f:
                for line in f:
                    self.request.send(line)
                else:
                    # 日志记录
                    self.logger.info('%s: %s' % (self.user_obj['name'], '文件%s下载完成' % full_path))
        else:
            self.send_response(300)
            # 日志记录
            self.logger.error('%s: %s' % (self.user_obj['name'], '文件%s不存在' % full_path))

    def _cd(self, data):
        '''处理用户切换目录请求
        1. 把target_dir和user_current_dir拼接起来
        2. 检测要切换的目录是否存在，如果存在，则切换目录
        3. 如果目录不存在，返回状态码
        '''
        path = data.get('target_dir')
        # 判断是否为返回上一级目录
        if path == '..':
            full_path = os.path.dirname(self.current_dir)
            # 判断是否合法
            if full_path.startswith(self.user_obj['home']):
                self.current_dir = full_path
                relative_path = os.path.relpath(
                    full_path, self.user_obj['home'])
                self.send_response(350, relative_dir=relative_path)
                # 日志记录
                self.logger.info('%s: %s' % (self.user_obj['name'], '切换目录%s' % full_path))
            else:
                self.send_response(351)
                # 日志记录
                self.logger.error('%s: %s' % (self.user_obj['name'], '切换目录%s失败' % full_path))
        # 判断是否为进入下一级目录
        # 如果路径名以'/'开头，则认为是绝对路径，从用户根目录开始
        elif path.startswith('/'):
            # 拼接目录
            full_path = os.path.join(self.user_obj['home'], path[1:])
            print(full_path)
            # 判断路径是否存在
            if os.path.isdir(full_path):
                self.current_dir = full_path
                relative_path = os.path.relpath(
                    full_path, self.user_obj['home'])
                self.send_response(350, relative_dir=relative_path)
                # 日志记录
                self.logger.info('%s: %s' % (self.user_obj['name'], '切换目录%s' % full_path))
            else:
                self.send_response(351)
                # 日志记录
                self.logger.error('%s: %s' % (self.user_obj['name'], '切换目录%s失败' % full_path))
        else:
            # 拼接目录
            full_path = os.path.join(self.current_dir, path)
            # 判断目录是否存在
            if os.path.isdir(full_path):
                self.current_dir = full_path
                relative_path = os.path.relpath(
                    full_path, self.user_obj['home'])
                self.send_response(350, relative_dir=relative_path)
                # 日志记录
                self.logger.info('%s: %s' % (self.user_obj['name'], '切换目录%s' % full_path))
            else:
                self.send_response(351)
                # 日志记录
                self.logger.error('%s: %s' % (self.user_obj['name'], '切换目录%s失败' % full_path))
        print('current_dir:', self.current_dir)

    def _ls(self, data):
        '''处理用户列出目录请求
        '''
        # 列出当前目录下的文件
        files = os.listdir(self.current_dir)
        res = []
        for file in files:
            # 判断是否是目录
            if os.path.isdir(os.path.join(self.current_dir, file)):
                dir = {'filename': file, 'is_dir': True}
            else:
                dir = {'filename': file, 'is_dir': False, 'size': os.path.getsize(
                    os.path.join(self.current_dir, file)), 'time': os.path.getmtime(os.path.join(self.current_dir, file))}
            res.append(dir)
        self.send_response(400,  res=res)
        # 日志记录
        self.logger.info('%s: %s' % (self.user_obj['name'], '列出目录%s' % self.current_dir))

    def _mkdir(self, data):
        '''在当前目录下创建文件夹'''
        # 拼接目录
        full_path = os.path.join(self.current_dir, data.get('dirname'))
        # 判断目录是否存在或文件名是否合法
        if os.path.isdir(full_path):
            self.send_response(501)
            # 日志记录
            self.logger.error('%s: %s' % (self.user_obj['name'], '创建目录%s失败，已经存在' % full_path))
        elif not re.match(r'^[\w\-]+$', data.get('dirname')):
            self.send_response(502)
            # 日志记录
            self.logger.error('%s: %s' % (self.user_obj['name'], '创建目录%s失败，文件名不合法' % full_path))
        else:
            # 创建目录
            os.mkdir(full_path)
            self.send_response(500)
            # 日志记录
            self.logger.info('%s: %s' % (self.user_obj['name'], '创建目录%s成功' % full_path))

    def _rm(self, data):
        '''在当前目录下删除文件'''
        # 拼接目录
        full_path = os.path.join(self.current_dir, data.get('filename'))
        # 判断文件是否存在
        if os.path.isfile(full_path):
            os.remove(full_path)
            self.send_response(600)
            # 日志记录
            self.logger.info('%s: %s' % (self.user_obj['name'], '删除文件%s' % full_path))
        elif os.path.isdir(full_path):
            os.rmdir(full_path)
            self.send_response(601)
            # 日志记录
            self.logger.info('%s: %s' % (self.user_obj['name'], '删除目录%s' % full_path))
        else:
            self.send_response(300)
            # 日志记录
            self.logger.error('%s: %s' % (self.user_obj['name'], '删除文件或目录%s失败，不存在' % full_path))

    def _put(self, data):
        '''上传文件到服务器
        1. 拿到local_file的文件名和大小
        2. 检查本地是否有同名文件
        '''
        local_file = data.get('local_file')
        full_path = os.path.join(self.current_dir, local_file)
        # 如果文件已存在，则给他打上时间戳
        if os.path.isfile(full_path):
            if '.' in full_path:
                lis = full_path.split('.')
                filename = lis[0] + '_' + str(int(time.time())) + '.' + lis[1]
        else:
            filename = full_path
        print(filename)
        with open(filename, 'wb') as f:
            print('已经打开')
            file_size = data.get('file_size')
            recieved_size = 0
            while recieved_size < file_size:
                if file_size - recieved_size < 8192:
                    data = self.request.recv(file_size - recieved_size)
                else:
                    data = self.request.recv(8192)
                f.write(data)
                recieved_size += len(data)
            else:
                # 日志记录
                self.logger.info('%s: %s' % (self.user_obj['name'], '上传文件%s成功' % filename))

    def _resend(self, data):
        # 拼接文件路径
        full_path = os.path.join(
            self.user_obj['home'], data.get('abs_filename'))
        # 判断文件是否存在
        if os.path.isfile(full_path):
            # 判断文件大小
            file_size = os.path.getsize(full_path)
            if file_size == data.get('file_size'):
                self.send_response(301)
                with open(full_path, 'rb') as f:
                    f.seek(data.get('recieved_size'))
                    for line in f:
                        self.request.send(line)
                    else:
                        # 日志记录
                        self.logger.info('%s: %s' % (self.user_obj['name'], '重传完成，文件%s' % full_path))
            else:
                self.send_response(300)
                # 日志记录
                self.logger.error('%s: %s' % (self.user_obj['name'], '重传失败，大小不一致，文件%s' % full_path))
        else:
            self.send_response(300)
            # 日志记录
            self.logger.error('%s: %s' % (self.user_obj['name'], '重传失败，文件%s不存在' % full_path))
