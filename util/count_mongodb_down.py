# coding=utf-8
# filepath = raw_input("Enter your file path: ")
#filename = raw_input("Enter your file name: ")
#print filepath
import sys
import time
import datetime

global error_count

def read_log(path,fileord):
    ISOTIMEFORMAT = '%Y-%m-%d'
    time_now = time.strftime(ISOTIMEFORMAT, time.localtime(time.time()))
    in_file = open(path, "r")
    out_file_name=path +str(fileord)+"_" + "-out-" + time_now;
    out_file = file(out_file_name, "w")
    line = in_file.readline()
    error_count=0
    try:
        while (line):
            #if "thinks that we are down" in line:
            if "replSet PRIMARY" in line or "replSet SECONDARY" in line:

                lineSplitArr = line.split()
                if "replSet PRIMARY" in line:
                    out_file.write("%s  %s  %s  replSet PRIMARY\n" % (lineSplitArr[1],lineSplitArr[2],lineSplitArr[3]))
                else:
                    out_file.write("%s  %s  %s  replSet SECONDARY\n" % (lineSplitArr[1],lineSplitArr[2],lineSplitArr[3]))
                error_count += 1
                line = in_file.readline()
            else:
                line = in_file.readline()

        in_file.close()
        out_file.close()
        return out_file_name
    except Exception:
        print("parse log file exception:%s" % e)

#.py文件作为模块整体导入的时候if以下代码不运行，而自身运行时运行
#
#
if __name__ == '__main__':
    start = datetime.datetime.now()
    try:
        path = sys.argv[1]
    except:
        path = 'log/mongodb.log'

    outfileName = read_log(path,0)
    print('filter down log to: %s ; using time:%s'% (outfileName,str(datetime.datetime.now() - start)))



