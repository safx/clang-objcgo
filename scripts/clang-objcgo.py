#!/usr/bin/env python

"""
objcgo: Cgo (Go lang) wrapper interfaces generattor for Objective-C 
"""

import re
from clang.cindex import CursorKind, TypeKind


def get_node_by_kind(kind, node):
    cs = filter_kind(kind, node)
    assert(len(cs) < 2)
    return cs[0] if len(cs) > 0 else None

def filter_kind(kind, node):
    return filter_node(lambda c:c.kind == kind, node)

def filter_node(fn, node):
    return filter(fn, node.get_children())


def get_info(node, depth=0):
    children = [get_info(c, depth+1) for c in node.get_children()]
    return { #'id' : get_cursor_id(node),
             'enc': node.objc_type_encoding,
             'type' : node.type.is_pod(),
             'kind' : node.kind,
             'usr' : node.get_usr(),
             'spelling' : node.spelling,
             'disp' : node.displayname,
             'is_definition' : node.is_definition(),
             'children' : children }


class Typename:
    cgo_unacceptable = None

    def __init__(self, raw):
        self._raw = str(raw)

    def __repr__(self):
        return self._raw

    @staticmethod
    def new(node):
        cref = get_node_by_kind(CursorKind.OBJC_CLASS_REF, node)
        tref = get_node_by_kind(CursorKind.TYPE_REF, node)

        if cref: return ObjcClassType(cref.displayname)
        if tref: return CType(tref.displayname, False) # FIXME: check const

        # Some PARM_DECLs and OBJC_INSTANCE_METHOD_DECLs have no children to detect typename.
        # In this case we get a typename information from Objective-C's type encoding.
        # see more details in https://developer.apple.com/library/ios/documentation/Cocoa/Conceptual/ObjCRuntimeGuide/Articles/ocrtTypeEncodings.html
        enc = node.objc_type_encoding

        # Strip all except characters of information of a return type when the kind of the node is OBJC_INSTANCE_METHOD_DECL.
        if node.kind == CursorKind.OBJC_INSTANCE_METHOD_DECL:
            # We assume that this encode contains '@0:8' for instance methods and does not bit field.
            m = re.match('^([^0-9]+)\d+@0:8', enc)
            assert(m)
            enc = m.group(1)

        # strip all additional Objective-C method encodings like `r` or 'n'.
        is_const = False
        m = re.match('^([rnNoORV]+)(.+)', enc)
        if m:
            enc = m.group(2)
            is_const = 'r' in m.group(1)

        encode_map = {
            'c': 'char',
            'i': 'int',
            's': 'short',
            'l': 'long',
            'q': 'long long',

            'C': 'unsigned char',
            'I': 'unsigned int',
            'S': 'unsigned short',
            'L': 'unsigned long',
            'Q': 'unsigned long long',

            'f': 'float',
            'd': 'double',
            'B': 'bool',
            '*': 'char*',
           #'#': 'Class',
           #':': 'SEL',
            '^v': 'void*' # FIXME
        }

        if enc == 'v':
            return VoidType()
        elif enc in encode_map:
            return CType(encode_map[enc], is_const)
        elif enc == '@':
            return ObjcClassType('NSObject')

        #print enc, node.displayname
        return InvalidType()

    @property
    def is_cgo_acceptable(self):
        return not Typename.is_reject(self._raw)

    @staticmethod
    def is_reject(raw):
        if not Typename.cgo_unacceptable:
            Typename.cgo_unacceptable = set([
                'va_list',
                'unichar',
                'SEL',
                'IMP', 
                'Class',
                'CGFloat',
                'AEDesc',
                'AppleEvent',
                'AEEventID',
                'AEEventClass',
                'NSAppleEventManagerSuspensionID',
                'NSMethodSignature', 
                'NSInvocation',
                'NSRange',
                'NSInteger',
                #'NSUInteger',
                #'BOOL',
                'NSComparisonResult',
                'NSLocale',
                'NSZone',
                'NSStringEncoding',
                'NSURLBookmarkCreationOptions',
                'NSStringCompareOptions',
                'NSTimeInterval',
                'NSDecimal',

                # NSProxy
                'NSProxy',
                'NSProtocolChecker',
                'NSDistantObject',

                # deprecated classes
                'NSURLHandle',
                'NSURLHandleStatus'
            ])

        return raw in Typename.cgo_unacceptable

    @property
    def raw(self):
        return self._raw

    @property
    def is_void(self):
        return False

    @property
    def objc_class(self):
        return False

    def box_value_go(self, value):
        #return ret_type + '_' + '(Id(C.' + clazz.raw + '_' + self.name.to_c() + '(' +  args_str + ')))'
        pass

    def to_return_c(self): #FIXME
        return self.to_param_c()

    def to_param_c(self):  #FIXME
        return self._raw

    def to_go(self, with_package=False):
        r = self._raw

        #if r == 'id': r = 'NSObject'
        if not with_package: return r
        return r # FIXME

