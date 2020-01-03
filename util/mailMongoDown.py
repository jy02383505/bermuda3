#! /usr/bin/env python
# -*- coding: utf-8 -*-
# 本例  无  命名规范
#for i in range(服务器)
#     从服务器i下载文件
#	运行 过滤解析  脚本 生成 命名为 outfile_日期_i
#
#合并 	outfile_日期_(1-n) 到  outfile_日期
#
#读 文件内容   send mail
#
import subprocess
import datetime,time
from . import count_mongodb_down
from . import send_mail_util
import sys,os
import configparser
import traceback


yesterday = datetime.date.today() - datetime.timedelta(days=1)
today =  datetime.date.today()

#refer to :http://greatghoul.iteye.com/blog/686130
def fileJoin(in_filenames, out_filename):
    out_file = open(out_filename, 'w+')
    err_files = []
    for file in in_filenames:
        try:
            in_file = open(file, 'r')
            out_file.write(in_file.read())
            #out_file.write(os.linesep)
            in_file.close()
        except IOError as errins:
            print('error joining ', file)
            print(errins)
            err_files.append(file)
    #out_file.write("Today we have %d down time(s)." % count_mongodb_down.errorcount )
    out_file.close()
    print('second step: joining completed. %d file(s) missed.outfile: %s' % (len(err_files),out_filename))

    if len(err_files) > 0:
        print('missed files:')
        print('--------------------------------')
        for file in err_files:
            print(file)
        print('--------------------------------')

def clrTmpFiles(in_filenames):
    for file in in_filenames:
        try:
            os.remove(file)
            #out_file.write(os.linesep)
        except IOError as errins:
           print(errins)
#   从服务器i下载文件
#	运行 过滤解析  脚本 生成 命名为 outfile_日期_i
def extractServerDownLog(svrAddr,i,rmtLogFile,daystr):
    ABSPATH=os.path.abspath(sys.argv[0])
    ABSPATH=os.path.dirname(ABSPATH)+"/"
    destfile = ABSPATH+ 'log/mongodb.log'
    try:
        cmd = 'scp -r root@'+svrAddr+':'+rmtLogFile+daystr+' '+destfile
        subprocess.call(cmd, shell=True)
        print('first step:rsync completed.cmd is %s begin to parse log by down flag  %s.' % (cmd,svrAddr))
        return count_mongodb_down.read_log(destfile,str(i)+daystr)
    except Exception:
        print('error pull file from server:%s' % svrAddr)
        print(traceback.format_exc())

def logMongoDownOutFile():
    config=configparser.ConfigParser()
    config.read('cons.cfg')
    #like ['192.168.2.100','192.168.2.101','192.168.2.102']
    remoteserver= str(config.get('remote','serverAddr')).split(",")
    rmtLogFile = config.get('remote','rmtLogFile')
    infiles=[]
    outfile='mongoDown.log'
    for daystr in [yesterday.strftime('%Y%m%d'),today.strftime('%Y%m%d')]:
        for i,svr in enumerate(remoteserver):
           infiles.append(extractServerDownLog(svr,i,rmtLogFile,daystr))
    #合并文件:merge many files into one outfile as result for email
    fileJoin(infiles,outfile)
    # clear these middle files
    clrTmpFiles(infiles)
    return outfile

'''
  #fulltime = 'Aug  28 23:16:48.717  replSet PRIMARY'
  return:Aug  28
   sep  9
   sep  1
'''
def formatMonthdayStr(countDate):
    monthStr =(time.ctime(time.mktime(countDate.timetuple()))).split(" ")[1]
    dayStr = (time.ctime(time.mktime(countDate.timetuple()))).split(" ")[2]
    if dayStr=='':
        dayStr=(time.ctime(time.mktime(countDate.timetuple()))).split(" ")[3]
    monthDayStr=monthStr+"  "+dayStr
    return monthDayStr

def constrMaildetailForLastday(outfile,countDate):
    in_file = open(outfile, "r")
    content=''
    monthDayStr=formatMonthdayStr(countDate)
    detailStr=''
    lineSplitArr=[]
    for line in in_file.readlines():
        if monthDayStr in line:
            content+= line
            lineSplitArr.append(line.split()[2])
    detailStr = str(content.count('\n'))
    if content.count('\n')>0:
       lineSplitArr.sort()
       detailStr +=" (切换时间点(ms):"+"; ".join(lineSplitArr)+")"
    return "<li>"+countDate.strftime('%Y年%m月%d日')+" : " + detailStr

def constrMailContent(newcontent):
    content=''
    loghistory = 'mongo_log_history_mail'
    cmd = "sed -i '1 i\\"+ newcontent+"' "+loghistory
    subprocess.call(cmd, shell=True)
    file = open(loghistory,'r')
    for line in file.readlines()[0:14]:
        content+=str(line)
    file.close()
    return content
'''
9.13 log rotate, change the way to constr mail content by adding last day log
'''
def sendmail(outfile):
    #另一个方案：cat mongoDown.log| sort -k1,2 -r |awk '{print $1,$2}'|uniq -c |head -14>t.log
    try:
        newcontent=constrMaildetailForLastday(outfile,yesterday)
        content="\r\n Hi All,<br> <ul>此邮件统计近两周的刷新数据库主从切换次数： "
        # for ld in range(14):
        #     preDay = datetime.date.today() - datetime.timedelta(days=(ld+1))
        #     content+=constrMaildetailForOneday(outfile,preDay)
        content+=constrMailContent(newcontent)
        content+="</ul>"
        print('last step: email to specified addr....\n'+content)
        send_mail_util.send(send_mail_util.ads_from,send_mail_util.ads_to,'刷新mongodb主从切换日报',content)
    except Exception:
        print('发送邮件异常:%s' % e)
#.py文件作为模块整体导入的时候if以下代码不运行，而自身运行时运行
#
#
if __name__ == '__main__':
    start = datetime.datetime.now()
    try:
        mongoDownLog =logMongoDownOutFile()
        #log file change into seperating daily,so should append it to old file mongoDown.log
        #then from now,should send mail by reading mongoDown_final.log
        # infiles=[mongoDownLog,'mongoDown.log']
        # finalOutfile='mongoDown_final.log'
        # #合并文件:merge many files into one outfile as result for email
        # fileJoin(infiles,finalOutfile)
    except Exception:
        print('mongodb日志警告发送异常:%s' % e)
    else:
        sendmail(mongoDownLog)
    print('--------------------------------')
    print('统计mongodb宕机日志-发送邮件用时：%s'+ str(datetime.datetime.now() - start))
