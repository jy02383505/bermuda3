#-*-coding:utf-8-*-
from Crypto import Random
from OpenSSL import crypto
from Crypto.Hash import SHA256
from Crypto.Cipher import PKCS1_v1_5 as Cipher_pkcs1_v1_5
from Crypto.Signature import PKCS1_v1_5 as Signature_pkcs1_v1_5
from Crypto.PublicKey import RSA
import base64

bermuda_pub_key = None
with open('/Application/bermuda3/conf/rsa/bermuda_pub.pem', 'r') as bermuda_pub:
    bermuda_pub_key = bermuda_pub.read()
if bermuda_pub_key is None:
    raise

bermuda_pri_key = None
with open('/Application/bermuda3/conf/rsa/bermuda_pri.pem', 'r') as bermuda_pri:
    bermuda_pri_key = bermuda_pri.read()
if bermuda_pri_key is None:
    raise

cache_pub_key = None
with open('/Application/bermuda3/conf/rsa/cache_pub.pem', 'r') as cache_pub:
    cache_pub_key = cache_pub.read()
if cache_pub_key is None:
    raise

portal_pub_key = None
with open('/Application/bermuda3/conf/rsa/portal_pub.pem', 'r') as portal_pub:
    portal_pub_key = portal_pub.read()
if portal_pub_key is None:
    raise


def fun(fp,pub_key,pri_key,seed=None):
    '''
    最终加密消息
    fp:明文
    seed:种子
    pub_key: 接收端公钥
    pri_key: 发送端私钥
    '''
    if seed:
        _cipher_wen= encrypt_trunk(fp,pub_key)
        _or=deal(_cipher_wen, seed)
        _result=base64.b64encode(_or)
        _signature_fp=sign(fp,pri_key)
        rest = _result+_signature_fp
    else:
        _cipher_wen= encrypt_trunk(fp,pub_key)
        _signature_fp=sign(fp,pri_key)
        rest = _cipher_wen + _signature_fp

    return rest


def deal(sign, key):     
    '''
    异或
    '''
    ltips = len(sign)
    lkey = len(key)
    secret = []
    num = 0
    for each in sign:
        if num >= lkey:
            num = num % lkey
        secret.append(ord(each) ^ ord(key[num]))
        num += 1

    res_s = ''
    for i in secret:
        res_s += chr(i)
    return res_s


def encrypt_trunk(cert,pub_key):
    '''
    加密 245字节一组
    '''
    lst=[]
    cert_len = len(cert)
    if cert_len%245==0:
        a=cert_len/245
    else:
        a=cert_len/245+1
    for i in range(0,a):
        if 245*(i+1)<cert_len:
            lst.append(cert[245*i:245*(i+1)])
        else:
            lst.append(cert[245*i:cert_len])
            #print len(lst[1])
    cipher_text=[]
    for j in range(0,a):
        rsakey = RSA.importKey(pub_key)
        cipher = Cipher_pkcs1_v1_5.new(rsakey)
        cipher_text.append(cipher.encrypt(lst[j]))
        cipher_w = ''
    for z in range(0,a):
        cipher_w += cipher_text[z]
    cipher_wen=base64.b64encode(cipher_w)
    return cipher_wen


def decrypt_trunk(cipher_wen,pri_key):
    '''
    解密 密文256字节一组
    '''
    random_generator = Random.new().read
    cip=base64.b64decode(cipher_wen)
    lst1=[]
    cip_len= len(cip)
    if cip_len%256==0:
         b=cip_len/256
    else:
        b=cip_len/256+1
    for k in range(0,b):
        if 256*(k+1)<cip_len:
            lst1.append(cip[256*k:256*(k+1)])
        else:
            lst1.append(cip[256*k:cip_len])
    m_text=[]
    #print len(lst1[1])
    for m in range(0,b):
        rsakey = RSA.importKey(pri_key)
        cipher = Cipher_pkcs1_v1_5.new(rsakey)
        m_text.append(cipher.decrypt(lst1[m],random_generator))
    m_wen= ''
    for n in range(0,b):
        m_wen += m_text[n]
    return m_wen


def sign(fp,pri_key):
    '''
    签名
    fp: 明文
    pri_key: 私钥
    '''
    rsakey = RSA.importKey(pri_key)
    signer = Signature_pkcs1_v1_5.new(rsakey)
    digest = SHA256.new()
    digest.update(fp)
    sign = signer.sign(digest)
    signature = base64.b64encode(sign)
    return signature


def verify_sign(_signature_fp,pub_key,fp):
    '''
    验签
    _signature_fp: 签名
    pub_key: 公钥
    fp: 明文
    '''
    rsakey = RSA.importKey(pub_key)
    verifier = Signature_pkcs1_v1_5.new(rsakey)
    digest = SHA256.new()
    digest.update(fp)
    is_verify = verifier.verify(digest,base64.b64decode(_signature_fp))
    return is_verify


def split_ciphertext_and_sign(_str):
    '''
    分离密文和签名
    '''
    return _str[:-344], _str[-344:]