class InvalidType(Typename):
    def __init__(self):
        Typename.__init__(self, '*INVALID TYPE*')

    @property
    def is_cgo_acceptable(self):
        return False

class VoidType(Typename):
    def __init__(self):
        Typename.__init__(self, '*VOID*')

    @property
    def raw(self): # FIXME
        raise AssertionError('Should not be called.')

    @property
    def is_void(self):
        return True

    @property
    def is_cgo_acceptable(self):
        return True

    def to_param_c(self):
        return 'void'

    def to_go(self):
        return ''


class CType(Typename):
    go_type_map = {
        'id': 'Id',

        'void*': 'unsafe.Pointer',
        'bool': 'C.bool',
        'BOOL': 'C.bool',

        'float': 'C.float',
        'double': 'C.double',

        'char': 'C.char',
        'short': 'C.short',
        'int': 'C.int',
        'long': 'C.long',
        'long long': 'C.longlong',

        'unsigned char': 'C.uchar',
        'unsigned short': 'C.ushort',
        'unsigned int': 'C.uint',
        'unsigned long': 'C.ulong',
        'unsigned long long': 'C.ulonglong',

        'char*': 'string',
        'NSRect': 'NSRect',
        'NSPoint': 'NSPoint',
        'NSUInteger': 'C.uint',

        'NSBackingStoreType': 'C.NSBackingStoreType'
    }

    def __init__(self, raw, is_const):
        Typename.__init__(self, raw)
        self.is_const = is_const

    @property
    def is_cgo_acceptable(self):
        return (not Typename.is_reject(self.raw)) and (self.raw in set(CType.go_type_map.keys()) or self.raw in Enum.declared_enumtypes or Typedef.get(self.raw))

    def box_value_go(self, value):
        #return ret_type + '_' + '(Id(C.' + clazz.raw + '_' + self.name.to_c() + '(' +  args_str + ')))'
        pass

    def to_param_c(self):
        type_map = {
            'id': 'void*',
            'BOOL': 'bool',
            'NSUInteger': 'uint',
        }

        r = self._raw
        if r in type_map:
            r = type_map[r]
        return ('const ' if self.is_const else '') + r

    def to_go(self):
        r = self._raw
        if r in CType.go_type_map:
            return CType.go_type_map[r]

        return 'C.' + r

class ObjcClassType(Typename):
    used_classes = set()

    def __init__(self, raw):
        if len(raw) == 0:
            raise AssertionError('empty string')

        Typename.__init__(self, raw)
        ObjcClassType.used_classes.add(self.raw)

    @property
    def objc_class(self):
        return True

    def to_return_c(self):
        return 'void*'

    def to_param_c(self):
        return 'void*' 


class Identifier:
    def __init__(self, raw):
        self._raw = str(raw)

    def __repr__(self):
        return self._raw

    @property
    def raw(self):
        return self._raw

class MethodName(Identifier):
    def __init__(self, raw):
        Identifier.__init__(self, raw)

    # getRed:green:blue:alpha: -> getRedGreenBlueAlpha
    @property
    def _to_camel(self):
        return reduce(lambda a,x:a + x[0].upper() + x[1:], filter(lambda x:x!="", self._raw.split(":")))

    def to_c(self):
        return self._to_camel

    def to_go(self):
        r = self._to_camel
        return r[0].upper() + r[1:]

