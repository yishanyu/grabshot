#!/usr/bin/python3
#-*-coding:utf-8-*-

import os
import sys
import traceback
import logging
import threading

import configparser
import time
import pymysql
from DBUtils.PooledDB import PooledDB


basedir = os.path.dirname(os.path.realpath(__file__))
locking = threading.Lock()

#logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(level=logging.DEBUG, format='%(threadName)s>{%(levelname)s}:%(message)s')


'''每个线程一个数据库连接对象'''
#@是装饰器
class Database(object):
    __dp = None
    
    def __init__(self):
        #logging.info('DatabaseIniting...')
        Database.__dp = DBPond()

    '''查询列表'''
    def fetchall(self, query, args=None):
        result = None
        with Database.__dp as db:
            try:
                db.cursor.execute(query, args)
                result = db.cursor.fetchall()
            except Exception as e:
                self.exception('fetchall')
        return result
    
    '''查询单条记录'''
    def fetchone(self, query, args=None):
        result = None
        with Database.__dp as db:
            try:
                db.cursor.execute(query, args)
                result = db.cursor.fetchone()
            except Exception as e:
                self.exception('fetchone')
        return result
    
    '''插入记录并返回主键ID'''
    def insert(self, query, args=None):
        result = None
        with Database.__dp as db:
            cs = db.cursor
            try:
                cs.execute(query, args)
                db.conn.commit()
            except Exception as e:
                db.conn.rollback()
                self.exception('insert')
            result = cs.lastrowid
        return result

    '''标准执行'''
    def execute(self, query, args=None):
        result = None
        with Database.__dp as db:
            cs = db.cursor
            try:
                cs.execute(query, args)
                db.conn.commit()
            except Exception as e:
                db.conn.rollback()
                self.exception('execute')
            result = cs.rowcount
        return result


    '''异常记录到数据库'''
    def exception(self, remark):
        #a,b,c = sys.exc_info()
        logging.info(traceback.format_exc(limit=1))
        content = traceback.format_exc()
        message = str(sys.exc_info())
        seetime = time.strftime('%F %T')
        sql = "INSERT INTO `smnt_except` (`service`, `message`, `content`, `remark`, `seetime`) VALUES ('sqlexcept', %s, %s, %s, %s);"

        with Database.__dp as db:
            cs = db.cursor
            #logging.debug(cs.mogrify(sql, (message, content, remark, seetime)))
            try:
                cs.execute(sql, args=(message, content, remark, seetime))
                db.conn.commit()
            except:
                pass

        return None




'''数据库可多线程共享的连接池'''
class DBPond():
    __pool = None
    
    def __init__(self):
        locking.acquire()
        
        if DBPond.__pool is None:
            cfgdir = '{basedir}{sep}conf{sep}config.ini'.format(basedir=basedir, sep=os.sep)
            dbsdir = '{basedir}{sep}conf{sep}database.ini'.format(basedir=basedir, sep=os.sep)
            cp = configparser.ConfigParser()
            cp.read(cfgdir, encoding='utf-8')
            plate = cp.get('general', 'plate')
            cp.read(dbsdir, encoding='utf-8')
            link = cp.items(plate)

            #[1]mincached 池最少空闲数，空间少于会创建新连接
            #[5]maxcached 池最大空闲数，空闲大于会关闭多的空闲连接
            #[3]maxshared 池最大共享数，连接数达到则新请求共享旧连接
            #[5]maxconnections 最大连接数
            #[5]maxusage 单个连接的最大复用次数
            DBPond.__pool = PooledDB(pymysql,
                                   host=link[0][1],
                                   port=int(link[4][1]),
                                   user=link[1][1],
                                   passwd=link[2][1],
                                   db=link[3][1],
                                   mincached=1,
                                   maxcached=5,
                                   maxshared=3,
                                   maxconnections=5,
                                   blocking=True,
                                   maxusage=5,
                                   setsession=None,
                                   use_unicode=False,
                                   charset='utf8')
            #logging.debug('********************CREATE:%d'%id(DBPond.__pool))
        else:
            #logging.debug('====USE:%d'%id(DBPond.__pool))
            pass
        
        locking.release()
        
    def __enter__(self):
        self.conn = DBPond.__pool.connection()
        self.cursor = self.conn.cursor()
        return self
    
    def __exit__(self, type, value, trace):
        #logging.debug('__exit__:%d'%id(self.__pool))
        self.cursor.close()
        self.conn.close()
        #return self



db = Database()
def testdb():
    #db = Database()
    
    version = db.fetchone('SELECT VERSION();')
    #logging.info(version)
    
    excepts = db.fetchall('SELECT COUNT(*) FROM `smnt_except`;')
    #logging.info(excepts)
    
    import hashlib
    for i in range(10):
        officeid, realname, passbase = ['guangzhou', '张三', str(time.time())]
        username = ''
        password = hashlib.md5(passbase.encode('utf8')).hexdigest()
        sql = "INSERT INTO `smnt_client` (`officeid`, `username`, `realname`, `password`, `passbase`) VALUES (%s, %s, %s, %s, %s)"
        userid = db.insert(sql, (officeid, username, realname, password, passbase))
        userkey = '%s%d'%(password[:16], userid)
        result = db.execute("UPDATE `smnt_client` SET `userkey`=%s WHERE `id`=%s;", (userkey, userid))
        #if result == 1:
        #    logging.info("新增成功：%s"%userkey)
        #else:
        #    logging.info("新增失败：%s"%result)

    version = db.execute("SELECT VERSION();")
    #logging.info(version)



if __name__ == '__main__':

    starttime = time.time()
    tl = []
    logging.info("testdb...")
    for i in range(50):
        i = threading.Thread(target=testdb)
        tl.append(i)
        i.start()

    for i in tl:
        i.join()

    logging.info("COST:%.3f"%(time.time()-starttime))
