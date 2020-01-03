#!/usr/bin/env python
# coding=utf-8
# Created by vance on 2016-07-05.

__author__ = 'vance'


import os
from bson.objectid import ObjectId as BObjectId
import binascii

def ObjectId(oid=None):
    if oid:
        return BObjectId(oid)
    else:
        try:
            vv = os.urandom(5)
            uid = binascii.hexlify(vv).decode()
            id = BObjectId()
            new_id = str(id)[:14]+uid
            nid = BObjectId(new_id)
            return nid
        except:
            return BObjectId()


if __name__ == '__main__':
    value = BObjectId()
    print(value)
    print(ObjectId(value))
    print(ObjectId())