class ParamName(Identifier):
    def __init__(self, raw):
        assert(not ':' in raw)
        Identifier.__init__(self, raw)

    def to_c(self):
        return self._raw

    def to_go(self):
        r = self._raw
        if r in set(['type', 'range', 'map', 'make']): return r + '_' # convert to un-reserved word for Go
        return r

class PropName(Identifier):
    def __init__(self, raw):
        assert(not ':' in raw)
        Identifier.__init__(self, raw)

    # value -> setValue:
    def to_setter_selector(self):
        return 'set' + self._raw[0].upper() + self._raw[1:] + ':'


class Base:
    def __init__(self, node):
        self.node = node

class Interface(Base):
    declared_classes = set()

    def __init__(self, node):
        def self_typename(self):
            # If current node is a OBJC_CATEGORY_DECL, the displayname of the node is a category name.
            # So we fix the interface name by using 'get_usr()' which returns a string containg an interface name.
            if node.kind == CursorKind.OBJC_CATEGORY_DECL:
                # ignore deprecated categories
                if 'Deprecated' in node.displayname: return None

                m = re.match("c:objc\((cy|ext)\)([^@]+).+", node.get_usr())
                assert(m)
                return ObjcClassType(m.group(2))

            return ObjcClassType(node.displayname)


        def super_typename(self):
            c = get_node_by_kind(CursorKind.OBJC_SUPER_CLASS_REF, self.node)
            return ObjcClassType(c.displayname) if c else None

        def bind(func, val):
            return lambda a: func(a, val)

        Base.__init__(self, node)
        self.typename       = self_typename(self)
        self.super_typename = super_typename(self)

        # return if deprecated class
        if not self.typename: return

        self.props         = map(Property                           , filter_kind(CursorKind.OBJC_PROPERTY_DECL, node))
        self.methods       = map(bind(InstanceMethod, self.typename), filter_kind(CursorKind.OBJC_INSTANCE_METHOD_DECL, node))
        self.class_methods = map(bind(ClassMethod   , self.typename), filter_kind(CursorKind.OBJC_CLASS_METHOD_DECL, node))

        map(lambda x:self.link_accessors(x), self.props)

        Interface.declared_classes.add(self.typename.raw)

    #def __repr__(self):
    #    return self.name + (' ' + self.super_typename if self.super_typename else '')

    def link_accessors(self, prop):
        def get_setter_selector(name):
            return 'set' + name[0].upper() + name[1:] + ':'

        getters = filter(lambda x: prop.name.raw == x.name.raw, self.methods)
        setters = filter(lambda x: prop.name.to_setter_selector() == x.name.raw, self.methods)

        assert(len(getters) <= 1)
        assert(len(setters) <= 1)

        if getters: getters[0].set_as_getter(prop)
        if setters: setters[0].set_as_setter(prop)

    def compile_c(self):
        if not self.typename.is_cgo_acceptable: return '\n// ' + self.typename.raw + '\n'

        s = ['', '////' + self.typename.raw]

        # force remove 'init' from NSObject
        if self.typename.raw == 'NSObject':
            self.methods = filter(lambda x: x.name.raw != 'init', self.methods)

        # output init (default ctor)
        init = filter(lambda x: x.name.raw == 'init', self.methods)
        assert(len(init) <= 1)
        if len(init) == 0:
            s.append('void* ' + self.typename.raw + '_init() {')
            s.append('  return [[' + self.typename.raw + ' alloc] init];')
            s.append('}')

        # output other methods
        s.append('\n'.join(map(lambda x:x.compile_c(), self.methods)))
        s.append('\n'.join(map(lambda x:x.compile_c(), self.class_methods)))
        return '\n'.join(s)

    def compile_go(self):
        if not self.typename.is_cgo_acceptable: return '\n'

        s = []

        # output struct
        s.append('type ' + self.typename.raw + ' struct {')
        if self.super_typename:
            s.append('  ' + self.super_typename.raw)
        else:
            s.append('  self Id')
        s.append('}')

        # output boxing method
        s.append('func ' + self.typename.raw + '_(i Id) ' + self.typename.raw + ' {')
        if self.super_typename:
            s.append('  return ' + self.typename.raw + '{ ' + self.super_typename.to_go() + '_(i) }')
        elif self.typename.raw == 'NSObject':
            s.append('  return NSObject{ i }')
        else:
            s.append('  return null') # FIXME
        s.append('}')

        # output init (default ctor)
        init = filter(lambda x: x.name.raw == 'init', self.methods)
        assert(len(init) <= 1)
        if len(init) == 0:
            s.append('func ' + self.typename.raw + '_init() ' + self.typename.raw + ' {')
            s.append('  p := ' + 'Id(C.' + self.typename.raw + '_init())')
            s.append('  return ' + self.typename.raw + '_(p)')
            s.append('}')

        # output other methods
        s.append('\n'.join(map(lambda x:x.compile_go(), self.methods)))
        s.append('\n'.join(map(lambda x:x.compile_go(), self.class_methods)))

        return '\n'.join(s)


