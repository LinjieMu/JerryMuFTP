import optparse
import socket
import json
import os
import shelve
import getpass
import time


class FTPclient():
    '''ftp客户端'''
    MSG_SIZE = 1024

    def __init__(self):
        # 客户端用户名
        self.username = None
        # 当前服务器文件夹
        self.current_dir = ''
        # 文件下载记录
        self.shelve_obj = shelve.open('download_record')
        # 实例化一个语法解析对象
        parser = optparse.OptionParser()
        # 添加语法解析规则
        parser.add_option('-s', '--server', dest='server',
                          help='ftp server ip_addr')
        parser.add_option('-P', '--port', dest='port', help='ftp server port')
        parser.add_option('-u', '--username',
                          dest='username', help='username info')
        parser.add_option('-p', '--password',
                          dest='password', help='password info')
        # 语法检测
        self.options, self.args = parser.parse_args()
        self.args_verification()
        # 建立连接
        self.make_connection()

    def args_verification(self):
        '''检查参数的合法性'''
        # 必须同时提供主机信息和端口信息
        if not self.options.server or not self.options.port:
            exit('错误: 必须提供端口和主机信息')
        

    def make_connection(self):
        '''建立socket链接'''
        # 向服务器发起连接请求
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((self.options.server, int(self.options.port)))
        except:
            exit('无法连接服务器，请检查服务器是否启动或已被占用')
        print('到%s:%s的控制连接建立成功' % (self.options.server, self.options.port))
        

    def interactive(self):
        '''处理client与server之间的所有交互'''
        # 登录认证
        if self.auth():
            # 检查是否有上次没有下载完的文件
            self.unfinished_check()
            while True:
                cmd = input('[%s %s]>>: ' %
                            (self.username, self.current_dir)).strip()
                # 没有输入时，不执行任何操作
                if not cmd:
                    continue
                # 判断命令是否为exit，如果是，则退出程序
                if cmd == 'exit':
                    break
                # 读取指令类型
                cmd_list = cmd.split()
                action_type = cmd_list[0]
                # 使用反射调用响应的函数
                if hasattr(self, '_%s' % action_type):
                    func = getattr(self, '_%s' % action_type)
                    func(cmd_list[1:])
                else:
                    print('命令错误')

    def parameter_check(self, args, min_args=None, max_args=None, exact_args=None):
        '''检查参数个数的合法性'''
        if min_args:
            if min_args > len(args):
                print('必须提供多于%s个参数，但实际提供了%s个参数' %
                      (min_args, len(args)))
                return False
        if max_args:
            if max_args < len(args):
                print('必须提供少于%s个参数，但实际提供%s个参数' %
                      (max_args, len(args)))
                return False
        if exact_args:
            if exact_args != len(args):
                print('必须提供%s个参数，但实际提供%s个参数' %
                      (exact_args, len(args)))
                return False
        return True

    def _get(self, cmd_args):
        '''从FTP服务器中下载文件'''
        '''
           函数执行流程：
           1. 获取文件名
           2. 发送到FTP服务器
           3. 等待服务器返回消息
            3.1 如果文件存在，则拿到文件大小
             3.1.1 循环接收文件
            3.2 如果文件不存在，返回错误码
        '''
        if self.parameter_check(cmd_args, min_args=1):
            # 获取文件名
            filename = cmd_args[0]
            # 发送到FTP服务器
            self.send_msg('get', filename=filename)
            # 等待服务器返回消息
            response = self.get_response()
            # print(response)
            if response.get('status_code') == 301:
                # 文件存在，获取文件大小
                file_size = response.get('file_size')
                print('找到该文件，大小为'+str(file_size))
                # 记录接收的文件
                file_abs_path = os.path.join(self.current_dir, filename)
                self.shelve_obj[file_abs_path] = [file_size, "%s.download" % filename]
                # 循环接收文件
                with open("%s.download" % filename, 'wb') as f:
                    # 打印进度条
                    progress_generator = self.progress_bar(file_size)
                    progress_generator.__next__()
                    
                    recieved_size = 0
                    while recieved_size < file_size:
                        if file_size - recieved_size < 8192:
                            data = self.sock.recv(
                                file_size - recieved_size)
                        else:
                            data = self.sock.recv(8192)
                        f.write(data)
                        recieved_size += len(data)
                        progress_generator.send(recieved_size)
                    else:
                        print()
                        print('---文件 [%s] 接收完成, 文件大小为: %s' %
                              (filename, recieved_size))
                # 正常下载完则进行改名
                os.rename("%s.download" % filename, filename)
                # 文件正常接收完的话关闭shelve
                del self.shelve_obj[file_abs_path]

    def _put(self, cmd_args):
        '''上传文件到FTP服务器
        1. 确保本地文件存在
        2. 发送文件名+文件大小到FTP服务器
        3. 打开文件发送给服务器
        '''
        if self.parameter_check(cmd_args, exact_args=1):
            local_file = cmd_args[0]
            if os.path.isfile(local_file):
                total_size = os.path.getsize(local_file)
                self.send_msg('put', file_size=total_size,
                              local_file=local_file)
                # 打印进度条
                progress_generator = self.progress_bar(total_size)
                progress_generator.__next__()

                upload_size = 0
                with open(local_file, 'rb') as f:
                    for line in f:
                        self.sock.send(line)
                        upload_size += len(line)
                        progress_generator.send(upload_size)
                    else:
                        print()
                        print('上传完成!'.center(50, '-'))
            else:
                print('文件不存在!')

    def _ls(self, cmd_args):
        '''列出FTP服务器中的文件'''
        '''
           函数执行流程：
           1. 发送到FTP服务器
           2. 等待服务器返回消息
           3. 打印文件列表
        '''
        # 判断参数个数是否小于2
        if self.parameter_check(cmd_args, exact_args=0):
            # 发送到FTP服务器
            self.send_msg('ls')
            # 等待服务器返回消息
            response = self.get_response()
            # print(response)
            if response.get('status_code') == 400:
                # 文件存在，打印文件列表
                res = response.get('res')
                print('文件名--------文件大小--------创建时间')
                for file in sorted(res, key=lambda x: x['is_dir'], reverse=True):
                    if file['is_dir']:
                        print('%s\t\t<DIR>' % file['filename'])
                    else:
                        now = file['time']
                        timeArray = time.localtime(now)
                        otherStyleTime = time.strftime("%Y-%m-%d %H:%M:%S", timeArray)
                        print('%s\t%s\t%s' % (file['filename'], file['size'],otherStyleTime))

    def _cd(self, cmd_args):
        '''改变当前目录文件夹'''
        if self.parameter_check(cmd_args, min_args=1):
            target_dir = cmd_args[0]
            self.send_msg('cd', target_dir=target_dir)
            response = self.get_response()
            if response.get('status_code') == 350:
                print('改变当前目录文件夹成功')
                self.current_dir = response.get('relative_dir')
                # print('relative_dir:%s' % response.get('relative_dir'))
                # print(response)
            else:
                print('改变当前目录文件夹失败')
                # print(response)

    def auth(self):
        '''用户认证'''
        count = 0
        # 认证三次，三次错误则退出程序
        while count < 3:
            username = input('username: ').strip()
            if not username:
                continue
            password = getpass.getpass('password: ').strip()
            cmd = {
                'action_type': 'auth',
                'username': username,
                'password': password
            }
            # 发送认证信息
            self.sock.send(json.dumps(cmd).encode('utf-8'))
            # 接收服务器的返回
            response = self.get_response()
            # print('response:', response)
            if response.get('status_code') == 200:
                self.username = username
                print('登录成功')
                return True
            else:
                print('登录失败')
                count += 1

    def get_response(self):
        '''接收服务器的响应'''
        data = self.sock.recv(self.MSG_SIZE).decode('utf-8')
        return json.loads(data)

    def send_msg(self, action_type, **kwargs):
        '''打包并发送消息到服务器'''
        msg_data = {
            'action_type': action_type,
        }
        msg_data.update(kwargs)
        msg_data['fill'] = ''

        bytes_msg = json.dumps(msg_data).encode('utf-8')
        if len(bytes_msg) < self.MSG_SIZE:
            msg_data['fill'] = msg_data['fill'].zfill(
                self.MSG_SIZE - len(bytes_msg))
            bytes_msg = json.dumps(msg_data).encode('utf-8')
        self.sock.send(bytes_msg)

    def _mkdir(self, cmd_args):
        '''创建目录'''
        if self.parameter_check(cmd_args, exact_args=1):
            dirname = cmd_args[0]
            self.send_msg('mkdir', dirname=dirname)
            response = self.get_response()
            if response.get('status_code') == 500:
                print('创建目录成功')
            else:
                print('创建目录失败')
            # print(response)

    def _rm(self, cmd_args):
        '''删除文件或目录'''
        if self.parameter_check(cmd_args, exact_args=1):
            filename = cmd_args[0]
            self.send_msg('rm', filename=filename)
            response = self.get_response()
            if response.get('status_code') == 600:
                print('删除文件成功')
            elif response.get('status_code') == 601:
                print('删除目录成功')
            else:
                print('删除文件或目录失败')
            # print(response) 

    def progress_bar(self, total_size, current_percent = 0):
        '''进度条打印'''
        last_percent = -1
        while True:
            recieved_size = yield current_percent
            current_percent = int(recieved_size/total_size*100)
            if current_percent > last_percent:
                print('#' * int(current_percent/2) +
                      '{percent}%'.format(percent=current_percent), end='\r', flush=True)
                last_percent = current_percent

    def unfinished_check(self):
        '''检查是否含有没有正常下完的文件，按照用户指令决定是否重传'''
        if list(self.shelve_obj.keys()):
            print('检测到有未完成的文件，是否重传？')
            for index, abs_file in enumerate(self.shelve_obj.keys()):
                recieved_size = os.path.getsize(self.shelve_obj[abs_file][1])
                print('%s. %s %s %s %s' % (index, 
                        abs_file,  
                        self.shelve_obj[abs_file][0], 
                        recieved_size, 
                        int(recieved_size/self.shelve_obj[abs_file][0]*100)
                    ),end='%\n')
            while True:
                choice = input("[select file to resend]").strip()
                if not choice:
                    continue
                if choice == 'exit':
                    return
                # 如果输入是数字
                if choice.isdigit():
                    choice = int(choice)
                    if choice >=0 and choice <= index:
                        select_file = list(self.shelve_obj.keys())[choice]
                        aready_received_size = os.path.getsize(self.shelve_obj[select_file][1])
                        print('重传文件：%s' % select_file)
                        # 发送重传请求
                        self.send_msg('resend', file_size=self.shelve_obj[select_file][0],
                            recieved_size = aready_received_size,
                            abs_filename=select_file)
                        # 获得服务器响应
                        response = self.get_response()
                        if response.get('status_code') == 301:
                            local_filename = self.shelve_obj[select_file][1]
                            with open(local_filename,'ab') as f:
                                total_size = self.shelve_obj[select_file][0]
                                # 创建进度条
                                progress_bar = self.progress_bar(total_size, aready_received_size)
                                progress_bar.__next__()

                                recv_size = aready_received_size
                                while recv_size < total_size:
                                    if total_size - recv_size < 8096:
                                        data = self.sock.recv(total_size - recv_size)
                                    else:
                                        data = self.sock.recv(8096)
                                    recv_size += len(data)
                                    f.write(data)
                                    progress_bar.send(recv_size)
                                else:
                                    print('file resend done!')
                            # 删除
                            del self.shelve_obj[select_file]
                            # 改名字
                            os.rename(local_filename, local_filename.replace('.download',''))
                            break
                        else:
                            print(response.get('status_msg'))
        if list(self.shelve_obj.keys()):
            self.unfinished_check()    



if __name__ == '__main__':
    client = FTPclient()
    client.interactive()    # 交互
    
    # /usr/bin/python3 /Users/linjiemu/Desktop/FTP/JerryMuFTP/client/JMclient.py -s  180.76.187.225  -P 20000