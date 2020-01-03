#-*- coding:utf-8 -*-
import smtplib
import logging.handlers
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import simplejson as json
import os

from util import log_utils
from core import queue
from util.send_imp_alarm import send_imp
from util.emailSender import EmailSender

# logger = logging.getLogger('router')
# logger.setLevel(logging.DEBUG)
logger = log_utils.get_rtime_Logger()

def send(to_addrs, subject, plainText, textType='txt', attachs=[]):
    email_obj = MIMEMultipart()
    if textType == 'txt':
        msg = MIMEText(plainText)
    elif textType == 'html':
        msg = MIMEText(plainText, 'html', 'utf-8')
    from_addr = 'noreply@chinacache.com'
    email_obj.attach(msg)
    email_obj['Subject'] = subject
    email_obj['From'] = from_addr
    email_obj['To'] = ','.join(to_addrs)

    try:
        if attachs:
            for _atta in attachs:
                _, atta_name = os.path.split(_atta)
                atta = MIMEText(open(_atta, 'rb').read(), 'base64', 'utf-8')
                atta['Content-Type'] = 'application/octet-stream'
                atta['Content-Disposition'] = 'attachment;filename="%s"' % atta_name
                email_obj.attach(atta)
    except Exception:
        logger.debug('sendEmail add attachs error is %s' % (e))

    e_s = EmailSender(from_addr, to_addrs, email_obj)
    r_send = e_s.sendIt()
    if r_send != {}:

        try:
            #s = smtplib.SMTP('corp.chinacache.com')
            s = smtplib.SMTP('anonymousrelay.chinacache.com')
            s.ehlo()
            s.starttls()
            s.ehlo()
        except:
            logger.debug("%s STARTTLS extension not supported by server" % email_obj['To'])
            pass
        #s.login('noreply', 'SnP123!@#')
        s.sendmail(from_addr, to_addrs, email_obj.as_string())
        s.quit()

def run(batch_size=500):
    try:
        messages = queue.get('email',batch_size)
        logger.debug("sendEmail.work process messages begin, count: %d " %len(messages))
        for body in messages:
            try:
                email = json.loads(body)
                to_addrs = email.get("to_addrs",None)
                if to_addrs and '@' in to_addrs[0]:
                    send(email.get("to_addrs"),email.get("title").encode("UTF-8") ,email.get("body").encode("UTF-8"))
                    # try:
                    #     send_imp(email.get("to_addrs"),email.get("title").encode("UTF-8"),email.get("body").encode("UTF-8"))
                    # except Exception,e:
                    #     logger.warning('seng to imp error:%s' % traceback.format_exc())
                    logger.debug("sendEmail.send %s to_addrs: %s " %(email.get('username'), email.get("to_addrs")))
                else:
                    logger.debug("sendEmail.send %s to_addrs is None " % email.get("username"))
            except Exception:
                logger.warning('sendEmail body error:%s' % traceback.format_exc())

        logger.debug("sendEmail.work process messages end, count: %d " %len(messages))
    except Exception:
        logger.warning('sendEmail work error:%s' % traceback.format_exc())