class Property(Base): # FIXME
    def __init__(self, node):
        Base.__init__(self, node)
        self.typename = Typename.new(self.node)
        self.name = PropName(self.node.displayname)
        assert(self.typename)

    def __repr__(self):
        p = '*' if self.node.type.kind == TypeKind.OBJCOBJECTPOINTER else ''
        return self.typename + p + ' ' + self.name



class Method(Base):
    unacceptalble_methods = set([
        # unavaliable
        'NSNetService_setIncludesPeerToPeer',
        'NSNetServiceBrowser_includesPeerToPeer',
        'NSNetServiceBrowser_setIncludesPeerToPeer',
        'NSURLSessionConfiguration_setDiscretionary',
        'NSNetService_includesPeerToPeer',
        'NSURLSessionConfiguration_sessionSendsLaunchEvents',
        'NSURLSessionConfiguration_setSessionSendsLaunchEvents',
        # deprecated
        'NSObject_allowsWeakReference',
        'NSObject_retainWeakReference',
        'NSObject_URLResourceDataDidBecomeAvailable',
        'NSObject_URLResourceDidFinishLoading',
        'NSObject_URLResourceDidCancelLoading',
        'NSObject_URLResourceDidFailLoadingWithReason',
        # un-compilable
        'NSURLSessionConfiguration_isDiscretionary',
        # black
        'NSEvent__addLocalMonitorForEventsMatchingMaskHandler',
        'NSExpression_expressionBlock',
        'NSArray_indexOfObjectPassingTest',
        'NSArray_indexesOfObjectsPassingTest',
        'NSDictionary_keysOfEntriesPassingTest',
        'NSFileManager_enumeratorAtURLIncludingPropertiesForKeysOptionsErrorHandler',
        'NSIndexSet_indexPassingTest',
        'NSIndexSet_indexesPassingTest',
        'NSOrderedSet_indexOfObjectPassingTest',
        'NSOrderedSet_indexesOfObjectsPassingTest',
        'NSSet_objectsPassingTest',
        'NSPredicate__predicateWithBlock',
    ])

    def __init__(self, node, class_typename, is_static):
        Base.__init__(self, node)
        self.name = MethodName(self.node.displayname)
        self.return_typename = Typename.new(self.node)
        self.class_typename = class_typename
        self.is_static = is_static

        # if return_typename is InvalidType, we change it to VoidType
        if isinstance(self.return_typename, InvalidType):
            #print 'W:', '+' if is_static else '-',  class_typename, self.name
            self.return_typename = VoidType()

        m = self.name.raw
        self.is_ctor   = m == 'init' or len(m) > 8 and m[:8] == 'initWith'
        self.is_getter = False
        self.is_setter = False

        self.params = map(Parametor, filter_kind(CursorKind.PARM_DECL, node))

        # overwrite return_typename if ctor, because the one is id or instancetype.
        if self.is_ctor: self.return_typename = self.class_typename

    def __repr__(self):
        return str(self.return_typename) + ' ' + str(self.name)

    @property        
    def is_cgo_acceptable(self):
        #if self.class_typename.raw + '/' + self.name.raw in Method.unacceptalble_methods: return False
        if self._funcname_c() in Method.unacceptalble_methods: return False

        if any(map(lambda x:not x.typename.is_cgo_acceptable, self.params)): return False
        if self.is_ctor: return True # FIXME: force True
            
        return self.return_typename.is_cgo_acceptable

    def get_cgo_rejected_reason(self):
        if self._funcname_c() in Method.unacceptalble_methods: return 'unacceptalble-method'

        rejected = [] if self.return_typename.is_cgo_acceptable else [self.return_typename]
        rejected.extend(map(lambda x:x.name, filter(lambda x:not x.typename.is_cgo_acceptable, self.params)))

        return 'REJECT: ' + ' '.join(map(lambda x:str(x), rejected))

    def set_as_getter(self, prop):
        assert(len(self.params) == 0)
        self.is_getter = True
        self.prop = prop
        self.return_typename = prop.typename
        if not self.return_typename:
            self.return_typename = self.prop.typename

    def set_as_setter(self, prop):
        assert(len(self.params) == 1)
        self.is_setter = True
        self.prop = prop
        self.params[0].typename = prop.typename

    def _funcname_c(self):
        return self.class_typename.raw + ('__' if self.is_static else '_') + self.name.to_c()

    def compile_c(self):
        is_static = self.is_ctor or self.is_static

        s = []

        params = map(lambda x:x.to_param_c(), self.params)
        if not is_static: params.insert(0, 'void* goobj')
        params_str = ', '.join(params)

        # This program currently can not handle methods return block object.
        # So replaces are skipped in these cases.
        if self.name.raw.count(':') == len(self.params):
            args_str = (self.name.raw.replace(':', ':%s ') % tuple(map(lambda x:x.to_arg_c(), self.params))).strip()
        else:
            args_str = self.name.raw

        s.append(self.return_typename.to_return_c() + ' ' + self._funcname_c() + '(' + params_str + ') {')
        if self.is_static:
            if self.is_ctor:
                s.append('  return [' + self.class_typename.raw + ' ' + args_str + '];')
                raise 'foobar'
            elif not self.return_typename.is_void:
                s.append('  return [' + self.class_typename.raw + ' ' + args_str + '];')
            else:
                s.append('  [' + self.class_typename.raw + ' ' + args_str + '];')
        else:
            if self.is_ctor:
                s.append('  return [[' + self.class_typename.raw + ' alloc] ' + args_str + '];')
            elif not self.return_typename.is_void:
                s.append('  return [(' + self.class_typename.raw + '*)goobj ' + args_str + '];')
            else:
                s.append('  [(' + self.class_typename.raw + '*)goobj ' + args_str + '];')

        s.append('}')

        if self.is_cgo_acceptable:
            return '\n'.join(s)
        else:
            return ('//' + self.get_cgo_rejected_reason() + '\n') + '//' + '\n//'.join(s)

    def compile_go(self):
        is_static = self.is_ctor or self.is_static
        ret_type = self.return_typename.to_go()

        params_str = ', '.join(map(lambda x:x.to_param_go(), self.params))

        args = map(lambda x:x.to_arg_go(), self.params)
        if not is_static: args.insert(0, 'goobj.Self()')
        args_str = ', '.join(args)

        instance = '' if is_static else '(goobj ' + self.class_typename.to_go() + ') '
        funcname = self.name.to_go()
        if is_static:
            funcname = self.class_typename.raw + '_' + funcname[0].lower() + funcname[1:]
        s = ['func ' + instance + funcname + '(' + params_str + ') ' + ret_type + ' {']

        if self.is_static:
            if self.return_typename.is_void:
                s.append('  C.' + self._funcname_c() + '(' +  args_str + ')')
            elif self.return_typename.objc_class:
                s.append('  return ' + ret_type + '_(Id(C.' + self._funcname_c() + '(' +  args_str + ')))')
            elif ret_type == 'NSRect' or ret_type == 'NSPoint' or ret_type == 'Id':
                s.append('  return ' + ret_type + '_(C.' + self._funcname_c() + '(' +  args_str + '))')
            else:
                s.append('  return ' + '(C.' + self._funcname_c() + '(' +  args_str + '))')
        else:
            if self.is_ctor or not self.return_typename.is_void or self.is_getter:
                if self.return_typename.objc_class:
                    s.append('  return ' + ret_type + '_' + '(Id(C.' + self._funcname_c() + '(' +  args_str + ')))')
                elif self.return_typename.raw == 'char*':
                    s.append('  return C.GoString(C.' + self._funcname_c() + '(' +  args_str + '))')
                elif ret_type == 'NSRect' or ret_type == 'NSPoint' or ret_type == 'Id':
                    s.append('  return ' + ret_type + '_(C.' + self._funcname_c() + '(' +  args_str + '))')
                else:
                    s.append('  return ' + '(C.' + self._funcname_c() + '(' +  args_str + '))')
            else:
                s.append('  C.' + self._funcname_c() + '(' +  args_str + ')')

        s.append('}')

        if self.is_cgo_acceptable:
            return '\n'.join(s)
        else:
            return ('//' + self.get_cgo_rejected_reason() + '\n') + '//' + '\n//'.join(s)


