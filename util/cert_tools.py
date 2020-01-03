# -*i-coding:utf-8-*-
import re, datetime, traceback
from OpenSSL import crypto
import urllib.request, urllib.error, urllib.parse
from Crypto.Hash import SHA256
import base64
from util import log_utils
from core import database

logger = log_utils.get_cert_Logger()
s1_db = database.s1_db_session()


def get_crl_object(cert_crl):
    if cert_crl==None:
        return
    else:
        logger.debug('cert_crl--is %s'%(cert_crl))
        cert_crl_url=re.findall("[http|https][\w|\W]*(?:\.crl)",cert_crl)
        logger.debug('cert_crl url--is %s'%(cert_crl_url))
        req = urllib.request.Request(cert_crl_url[0])
        req.add_header('User-Agent','Mozilla/5.0')
        try:
            response = urllib.request.urlopen(req, timeout=3)
        except:
            logger.debug('cert_crl error--')
            return
        fp = response.read()
        try:
            try:
                try:
                    crl_object = crypto.load_crl(crypto.FILETYPE_PEM, fp)
                except Exception:
                    crl_object = crypto.load_crl(crypto.FILETYPE_ASN1, fp)
            except Exception:
                crl_object = crypto.load_crl(crypto.FILETYPE_TXT, fp)
        except Exception:
            crl_object = None
        if crl_object is None:
            return
        else:
            return crl_object


def get_revoke(cert, crl_object):
    '''
    查看此证书是否已被吊销
    '''
    s=[]
    revoked_obj = crl_object.get_revoked()
    if not revoked_obj:
        return False
    for rvk in revoked_obj:
        s.append(rvk.get_serial())
    a=str(cert.get_serial_number())
    if a in s:
        return True
    else:
        return False


def get_pubkey_len(cert):
    '''
    公钥长度
    '''
    pubkey_len=cert.get_pubkey().bits()
    return pubkey_len

def get_Validity(cert):
    '''
    证书有效时间戳
    '''
    cert_time={'begin_time':cert.get_notBefore(),'end_time':cert.get_notAfter()}
    return cert_time

def make_validity_to_China(cert_time_dict):
    '''
    证书时间时区转换
    '''
    logger.debug('-----make_validity_to_China  cert_time_dict %s'%(cert_time_dict))
    res = {}
    for k, v in list(cert_time_dict.items()):
        if 'Z' in v:
            logger.debug('-----make_validity_to_China  had Z ! ')
            #UTC
            _t = v[:-1]
            _date_obj = datetime.datetime.strptime(_t, '%Y%m%d%H%M%S')
            china_date = _date_obj + datetime.timedelta(hours=8)
            res[k] = china_date.strftime('%Y%m%d%H%M%S')
        elif '+' in v:
            logger.debug('-----make_validity_to_China  had + ! ')
            #带时区
            _date_s = v[:-5]
            if v[-4:] == '0800':
                res[k] = _date_s
            else:
                _h = int(v[-4:-2])
                _m = int(v[-2:])
                _date_obj = datetime.datetime.strptime(_date_s, '%Y%m%d%H%M%S')
                china_date = _date_obj - datetime.timedelta(hours=_h, minutes=_m) + datetime.timedelta(hours=8)
                res[k] = china_date.strftime('%Y%m%d%H%M%S')
        elif '-' in v:
            logger.debug('-----make_validity_to_China  had - ! ')
            #带时区
            _h = int(v[-4:-2])
            _m = int(v[-2:])
            _date_obj = datetime.datetime.strptime(_date_s, '%Y%m%d%H%M%S')
            china_date = _date_obj + datetime.timedelta(hours=_h, minutes=_m) + datetime.timedelta(hours=8)
            res[k] = china_date.strftime('%Y%m%d%H%M%S')
        else:
            res[k] = v

    return res



