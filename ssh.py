#_*_ coding:utf-8_*_
import paramiko

ssh = paramiko.SSHClient()
ssh.load_system_host_keys() ####获取ssh key密匙，默认在~/.ssh/knows_hosts
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname = "10.10.10.27",port="22222",username="root")
print(ssh)