class InstanceMethod(Method):
    def __init__(self, node, class_typename = None):
        Method.__init__(self, node, class_typename, False)

class ClassMethod(Method):
    def __init__(self, node, class_typename = None):
        Method.__init__(self, node, class_typename, True)


class Parametor(Base):
    def __init__(self, node):
        Base.__init__(self, node)

        self.typename = Typename.new(self.node)
        self.name = ParamName(self.node.displayname)

    def __repr__(self):
        return str(self.typename) + '/' + str(self.name)

    def to_arg_c(self):
        name = self.typename.raw
        if not self.typename: return 'FIXME' # FIXME
        if self.typename and self.typename.objc_class:
            if self.typename.raw == 'NSError':
                return '(' + self.typename.raw + '**)&' + self.name.to_c()
            else:
                return '(' + self.typename.raw + '*)' + self.name.to_c()
        if self.typename: return self.name.to_c()
        return 'FIXME' # FIXME

    def to_param_c(self):
        if not self.typename: return 'FIXMEx' # FIXME
        return self.typename.to_param_c() + ' ' + self.name.to_c()

    def to_arg_go(self):
        name = self.name.to_go()
        if not self.typename: return 'FIXMEz' # FIXME
        if self.typename and self.typename.objc_class: return name + '.Self()' 
        if self.typename.raw == 'id': return 'unsafe.Pointer(' + name + ')'
        if self.typename.raw == 'char*': return 'C.CString(' + name + ')'
        if self.typename.raw == 'NSRect': return 'C.CGRectMake(C.CGFloat(%s.X), C.CGFloat(%s.Y), C.CGFloat(%s.Width), C.CGFloat(%s.Height))' % (name, name, name, name)
        if self.typename.raw == 'NSPoint': return 'C.CGPointMake(C.CGFloat(%s.X), C.CGFloat(%s.Y))' % (name, name)
        if self.typename: return name
        return 'FIXME' # FIXME

    def to_param_go(self):
        name = self.name.to_go()
        if not self.typename: return 'FIXMEy' # FIXME
        if self.typename.raw == 'id': return name + ' Id'
        if self.typename.raw == 'char*': return name + ' string'
        if self.typename.raw == 'void*': return name + ' unsafe.Pointer'
        return name + ' ' + self.typename.to_go()


