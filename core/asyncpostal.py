import asyncore
import logging
import socket, sys, time
from io import StringIO
from util import log_utils


# LOG_FILENAME = '/Application/bermuda3/logs/asyncpostal.log'
# # logging.basicConfig(filename=LOG_FILENAME,
# #                     format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
# #                     level=logging.INFO)
# formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
# fh = logging.FileHandler(LOG_FILENAME)
# fh.setFormatter(formatter)
#
# logger = logging.getLogger('asyncpostal')
# logger.addHandler(fh)
# logger.setLevel(logging.WARNING)

logger = log_utils.get_postal_Logger()


class HttpClient(asyncore.dispatcher):
    def __init__(self, host, port, path='', body='', read_count=1000, my_map=None, connect_timeout=1.5, response_timeout=1.5):
        self.host = host
        self.start_time = time.time()
        self.connect_time = time.time()
        self.logger = logger
        asyncore.dispatcher.__init__(self)
        self.buffer = bytes('POST /%s HTTP/1.0\r\nContent-Length:%d\r\n\r\n%s' % (path if path else '', len(body), body), 'ascii')
        # self.buffer = StringIO()
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        address = (self.host, port)
        self.logger.debug('connecting to %s', address)
        self.connect(address)
        self.strerror = 'no_error'
        self.read_count = read_count
        self.response_code = 200
        self.total_cost = 0
        self.connect_cost = 0
        self.response_cost = 0
        self.connect_timeout = connect_timeout
        self.response_timeout = response_timeout

    # 501 the refreshd response too slow
    # 502 The network is OK,But the refreshd does not work
    # 503 can not reach the server

    def handle_connect(self):
        self.connect_time = time.time()
        self.logger.debug('handle_connect(),{0}'.format(self.connect_time))

    def handle_close(self):
        self.close()
        end_time = time.time()
        self.connect_cost = self.connect_time - self.start_time
        self.total_cost = end_time - self.start_time
        self.response_cost = end_time - self.connect_time
        self.logger.debug(
            'host={0} code={1} cost={2:.2f} connect_cost={3:.2f} response_cost={4:.2f}'.format(
            self.host, self.response_code, self.total_cost, self.connect_cost,
             self.response_cost))

    def handle_error(self):
        try:
            t, v, tb = sys.exc_info()
            self.strerror = v.strerror
            self.response_code = 502
        except Exception as e:
            self.response_code = 502
            self.strerror = 'Connection refused %s' % e

    def writable(self):
        is_writable = (not self._is_connect_timeout()) and (len(self.buffer) > 0)
        return is_writable

    def _is_connect_timeout(self):
        is_timeout = True if not self.connected and (time.time() - self.start_time) >= self.connect_timeout else False
        return is_timeout

    def _is_response_timeout(self):
        is_timeout = True if self.connected and (time.time() - self.connect_time) >= self.response_timeout else False
        return is_timeout

    def readable(self):
        if self._is_connect_timeout():
            self.connect_time = time.time()
            self.strerror = 'Connection time out'
            self.response_code = 503
            self.handle_close()
            return False
        if self._is_response_timeout():
            self.strerror = 'readable too much'
            self.response_code = 501
            self.handle_close()
            return False
        return True

    def handle_write(self):
        sent = self.send(self.buffer)
        self.logger.debug('handle_write() -> "%s"', self.buffer[:sent])
        self.buffer = self.buffer[sent:]

    def handle_read(self):
        self.logger.debug('handle_read() -> starting')
        data = self.recv(8192)
        self.logger.debug('handle_read() -> %d bytes', len(data))
        self.buffer.write(data)


import aiohttp
import asyncio