def get_subject(cert):
    '''
    证书持有者
    '''
    sub = cert.get_subject()
    subject={'CN':sub.CN,'O':sub.O,'OU':sub.OU,'ST':sub.ST,'C':sub.C,'L':sub.L}
    return subject

def get_issuer(cert):
    '''
    签发机构
    '''
    iss = cert.get_issuer()
    issuer={'C':iss.C,'O':iss.O,'OU':iss.OU,'CN':iss.CN,'ST':iss.ST,'L':iss.L}
    return issuer

def is_expire(cert):
    '''
    证书是否过期
    '''
    return cert.has_expired()


def extension_analysis(cert):
    '''
    拓展解析
    '''
    s={}
    extension_len=cert.get_extension_count()
    for j in range(extension_len):
        shrot_name=cert.get_extension(j).get_short_name()
        try:
            extension_text=cert.get_extension(j).__str__()
        except Exception:
            continue
        s[shrot_name]=extension_text
    return s


def get_crl(cert):
    '''
    crl 吊销列表地址
    '''
    d=extension_analysis(cert)
    if ('crlDistributionPoints' in d)==True:
        return d['crlDistributionPoints']
    else:
        return None

def get_DNS(cert):
    '''
    多dns
    '''
    d=extension_analysis(cert)
    if ('subjectAltName' in d)==True:
        strs = d['subjectAltName'].replace('DNS:', '')
        dns_list = strs.split(',')
        return [i.strip() for i in dns_list]
    else:
        return []


def crt_number(crt):
    '''
    判断传进的证书内容有几段
    '''
    s=re.findall("\-\-\-\-\-BEGIN CERTIFICATE\-\-\-\-\-[\w|\W]+?(?:\-\-\-\-\-END CERTIFICATE\-\-\-\-\-)",crt)
    crt_len=len(s)
    return crt_len


def get_cert(crt):
    '''
    由顶层逐个解析返回　证书对象
    [3级,中级,根]
    '''

    res = []
    detail = re.findall("\-\-\-\-\-BEGIN CERTIFICATE\-\-\-\-\-[\w|\W]+?(?:\-\-\-\-\-END CERTIFICATE\-\-\-\-\-)",crt)
    for x in range(len(detail)):
        crt_obj = crypto.load_certificate(crypto.FILETYPE_PEM, detail[x])
        res.append(crt_obj)
    return res


def check_consistency(cert,key_str):
    '''
    证书和私钥的一致性
    '''
    data='chinacache'
    try:
        key_obj=crypto.load_privatekey(crypto.FILETYPE_PEM, key_str)
        sign=crypto.sign(key_obj,data,'sha256')
        b=crypto.verify(cert,sign,data,'sha256')
        return True
    except Exception:
        return False


def get_public_key(cert):

    from cryptography.hazmat.primitives import serialization
    pk_obj = cert.get_pubkey()
    cry_obj = pk_obj.to_cryptography_key()
    res = cry_obj.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    logger.debug('-----public key is %s'%(res))
    return res



def get_middle_cert_url(cert):
    '''
    获取中间证书下载地址
    '''
    cert_url = ''
    try:
        cert_extension=extension_analysis(cert)
        s= cert_extension['authorityInfoAccess']
        cert_re =re.findall("(?<=CA Issuers \- URI\:).*",s)
        if cert_re:
            cert_url = cert_re[0]
    except Exception:
        logger.debug('-----get_middle_cert_url error is %s'%(e))

    return cert_url


def dump_all_chain(chain):
    '''
    根据证书链对象　生成完整证书字符串
    '''

    s = ''
    for n, i in enumerate(chain):
        crt_str = crypto.dump_certificate(crypto.FILETYPE_PEM, i)
        crt_str = crt_str.strip('\n')
        if n == 0:
            s += crt_str
        else:
            s += '\n' + crt_str

    return s