class Enum(Base):
    declared_enumtypes = set()
    deprecated = set([
        'NSDataWritingFileProtectionNone',
        'NSDataWritingFileProtectionComplete',
        'NSDataWritingFileProtectionCompleteUnlessOpen',
        'NSDataWritingFileProtectionCompleteUntilFirstUserAuthentication',
        'NSDataWritingFileProtectionMask',
        'NSURLErrorCancelledReasonUserForceQuitApplication',
        'NSURLErrorCancelledReasonBackgroundUpdatesDisabled',
    ])

    def __init__(self, node):
        self.name = node.displayname # FIXME: Typename?
        self.constants = filter(lambda x:not x in Enum.deprecated, map(lambda x:x.displayname, filter_kind(CursorKind.ENUM_CONSTANT_DECL, node)))

        if len(self.name) > 0:
            Enum.declared_enumtypes.add(self.name)

class Typedef(Base):
    declared_typedefs = {}
    deprecated = set([
    ])

    def __init__(self, node):
        self.typename = node.displayname # FIXME: Typename?
        self.desttype = Typename.new(node)

    @staticmethod
    def add(node):
        td = Typedef(node)
        if isinstance(td.desttype, InvalidType):
            Typedef.declared_typedefs[td.typename] = td
        return td

    @staticmethod
    def get(ident):
        if not ident in Typedef.declared_typedefs: return None
        return Typedef.declared_typedefs[ident]


