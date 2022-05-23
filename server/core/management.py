from core import main
import logging
from conf import settings
import configparser
import getpass
import hashlib
import os
import time

class ManagementTool(object):
    '''负责对用户输入的指令进行解析并执行特定的功能'''

    def __init__(self, sys_argv):
        # 创建一个logger
        self.logger = logging.getLogger('ftp_management')
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
        self.sys_argv = sys_argv    # 记录指令
        self.verify_argv()               # 验证指令

    def verify_argv(self):
        '''验证指令是否合法'''
        if len(self.sys_argv) < 2:  # 判断指令长度是否大于2
            self.help_msg()
        cmd = self.sys_argv[1]
        if not hasattr(self, cmd):   # 判断是否含有该命令
            self.help_msg()

    def help_msg(self):
        '''打印所有的指令格式'''
        msg = '''
正确的输入参数为：
------------------------------
start       |   开启FTP服务器
createuser  |   创建用户   
deleteuser  |   删除用户 
ls          |   查看用户列表
------------------------------
        '''
        exit(msg)   # 退出，并打印指令输入格式

    def excute(self):
        '''执行指令'''
        cmd = self.sys_argv[1]
        func = getattr(self, cmd)
        func()  # 执行命令对应的函数

    def start(self):
        '''开启FTP服务端'''
        self.logger.info('准备运行FTP服务器')
        server = main.FTPserver(self)
        server.run_forever()

    def createuser(self):
        '''创建用户'''
        config = configparser.ConfigParser()
        config.read(settings.ACCOUNT_FILE)
        count = 0
        while count < 3:
            username = input('请输入用户名：')
            print(username)
            if username in config.sections():
                print('用户名已存在，请重新输入')
                count += 1
                continue
            password = getpass.getpass('请输入密码：')
            password_again = getpass.getpass('请再次输入密码：')
            if password != password_again:
                print('两次密码不一致，请重新输入')
                count += 1
                continue
            config.add_section(username)
            # 对用户输入的密码进行MD5加密
            md5_obj = hashlib.md5()
            md5_obj.update(password.encode('utf-8'))
            md5_password = md5_obj.hexdigest()
            # 将用户信息写入文件
            config.set(username, 'name', username)
            config.set(username, 'password', md5_password)
            with open(settings.ACCOUNT_FILE, 'w') as f:
                config.write(f)
            # 提示用户创建成功
            print('用户%s创建成功'%username)
            # 日志记录
            self.logger.info('用户%s创建成功' % username)
            # 创建用户文件夹
            user_home_dir = '%s/%s' % (settings.USER_HOME_BASE_DIR, username)
            if not os.path.exists(user_home_dir):
                os.mkdir(user_home_dir, mode=0o777)   #创建目录并修改权限为755
            break

    def deleteuser(self):
        '''删除用户'''
        # 列出当前所有用户
        self.ls()
        config = configparser.ConfigParser()
        config.read(settings.ACCOUNT_FILE)
        count = 0
        while count < 3:
            username = input('请输入用户名：')
            if username not in config.sections():
                print('用户名不存在，请重新输入')
                count += 1
                continue
            if input('确定删除用户%s吗？(y/n)'%username) == 'y':
                config.remove_section(username)
                with open(settings.ACCOUNT_FILE, 'w') as f:
                    config.write(f)
                print('用户%s删除成功'%username)
                # 日志记录
                self.logger.info('用户%s删除成功' % username)
                # 更改用户文件夹名称
                user_home_dir = '%s/%s' % (settings.USER_HOME_BASE_DIR, username)
                if os.path.exists(user_home_dir):
                    os.rename(user_home_dir, '%s/%s'%(settings.USER_HOME_BASE_DIR, 'del_%s_%s'%(username, time.time())))
                break
            else:
                print('用户删除失败')
                break

    def ls(self):
        '''列出所有用户'''
        print('用户列表'.center(20, '-'))
        config = configparser.ConfigParser()
        config.read(settings.ACCOUNT_FILE)
        for index,username in enumerate(config.sections()):
            print('No.%s\t%s'%(index+1,username))
        print('-'*24)

            
            


