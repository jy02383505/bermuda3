

class Counter(dict):

    def __init__(self, kw):
        super(Counter, self).__init__()
        self.update(kw)


    def __add__(self, other):
        '''Add counts from two counters.

        >>> Counter('abbb') + Counter('bcc')
        Counter({'b': 4, 'c': 2, 'a': 1})

        '''
        if not isinstance(other, Counter):
            return NotImplemented
        result = Counter({})
        for elem, count in list(self.items()):
            newcount = int(count) + int(other[elem])
            if newcount > 0:
                result[elem] = newcount
        for elem, count in list(other.items()):
            if elem not in self and int(count) > 0:
                result[elem] = int(count)
        return result


    def __missing__(self, key):
        'The count of elements not in the Counter is zero.'
        # Needed so that self[missing_item] does not raise KeyError
        return 0

if __name__ == '__main__':

    a = {'a':1}
    b = {'b':1,'a':2, 'c':3}
    c = {'a':1 } 
    d = Counter(a) + Counter(b) + Counter(c)
    print(dict(d))