def parse_root(node):
    if node.kind == CursorKind.TRANSLATION_UNIT:
        (interfaces, enums) = parse_translation_unit(node)

        print '''package sample
/*
#cgo CFLAGS: -x objective-c -I../../objc -I../../out
#cgo LDFLAGS: -framework Foundation -framework AppKit
#import <Cocoa/Cocoa.h>
#import <objc/message.h>
#import <objc/runtime.h>
#import <MySample.h>

// runtime
const char* CCG_object_getClassName(void* px) {
    return object_getClassName(px);
}
// NSObject
const char* NSObject_descripton(void* p) {
    return [[(id)p description] UTF8String];
}
'''
        print ''.join(map(lambda x:x.compile_c()+'\n', interfaces))
        print '\n\n'

        print '''*/
import "C"
import "unsafe"
'''
        # output enum constants
        # print 'const ('
        # for e in enums:
        #     for i in e.constants:
        #         print '  ' +  i + ' = C.' + i
        # print ')'

        # 
        print ''' 
type Id unsafe.Pointer

func Id_(r unsafe.Pointer) Id {
    return Id(r)
}

///// struct for Go
type NSRect struct {
    X float64
    Y float64
    Width float64
    Height float64
}

func NSRect_(r C.NSRect) NSRect {
    return NSRect{float64(r.origin.x), float64(r.origin.y), float64(r.size.width), float64(r.size.height)}
}

type NSPoint struct {
    X float64
    Y float64
}

func NSPoint_(r C.NSPoint) NSPoint {
    return NSPoint{float64(r.x), float64(r.y)}
}


///// additional for Go
func (obj NSObject) Self() unsafe.Pointer {
    return unsafe.Pointer(obj.self)
}
func (obj NSObject) String() string {
    return C.GoString(C.NSObject_descripton(obj.Self()))
}
func (obj NSObject) GetClassName() string {
    p := C.CCG_object_getClassName(obj.Self())
    return C.GoString(p)
}
///// END
'''
        # 
        print ''.join(map(lambda x:x.compile_go()+'\n', interfaces))
        print '\n'
           
        # create skelton implementations of interfaces that have no interface declaration.
        for i in ObjcClassType.used_classes.difference(Interface.declared_classes):
            print '''type %s struct {
    NSObject
}
func %s_(i Id) %s {
    return %s{ NSObject_(i) }
}
''' % (i,i,i,i)


def parse_translation_unit(node):
    map(Typedef.add, filter_kind(CursorKind.TYPEDEF_DECL, node))

    enums = map(Enum, filter_kind(CursorKind.ENUM_DECL, node))

    interfaces = filter(lambda x:x.typename, map(Interface, filter_kind(CursorKind.OBJC_INTERFACE_DECL, node)))

    # merge category's methods into classes
    categories = filter(lambda x:x.typename, map(Interface, filter_kind(CursorKind.OBJC_CATEGORY_DECL, node)))
    for c in categories: # FIXME: create Category class?
        for i in interfaces:
            if i.typename.raw == c.typename.raw:
                i.methods.extend(c.methods)
                # FIXME: add class methods, props
    return (interfaces, enums)


def create_go_source(node):
    parse_root(node)


def main():
    from clang.cindex import Index
    from pprint import pprint

    from optparse import OptionParser, OptionGroup

    # TODO: global opts

    parser = OptionParser("usage: %prog [options] {filename} [clang-args*]")
    parser.disable_interspersed_args()
    (opts, args) = parser.parse_args()

    if len(args) > 0:
        args.append('-c')
        args.append('-ObjC')
        args.append('-m64')
        args.append('-fobjc-arc')

        tu = Index.create().parse(None, args)
        if tu:
            create_go_source(tu.cursor)
        else:
            parser.error("unable to load input")

    else:
        parser.error('invalid number arguments')

if __name__ == '__main__':
    main()