class AioClient:

    def __init__(self, host=None, port=None, path=None, body=None, connect_timeout=1.5, response_timeout=1.5, logger=None, dev=None, url=None):
        self.host = host
        self.port = port
        self.path = path
        self.body = body
        self.connect_timeout = connect_timeout
        self.response_timeout = response_timeout

        self.logger = logger # optional
        self.dev = dev # for user: autodesk
        self.url = url # for user: autodesk

        self.strerror = 'no_error'
        self.response_code = 200
        self.total_cost = 0
        self.connect_cost = 0
        self.response_cost = 0
        self.request_start_time = 0
        self.request_end_time = 0


    def makeUrl(self):
        if self.host and self.port:
            url = 'http://{}:{}'.format(self.host, self.port) if not self.host.startswith('http') else '{}:{}'.format(self.host, self.port)
            if self.path:
                url = 'http://{}:{}{}'.format(self.host, self.port, self.path if self.path.startswith('/') else '/'+self.path)
        elif self.url:
            url = self.url if self.url.startswith('http') else 'https://' + self.url
        return url

    async def doget(self, session, url):
        async with session.get(url) as response:
            return await response.text()

    async def dohead(self, session, url):
        async with session.head(url) as response:
            return await response.text()

    async def dopost(self, session, url, body):
        async with session.post(url, data=bytes(body, encoding='utf-8')) as response:
        # async with session.post(url, data=bytes(json.dumps(body), encoding='utf-8') if isinstance(body, dict) else bytes(body)) as response:
        # async with session.post(url, json=body, headers={'greetings': 'HHHHHHHHHello.'}) as response:
        # async with session.post(url, json=body) as response:
            # async with session.post(url, data=json.dumps(body), headers={'greetings': 'nihao'}) as response:
            return await response.text()

    async def on_connection_create_start(self, session, trace_config_ctx, params):
        self.connection_create_start_time = session.loop.time()

    async def on_connection_create_end(self, session, trace_config_ctx, params):
        self.connection_create_end_time = session.loop.time()
        if self.connection_create_end_time - self.connection_create_start_time >= self.connect_timeout:
            self.response_code = 503
            session.close()

    async def on_request_start(self, session, trace_config_ctx, params):
        self.request_start_time = session.loop.time()

    async def on_request_end(self, session, trace_config_ctx, params):
        self.request_end_time = session.loop.time()
        if self.request_end_time - self.connection_create_end_time >= self.response_timeout:
            self.response_code = 501
            session.close()

    async def on_request_exception(self, session, trace_config_ctx, params):
        self.response_code = 502
        # self.strerror = 'errors occured: {}'.format(self.exception)

    async def main(self, methodType='POST'):
        conn = aiohttp.TCPConnector(limit=200) # amount of connections simultaneously limit default: 100;no limitation: 0
        timeout = aiohttp.ClientTimeout(sock_connect=self.connect_timeout, sock_read=self.response_timeout)

        trace_config = aiohttp.TraceConfig()
        trace_config.on_connection_create_start.append(self.on_connection_create_start)
        trace_config.on_connection_create_end.append(self.on_connection_create_end)
        trace_config.on_request_start.append(self.on_request_start)
        trace_config.on_request_end.append(self.on_request_end)
        trace_config.on_request_exception.append(self.on_request_exception)

        async with aiohttp.ClientSession(timeout=timeout, connector=conn, headers={'greetings': 'hello_world.'}, trace_configs=[trace_config]) as session:
            # r = await fetch(session, 'http://localhost:55555/hello/lym')
            # return r

            result = {}
            if methodType.lower() == 'post':
                result['response_body'] = await self.dopost(session, self.makeUrl(), self.body)
            elif methodType.lower() == 'get':
                result['response_body'] = await self.doget(session, self.makeUrl())
            elif methodType.lower() == 'head':
                result['response_body'] = await self.dohead(session, self.makeUrl())

            result['total_cost'] = self.request_end_time - self.request_start_time
            result['connect_cost'] = self.connection_create_end_time - self.connection_create_start_time
            result['response_cost'] = self.request_end_time - self.connection_create_end_time
            result['response_code'] = self.response_code
            result['host'] = self.host
            result['strerror'] = self.strerror
            result['dev'] = self.dev # special for user: autodesk
            return result

def doTheLoop(clients, logger):
    logger.info('doloop [LOOP STARTING...]')
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    results = loop.run_until_complete(asyncio.wait([c.main() for c in clients]))
    loop.run_until_complete(asyncio.sleep(0.250))
    loop.close()
    logger.info('doloop [LOOP DONE...] results: {}'.format(results))
    return [i.result() for i in results[0]]
