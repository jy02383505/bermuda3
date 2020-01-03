#!/usr/bin/env python
# coding: utf-8

import traceback
import smtplib
from core.config import config
from util import log_utils


logger = log_utils.get_rtime_Logger()


class EmailSender:

    def __init__(self, from_addr, to_addrs, msg, passwd=None):
        self.from_addr = from_addr if '@' in from_addr else config.get('emailinfo', from_addr)
        self.to_addrs = to_addrs if isinstance(to_addrs, list) else [i for i in to_addrs.split(',') if i]

        self.passwd = passwd if passwd else config.get('emailinfo', '{}_pwd'.format(from_addr[:from_addr.find('@')]))
        self.mail_server = config.get('emailinfo', 'mail_server')
        self.mail_port = int(config.get('emailinfo', 'mail_port'))

        self.msg = msg
        logger.info("EmailSender from_addr: %s|| passwd: %s|| to_addrs(%s): %s" % (self.from_addr, self.passwd, type(self.to_addrs), self.to_addrs))
        
    def sendIt(self):
        try:
            s = smtplib.SMTP_SSL(self.mail_server, self.mail_port)
            s.ehlo()
            r_login = s.login(self.from_addr, self.passwd)
            r_send = s.sendmail(self.from_addr, self.to_addrs, self.msg.as_string())
            s.quit()
            logger.info("EmailSender [done: sendIt] r_login: %s|| r_send: %s" % (r_login, r_send))
            return r_send # {} normally
        except smtplib.SMTPException:
            # print("Error: %s" % traceback.format_exc())
            logger.debug("EmailSender [error]: %s" % (traceback.format_exc(), ))
