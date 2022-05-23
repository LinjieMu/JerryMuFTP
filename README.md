## 1. 服务端说明

### 1. 配置主机IP和端口

如果您想在本地测试，请将`./server/conf/settings.py`文件中第3行`HOST`变量改为`'127.0.0.1'`。如果您想在服务器上运行，请将`./server/conf/settings.py`文件中第3行`HOST`变量改为`'0.0.0.0'`。默认服务端口为2000，可以更改`PORT`进行修改。在服务器运行时请保证防火强已经打开。

### 2. 服务端基本功能

原文件已创建好了用户`Root`，您可以直接登录Root用户，密码为abc123。账户信息存储在文件`./server/conf/accounts.ini`中，其中密码已经过MD5加密。FTP用户文件目录为`./server/home/[username]`。下面展示基本功能：

- 查看服务端功能：

  `python3 ./server/bin/JMserver.py`

  输出结果为：

  ```
  正确的输入参数为：
  ------------------------------
  start       |   开启FTP服务器
  createuser  |   创建用户   
  deleteuser  |   删除用户 
  ls          |   查看用户列表
  ------------------------------
  ```

- 创建用户：`python3 ./server/bin/JMserver.py createuser`

- 删除用户：`python3 ./server/bin/JMserver.py deleteuser`

- 查看用户列表：`python3 ./server/bin/JMserver.py ls`

- 启动FTP服务端：`python3 ./server/bin/JMserver.py start`

### 3. 日志功能

FTP服务端会自动记录连接日志，日志文件为`./server/log/server.log`。**请注意**，由于时间原因本人并未做服务端的并发，该服务端只允许同一时刻单用户端连接。

## 2. 客户端

### 1. 连接发起

如果您是在本地测试，且没有改变端口号，则输入`python3 ./client/JMclient.py -P 20000 -s 127.0.0.1`进行连接。连接后输入用户密码即可。如果您在服务器上运行，则输入`python3 ./client/JMclient.py -P [端口号] -s [服务器IP]`。

### 2. 功能介绍

1. `get [文件名]`：从服务器上获取文件
2. `put [文件名]`：向服务器上传文件
3. `cd [目录名]`：目录切换
4. `ls`：列出当前目录下的文件列表
5. `rm [文件名或目录名]`：删除文件或目录（必须为空目录）

另外如果在下载过程中意外中断，第二次连接会有是否进行断点重传提示，输入`quit`取消重传。在下载和上传过程中会有进度栏提示。