def get_upper_cert(url):
    '''
    通过url获取中间证书
    '''
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent','Mozilla/5.0')
        response = urllib.request.urlopen(req, timeout=3)
        fp = response.read()
        try:
            crl_object = crypto.load_certificate(crypto.FILETYPE_PEM, fp)
        except Exception:
            crl_object = crypto.load_certificate(crypto.FILETYPE_ASN1, fp)

        return crl_object

    except Exception:
        logger.debug('-----get_upper_cert error is %s'%(traceback.format_exc()))
        return None


def get_all_chain(crt_strs):
    '''
    获取完整证书链内容
    return 1(无根证书) 2(获取中间证书异常) 3(获取中间证书异常500)
    '''
    is_valid_chain, chain = chain_adjustment(crt_strs)

    if is_valid_chain == True:
       #_all_chain = all_chain(chain)
       _all_chain = chain
       if _all_chain == 1:
           return 1
       elif _all_chain == 2:
           return 2
       elif _all_chain == 3:
           return 3
       else:
           s=dump_all_chain(_all_chain)
           return s
    else:
       return None


def all_chain(chain):
    '''
    补齐证书链的证书
    return 1(无根证书) 2(获取中间证书异常) 3(获取中间证书异常500)
    '''
    _all_chain = [c for c in chain]
    while True:
        try:
            last_chain = _all_chain[-1]
            last_chain_sub = get_subject(last_chain)
            last_chain_iss = get_issuer(last_chain)
            if last_chain_sub == last_chain_iss:
                break
            cert_url = get_middle_cert_url(last_chain)
            if not cert_url:
                #add root
                _issuer=get_issuer(last_chain)
                root_cert = s1_db.cert_root.find_one({"subject" :_issuer})
                if not root_cert:
                    #无根证书
                    return 1
                _all_chain.append(crypto.load_certificate(crypto.FILETYPE_PEM, root_cert['cert']))
            else:
                last_chain = get_upper_cert(cert_url)
                if not last_chain:
                    #未获取到中间证书
                    return 2
                _all_chain.append(last_chain)
        except Exception:
            logger.debug('-----all_chain error is %s'%(traceback.format_exc()))
            return 3

    return _all_chain


def chain_adjustment(crt_strs):
    '''
    检查证书链
    '''
    is_valid_chain = False
    chain = []
    try:
        cert_list = get_cert(crt_strs)
        chain = [[] for x in cert_list]
        for n, i in enumerate(cert_list):
            issuer = get_issuer(i)
            chain[n].append(i)
            check_list = [i]
            check_count = 0
            while True:
                for _n, _i in enumerate(cert_list):
                    if _i in check_list:
                        continue
                    _sub = get_subject(_i)
                    if issuer == _sub:
                        chain[n].append(_i)
                        issuer = get_issuer(_i)
                        check_list.append(_i)
                check_count += 1

                if check_count == len(cert_list):
                    break

        for c in chain:
            if len(c) == len(cert_list):
                is_valid_chain = True
                chain=c

    except Exception:
        logger.debug('-----chain_adjustment error is %s'%(traceback.format_exc()))

    return is_valid_chain, chain


if __name__ == '__main__':
    key=crypto.load_privatekey(crypto.FILETYPE_PEM, open('/home/lee/Documents/server.key').read())
    with open('/home/lee/Documents/root.crt', 'r') as crt:
        crt1 = crt.read()
    with open('/home/lee/Documents/server.crt', 'r') as _crt:
        crt2 = _crt.read()
    root_cert=get_cert(crt1,1)
    temp=get_cert(crt2,2)
    intermediate_cert=temp[0]
    three_cert=temp[1]
    pubkey=three_cert.get_pubkey()
    print(get_pubkey_len(three_cert))
    print(get_subject(three_cert))
    print(get_issuer(three_cert))
    print(get_DNS(three_cert))
    print(get_Validity(three_cert))
    print(get_revoke(three_cert))
    print(bool(three_cert.has_expired()))
    print(check_consistency(three_cert,key))
    print(check_cert_chain(root_cert,intermediate_cert,three_cert)) 
