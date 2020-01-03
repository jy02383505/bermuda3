'''
Created on 2011-11-2

@author: IBM
'''
#from core.rediswrapper import RedisWrapper
from .config import config
import redis, logging


def getMDB(db):
    '''
    monitor redis
    '''
    pool = redis.ConnectionPool(host=config.get('monitor', 'cache_host'), port=6379, db=db, password=config.get('monitor', 'cache_password'))
    return redis.Redis(connection_pool=pool)
    

def getDB(db):
    pool = redis.ConnectionPool(host=config.get('redis', 'host'), port=6379, db=db, password=config.get('redis', 'password'))
    r = RedisWrapper(connection_pool=pool)
    r.set_bredis(config.get('redis', 'host_bak'), db, password=config.get('redis', 'password'))
    return r

class RedisWrapper(redis.Redis):
    def set_bredis(self, host, db, password):
        pool = redis.ConnectionPool(host=config.get('redis', 'host_bak'), port=6379, db=db, password=password)
        self.bredis  = redis.Redis(connection_pool=pool)

    def exists(self, key):
        try:
            return super(RedisWrapper, self).exists(key)
        except Exception:
            return self.bredis.exists(key)     

    def expire(self, key, CACHE_TIMEOUT):
        try:
            return super(RedisWrapper, self).expire(key , CACHE_TIMEOUT)
        except Exception:
            return self.bredis.expire(key , CACHE_TIMEOUT)

    def delete(self, key):
        try:
            return super(RedisWrapper, self).delete(key)
        except Exception:
            return self.bredis.delete(key)

    def get(self, key):
          try:
                return super(RedisWrapper, self).get(key)
          except Exception:
                return self.bredis.get(key)

    def set(self, key, value):
        try: 
            super(RedisWrapper, self).set(key, value)
        except Exception:
            self.bredis.set(key, value)

    def pipeline(self):
        try:
            pipe = super(RedisWrapper, self).pipeline()
            pipe.watch("test")
            pipe.execute()
            return pipe
        except Exception:
            return self.bredis.pipeline()

    def hvals(self, key):
        try:
            return super(RedisWrapper, self).hvals(key)
        except Exception:
            return self.bredis.hvals(key)
    def hkeys(self,hash_name):
        try:
            return super(RedisWrapper, self).hkeys(hash_name)
        except Exception:
            return self.bredis.hkeys(hash_name)


    def hset(self,hash_name, key_name, value):
        try:
            return super(RedisWrapper, self).hset(hash_name, key_name, value)
        except Exception:
            return self.bredis.hset(hash_name, key_name, value)

    def hmset(self, name, mapping):
        try:
            return super(RedisWrapper, self).hmset(name, mapping)
        except Exception:
            return self.bredis.hmset(name, mapping)
    '''right push'''
    def rpush(self, name, *values):
        try:
            return super(RedisWrapper, self).rpush(name,values)
        except Exception:
            return self.bredis.rpush(name,values)
    '''right pop'''
    def rpop(self, name, *values):
        try:
            return super(RedisWrapper, self).rpop(name,values)
        except Exception:
            return self.bredis.rpop(name,values)

    def hexists(self, name, key):
        try:
            return super(RedisWrapper, self).hexists(name, key)
        except Exception:
            return self.bredis.hexists(name, key)
'''
1=post BlackList , preload_cache
2=user_cache
3=search result_cache
4=splitter COUNTER_CACHE
8=RegexConfig_cache
10 = device_BU
11=firstlayer_cache
12=device_cache
13=channels_cache
15=REWRITE_CACHE
5=PRELOAD_DEVS
'''



